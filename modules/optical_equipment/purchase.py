#This file is part of Tryton.  The COPYRIGHT file at the top level of
#txhis repository contains the full copyright notices and license terms
from trytond.pool import Pool, PoolMeta
from trytond.model import (
    ModelView, ModelSQL, Workflow, fields)
from trytond.modules.product import price_digits, round_price
from trytond.pyson import Eval, If, Bool
from trytond.exceptions import UserError
from trytond.i18n import gettext
from trytond.transaction import Transaction


class Purchase(metaclass=PoolMeta):
    "Purchase Equipment" 
    __name__ = 'purchase.purchase'

    equipment_create = fields.Boolean("Equipments Creates", readonly=True)

    @classmethod
    def __setup__(cls):
        super(Purchase, cls).__setup__()
        cls._buttons.update({
            'create_equipments': {
                'invisible':  If(Eval('invoice_state') == 'none', True) |
                If(Bool(Eval('equipment_create')), True),
                'depends': ['invoice_state'],}})

    @classmethod
    def copy(cls, purchases, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('number', None)
        default.setdefault('invoice_state', 'none')
        default.setdefault('invoices_ignored', None)
        default.setdefault('moves', None)
        default.setdefault('shipment_state', 'none')
        default.setdefault('purchase_date', None)
        default.setdefault('quoted_by')
        default.setdefault('confirmed_by')
        default.setdefault('equipment_create', None)

        return super(Purchase, cls).copy(purchases, default=default)

    @classmethod
    @ModelView.button
    def create_equipments(cls, purchases):
        if len(purchases) == 1:
            pool = Pool()
            Equipment = pool.get('optical_equipment.equipment')
            Config = pool.get('optical_equipment.configuration')
            config = Config(1)
            
            purchase = purchases[0]
            
            for line in purchase.lines:
                if line.product.equipment:
                    for i in range(0,int(line.quantity)):
                        equipment = Equipment(
                            company=line.company,
                            location=line.to_location,
                            equipment_type=line.product.equipment_type,
                            propietary=line.company.party,
                            propietary_address=line.address_equipment,
                            product=line.product,
                            model_category=line.product.model_category, 
                            mark_category=line.product.mark_category,
                            reference_category=line.product.reference_category,
                            useful_life=line.product.useful_life if line.product.useful_life else 0,
                            calibration=True  if line.product.calibration else False,
                            warranty=line.product.warranty if line.product.warranty else 0,
                            risk=line.product.risk,
                            origin_country=line.product.origin_country,
                            use=line.product.use,
                            biomedical_class=line.product.biomedical_class,
                            refurbish=line.refurbish,
                            serial=None if line.quantity > 1 else line.serial_equipment,
                            health_register=line.health_register,
                            software_version=line.product.software_version if line.product.software_required else "No Aplica",
                            maintenance_frequency="none",
                            purchase_origin=line,
                        )
                        equipment.save()
                else:
                    continue
            purchase.equipment_create = True
            cls.save(purchases)
        else:
            raise UserError(str("Número de Compras Invalido."))

            
class Line(metaclass=PoolMeta):
    "Purchase Line Equipment"
    __name__ = 'purchase.line'

    origin_country = fields.Many2One('country.country',"Origin Country")
    address_equipment = fields.Many2One('party.address', "Direccion", required=True)
    serial_equipment = fields.Char("Serial", size=None,
                                   states={'invisible': If(Eval('quantity') > 1, True)})
    refurbish = fields.Boolean("Refurbish")
    product_equipment = fields.Boolean("Product Equipment",
                                       states={'readonly': True})
    software_version = fields.Char("Software version")
    health_register = fields.Char("Health Register", states={'required': Eval('product_equipment', True)})

    
    @classmethod
    def default_address_equipment(cls):
        pool = Pool()
        Company = pool.get('company.company')
        company = Transaction().context.get('company')
        if company:
            company = Company(company)
            
            return company.party.addresses[0].id

    @fields.depends(
        'product', 'quantity', methods=['_get_context_purchase_price'])
    def on_change_quantity(self):
        Product = Pool().get('product.product')
        if self.quantity > 1 or self.quantity < 1:
            self.serial_equipment = None
            
        if not self.product:
            self.serial_equipment = None
            return

        with Transaction().set_context(self._get_context_purchase_price()):
            self.unit_price = Product.get_purchase_price([self.product],
                abs(self.quantity or 0))[self.product.id]

            if self.unit_price:
                self.unit_price = round_price(self.unit_price)

    @fields.depends('product', 'unit', 'purchase', '_parent_purchase.party',
                    '_parent_purchase.invoice_party', 'product_supplier', 'product_equipment',
                    'serial_equipment', 'software_version', 'health_register',
                    'refurbish', methods=['compute_taxes', 'compute_unit_price',
                                          '_get_product_supplier_pattern'])
    def on_change_product(self):
        if not self.product:
            self.product_equipment = False
            self.address_equipment = None
            self.serial_equipment = None
            self.software_version = None
            self.health_register = None
            self.refurbish = None
            self.quantity = None
            self.unit_price = None
            self.unit = None

            return

        party = None
        if self.purchase:
            party = self.purchase.invoice_party or self.purchase.party
        # Set taxes before unit_price to have taxes in context of purchase
        # price
        self.taxes = self.compute_taxes(party)

        category = self.product.purchase_uom.category
        if not self.unit or self.unit.category != category:
            self.unit = self.product.purchase_uom

        product_suppliers = list(self.product.product_suppliers_used(
                **self._get_product_supplier_pattern()))
        if len(product_suppliers) == 1:
            self.product_supplier, = product_suppliers
        elif (self.product_supplier
                and self.product_supplier not in product_suppliers):
            self.product_supplier = None

        self.unit_price = self.compute_unit_price()

        self.type = 'line'
        self.amount = self.on_change_with_amount()
        if self.product.equipment:
            self.product_equipment = True
            self.address_equipment = self.default_address_equipment()
            if self.product.software_required:
                self.software_version = self.product.software_version
        
    @classmethod
    def view_attributes(cls):
        return super(Line, cls).view_attributes() + [
            ('//page[@id="equipment"]', 'states', {
                    'invisible': ~Eval('product_equipment', True),
                    })]
