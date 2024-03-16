# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import (
    Workflow, ModelSQL, ModelView, fields, sequence_ordered)
from trytond.pyson import Bool, Eval, If, Id, Equal
from trytond.pool import Pool
from trytond.modules.company import CompanyReport
from trytond.transaction import Transaction

_digits = (16, 2)
_states = {'readonly': If(Eval('state') != 'draft', True)}


class Calibration(ModelSQL, ModelView):
    'Calibration of Maintenance'
    __name__ = 'optical_equipment.maintenance.calibration'

    _states = {'readonly': True}

    maintenance = fields.Many2One('optical_equipment.maintenance', "Maintenance", ondelete="CASCADE",
                                  required=True)
    graph_dates = fields.Char("Graph Dates", readonly=True)
    diopter = fields.Float("Diopter", states=_states)
    mean = fields.Float("Mean", states=_states)
    dev_std = fields.Float("Standart Desviation", states=_states)
    uncertain_type_A = fields.Float("Uncertain Type A", states=_states)
    uncertain_pattern = fields.Float("Uncertain Pattern", states=_states)
    k_c_calibration = fields.Float("K Crt Calibration", states=_states)
    uncertain_U_b1 = fields.Float("U_b1", states=_states)
    d_resolution = fields.Float("d_resolution", states=_states)
    uncertain_U_b2_dig = fields.Float("U_b2", states=_states)
    uncertain_U_b2_ana = fields.Float("U_b2", states=_states)
    uncertain_combinated = fields.Float("U_combinated", states=_states)
    uncertain_eff = fields.Float("U eff", states=_states)
    t_student = fields.Float("T Student", states=_states)

    uncertain_expanded = fields.Float("Uexpand", _digits, states=_states)

    state = fields.Char('State')


class CalibrationSample(sequence_ordered(), ModelView, ModelSQL):
    'Samples of Calibration'
    __name__ = 'optical_equipment.maintenance.calibration_sample'

    maintenance = fields.Many2One('optical_equipment.maintenance', 'Maintenance')
    product = fields.Function(fields.Integer("Product ID"), 'on_change_with_product')
    number_sample = fields.Float("Sample #", _digits)
    value_patterns = fields.Many2One('optical_equipment.product_pattern', "Value Pattern", ondelete='RESTRICT', required=True,
                                     domain=[('product', '=', Eval('product'))],
                                     depends=['product'])
    value_equipment = fields.Float("Value in Equipment", _digits, required=True,
                                   states={'readonly': Eval('value_patterns') is None})
    mistake = fields.Float("Mistake", _digits)
    mistake_rate = fields.Float("% Mistake", _digits,
                                states={'readonly': True},
                                depends=['mistake'])

    @fields.depends('maintenance', '_parent_maintenance.equipment')
    def on_change_with_product(self, name=None):
        if self.maintenance:
            return self.maintenance.equipment.product.template.id

    @fields.depends('value_patterns', 'value_equipment',
                    'mistake', 'mistake_rate')
    def on_change_value_equipment(self):
        if float(self.value_patterns.pattern) < 0:
            self.mistake = self.value_patterns.pattern - self.value_equipment
        else:
            if self.value_patterns.pattern > self.value_equipment:
                self.mistake = self.value_patterns.pattern - self.value_equipment
            else:
                self.mistake = -self.value_patterns.pattern + self.value_equipment

        if self.value_patterns.pattern == self.value_equipment:
            self.mistake_rate = 0
        else:
            self.mistake_rate = abs(self.mistake / self.value_patterns.pattern) * 100


class CalibrationReport(CompanyReport):
    __name__ = 'optical_equipment.maintenance'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(CalibrationReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        context['today'] = Date.today()

        return context
