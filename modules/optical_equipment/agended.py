# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import ModelSQL, ModelView, fields
from trytond.wizard import (
    Button, StateAction, StateTransition, StateView, Wizard)
from trytond.pool import Pool
from trytond.exceptions import UserError

import datetime
from datetime import timedelta


class AgendedInitial(ModelView):
    'Agended maintenance service'
    __name__ = 'optical_equipment_maintenance.agended'

    maintenance_service = fields.Many2One('optical_equipment_maintenance.service',"Maintenaince Service",
                                          required=True, domain=[('state', '=', 'draft')])
    estimated_agended = fields.DateTime("Date Maintenance", required=True)
    technical = fields.Many2One('company.employee', "Technical", required=True)

    
class AssingAgended(Wizard):
    'Assing Agended'
    __name__ = 'optical_equipment_maintenance.assing_agended'

    start = StateView('optical_equipment_maintenance.agended',
                      'optical_equipment.assing_agended_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Assing', 'assing_agended', 'tryton-ok', default=True),
                      ])

    assing_agended = StateAction('optical_equipment.act_maintenance_service_form')


    def default_start(self, fields):
        if len(self.records) > 0: 
            default = {'maintenance_service': self.records[0].id}
        else:
            default = {'maintenance_service': None}
        return default
    
    def do_assing_agended(self, action):
        pool = Pool()
        Diary = pool.get('optical_equipment_maintenance.diary')
        Config = pool.get('optical_equipment.configuration')
        config = Config(3)
        
        MaintenanceService = pool.get('optical_equipment_maintenance.service')
        diary = Diary(code=config.agended_sequence.get(),
                      maintenance_service=self.start.maintenance_service,
                      date_expected=self.start.estimated_agended,
                      date_estimated=self.start.estimated_agended + timedelta(days=15),
                      date_end=self.start.estimated_agended + timedelta(days=15),
                      technical=self.start.technical.id,
                      state='agended')
        diary.save()

        maintenanceService = self.start.maintenance_service
        maintenanceService.estimated_agended = self.start.estimated_agended
        maintenanceService.technical = self.start.technical
        maintenanceService.state_agended = 'agended'
        maintenanceService.state = 'agended'
        maintenanceService.current_agended = diary.id
        maintenanceService.history_agended += (diary.id,)
        maintenanceService.set_code(maintenanceService)
        maintenanceService.save()
        
        
class ReAgended(ModelView):
    'Agended maintenance service'
    __name__ = 'optical_equipment_maintenance.reagended'

    maintenance_service = fields.Many2One('optical_equipment_maintenance.service',"Maintenaince Service",
                                          required=True, domain=[('state', '=', 'failed')])
    estimated_agended = fields.DateTime("Date Maintenance", required=True)
    technical = fields.Many2One('company.employee', "Technical", required=True)

    
class ReAssingAgended(Wizard):
    'Assing Agended'
    __name__ = 'optical_equipment_maintenance.reassing_agended'

    start = StateView('optical_equipment_maintenance.reagended',
                      'optical_equipment.reassing_agended_view_form', [
                          Button('Cancel', 'end', 'tryton-cancel'),
                          Button('Assing', 'assing_agended', 'tryton-ok', default=True),
                      ])

    assing_agended = StateAction('optical_equipment.act_maintenance_service_form')

    def default_start(self, fields):
        if len(self.records) > 0: 
            default = {'maintenance_service': self.records[0].id}
        else:
            default = {'maintenance_service': None}
        return default

    def do_assing_agended(self, action):
        pool = Pool()
        Diary = pool.get('optical_equipment_maintenance.diary')
        
        diary = Diary(maintenance_service=self.start.maintenance_service,
                      date_expected=self.start.estimated_agended,
                      date_estimated=self.start.estimated_agended + timedelta(days=15),
                      date_end=self.start.estimated_agended + timedelta(days=15),
                      technical=self.start.technical.id,
                      state='agended')
        diary.save()

        maintenanceService = self.start.maintenance_service
        maintenanceService.estimated_agended = self.start.estimated_agended
        maintenanceService.technical = self.start.technical
        maintenanceService.state_agended = 'agended'
        maintenanceService.state = 'agended'
        maintenanceService.history_agended += (diary.id,)
        maintenanceService.save()


class ServiceMaintenanceAgended(ModelSQL):
    'Service Maintenance - Agended'
    __name__ = 'optical_equipment_maintenance.service-maintenance.diary'

    maintenance_service = fields.Many2One('optical_equipment_maintenance.service', "Maintenance Service")
    agended = fields.Many2One('optical_equipment_maintenance.diary', "Agended")
