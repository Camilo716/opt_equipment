from trytond.model import (
    ModelSQL, ModelView, fields)


class Diary(ModelSQL, ModelView):
    'Diary'
    __name__ = 'optical_equipment_maintenance.diary'
    _rec_name = 'code'

    code = fields.Char("Code", states={'readonly': True})
    date_expected = fields.DateTime("Expected Date", required=True)
    date_estimated = fields.DateTime("Estimated Date")
    date_end = fields.DateTime("Date End")
    maintenance_service = fields.Many2One(
        'optical_equipment_maintenance.service', 'Maintenance Service',
        required=True)
    technical = fields.Many2One('company.employee', "Technical", required=True)
    state = fields.Selection([('draft', "Draft"),
                              ('agended', "Agended"),
                              ('in_progress', "In Progress"),
                              ('failed', "Failed"),
                              ('finished', "Finished")
                              ], "State",
                             required=True, readonly=True, sort=True)

    @classmethod
    def default_state(self):
        return 'draft'
