# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from trytond.model import \
    DeactivableMixin, Workflow, ModelSQL, ModelView, fields
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.i18n import gettext
from trytond.exceptions import UserError
from trytond.model.exceptions import AccessError
from trytond.wizard import Button, StateAction, StateView, Wizard
from trytond.modules.company import CompanyReport


_MAINTENANCE_FREQUENCY = [
    ('none', ''), ('6', 'Seis Meses'), ('12', 'Doce Meses')]


class OpticalEquipment(DeactivableMixin, Workflow, ModelSQL, ModelView):
    'Optical Equipment'
    __name__ = 'optical_equipment.equipment'
    _rec_name = 'rec_name'
    _order_name = 'code'

    _states = {
        'readonly': Eval('state') != 'draft',
    }

    _states_product = {'readonly': Eval('product', True)}

    _depends = ['state']

    _states_serial = {
        'readonly': Eval('state') != 'draft',
    }

    code = fields.Char('Code', states={'readonly': True})

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('registred', 'Registred'),
            ('uncontrated', 'UnContrated'),
            ('contrated', 'Contrated'),
        ],
        'State',
        required=True,
        readonly=True,
        sort=False,
    )

    company = fields.Many2One('company.company', 'Company', readonly=True)
    contract = fields.Many2One(
        'optical_equipment.contract', 'Contract', ondelete='CASCADE'
    )
    location = fields.Many2One(
        'stock.location',
        'Location',
        states=_states,
    )
    propietary = fields.Many2One(
        'party.party',
        'Propietary',
        required=True,
        states=_states,
    )
    propietary_address = fields.Many2One(
        'party.address',
        'Propietary Address',
        required=True,
        domain=[('party', '=', Eval('propietary'))],
        states=_states,
    )
    propietarys = fields.Many2Many(
        'optical_equipment.equipment-party.party',
        'equipment', 'party', 'Propietarys'
    )
    product = fields.Many2One(
        'product.product',
        'Product',
        domain=[('equipment', '=', True)],
        states=_states,
        depends=['equipment'],
    )
    refurbish = fields.Boolean(
        'Refurbish',
        states=_states,
    )
    equipment_type = fields.Char('type', states=_states_product)
    risk = fields.Char('Type risk', states=_states_product)
    use = fields.Char('Use', states=_states_product)
    biomedical_class = fields.Char('Biomedical Class', states=_states_product)
    main_tecnology = fields.Char('Main tecnology', states=_states_product)
    calibration = fields.Boolean('Apply calibration', states=_states_product)
    mark_category = fields.Many2One(
        'product.category',
        'Mark',
        required=True,
        domain=[('parent', '=', None), ('accounting', '=', False)],
        states=_states,
    )
    model_category = fields.Many2One(
        'product.category',
        'Model',
        required=True,
        domain=[('parent', '=', Eval('mark_category')),
                ('accounting', '=', False)],
        states=_states,
    )
    reference_category = fields.Many2One(
        'product.category',
        'Reference',
        domain=[('parent', '=', Eval('model_category'))],
        states=_states,
        depends=['model_category'],
    )
    origin_country = fields.Many2One(
        'country.country',
        'Origin Country',
        states=_states,
    )

    software_version = fields.Char(
        'Software version',
        size=None,
        states=_states,
    )
    useful_life = fields.Integer(
        'Useful life',
        states=_states,
    )
    warranty = fields.Integer(
        'Warranty',
        states=_states,
    )
    serial = fields.Char('Serial', size=None,
                         states=_states_serial, depends=_depends)
    health_register = fields.Char(
        'Health Register',
        size=None,
        states=_states,
    )
    # contract_history =
    # fields.Many2Many('optical_equipment.contract-optical_equipment.equipment',
    # 'equipment','contract', 'Contracts', states={'readonly': True})
    contract_history = fields.Function(
        fields.One2Many('optical_equipment.contract',
                        'equipment', 'Contracts'),
        'get_contracts_of_equipment',
    )
    maintenance_history = fields.Function(
        fields.Many2Many(
            'optical_equipment.maintenance-optical_equipment.equipment',
            'equipment',
            'maintenance',
            'Maintenances',
        ),
        'get_maintenances_of_equipment',
    )
    software_version = fields.Char(
        'Software version',
        size=None,
        states=_states,
    )

    maintenance_frequency = fields.Selection(
        _MAINTENANCE_FREQUENCY, 'Maintenance Frequency',
        depends=['propietary']
    )
    purchase_origin = fields.Reference(
        'Purchase Origin',
        selection='get_origin', states={'readonly': True}
    )
    sale_destination = fields.Reference(
        'Sale Destination',
        selection='get_destination', states={'readonly': True}
    )
    shipment_destination = fields.Reference(
        'Stock Move', selection='get_shipment', states={'readonly': True}
    )
    rec_name = fields.Function(fields.Char('rec_name'), 'get_rec_name')

    technician_responsible = fields.Function(
        fields.Char('Technician Responsible'), 'get_technical'
    )
    invima = fields.Function(fields.Char('Invima'), 'get_invima')

    del _states_serial, _states, _depends

    def get_technical(self, name):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)

        if config.technician_responsible:
            technician_responsible = config.technician_responsible
            return technician_responsible.party.name

    def get_invima(self, name):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)
        if config.technician_responsible.invima:
            return config.technician_responsible.invima

    @fields.depends('product', 'serial', 'code')
    def get_rec_name(self, name):
        name = str(self.product.name) + '@' + \
                   str(self.serial) + '/' + str(self.code)

        return name

    @staticmethod
    def _get_shipment():
        'Return list of Model names for shipment Reference'
        return [
            'stock.shipment.in',
            'stock.shipment.out',
            'stock.shipment.out.return',
            'stock.shipment.in.return',
            'stock.shipment.internal',
        ]

    @classmethod
    def get_shipment(cls):
        IrModel = Pool().get('ir.model')
        get_name = IrModel.get_name
        models = cls._get_shipment()

        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        pool = Pool()
        Purchase = pool.get('purchase.line')

        return [Purchase.__name__]

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()

        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    def _get_destination(cls):
        'Return list of Model names for origin Reference'
        pool = Pool()
        Sale = pool.get('sale.line')

        return [Sale.__name__]

    @classmethod
    def get_destination(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_destination()

        return [(None, '')] + [(m, get_name(m)) for m in models]

    @classmethod
    def __setup__(cls):
        super(OpticalEquipment, cls).__setup__()
        cls._transitions = {
            ('draft', 'registred'),
            ('registred', 'draft'),
            ('registred', 'uncontrated'),
            ('uncontrated', 'contrated'),
        }
        cls._buttons.update(
            {
                'draft': {'invisible': Eval('state') != 'registred'},
                'registred': {
                    'invisible': Eval('state').in_(
                        ['registred', 'uncontrated', 'contrated']
                    )
                },
            }
        )

    @classmethod
    def set_code(cls, equipments):
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)

        for equipment in equipments:
            if config.equipment_sequence is not None:
                if not equipment.code:
                    try:
                        equipment.code = config.equipment_sequence.get()
                        cls.save(equipments)
                    except UserError:
                        raise UserError(str('Validation Error'))
            else:
                raise UserError(
                    gettext('optical_equipment.msg_not_sequence_equipment'))

    def get_contracts_of_equipment(self, records):
        pool = Pool()
        ContractsEquipment = pool.get('optical_equipment.contract')
        contractsEquipment = set()

        contractsEquipment = ContractsEquipment.search(
            [('party', '=', self.propietary),
             ('history_equipments', 'in', [self.id])]
        )
        contracts = []

        for key in contractsEquipment:
            contracts.append(key.id)

        return contracts

    def get_maintenances_of_equipment(self, records):
        pool = Pool()
        MaintenancesEquipment = pool.get('optical_equipment.maintenance')
        maintenancesEquipment = set()

        maintenancesEquipment = MaintenancesEquipment.search(
            ['equipment', '=', self.id]
        )
        maintenances = []

        for key in maintenancesEquipment:
            maintenances.append(key.id)

        return maintenances

    def get_technician_signature(self):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)
        if config.technician_signature:
            return config.technician_signature

    @classmethod
    def default_state(cls):
        return 'draft'

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @fields.depends('propietary', 'maintenance_frequency')
    def on_change_propietary(self):
        if self.propietary:
            if self.propietary.customer_type == 'ips':
                self.maintenance_frequency = '6'
            else:
                self.maintenance_frequency = '12'
        else:
            self.maintenance_frequency = 'none'

    @fields.depends(
        'product',
        'equipment_type',
        'use',
        'biomedical_class',
        'calibration',
        'mark_category',
        'model_category',
    )
    def on_change_product(self):
        if self.product:
            self.equipment_type = self.product.equipment_type
            self.use = self.product.use
            self.biomedical_class = self.product.biomedical_class
            self.calibration = self.product.calibration
            self.mark_category = self.product.mark_category
            self.model_category = self.product.model_category
            self.reference_category = self.product.reference_category
            self.useful_life = (
                self.product.useful_life if self.product.useful_life else int(
                    0)
            )
            self.calibration = True if self.product.calibration else False
            self.warranty =\
                self.product.warranty if self.product.warranty else int(0)
            self.risk = self.product.risk
            self.origin_country = self.product.origin_country
            self.use = self.product.use
            self.biomedical_class = self.product.biomedical_class
        else:
            self.equipment_type = None
            self.use = None
            self.biomedical_class = None
            self.calibration = None
            self.mark_category = None
            self.model_category = None
            self.reference_category = None
            self.useful_life = None
            self.calibration = False
            self.warranty = None
            self.risk = None
            self.origin_country = None
            self.use = None
            self.biomedical_class = None
            self.refurbish = None
            self.serial = None
            self.health_register = None
            self.software_version = None

    @classmethod
    def delete(cls, equipments):
        for equipment in equipments:
            if equipment.purchase_origin:
                raise AccessError(gettext('estos equipos no se pueden borrar'))
            elif equipment.state != 'draft' and equipment.serial is not None:
                raise AccessError(gettext('estos equipos no se pueden borrar'))
        super(OpticalEquipment, cls).delete(equipments)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, equipments):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('registred')
    def registred(cls, equipments):
        for i in equipments:
            if i.serial is None:
                raise UserError(str('El Equipo no cuenta con un Serial'))
            else:
                cls.set_code(equipments)


class EquipmentMaintenance(ModelSQL, ModelView):
    'Optical Equipment - Equipment - Maintenance'
    __name__ = 'optical_equipment.maintenance-optical_equipment.equipment'

    equipment = fields.Many2One(
        'optical_equipment.equipment',
        'Equipment',
    )
    maintenance = fields.Many2One(
        'optical_equipment.maintenance',
        'Maintenances',
    )


class EquipmentContract(ModelSQL, ModelView):
    'Optical Equipment - Contracs Equipment'
    __name__ = 'optical_equipment.contract-optical_equipment.equipment'

    equipment = fields.Many2One(
        'optical_equipment.equipment',
        'Equipment',
    )
    contract = fields.Many2One(
        'optical_equipment.contract',
        'Contract',
    )


class EquipmentParty(ModelSQL, ModelView):
    'Optical Equipment - Party'
    __name__ = 'optical_equipment.equipment-party.party'

    equipment = fields.Many2One(
        'optical_equipment.equipment',
        'Equipment',
    )
    party = fields.Many2One(
        'party.party',
        'Party',
    )


class ChangePropietary(ModelView):
    'Change of Propietary Equipment'
    __name__ = 'optical_equipment.change_propietary.form'

    old_propietary = fields.Many2One(
        'party.party', 'Old Propietary', states={'required': True}
    )
    equipments = fields.Many2Many(
        'optical_equipment.equipment',
        None,
        None,
        'Equipments',
        domain=[('propietary', '=', Eval('old_propietary'))],
        depends=['old_propietary'],
    )
    new_propietary = fields.Many2One(
        'party.party', 'New Propietary', states={'required': True}
    )
    new_address = fields.Many2One(
        'party.address',
        'New Address',
        required=True,
        domain=[('party', '=', Eval('new_propietary'))],
        states={'required': True},
    )
    change_date = fields.Date('Change Date', readonly=True)

    @classmethod
    def default_change_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()


class NewPropietary(Wizard):
    'Change Propietary'
    __name__ = 'optical_equipment.change_propietary'

    start = StateView(
        'optical_equipment.change_propietary.form',
        'optical_equipment.change_propietary_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'change_propietary', 'tryton-ok', default=True),
        ],
    )
    change_propietary = StateAction(
        'optical_equipment.act_optical_equipment_form')

    def do_change_propietary(self, action):
        equipments = self.start.equipments
        new_propietary = self.start.new_propietary
        new_address = self.start.new_address

        for equipment in equipments:
            equipment.propietarys += (equipment.propietary,)
            equipment.propietary = new_propietary
            equipment.propietary_address = new_address
            equipment.maintenance_frequency = (
                '6' if new_propietary.customer_type == 'ips' else '12'
            )
            equipment.save()


class ChangeEquipment(ModelSQL):
    'Change Equipment'
    __name__ = 'optical_equipment.equipment-change_propietary.form'

    maintenance_service = fields.Many2One(
        'optical_equipment_maintenance.service', 'Maintenance Service'
    )
    equipment = fields.Many2One('optical_equipment.equipment', 'Equipment')
    change = fields.Many2One(
        'optical_equipment.change_propietary.form', 'Change')


class EquipmentReport(CompanyReport):
    __name__ = 'optical_equipment.equipment'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(EquipmentReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        context['today'] = Date.today()

        return context
