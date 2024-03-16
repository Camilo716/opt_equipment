from trytond.pool import Pool, PoolMeta
from trytond.model import (
    ModelSQL, ModelView, Workflow, fields)
from trytond.modules.company import CompanyReport
from trytond.pyson import Eval, If, Bool
from trytond.modules.company.model import set_employee
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)

from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits

import datetime
from datetime import timedelta, date


class Cron(metaclass=PoolMeta):
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.method.selection.append(
            ('optical_equipment.contract|contract_expiration', 'Contract Expiration'),
        )


class Contract(Workflow, ModelSQL, ModelView):
    'Contracts'
    __name__ = 'optical_equipment.contract'
    _rec_name = 'number'
    _order_name = 'number'

    company = fields.Many2One(
        'company.company', "Company", required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('party', True),
        }, help="Make the subscription belong to the company.")
    number = fields.Char(
        "Number", readonly=True,
        help="The main identification of the subscription.")
    reference = fields.Char(
        "Reference",
        help="The identification of an external origin.")
    description = fields.Char("Description",
                              states={
                                  'readonly': Eval('state') != 'draft',
                              })
    party = fields.Many2One(
        'party.party', "Party", required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('party', True),
        }, help="The party who subscribes.")
    equipment = fields.Many2One('optical_equipment.equipment', "Equipment")
    contact = fields.Many2One('party.contact_mechanism', "Contact", required=True)
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
                                      required=True, domain=[('party', '=', Eval('party'))],
                                      states={
                                          'readonly': (Eval('state') != 'draft') | Eval('party', True),
                                      })
    start_date = fields.Date("Start Date", required=True,)
    end_date = fields.Date("End Date",
                           domain=['OR',
                                   ('end_date', '>=', If(
                                       Bool(Eval('start_date')),
                                       Eval('start_date', datetime.date.min),
                                       datetime.date.min)),
                                   ('end_date', '=', None),
                                   ],
                           states={
                               'readonly': Eval('state') != 'draft',
                           })

    maintenance_services = fields.Many2Many('optical_equipment_maintenance.service-equipment.contract',
                                            'contract', 'maintenance_services', "Prorogues",
                                            states={'readonly': Eval('state') != 'draft'})

    current_equipments = fields.Many2Many('optical_equipment.contract-optical_equipment.equipment',
                                          'contract', 'equipment', "Current Equipments",
                                          states={'readonly': Eval('state') != 'draft'})
    history_equipments = fields.One2Many('optical_equipment.equipment', 'contract', "Equipments",
                                         states={'readonly': Eval('state') != 'draft'})
    price_contract = Monetary("Price Contract", digits=price_digits, currency='currency', required=True,
                              states={'readonly': Eval('state') != 'draft'})
    state = fields.Selection([
        ('draft', "Draft"),
        ('running', "Running"),
        ('closed', "Closed"),
        ('cancelled', "Cancelled"),
    ], "State", readonly=True, required=False, sort=False,
        help="The current state of the subscription.")

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._order = [
            ('number', 'DESC NULLS FIRST'),
            ('id', 'DESC'),
        ]
        cls._transitions = ({
            ('draft', 'running'),
            ('running', 'draft'),
            ('running', 'closed'),
            ('running', 'cancelled'),
            ('cancelled', 'draft')
        })
        cls._buttons.update({
            'draft': {'invisible': Eval('state').in_(['draft', 'closed'])},
            'running': {'invisible': Eval('state').in_(['cancelled', 'running'])},
            'closed': {'invisible': Eval('state').in_(['draft', 'cancelled'])},
            'cancelled': {'invisible': Eval('state').in_(['draft', 'cancelled'])}
        })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_state():
        return 'draft'

    @classmethod
    def set_number(cls, contracts):
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(4)

        if config.contract_sequence is not None:
            if not contracts[0].number:
                try:
                    contracts[0].number = config.contract_sequence.get()
                    cls.save(contracts)
                except UserError:
                    raise UserError(str('Validation Error'))
        else:
            raise UserError(gettext('optical_equipment.msg_not_sequence_equipment'))

    @classmethod
    def contract_expiration(cls):
        pool = Pool()
        Contracts = pool.get('optical_equipment.contract')

        contracts_to_expire = cls.search([('state', '=', 'running'),
                                          ('end_date', '<=', date.today())])

        if contracts_to_expire != []:
            for contract in contracts_to_expire:
                cls.closed([contract])

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, contracts):
        contract = contracts[0]
        for equipment in contract.current_equipments:
            equipment.state = "uncontrated"
            equipment.contract_history += (contract.id,)
            equipment.save()
        contract.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('closed')
    def closed(cls, contracts):
        contract = contracts[0]
        for equipment in contract.current_equipments:
            equipment.state = "uncontrated"
            equipment.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('running')
    def running(cls, contracts):
        contract = contracts[0]
        for equipment in contract.current_equipments:
            equipment.state = "contrated"
            equipment.contract_history += (contract.id,)
            equipment.save()

        cls.set_number(contracts)
        contract.state = 'running'
        contract.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancelled(cls, contracts):
        contract = contracts[0]
        for equipment in contract.current_equipments:
            equipment.state = "uncontrated"
            equipment.save()


class ContractMaintenanceServices(ModelSQL):
    'Contract - Maintenance Services'
    __name__ = 'optical_equipment_maintenance.service-equipment.contract'

    maintenance_services = fields.Many2One(
        'optical_equipment_maintenance.service', "Maintenance Service", )
    contract = fields.Many2One('optical_equipment.contract', "Contract")


class ContractEquipment(ModelSQL):
    'Optical Equipment - Contract'
    __name__ = 'optical_equipment.contract-optical_equipment.equipment'

    equipment = fields.Many2One('optical_equipment.equipment', 'Equipment', )
    contract = fields.Many2One('optical_equipment.contract', 'Contract', )


class ContractReport(CompanyReport):
    __name__ = 'optical_equipment.contract'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(ContractReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        context['today'] = Date.today()

        return context


class CreateContractInitial(ModelView, ModelSQL):
    'Create Contract Inicial'
    __name__ = 'optical_equipment_create.contract'

    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    company = fields.Many2One(
        'company.company', "Company", readonly=True, required=True,
        states={
            'readonly': (Eval('state') != 'draft') | Eval('party', True),
        }, help="Make the subscription belong to the company.")
    party = fields.Many2One(
        'party.party', "Party", required=True,
        help="The party who subscribes.")
    invoice_address = fields.Many2One('party.address', 'Invoice Address',
                                      required=True, domain=[('party', '=', Eval('party'))])
    payment_term = fields.Many2One('account.invoice.payment_term',
                                   'Payment Term')
    contact = fields.Many2One(
        'party.contact_mechanism', "Contact", required=True,
        domain=[('party', '=', Eval('party'))],
        context={
            'company': Eval('company', -1),
        })
    start_date = fields.Date("Start Date", required=True)
    end_date = fields.Date("End Date",
                           domain=['OR',
                                   ('end_date', '>=', If(
                                       Bool(Eval('start_date')),
                                       Eval('start_date', datetime.date.min),
                                       datetime.date.min)),
                                   ('end_date', '=', None),
                                   ])
    unit_price = Monetary("Unit Price", digits=price_digits, currency='currency', required=True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_currency():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.id

    @classmethod
    def default_start_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()

    @fields.depends('party')
    def on_change_party(self):
        pool = Pool()
        Date = pool.get('ir.date')
        if self.party:
            self.invoice_address = self.party.address_get(type='invoice')
            if self.party.customer_type == "ips":
                self.end_date = Date.today() + timedelta(days=182)
            else:
                self.end_date = Date.today() + timedelta(days=365)


class CreateContract(Wizard):
    __name__ = 'optical_equipment.maintenance.contract'

    start = StateView('optical_equipment_create.contract',
                      'optical_equipment.create_contract_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Create', 'create_contract', 'tryton-ok', default=True),
                      ])
    create_contract = StateAction('optical_equipment.act_contract_form')

    def default_start(self, fields):
        if self.record:
            default = {'party': self.record.propietary.id,
                       'invoice_address': self.record.propietary_address.id,
                       'unit_price': (self.record.sale_origin.amount
                                      if self.record.sale_origin.__name__ == "sale.line"
                                      else self.record.sale_origin.total_amount),
                       }
            return default

    @property
    def _subscription_start(self):
        return dict(
            party=self.start.party,
            contact=self.start.contact,
            start_date=self.start.start_date,
            end_date=self.start.end_date,
            invoice_address=self.start.invoice_address,
            unit_price=self.start.unit_price
        )

    def do_create_contract(self, action):
        maintenance_service = self.records[0]
        pool = Pool()
        Contract = pool.get('optical_equipment.contract')

        dates = self._subscription_start

        prorogues = (maintenance_service,)
        equipments = []
        for line in maintenance_service.lines:
            equipments.append(line.equipment.id)

        if maintenance_service.contract_origin:
            contract = maintenance_service.contract_origin
            contract.history_equipments += tuple(equipments)
            contract.current_equipments = equipments
            contract.invoice_address = dates['invoice_address']
            contract.contact = dates['contact']
            contract.start_date = dates['start_date']
            contract.end_date = dates['end_date']
            contract.maintenance_services += prorogues
            contract.state = 'draft'
            contract.price_contract = dates['unit_price']
        else:
            contract = Contract(party=dates['party'],
                                invoice_address=dates['invoice_address'],
                                contact=dates['contact'],
                                start_date=dates['start_date'],
                                end_date=dates['end_date'],
                                maintenance_services=prorogues,
                                current_equipments=equipments,
                                state='draft',
                                price_contract=dates['unit_price']
                                )

        contract.save()
