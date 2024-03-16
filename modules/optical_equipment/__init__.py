# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import (agended, balance_sale_party, calibration, configuration,
               contract, company, diary, equipment, party, product,
               maintenance, move, purchase, sale)

__all__ = ['register']


def register():
    Pool.register(
        company.Employee,
        equipment.OpticalEquipment,
        equipment.EquipmentParty,
        contract.Contract,
        contract.ContractMaintenanceServices,
        equipment.EquipmentContract,
        equipment.EquipmentMaintenance,
        equipment.ChangePropietary,
        equipment.ChangeEquipment,
        agended.AgendedInitial,
        agended.ReAgended,
        agended.ServiceMaintenanceAgended,
        calibration.Calibration,
        calibration.CalibrationSample,
        configuration.Configuration,
        diary.Diary,
        contract.Cron,
        contract.ContractEquipment,
        contract.CreateContractInitial,
        party.Address,
        party.Party,
        product.Template,
        product.Product,
        product.Pattern,
        product.UsePattern,
        product.Image,
        purchase.Purchase,
        purchase.Line,
        sale.Sale,
        sale.SaleDate,
        sale.SaleLine,
        balance_sale_party.BalanceSalePartyStart,
        maintenance.MaintenanceService,
        maintenance.MaintenanceServiceLine,
        maintenance.MaintenanceLine,
        maintenance.MaintenanceActivity,
        maintenance.ChangePropietaryMaintenance,
        move.Move,
        move.ShipmentOut,
        move.ShipmentInternal,
        move.ShipmentOutReturn,
        balance_sale_party.BalanceSalePartyStart,
        module='optical_equipment', type_='model'
    )
    Pool.register(
        agended.AssingAgended,
        agended.ReAssingAgended,
        contract.CreateContract,
        equipment.NewPropietary,
        maintenance.NewPropietaryMaintenance,
        balance_sale_party.PrintBalanceSaleParty,
        sale.ConfirmSaleDate,
        module='optical_equipment', type_='wizard')
    Pool.register(
        calibration.CalibrationReport,
        contract.ContractReport,
        equipment.EquipmentReport,
        maintenance.MaintenanceServiceReport,
        move.PickingListDeliveryReport,
        move.CapacitationReport,
        balance_sale_party.BalanceSaleParty,
        module='optical_equipment', type_='report')
