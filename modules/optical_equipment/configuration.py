from trytond.model import (
    ModelSingleton, ModelSQL, ModelView, fields)
from trytond.pyson import Id, Eval


class Configuration(ModelSingleton, ModelSQL, ModelView):
    'Equipment Configuration'
    __name__ = 'optical_equipment.configuration'

    technician_responsible = fields.Many2One(
        'company.employee', "Technician Responsible")
    invima = fields.Char('Invima', states={
        'required': Eval('technician_responsible', True)
    })
    technician_signature = fields.Binary('Technician Signature')
    equipment_sequence = fields.Many2One(
        'ir.sequence', "Equipment Sequence", domain=[
            ('sequence_type', '=',
             Id('optical_equipment', 'sequence_type_equipment'))])
    maintenance_sequence = fields.Many2One(
        'ir.sequence', "Maintenance Sequence",
        domain=[('sequence_type', '=',
                 Id('optical_equipment', 'sequence_type_maintenances'))])
    agended_sequence = fields.Many2One(
        'ir.sequence', "Agended Sequence",
        domain=[('sequence_type', '=',
                 Id('optical_equipment', 'sequence_type_agended'))])
    contract_sequence = fields.Many2One(
        'ir.sequence', "Contract Sequence", domain=[
            ('sequence_type', '=',
             Id('optical_equipment', 'sequence_type_contract'))])
    temperature_min = fields.Float("Temp Min")
    temperature_max = fields.Float("Temp Max")
    temperature_uom = fields.Many2One(
        'product.uom', 'Temperature UOM',
        domain=[
            ('category', '=', Id(
                'optical_equipment', "uom_cat_temperature"))],
        depends={'itemperature_min'})
    moisture_min = fields.Float("Moisture Min")
    moisture_max = fields.Float("Moisture Max")
    moisture_uom = fields.Many2One(
        'product.uom', "Moisture UOM",
        domain=[
            ('category', '=', Id(
                'optical_equipment', 'uom_cat_relative_humedity'))],
        depends={'moisture_min'})
    sale_quote_number = fields.Many2One('ir.sequence', "Sale Quote Number",
                                        domain=[
                                            ('sequence_type', '=', Id(
                                                'sale', 'sequence_type_sale'))
                                        ])
