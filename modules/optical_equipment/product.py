# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms
from trytond.pool import Pool, PoolMeta
from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Bool, If, Eval, Id


_RISK = [('n/a', 'No aplíca'), ('uno', 'I'), ('dosA', 'IIA'), ('dosB', 'IIB')]

_USE = [('', ''), ('medico', 'Médico'),
        ('basico', 'Basico'), ('apoyo', 'Apoyo')]

_BIOMEDICAL_CLASS = [
    ('n/a', 'No aplíca'),
    ('diagnostico', 'Diagnóstico'),
    ('rehabilitación', 'Rehabilitación'),
]

_MAIN_TECNOLOGY = [
    ('', ''),
    ('mecanico', 'Mecánico'),
    ('electrico', 'Electrico'),
    ('electronico', 'Electrónico'),
    ('hidraulico', 'Hidraulico'),
    ('neumatico', 'Neumatico'),
]

_EQUIPMENT_TYPE = [
    ('', ''),
    ('mobiliario_optico', 'Mobiliario óptico'),
    ('refraccion', 'Refracción'),
    ('medico', 'Medicion'),
    ('accesorios', 'Accesorios'),
]

NON_MEASURABLE = ['service']


class Template(metaclass=PoolMeta):
    'Template'
    __name__ = 'product.template'

    product = fields.Many2One(
        'optical_equipment.maintenance',
        'Maintenance Activity',
        ondelete='CASCADE',
    )
    equipment = fields.Boolean(
        'It is equipment',
        states={
            'invisible': Eval('type', 'goods') != 'goods',
        },
    )
    maintenance_activity = fields.Boolean(
        'Maintenance Activity',
        states={
            'invisible': Eval('type', 'service') != 'service',
            'readonly': If(Eval('equipment', True), True)
            | If(Eval('replacement', True), True),
        },
    )
    replacement = fields.Boolean(
        'Replacement',
        states={
            'invisible': Eval('type', 'goods') != 'goods',
            'readonly': If(Eval('equipment', True), True)
            | If(Eval('maintenance_activity', True), True),
        },
    )

    maintenance_required = fields.Boolean(
        'Miantenance Required',
        states={
            'invisible':
                (Eval('type', 'goods') != 'goods')
        }
    )
    equipment_type = fields.Selection(
        _EQUIPMENT_TYPE, 'Equipment type',
        states={
            'required':
                Eval('equipment', False)
        }
    )
    risk = fields.Selection(_RISK, 'Type risk')
    use = fields.Selection(
        _USE,
        'Use',
        states={'required': Eval('equipment', False)},
        depends={'equipment'},
    )
    biomedical_class = fields.Selection(
        _BIOMEDICAL_CLASS,
        'Biomedical Class',
        states={'required': Eval('equipment', False)},
    )
    main_tecnology = fields.Selection(
        _MAIN_TECNOLOGY, 'Main tecnology',
        states={
            'required':
                Eval('equipment', False)
        }
    )
    calibration = fields.Boolean('Apply calibration')
    observation = fields.Text('Observation')

    # Mark, Category, Reference
    mark_category = fields.Many2One(
        'product.category',
        'Mark',
        domain=[('parent', '=', None), ('accounting', '=', False)],
        states={'required': Eval('equipment', False)},
    )
    model_category = fields.Many2One(
        'product.category',
        'Model',
        domain=[('parent', '=', Eval('mark_category')),
                ('accounting', '=', False)],
        states={'required': Eval('equipment', False)},
    )
    reference_category = fields.Many2One(
        'product.category',
        'Reference',
        domain=[('parent', '=', Eval('model_category'))],
    )

    # Information Equipment
    origin_country = fields.Many2One('country.country', 'Origin Country')
    refurbish = fields.Boolean('Refurbish')
    software_required = fields.Boolean('Software Required')
    software_version = fields.Char(
        'Software version',
        states={'invisible': ~Eval('software_required', True)},
        depends={'software_required'},
    )

    # These are measurements required for the equipments, are in this place
    # for manage of class 'product.template'

    temperature_min = fields.Float('Temp Min')
    temperature_max = fields.Float('Temp Max')
    temperature_uom = fields.Many2One(
        'product.uom',
        'Temperature UOM',
        domain=[
            ('category', '=', Id('optical_equipment', 'uom_cat_temperature'))
        ],
    )
    frequency = fields.Float('Frequency')
    frequency_uom = fields.Many2One(
        'product.uom',
        'Frequency UOM',
        domain=[
            ('category', '=', Id('optical_equipment', 'uom_cat_frequency'))
        ]
    )
    moisture_min = fields.Float('Moisture Min')
    moisture_max = fields.Float('Moisture Max')
    moisture_uom = fields.Many2One(
        'product.uom',
        'Moisture UOM',
        domain=[
            ('category', '=',
                Id('optical_equipment', 'uom_cat_relative_humedity'))
        ],
    )
    electrical_equipment = fields.Boolean('Electrical Equipment')
    frequency = fields.Float(
        'Frequency', states={'invisible': ~Bool(Eval('electrical_equipment'))}
    )
    frequency_uom = fields.Many2One(
        'product.uom',
        'Frequency UOM',
        domain=[
            ('category', '=', Id('optical_equipment', 'uom_cat_frequency'))
        ],
    )
    voltageAC = fields.Float(
        'Voltage AC', states={'invisible': ~Bool(Eval('electrical_equipment'))}
    )
    voltageAC_uom = fields.Many2One(
        'product.uom',
        'Voltage AC UOM',
        domain=[
            ('category', '=',
                Id('optical_equipment', 'uom_cat_electrical_tension'))
        ],
    )
    voltageDC = fields.Float(
        'Voltage DC', states={'invisible': ~Bool(Eval('electrical_equipment'))}
    )
    voltageDC_uom = fields.Many2One(
        'product.uom',
        'Voltage DC UOM',
        domain=[
            ('category', '=',
                Id('optical_equipment', 'uom_cat_electrical_tension'))
        ],
    )

    useful_life = fields.Integer('Useful life')
    warranty = fields.Integer('Warranty')

    # calibration parameters
    use_pattern = fields.Many2One(
        'optical_equipment.use_pattern',
        'Use Pattern',
        ondelete='RESTRICT',
        states={'required': Eval('calibration', True)},
    )
    measuring_range = fields.Selection(
        [('dioptria', 'Dioptria'), ('mmhg', 'mmHg')], 'Rango de Medición'
    )
    MEP = fields.Float(
        'MEP',
        states={'required': Eval('calibration', False)},
    )
    uncertainy_pattern = fields.Float(
        'Uncertainy Pattern',
        states={'required': Eval('calibration', True)},
        help="Agregar valores separados por ',' Ej:-5,+5,-10,+10",
    )
    k_pattern = fields.Char(
        'K Pattern',
        states={'required': Eval('calibration', False)},
        help="Agregar valores separados por ',' Ej:-5,+5,-10,+10",
    )
    k_pattern_list = fields.One2Many(
        'optical_equipment.product_pattern',
        'product',
        'List of patterns K',
        states={'required': Eval('calibration', False)},
    )
    resolution_type = fields.Selection(
        [('', ''), ('analoga', 'Analoga'), ('digital', 'Digital')],
        'Resolution Type',
        states={'required': Eval('calibration', False)},
    )

    d_resolution = fields.Float('Resolution d')
    analog_resolution = fields.Float('Analog resolution')
    a_factor_resolution = fields.Float('(a) Resolution')
    Usubi = fields.Integer(
        'Usub i', states={'required': Eval('calibration', False)})

    # maintenance activities
    initial_operation = fields.Boolean(
        'Verificación inicial de funcionamiento')
    check_equipment = fields.Boolean('Revisión del Equipo')
    check_electric_system = fields.Boolean('Revisión del sistema electríco')
    clean_int_ext = fields.Boolean('Limpieza interior y exterior')
    clean_eyes = fields.Boolean('Limpieza de lentes y espejos')
    optical = fields.Boolean('Optical')
    check_calibration = fields.Boolean('Verificar Calibración')

    # Maintenance activites Preventives
    preventive_activities = fields.Text('Preventive Activities')

    @classmethod
    def view_attributes(cls):
        return super(Template, cls).view_attributes() + [
            (
                "//page[@id='features']",
                'states',
                {
                    'invisible': ~Eval('equipment'),
                },
            ),
            (
                "//page[@id='calibration']",
                'states',
                {'invisible': ~Eval('calibration')},
            ),
            (
                "//page[@id='maintenance_activities']",
                'states',
                {'invisible': ~Eval('maintenance_required')},
            ),
        ]

    @classmethod
    @fields.depends('measuring_range')
    def default_measuring_range(self):
        return 'dioptria'

    @classmethod
    @fields.depends('temperature_min')
    def default_temperature_min(self):
        return 0

    @classmethod
    @fields.depends('temperature_max')
    def default_temperature_max(self):
        return 0

    @classmethod
    def default_frequency(cls):
        return 0

    @classmethod
    def default_moisture_min(cls):
        return 0

    @classmethod
    def default_moisture_max(cls):
        return 0

    @classmethod
    def default_voltageDC(cls):
        return 0

    @classmethod
    def default_voltageAC(cls):
        return 0

    def default_risk():
        return 'n/a'

    def default_use():
        return None

    def default_biomedical_class():
        return 'n/a'

    def default_main_tecnology():
        return None

    def default_calibration():
        return False

    def default_refurbish():
        return False

    @classmethod
    @fields.depends('temperature')
    def default_temperature_uom(self):
        pool = Pool()
        Measurements = pool.get('product.uom')
        measurement = Measurements.search(['name', '=', 'Celsius'])[0].id

        return measurement

    @classmethod
    def default_frequency_uom(cls):
        pool = Pool()
        Measurements = pool.get('product.uom')
        measurement = Measurements.search(['name', '=', 'Hertz'])[0].id

        return measurement

    @classmethod
    def default_moisture_uom(cls):
        pool = Pool()
        Measurements = pool.get('product.uom')
        measurement = Measurements.search(
            ['name', '=', 'Relative Humedity'])[0].id

        return measurement

    @classmethod
    def default_voltageAC_uom(cls):
        pool = Pool()
        Measurements = pool.get('product.uom')
        measurement = Measurements.search(['name', '=', 'Volt'])[0].id

        return measurement

    @classmethod
    def default_voltageDC_uom(cls):
        pool = Pool()
        Measurements = pool.get('product.uom')
        measurement = Measurements.search(['name', '=', 'Volt'])[0].id

        return measurement

    @fields.depends('voltageDC', 'voltageDC_uom')
    def on_change_voltageDC_uom(self):
        pool = Pool()
        Measurements = pool.get('product.uom')
        measurement = Measurements.search(['name', '=', 'Volt'])[0].id
        self.voltageDC_uom = measurement

    @fields.depends('software_required', 'software_version')
    def on_change_with_sotfware_required(self):
        self.software_version = None

    @fields.depends('d_resolution', 'analog_resolution', 'a_factor_resolution')
    def on_change_resolution_type(self):
        self.d_resolution = None
        self.analog_resolution = None
        self.a_factor_resolution = None

    @fields.depends('equipment', 'replacement')
    def on_change_equipment(self):
        if self.equipment:
            self.replacement = False
            self.maintenance_activity = False
            self.calibration = False
            self.mark_category = None
            self.model_category = None
            self.reference_category = None
            self.equipment_type = None
            self.risk = 'n/a'
            self.biomedical_class = 'n/a'
            self.use = ''
            self.useful_life = 0
            self.warranty = 0

    @fields.depends('mark_category', 'model_category', 'reference_category')
    def on_change_mark_category(self):
        if not self.mark_category:
            self.model_category = None
            self.reference_category = None

    @fields.depends('model_category', 'reference_category')
    def on_change_model_category(self):
        if not self.model_category:
            self.reference_category = None

    @fields.depends('electrical_equipment')
    def on_change_electrical_equipment(self):
        if self.electrical_equipment:
            self.voltageAC = 0
            self.voltageDC = 0
            self.frequency = 0

    @classmethod
    def copy(cls, templates, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('code', None)
        default.setdefault('images', None)
        return super().copy(templates, default=default)


class Product(metaclass=PoolMeta):
    __name__ = 'product.product'

    @classmethod
    def copy(cls, products, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()

        default.setdefault('suffix_code', None)
        default.setdefault('code', None)
        default.setdefault('poduct', None)
        default.setdefault('images', None)
        return super().copy(products, default=default)


class Image(metaclass=PoolMeta):
    __name__ = 'product.image'

    @classmethod
    def __setup__(cls):
        super().__setup__()

    @classmethod
    def copy(cls, images, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.setdefault('template', None)
        default.setdefault('product', None)
        return super().copy(images, default=default)


class UsePattern(ModelSQL, ModelView):
    'Use Pattern'
    __name__ = 'optical_equipment.use_pattern'
    _rec_name = 'name_pattern'

    name_pattern = fields.Char('Name Pattern', required=True)


class Pattern(ModelSQL, ModelView):
    'Pattern K of equipment'
    __name__ = 'optical_equipment.product_pattern'
    _rec_name = 'rec_name'

    product = fields.Many2One(
        'product.template', 'Template', ondelete='CASCADE')
    pattern = fields.Float('Value Pattern')
    rec_name = fields.Function(fields.Char('rec_name'), 'get_rec_name')

    @fields.depends('pattern')
    def get_rec_name(self, name):
        if self.pattern:
            return str(self.pattern)
