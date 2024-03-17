from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, fields
from trytond.pyson import Eval, If
from decimal import Decimal
from trytond.transaction import Transaction
from trytond.model import Workflow
from trytond.modules.company.model import (
    set_employee)

from trytond.exceptions import UserError
from trytond.wizard import (
    Button, StateAction, StateView, Wizard)
from trytond.i18n import gettext
from trytond.modules.sale.exceptions import PartyLocationError


class Sale(metaclass=PoolMeta):
    'Sale'
    __name__ = 'sale.sale'

    quote_number = fields.Char("Quote Number", readonly=True)

    sale_type = fields.Selection([
            ('maintenance', 'Maintenance'),
            ('equipments', 'Equipments'),
            ('replaces', 'Replaces')],
        "Sale Type", required=True,
        states={
            'readonly': Eval('state') != 'draft'})

    maintenance_type = fields.Selection([
            ('', ""),
            ('preventive', 'Preventive'),
            ('corrective', 'Corrective')],
        "Maintenance Type",
        states={
            'invisible': Eval('sale_type') != "maintenance",
            'required': Eval('sale_type') == "maintenance",
            'readonly': Eval('state') != 'draft'},
        depends=['sale_type'])

    contract_ref = fields.Reference(
        "Contract Base", selection='get_origin_contract',
        domain={
            'optical_equipment.contract': [
                ('party', '=', Eval('party')),
                ('state', '=', 'closed'),
                ]},
        states={
            'invisible': (
                Eval('sale_type') != 'maintenance')},
        search_context={
            'related_party': Eval('party'), })

    agended = fields.Boolean("Scheduling", states={
        'invisible': (Eval('sale_type') != 'maintenance')})
    payment_term_description = fields.Char("Payment Term", states={
        'readonly': Eval('state') != 'draft',
    }, depends=['state'])

    @classmethod
    def __setup__(cls):
        super(Sale, cls).__setup__()
        cls.contact.states['required'] = True
        cls.description.states['required'] = True
        cls.sale_date.states['required'] = True
        cls._buttons.update({
            'draft': {
                'invisible': (Eval('state').in_(
                    ['cancelled', 'draft']))},
            'report': {}})

        cls._transitions |= set((
            ('draft', 'quotation'),
            ('quotation', 'confirmed'),
            ('confirmed', 'processing'),
            ('confirmed', 'draft'),
            ('processing', 'processing'),
            ('processing', 'done'),
            ('done', 'processing'),
            ('draft', 'cancelled'),
            ('quotation', 'cancelled'),
            ('quotation', 'draft'),
            ('cancelled', 'draft'),
            ('processing', 'draft')
        ))

    @fields.depends('lines', 'sale_type', 'agended')
    def on_chage_sale_type(self):
        self.lines = []
        if self.sale_type != "maintenance":
            self.agended = False
        elif self.sale_type == "maintenance":
            self.invoice_method = 'order'

    @classmethod
    def default_agended(self):
        return False

    @classmethod
    def _get_origin_contract(cls):
        'Return list of Model names for origin Reference'
        pool = Pool()
        Contract = pool.get('optical_equipment.contract')

        return [Contract.__name__]

    @classmethod
    def get_origin_contract(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin_contract()

        return [(None, '')] + [(m, get_name(m)) for m in models]

    def _get_shipment_sale(self, Shipment, key):
        Shipment = super(Sale, self)._get_shipment_sale(Shipment, key)
        Shipment.sale_type = self.sale_type
        Shipment.service_maintenance_initial = \
            True if self.sale_type != 'equipments' else False

        return Shipment

    @ classmethod
    def set_quote_number(cls, sales):
        '''
        Fill the number field with the sale sequence
        '''
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)
        for sale in sales:
            if config.equipment_sequence is not None:
                if not sale.quote_number:
                    try:
                        sale.quote_number = config.sale_quote_number.get()
                        cls.save(sales)
                    except UserError:
                        raise UserError(str('Validation Error'))
            else:
                raise UserError(
                    gettext('optical_equipment.msg_not_sequence_quote'))

    @ classmethod
    def copy(cls, sales, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('number', None)
        default.setdefault('invoice_state', 'none')
        default.setdefault('invoices_ignored', None)
        default.setdefault('moves', None)
        default.setdefault('shipment_state', 'none')
        default.setdefault('quoted_by')
        default.setdefault('confirmed_by')

        return super(Sale, cls).copy(sales, default=default)

    @ classmethod
    @ ModelView.button_action(
        'optical_equipment.wizard_print_balance_sale_party')
    def report(cls, sales):
        pass

    @ classmethod
    @ ModelView.button
    @ Workflow.transition('quotation')
    def quote(cls, sales):
        for sale in sales:
            sale.check_for_quotation()
        cls.set_quote_number(sales)

        for sale in sales:
            sale.set_advance_payment_term()
        cls.save(sales)

    @ classmethod
    @ ModelView.button_action(
        'optical_equipment.wizard_confirm_sale_date')
    @ Workflow.transition('confirmed')
    @ set_employee('confirmed_by')
    def confirm(cls, sales):
        pool = Pool()
        Configuration = pool.get('sale.configuration')
        transaction = Transaction()
        context = transaction.context
        cls.set_sale_date(sales)
        cls.store_cache(sales)
        config = Configuration(1)

        MaintenanceService = pool.get('optical_equipment_maintenance.service')
        for sale in sales:
            if sale.sale_type == 'maintenance' and not sale.agended:
                for line in sale.lines:
                    maintenanceService = MaintenanceService(
                        description=sale.description,
                        maintenance_type=sale.maintenance_type,
                        state_agended='no_agenda',
                        propietary=sale.party,
                        propietary_address=sale.shipment_address,
                        contract_origin=sale.contract_ref
                        if sale.contract_ref else None,
                        sale_origin=sale,
                        sale_date=sale.sale_date,
                        state="draft"
                    )
                    maintenanceService.save()
                sale.agended = True
                sale.state = "confirmed"
                sale.save()

        cls.set_number(sales)
        with transaction.set_context(
                queue_scheduled_at=config.sale_process_after,
                queue_batch=context.get('queue_batch', True)):
            cls.__queue__.process(sales)


class SaleLine(metaclass=PoolMeta):
    'SaleLine'
    __name__ = 'sale.line'

    product_equipment = fields.Boolean("Product Equipment")
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
                                  'on_change_with_unit_digits')

    @classmethod
    def __setup__(cls):
        super(SaleLine, cls).__setup__()
        cls.product.domain.append(
            If(Eval('_parent_sale.sale_type') == 'maintenance',
               [('type', '=', 'service'),
                ('maintenance_activity', '=', True)], []))
        cls.product.domain.append(
            If(Eval('_parent_sale.sale_type') == 'replaces',
                [('replacement', '=', True)], []))

    def on_change_with_unit_digits(self, name=None):
        if self.unit:
            return self.unit.digits
        return 2

    @fields.depends(
        'product', 'unit', 'quantity', 'sale',
        '_parent_sale.party', '_parent_sale.sale_type',
        methods=[
            '_get_tax_rule_pattern',
            '_get_context_sale_price',
            'on_change_with_amount'])
    def on_change_product(self):
        Product = Pool().get('product.product')
        if not self.product:
            self.product_equipment = False
            self.unit = None
            self.quantity = None
            return

        else:
            party = None

            if self.sale.sale_type == 'equipments':
                self.quantity = 1

            if self.sale and self.sale.party:
                self.product_equipment = False
                party = self.sale.party

            # Set taxes before unit_price
            # to have taxes in context of sale price
            taxes = []
            pattern = self._get_tax_rule_pattern()
            for tax in self.product.customer_taxes_used:
                if party and party.customer_tax_rule:
                    tax_ids = party.customer_tax_rule.apply(tax, pattern)
                    if tax_ids:
                        taxes.extend(tax_ids)
                    continue
                taxes.append(tax.id)

            if party and party.customer_tax_rule:
                tax_ids = party.customer_tax_rule.apply(None, pattern)
                if tax_ids:
                    taxes.extend(tax_ids)
            self.taxes = taxes

            category = self.product.sale_uom.category
            if not self.unit or self.unit.category != category:
                self.unit = self.product.sale_uom
                self.unit_digits = self.product.sale_uom.digits

            with Transaction().set_context(self._get_context_sale_price()):
                self.unit_price = Product.get_sale_price(
                    [self.product],
                    self.quantity or 0
                )[self.product.id]

                if self.unit_price:
                    self.unit_price = self.unit_price.quantize(
                        Decimal(1) / 10 ** self.__class__.unit_price.digits[1])

            self.type = 'line'
            self.amount = self.on_change_with_amount()

            if self.product.equipment:
                self.product_equipment = True

    def get_move(self, shipment_type):
        '''
        Return moves for the sale line according to shipment_type
        '''

        pool = Pool()
        Move = pool.get('stock.move')

        if self.type != 'line':
            return

        if not self.product:
            return

        if self.product.type not in Move.get_product_types():
            return

        if (shipment_type == 'out') != (self.quantity >= 0):
            return

        quantity = (self._get_move_quantity(shipment_type)
                    - self._get_shipped_quantity(shipment_type))

        quantity = self.unit.round(quantity)

        if quantity <= 0:
            return

        if not self.sale.party.customer_location:
            raise PartyLocationError(
                gettext('sale.msg_sale_customer_location_required',
                        sale=self.sale.rec_name,
                        party=self.sale.party.rec_name))

        move = Move()
        move.quantity = quantity
        move.uom = self.unit
        move.product = self.product
        move.from_location = self.from_location
        move.to_location = self.to_location
        move.state = 'draft'
        move.company = self.sale.company

        if move.on_change_with_unit_price_required():
            move.unit_price = self.unit_price
            move.currency = self.sale.currency

        move.planned_date = self.planned_shipping_date
        move.invoice_lines = self._get_move_invoice_lines(shipment_type)
        move.origin = self

        return move


class SaleDate(ModelView):
    'Confirmacíon Fecha de Venta'
    __name__ = 'optical_equipment.confirm_sale_date.form'

    sale_date = fields.Date("Fecha Venta", required=True)


class ConfirmSaleDate(Wizard):
    'Confirmacíon Fecha de Venta'
    __name__ = 'optical_equipment.confirm_sale_date'

    start = StateView('optical_equipment.confirm_sale_date.form',
                      'optical_equipment.confirm_sale_date_view_form', [
                          Button('Confirmar', 'confirm_date',
                                 'tryton-ok', default=True),
                      ])

    confirm_date = StateAction('sale.act_sale_form')

    def default_start(self, fields):
        if self.record:
            return {'sale_date': self.record.sale_date}

    def do_confirm_date(self, action):
        self.record.sale_date = self.start.sale_date
        self.record.state = 'processing'
        self.record.save()
