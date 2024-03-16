# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    Workflow, ModelSQL, ModelView, Unique, fields, sequence_ordered)
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)
from trytond.modules.company import CompanyReport
from trytond.transaction import Transaction
from trytond.pyson import Bool, Eval, If, Id, Equal
from trytond.pool import Pool
from trytond.modules.currency.fields import Monetary
from trytond.modules.product import price_digits

import datetime
from datetime import timedelta

from scipy.stats import t
import matplotlib.pyplot as plt
import numpy as np
import math as mt

from io import BytesIO
from trytond.exceptions import UserError

_digits = (16, 2)


class MaintenanceService(Workflow, ModelSQL, ModelView):
    'Equipment Maintenance Service'
    __name__ = 'optical_equipment_maintenance.service'
    _rec_name = 'rec_name'
    _order_name = 'code'

    #_states = {'readonly': If(Eval('state') != 'draft', True)}
    _states = {}
    
    code = fields.Char("Code", readonly=True, )
    reference = fields.Char("Reference",
                            help="The identification of an external origin.")
    description = fields.Char("Description", states=_states)
    sale_date = fields.Char("Sale Date")
    contract_origin = fields.Reference(
        "Contract Base", selection='get_origin_contract',
        #states={'readonly': If(Eval('state') == 'finished', True)}
        )
    sale_origin = fields.Reference(
        "Sale Origin", selection='get_origin',
        states={'readonly': True})
    company = fields.Many2One('company.company', "Company", readonly=True)
    maintenance_type = fields.Selection([('initial', 'Initial'),
                                         ('preventive', 'Preventive'),
                                         ('corrective', 'Corrective')
                                         ], "Maintenance Type", states=_states)
    propietary = fields.Many2One('party.party', "Propietary", required=True,
                                 states=_states)
    propietary_address = fields.Many2One(
        'party.address', "Propietary Address", required=True,
        domain=[('party', '=', Eval('propietary'))],
        states=_states)
    lines = fields.One2Many(
        'optical_equipment.maintenance', 'service_maintenance', "Lines")
    estimated_agended = fields.DateTime("Date Maintenance", readonly=True)
    current_agended = fields.Many2One(
        'optical_equipment_maintenance.diary', "Current Agended",
        states=_states)
    history_agended = fields.Many2Many(
        'optical_equipment_maintenance.service-maintenance.diary', 'maintenance_service', 'agended', "History Agended", readonly=True)
    state_agended = fields.Selection([('no_agenda', "No agenda"),
                                      ('agended', "Agended"),
                                      ('in_progress', "In progress"),
                                      ('finish', "Finish"),
                                      ('failed', "Failed")], "State Agenda", readonly=True)
    technical = fields.Many2One('company.employee', "Technical", readonly=True)
    state = fields.Selection([('draft', "Draft"),
                              ('agended', "Agended"),
                              ('in_progress', "In Progress"),
                              ('failed', "Failed"),
                              ('finished', "Finished")
                              ], "State", required=True, readonly=True, sort=True)
    rec_name = fields.Function(fields.Char('rec_name'), 'get_rec_name')
    temperature_min = fields.Float("Temp Min", 
                                   #states={
       # 'readonly': If(Eval('state') == 'finished', True),
       # 'required': If(Eval('state') == 'in_progress', True)}
    )
    temperature_max = fields.Float("Temp Max", 
                                   #states={
        # 'readonly': If(Eval('state') == 'finished', True),
        # 'required': If(Eval('state') == 'in_progress', True)}
        )
    temperature_uom = fields.Many2One('product.uom', 'Temperature UOM',
                                      domain=[
                                          ('category', '=', Id(
                                              'optical_equipment', "uom_cat_temperature"))],
                                      #states={'invisible': If(Eval('temperature_min') is None, True),
                                      #        'readonly': (Eval('state') == 'finished'),
                                      #        'required': If(Eval('state') == 'in_progress', True)},
                                      )
    moisture_min = fields.Float("Moisture Min", 
                                # states={
        # 'readonly': If(Eval('state') == 'finished', True),
        # 'required': If(Eval('state') == 'in_progress', True)}
        )
    moisture_max = fields.Float("Moisture Max", 
                                # states={
        #'readonly': If(Eval('state') == 'finished', True),
        #'required': If(Eval('state') == 'in_progress', True)}
        )
    moisture_uom = fields.Many2One('product.uom', "Moisture UOM",
                                   domain=[
                                       ('category', '=', Id(
                                           'optical_equipment', 'uom_cat_relative_humedity'))],
                                   #states={'invisible': If(Eval('moisture_min') is None, True),
                                   #        'readonly': Eval('state') == 'finished',
                                   #        'required': If(Eval('state') == 'in_progress', True)},
                                   )
#
    technician_responsible = fields.Char('Technician Responsible')
    invima = fields.Char('Invima')
    technician_signature = fields.Binary('Technician Signature')

    @fields.depends('maintenance_type', 'code')
    def get_rec_name(self, name):
        if self.maintenance_type and self.code:
            name = str(self.maintenance_type) + '@' + str(self.code)
        else:
            name = str(self.maintenance_type) + '@' + 'Borrador'

        return name

    @classmethod
    def __setup__(cls):
        super(MaintenanceService, cls).__setup__()
        cls._order = [
            ('code', 'DESC'),
            ('id', 'DESC')]
        cls._transitions = ({
            ('draft', 'agended'),
            ('agended', 'in_progress'),
            ('in_progress', 'finished'),
        })
        cls._buttons.update({
            'reassing_agended': {'invisible': Eval('state') != 'failed'},
            'assing_agended': {'invisible': Eval('state') != 'draft'},
            'in_progress': {'invisible': Eval('state').in_(['draft', 'in_progress', 'finished'])},
            'finished': {'invisible': Eval('state').in_(['draft', 'agended', 'finished'])}
        })

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_temperature_min():
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)
        temperature_min = config.temperature_min

        return temperature_min

    @staticmethod
    def default_temperature_max():
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)
        temperature_max = config.temperature_max

        return temperature_max

    @staticmethod
    def default_moisture_min():
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)
        moisture_min = config.moisture_min

        return moisture_min

    @staticmethod
    def default_temperature_uom():
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)
        temperature_uom = config.temperature_uom.id

        return temperature_uom

    @staticmethod
    def default_moisture_uom():
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)
        moisture_uom = config.moisture_uom.id

        return moisture_uom

    @staticmethod
    def default_moisture_max():
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(1)
        moisture_max = config.moisture_max

        return moisture_max

    @classmethod
    def default_maintenance_type(self):
        return 'preventive'

    @classmethod
    def default_state_agended(self):
        return 'no_agenda'

    @classmethod
    def default_state(self):
        return 'draft'

    @classmethod
    def default_technician_responsible(cls):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)

        if config.technician_responsible:
            technician_responsible = config.technician_responsible
            return technician_responsible.party.name

    @classmethod
    def default_invima(cls):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)
        if config.technician_responsible:
            return config.technician_responsible.invima

    @classmethod
    def default_technician_signature(cls):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)
        if config.technician_signature:
            return config.technician_signature

    @classmethod
    def _get_origin(cls):
        'Return list of Model names for origin Reference'
        pool = Pool()
        Sale = pool.get('sale.sale')
        SaleLine = pool.get('sale.line')

        return [Sale.__name__, SaleLine.__name__]

    @classmethod
    def get_origin(cls):
        Model = Pool().get('ir.model')
        get_name = Model.get_name
        models = cls._get_origin()

        return [(None, '')] + [(m, get_name(m)) for m in models]

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

    @classmethod
    def set_code(cls, maintenance):
        pool = Pool()
        Config = pool.get('optical_equipment.configuration')
        config = Config(2)
        if config.maintenance_sequence is not None:
            if not maintenance.code:
                try:
                    maintenance.code = config.maintenance_sequence.get()
                    maintenance.save()
                except UserError:
                    raise UserError(str('Validation Error'))
        else:
            raise UserError(gettext('optical_equipment.msg_not_sequence_equipment'))

    @classmethod
    @ModelView.button_action(
        'optical_equipment.act_assing_agended')
    def assing_agended(cls, maintenances):
        pass

    @classmethod
    @ModelView.button_action(
        'optical_equipment.act_reassing_agended')
    def reassing_agended(cls, maintenances):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('in_progress')
    def in_progress(cls, maintenances):
        for maintenance in maintenances:
            maintenance.current_agended.state = 'in_progress'
            maintenance.current_agended.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('finished')
    def finished(cls, maintenances):
        for maintenance in maintenances:
            maintenance.current_agended.state = 'finished'
            maintenance.current_agended.save()


class MaintenanceServiceLine(Workflow, ModelSQL, ModelView):
    'Equipment Maintenance Line'
    __name__ = 'optical_equipment.maintenance'
    # _rec_name = 'rec_name'
    _states = {'required': True,
               'readonly': Eval('state').in_(['finished'])}

    service_maintenance = fields.Many2One('optical_equipment_maintenance.service', "Maintenance Service",
                                          ondelete='CASCADE',
                                          domain=[('state', 'in', ['draft', 'in_progress', 'finished']),
                                                  ('propietary', '=', Eval('propietary'))],
                                          states=_states)
    code = fields.Char(
        "Code", states={'readonly': True})
    maintenance_type = fields.Selection([('initial', 'Initial'),
                                         ('preventive', 'Preventive'),
                                         ('corrective', 'Corrective')], "Maintenance Type", states=_states)
    state = fields.Selection([('draft', "Draft"),
                              ('finished', "Finished")
                              ], "State", readonly=True, sort=False,
                             states=_states)
    company = fields.Many2One('company.company', "Company", readonly=True)
    propietary = fields.Many2One('party.party', "Propietary", states=_states,)
    propietary_address = fields.Many2One('party.address', "Propietary Address",
                                         states=_states,
                                         domain=[('party', '=', Eval('propietary'))],)
    equipment = fields.Many2One('optical_equipment.equipment', "Equipment",
                                domain=[('state', 'in', ['registred', 'uncontrated', 'contrated']),
                                        ('propietary', '=', Eval('propietary')),
                                        ('propietary_address', '=', Eval('propietary_address'))],
                                states=_states,)
    equipment_calibrate = fields.Boolean("Calibrate Equipment", states={'readonly': True})

    # Preventive maintenance
    initial_operation = fields.Boolean("Verificación inicial de funcionamiento")
    check_equipment = fields.Boolean("Revisión del Equipo")
    check_electric_system = fields.Boolean("Revisión del sistema electríco")
    clean_int_ext = fields.Boolean("Limpieza interior y exterior")
    clean_eyes = fields.Boolean("Limpieza de lentes y espejos")
    check_calibration = fields.Boolean("Verificar Calibración")
    maintenance_activity = fields.One2Many(
        'optical_equipment_maintenance.activity',
        'maintenance',
        "Maintenance Activitys")
    # Calibration
    patterns_equipments = fields.Char("K Pattern", states={'readonly': True},)
    lines_calibration = fields.One2Many('optical_equipment.maintenance.calibration_sample', 'maintenance', "Lines of Calibration",
                                        states={'readonly': Eval('state') == 'finished'})
    calibration_total = fields.One2Many('optical_equipment.maintenance.calibration', 'maintenance', "Calibration Total",
                                        states={'readonly': Eval('state') == 'finished'})
    maintenance_lines = fields.One2Many(
        'optical_equipment.maintenance.line', 'maintenance', 'Lines')
    description_activity = fields.Char('Activity')
    next_maintenance = fields.Function(fields.Date('Next Maintenance'), 'get_next_maintenance')
    temperature_min = fields.Float("Temp Min")
    temperature_max = fields.Float("Temp Max")
    temperature_uom = fields.Many2One('product.uom', 'Temperature UOM',
                                      domain=[
                                          ('category', '=', Id(
                                              'optical_equipment', "uom_cat_temperature"))],
                                      #states={'invisible': If(Eval('temperature_min') is None, True),
                                      #        'readonly': (Eval('state') == 'finished')},
                                      )
    moisture_min = fields.Float("Moisture Min")
    moisture_max = fields.Float("Moisture Max")
    moisture_uom = fields.Many2One('product.uom', "Moisture UOM",
                                   domain=[
                                       ('category', '=', Id(
                                           'optical_equipment', 'uom_cat_relative_humedity'))],
                                   #states={'invisible': If(Eval('moisture_min') is None, True),
                                    #       'readonly': Eval('state') == 'finished'},
                                    )
    graph_calibration = fields.Binary('Graphs')
    rec_name = fields.Function(fields.Char('rec_name'), 'get_rec_name')

    technician_responsible = fields.Char('Technician Responsible')
    invima = fields.Char('Invima')
    technician_signature = fields.Binary('Technician Signature')

    @classmethod
    def default_technician_responsible(cls):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)

        if config.technician_responsible:
            technician_responsible = config.technician_responsible
            return technician_responsible.party.name

    @classmethod
    def default_invima(cls):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)
        if config.technician_responsible:
            return config.technician_responsible.invima

    @classmethod
    def default_technician_signature(cls):
        pool = Pool()
        ConfigurationEquipment = pool.get('optical_equipment.configuration')
        config = ConfigurationEquipment(1)
        if config.technician_signature:
            return config.technician_signature

    @classmethod
    def __setup__(cls):
        super(MaintenanceServiceLine, cls).__setup__()
        cls._transitions.update({
            ('draft', 'finished')
        })
        cls._buttons.update({
            'in_progress': {'invisible': Eval('state').in_(['draft', 'in_progress', 'finished'])},
            'finished': {},
            #'finished': {'invisible': (Eval('state').in_(['finished'])) |
            #             ((Eval('maintenance_type') == 'corrective') & (Eval('maintenance_lines') == ()))},
            'samples': {},
            #'samples': {'invisible': (Eval('state').in_(['finished'])) | (Eval('lines_calibration') != ()) | (~Eval('equipment_calibrate'))},
            'calibrate': {}
            #'calibrate': {'invisible': (Eval('lines_calibration') == ()) | (Eval('state').in_(['finished'])),
            #              'depends': ['state'], }
        })

    @classmethod
    def view_attributes(cls):
        return super(MaintenanceServiceLine, cls).view_attributes() + [
            ('//page[@id="preventive"]', 'states', {
                'invisible': If(Eval('maintenance_type') == 'corrective', True),
            }),
            ('//page[@id="corrective"]', 'states', {
                'invisible': If(Eval('maintenance_type') != 'corrective', True),
            }),
            ('//page[@id="calibration"]', 'states', {
                'invisible': ~Eval('equipment_calibrate'),
            }),
            ('//page[@id="graph"]', 'states', {
                'invisible': ~Eval('equipment_calibrate'),
            })
        ]

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @classmethod
    def default_state(cls):
        return 'draft'

    @classmethod
    def default_maintenance_type(cls):
        return 'preventive'

    @classmethod
    def default_state_agended(cls):
        return 'no_agenda'

    @fields.depends('temperature_min', 'temperature_uom')
    def on_change_temperature_min(self):
        if self.temperature_min:
            pool = Pool()
            Measurements = pool.get('product.uom')
            self.temperature_uom = Measurements.search(['name', '=', 'Celsius'])[0].id

    @fields.depends('moisture_min', 'moisture_uom')
    def on_change_moisture_min(self):
        pool = Pool()
        Measurements = pool.get('product.uom')
        self.moisture_uom = Measurements.search(['name', '=', 'Relative Humedity'])[0].id

    @fields.depends('service_maintenance')
    def on_change_service_maintenance(self):
        if self.service_maintenance:
            self.propietary = self.service_maintenance.propietary
            self.propietary_address = self.service_maintenance.propietary_address
            service = self.service_maintenance
            self.temperature_min = service.temperature_min
            self.temperature_max = service.temperature_max
            self.temperature_uom = service.temperature_uom
            self.moisture_min = service.moisture_min
            self.moisture_max = service.moisture_max
            self.moisture_uom = service.moisture_uom
        else:
            self.propietary = None
            self.propietary_address = None
            self.temperature_min = None
            self.temperature_max = None
            self.temperature_uom = None
            self.moisture_min = None
            self.moisture_max = None
            self.moisture_uom = None

    @fields.depends('equipment', 'patterns_equipments')
    def on_change_equipment(self):
        if self.equipment:
            self.patterns_equipments = self.equipment.product.k_pattern
            self.equipment_calibrate = self.equipment.product.calibration
            self.initial_operation = self.equipment.product.initial_operation
            self.check_equipment = self.equipment.product.check_equipment
            self.check_electric_system = self.equipment.product.check_electric_system
            self.clean_int_ext = self.equipment.product.clean_int_ext
            self.clean_eyes = self.equipment.product.clean_eyes
            self.check_calibration = self.equipment.product.check_calibration
        else:
            self.patterns_equipments = None
            self.equipment_calibrate = False
            self.initial_operation = False
            self.check_equipment = False
            self.check_electric_system = False
            self.clean_int_ext = False
            self.clean_eyes = False
            self.check_calibration = False

    def get_next_maintenance(self, action):
        next_maintenance = None
        if self.service_maintenance.estimated_agended:
            if self.propietary.customer_type == "ips":
                next_maintenance = self.service_maintenance.estimated_agended + timedelta(days=182)
            else:
                next_maintenance = self.service_maintenance.estimated_agended + timedelta(days=365)
        return next_maintenance

    def get_standard_deviation(samples):
        """
        This function calculated the
        standartd deviation
        """
        sum_samples = sum(samples)
        n_samples = len(samples)
        mean = sum_samples / n_samples
        dev_std_square = sum((l - mean)**2 for l in samples) / (n_samples - 1)
        dev_std = mt.sqrt(dev_std_square)

        return dev_std

    def get_uncertain_type_A(samples, dev_std):
        """
        This function calculated the
        uncertain type A
        """
        n_samples = len(samples)
        uncertain_type_A = dev_std / mt.sqrt(n_samples)

        return uncertain_type_A

    def get_uncertain_pattern(self):
        """
        uncertain_pattern = 0,25 constante viene del equipo
        """
        uncertain_pattern = 0.25

        return uncertain_pattern

    def get_k_certificated_calibration(self):
        k_certificated_calibration = 2

        return k_certicated_calibration

    def get_uncertain_U_b1(self):
        uncertain_b1 = MEP / mt.sqrt(3)
        uncertain_b1a = uncertain_pattern / k_certificated_calibration

        return uncertain_b1

    def default_d_resolution(self):
        return d

    def get_uncertain_b2_digital(self):
        uncertain_b2 = d / 2 * mt.sqrt(3)

        return uncertain_b2

    def get_uncertain_b2_analog(self):
        """
        Incertidumbre por resolución Análoga
        a contante que viene del equipo
        """
        uncertain_b2_analog = d / a * math.sqrt(3)

        return uncertain_b2_analog

    def get_uncertain_combinated(self):
        """
        Incertidumbre Combinada
        """
        sum_uncertain_c = uncertain_type_A**2 + uncertain_b1**2 + uncertain_b2**2
        uncertain_c = math.sqrt(sum_uncertain_c)

        return uncertain_c

    def get_uncertain_eff(self):
        """
        Grados Efectivos de libertad
        """
        uncertain_eff = uncertain_c**4 / \
            ((uncertain_type_A**4) / (len(sample) - 1) +
             (uncertain_b1**4 / U_subi) + (uncertain_b2**4 / U_subi))

        return uncertain_eff

    def get_create_graph(matrix, patterns, resolution, equipment_risk):
        image = BytesIO()
        errors = []
        yerr = []

        upresolution = resolution if resolution >= 0 else (resolution * -1)
        lowresolution = resolution if resolution < 0 else (resolution * -1)

        count = 0
        for pattern in patterns:
            error = pattern - matrix[count][0]
            yerr.append(matrix[count][1])
            errors.append(error)
            count += 1

        labels = list(patterns)

        x = labels
        y = errors

        if equipment_risk == 'IIB':
            if sum(errors) == 0:
                top = 1.5
                bottom = -1.5
            else:
                top = 2
                bottom = -2
        else:
            top = 0.60
            bottom = -0.60

        ls = 'dotted'
        fig, ax1 = plt.subplots(nrows=1, ncols=1)

        # Límites del Eje Y
        ax1.set_ylim(bottom, top)
        # Límites del Eje X
        ax1.set_xlim((min(labels) - 1, max(labels) + 1))

        ax1.yaxis.grid(True)
        ax1.xaxis.grid(True)

        ax1.set_title('Error[D]')
        ax1.set_xlabel('Patrones')
        ax1.set_ylabel('Valores Observados')

        ax1.set_yticks([lowresolution, 0.0, upresolution])
        # ax1.set_xticks([-10.0,-5.0,0.0,5.0,10.0])

        ax1.errorbar(x, y, yerr=yerr, marker='D', markersize=10, linestyle=ls)

        plt.savefig(image, format='png')
        plt.close()

        return image.getvalue()

    @classmethod
    @ModelView.button
    @Workflow.transition('in_progress')
    def in_progress(cls, maintenances):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('finished')
    def finished(cls, maintenances):
        for maintenance in maintenances:
            if maintenance.equipment.product.calibration and maintenance.calibration_total == ():
                raise UserError("No puede finalizar este mantenimiento sin una calibración")
            else:
                maintenance.state = 'finished'
                maintenance.code = maintenance.id
                maintenance.save()

    @classmethod
    @ModelView.button
    def samples(cls, maintenances):
        pool = Pool()
        CalibrationSample = pool.get('optical_equipment.maintenance.calibration_sample')
        for maintenance in maintenances:
            patterns = maintenance.equipment.product.k_pattern_list
            for pattern in patterns:
                samples = []
                calibrationSample = CalibrationSample(
                    maintenance=maintenance.id,
                    product=maintenance.equipment.product.template.id,
                    value_patterns=pattern.id,
                    value_equipment=pattern.pattern,
                    mistake=0,
                    mistake_rate=0)
                samples = [calibrationSample] * 5
                maintenance.lines_calibration += tuple(samples)
                maintenance.save()

    @classmethod
    @ModelView.button
    def calibrate(cls, maintenances):
        pool = Pool()
        CalibrationLineTotal = pool.get('optical_equipment.maintenance.calibration')
        dates = {}
        dates_mistake_pattern = []
        patterns = set()

        for maintenance in maintenances:
            maintenance.calibration_total = ()
            if len(maintenance.lines_calibration) < 5:
                raise UserError("Por favor Ingrese mas de (5) Muestras por patrón (Dioptría)")
            else:
                for line in maintenance.lines_calibration:
                    if line.value_patterns.pattern not in patterns:
                        patterns.add(line.value_patterns.pattern)
                        dates[line.value_patterns.pattern] = [line.value_equipment]
                    else:
                        dates[line.value_patterns.pattern].append(line.value_equipment)

            for pattern in patterns:
                samples = dates[pattern]
                mean = sum(samples) / len(samples)
                U_subi = maintenance.equipment.product.Usubi
                uncertain_pattern = maintenance.equipment.product.uncertainy_pattern
                MEP = maintenance.equipment.product.MEP
                dev_std = cls.get_standard_deviation(samples)
                uncertain_type_A = cls.get_uncertain_type_A(samples, dev_std)
                k_certificated_calibration = 2
                uncertain_b1 = MEP / mt.sqrt(3)  # Ub1_patron a 2 Decimales
                uncertain_b1a = uncertain_pattern / k_certificated_calibration  # Ub1_MEP

                if maintenance.equipment.product.resolution_type == "analoga":
                    a_resolution = maintenance.equipment.product.analog_resolution
                    resolution = a_resolution
                    factor_a = maintenance.equipment.product.a_factor_resolution
                    uncertain_b2_analog = (a_resolution) / (factor_a * mt.sqrt(3))
                    sum_uncertain_c = (uncertain_type_A**2) + \
                        (uncertain_b1**2) + (uncertain_b2_analog**2)
                    uncertain_c = mt.sqrt(sum_uncertain_c)
                    uncertain_eff = uncertain_c**4 / \
                        ((uncertain_type_A**4) / (len(samples) - 1) +
                         (uncertain_b1**4 / U_subi) + (uncertain_b2_analog**4 / U_subi))
                elif maintenance.equipment.product.resolution_type == "digital":
                    d_resolution = maintenance.equipment.product.d_resolution
                    resolution = d_resolution
                    uncertain_b2_digital = (d_resolution) / (2 * mt.sqrt(3))
                    sum_uncertain_c = (uncertain_type_A**2) + \
                        (uncertain_b1**2) + (uncertain_b2_digital**2)
                    uncertain_c = mt.sqrt(sum_uncertain_c)
                    uncertain_eff = uncertain_c**4 / \
                        ((uncertain_type_A**4) / (len(samples) - 1) +
                         (uncertain_b1**4 / U_subi) + (uncertain_b2_digital**4 / U_subi))

                t_student = t.ppf(1 - 0.025, uncertain_eff)
                uncertain_expanded = round((t_student * uncertain_c), 2)
                dates_mistake_pattern.append([mean, uncertain_expanded])

                if maintenance.equipment.product.resolution_type == "analoga":
                    calibrationLineTotal = CalibrationLineTotal(
                        diopter=pattern,
                        mean=mean,
                        dev_std=dev_std,
                        uncertain_type_A=uncertain_type_A,
                        uncertain_pattern=uncertain_pattern,
                        k_c_calibration=k_certificated_calibration,
                        uncertain_U_b1=uncertain_b1,
                        d_resolution=a_resolution,
                        uncertain_U_b2_dig=0,
                        uncertain_U_b2_ana=uncertain_b2_analog,
                        uncertain_combinated=uncertain_c,
                        uncertain_eff=uncertain_eff,
                        t_student=t_student,
                        uncertain_expanded=uncertain_expanded,
                        state='Aprobado' if uncertain_expanded <= a_resolution else 'Rechazado'
                    )
                    maintenance.calibration_total += (calibrationLineTotal,)

                elif maintenance.equipment.product.resolution_type == "digital":
                    calibrationLineTotal = CalibrationLineTotal(
                        diopter=pattern,
                        mean=mean,
                        dev_std=dev_std,
                        uncertain_type_A=uncertain_type_A,
                        uncertain_pattern=uncertain_pattern,
                        k_c_calibration=k_certificated_calibration,
                        uncertain_U_b1=uncertain_b1,
                        d_resolution=d_resolution,
                        uncertain_U_b2_dig=uncertain_b2_digital,
                        uncertain_U_b2_ana=0,
                        uncertain_combinated=uncertain_c,
                        uncertain_eff=uncertain_eff,
                        t_student=t_student,
                        uncertain_expanded=uncertain_expanded,
                        state='Aprobado' if uncertain_expanded <= d_resolution else 'Rechazado'
                    )
                    maintenance.calibration_total += (calibrationLineTotal,)
                maintenance.save()

            equipment_risk = maintenance.equipment.product.risk
            image = cls.get_create_graph(
                dates_mistake_pattern, patterns, resolution, equipment_risk)
            maintenance.graph_calibration = image
            maintenance.save()


class MaintenanceLine(ModelSQL, ModelView):
    'Maintenance Line'
    __name__ = 'optical_equipment.maintenance.line'

    line_replace = fields.Boolean(
        "Replace",
        #states={
        #    'readonly': If(
        #        Eval('line_maintenance_activity') == True,
        #        True)}
        )
    line_maintenance_activity = fields.Boolean(
        "Maintenance Activity", 
        #states={
         #   'readonly': If(
         #       Eval('line_replace') == True, True)}
         )
    maintenance = fields.Many2One(
        'optical_equipment.maintenance',
        'Maintenance',
        ondelete='CASCADE',
    )
    replacement = fields.Many2One('product.product', 'Replacement', ondelete='RESTRICT',
                                  domain=[('replacement', '=', True)],
                                  #states={'invisible': (If(Eval('line_maintenance_activity') == True, True)) | (If(Eval('line_replace') == False, True)),
                                  #        'required': If(Eval('line_replace') == True, True)},
                                  depends={'line_replace'})
    maintenance_activity = fields.Many2One('product.product', 'Maintenance activity',
                                           domain=[('maintenance_activity', '=', True)],
                                           #states={'invisible': If(Eval('line_replace') == True, True) |
                                           #        (If(Eval('line_maintenance_activity') == False, True)),
                                           #        'required': If(Eval('line_maintenance_actitvity') == True, True)},
                                           depends={'line_maintenance_activity'})

    quantity = fields.Float("Quantity", required=True, digits='unit')
    actual_quantity = fields.Float(
        "Actual Quantity", digits='unit', readonly=True,
        states={
            'invisible': Eval('type') != 'line',
        })
    unit = fields.Many2One('product.uom', 'Unit', ondelete='RESTRICT',
                           states={
                               'readonly': Eval('_parent_maintenance.state') != 'draft',
                           }, domain=[If(Bool(Eval('product_uom_category')),
                                         ('category', '=', Eval('product_uom_category')),
                                         ('category', '!=', -1)),
                                      ])
    product_uom_category = fields.Function(fields.Many2One('product.uom.category', 'Product Uom Category'),
                                           'on_change_with_product_uom_category')
    description = fields.Text("Description", states={
        'readonly': Eval('_parent_maintenance.state') != 'draft',
    })
    company = fields.Function(
        fields.Many2One(
            'company.company',
            "Company"),
        'on_change_with_company')

    @fields.depends('maintenance', '_parent_maintenance.company')
    def on_change_with_company(self, name=None):
        if self.maintenance and self.maintenance.company:
            return self.maintenance.company.id

    @fields.depends('line_replace', 'replacement')
    def on_change_line_replace(self, name=None):
        if self.line_replace == False:
            self.replacement = None

    @fields.depends('line_maintenance_activity', 'maintenance_activity')
    def on_change_line_maintenance_activity(self, name=None):
        if self.line_maintenance_activity == False:
            self.maintenance_activity = None

    @fields.depends('replacement', 'maintenance', 'unit', 'maintenance')
    def on_change_replacement(self):
        if not self.replacement:
            self.unit = None
            return

        if not self.unit or self.unit.category != category:
            self.unit = self.replacement.sale_uom

    @fields.depends('maintenance_activity',
                    'quantity', 'unit')
    def on_change_maintenance_activity(self):
        if not self.maintenance_activity:
            self.quantity = None
            self.unit = None
            return

        self.quantity = 1
        if not self.unit or self.unit.category != category:
            self.unit = self.maintenance_activity.sale_uom


class MaintenanceActivity(ModelView, ModelSQL):
    'Maintenance Activitys'
    __name__ = 'optical_equipment_maintenance.activity'

    maintenance = fields.Many2One('optical_equipment.maintenance', 'Maintenance')
    product = fields.Many2One('product.product', 'Product',
                              domain=[('maintenance_activity', '=', True)])


class ChangePropietaryMaintenance(ModelView):
    'Change of Propietary Equipment'
    __name__ = 'optical_equipment.change_propietary_maintenance.form'

    old_propietary = fields.Many2One('party.party', 'Old Propietary',
                                     states={'required': True})
    maintenance_service = fields.Many2Many('optical_equipment_maintenance.service', None, None, "Maintenance Service",
                                           domain=[('propietary', '=', Eval('old_propietary'))],
                                           depends=['old_propietary'])
    new_propietary = fields.Many2One('party.party', "New Propietary",
                                     states={'required': True})
    new_address = fields.Many2One('party.address', "New Address", required=True,
                                  domain=[('party', '=', Eval('new_propietary'))],
                                  states={'required': True})
    change_date = fields.Date("Change Date", readonly=True)

    @classmethod
    def default_change_date(cls):
        pool = Pool()
        Date = pool.get('ir.date')
        return Date.today()


class NewPropietaryMaintenance(Wizard):
    'Change Propietary'
    __name__ = 'optical_equipment.change_propietary_maintenance'

    start = StateView('optical_equipment.change_propietary_maintenance.form',
                      'optical_equipment.change_propietary_maintenance_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Create', 'change_propietary', 'tryton-ok', default=True),
                      ])
    change_propietary = StateAction('optical_equipment.act_optical_equipment_form')

    def do_change_propietary(self, action):
        old_propietary = self.start.old_propietary
        services = self.start.maintenance_service
        new_propietary = self.start.new_propietary
        new_address = self.start.new_address

        for service in services:
            service.propietary = new_propietary
            service.propietary_address = new_address
            service.save()
            for maintenance in service.lines:
                maintenance.propietary = new_propietary
                maintenance.propietary_address = new_address
                maintenance.save()


class MaintenanceServiceReport(CompanyReport):
    __name__ = 'optical_equipment_maintenance.service'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(MaintenanceServiceReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        context['today'] = Date.today()

        return context
