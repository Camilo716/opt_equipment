from trytond.model import fields, ModelView, Workflow
from trytond.modules.company import CompanyReport
from trytond.modules.company.model import set_employee
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval, If
from trytond.exceptions import UserError
from itertools import groupby
from trytond.transaction import Transaction, without_check_access

from functools import wraps


def process_sale(moves_field):
    def _process_sale(func):
        @wraps(func)
        def wrapper(cls, shipments):
            pool = Pool()
            Sale = pool.get('sale.sale')
            transaction = Transaction()
            context = transaction.context
            with without_check_access():
                sales = set(
                    m.sale
                    for s in cls.browse(shipments)
                    for m in getattr(s, moves_field)
                    if m.sale
                )
            func(cls, shipments)
            if sales:
                with transaction.set_context(
                    queue_batch=context.get('queue_batch', True)
                ):
                    Sale.__queue__.process(sales)

        return wrapper

    return _process_sale


class Move(metaclass=PoolMeta):
    'Stock Move'
    __name__ = 'stock.move'

    return_equipment = fields.Boolean('Devolución')
    equipment = fields.Many2One(
        'optical_equipment.equipment',
        'Equipment',
        domain=[
            If(
                Eval('return_equipment', True),
                ('state', 'in', ['uncontrated', 'contrated']),
                ('state', '=', 'registred'),
            ),
            ('product', '=', Eval('product')),
        ],
        depends=['product_equipment', 'move_type'],
    )
    equipment_serial = fields.Function(
        fields.Char(
            'Serial',
            depends=['product_equipment'],
        ),
        'get_equipment_serial',
    )
    product_equipment = fields.Function(
        fields.Boolean('It Equipment'), 'get_product_equipment'
    )

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.origin.states['required'] = False

    @fields.depends('product')
    def get_product_equipment(self, product):
        if self.product.equipment:
            return True
        else:
            return False

    @fields.depends('equipment')
    def get_equipment_serial(self, equipment):
        if self.equipment:
            return self.equipment.serial
        else:
            return None

    @fields.depends('product', 'equipment', 'uom')
    def on_change_product(self):
        if not self.product:
            return

        defaultCategory = self.product.default_uom.category
        if not self.uom or self.uom.category != defaultCategory:
            self.uom = self.product.default_uom

    @fields.depends(methods=['get_equipment_serial'])
    def on_change_equipment(self):
        if self.equipment:
            self.product = self.equipment.product.id
            self.equipment_serial = self.get_equipment_serial(self.equipment)
        else:
            self.equipment_serial = None


class ShipmentOut(metaclass=PoolMeta):
    'Customer Shipment'
    __name__ = 'stock.shipment.out'

    service_maintenance_initial = fields.Boolean(
        'Maintenance Initial', states={'readonly': True}
    )
    sale_type = fields.Char('Type sale origin')

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        cls._buttons.update(
            {
                'maintenance_initial': {
                    'invisible': (
                        (Eval('service_maintenance_initial', True))
                        | (Eval('sale_type').in_(['maintenance', 'replaces']))
                    )
                }
            }
        )

    @classmethod
    def view_attributes(cls):
        return super(ShipmentOut, cls).view_attributes() + [
            (
                "//page[@name='inventory_moves']",
                'states',
                {
                    'invisible': False,
                },
            ),
        ]

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @set_employee('done_by')
    @process_sale('outgoing_moves')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')
        Locations = pool.get('stock.location')
        Equipments = pool.get('optical_equipment.equipment')
        for shipment in shipments:
            for move in shipment.inventory_moves:
                count = 0
                if not move.equipment:
                    count += 1
                    continue

                equipment = move.equipment
                Id = equipment.id
                equipment = Equipments.search(['id', '=', Id])[0]
                equipment.propietary = shipment.customer.id
                equipment.propietary_address = shipment.delivery_address.id
                equipment.location = Locations.search(
                    ['name', '=', 'Cliente'])[0].id
                equipment.state = 'uncontrated'
                equipment.shipment_destination = shipment
                equipment.sale_destination =\
                    shipment.outgoing_moves[count].origin
                equipment.propietarys += (shipment.customer,)
                equipment.maintenance_frequency = (
                    '6'
                    if shipment.customer.customer_type == 'ips'
                    else '12'
                )
                count += 1
                equipment.save()

        Move.delete([
            m for s in shipments
            for m in s.outgoing_moves
            if m.state == 'staging'
        ])

        Move.do([m for s in shipments for m in s.outgoing_moves])
        iterator = groupby(shipments, key=lambda s: s.company)
        for company, c_shipments in iterator:
            with Transaction().set_context(company=company.id):
                today = Date.today()
            cls.write(
                [s for s in c_shipments if not s.effective_date],
                {
                    'effective_date': today,
                },
            )

    @classmethod
    @ModelView.button
    def maintenance_initial(cls, shipments):
        pool = Pool()
        MaintenanceService = pool.get('optical_equipment_maintenance.service')
        Maintenance = pool.get('optical_equipment.maintenance')

        for shipment in shipments:
            serial = False
            number_equipments = 0
            maintenance_required = 0
            for move in shipment.inventory_moves:
                if move.product_equipment and move.equipment:
                    serial = True
                    number_equipments += 1
                    if move.equipment.product.maintenance_required:
                        maintenance_required += 1
                elif not move.product_equipment:
                    serial = True
                else:
                    serial = False

            if number_equipments < 1 or maintenance_required < 1:
                shipment.service_maintenance_initial = True
                shipment.save()
                break

            sale_origin = shipment.outgoing_moves[0].origin.sale
            maintenanceService = MaintenanceService.search(
                ['sale_origin', '=', sale_origin]
            )
            if maintenanceService == []:
                maintenanceService = MaintenanceService(
                    sale_date=shipment.outgoing_moves[0].origin.sale.sale_date,
                    sale_origin=shipment.outgoing_moves[0].origin.sale,
                    maintenance_type='initial',
                    propietary=shipment.customer.id,
                    propietary_address=shipment.delivery_address.id,
                    state='draft',
                )
                maintenanceService.save()
            else:
                maintenanceService = maintenanceService[0]
                maintenanceService.state = 'draft'
                maintenanceService.save()

            if not serial:
                error = 'Por favor Primero debe Asignar'
                + 'un serial a todos los Equipos.'
                raise UserError(str(error))

            for move in shipment.inventory_moves:
                valid = \
                    move.product_equipment \
                    and move.equipment \
                    and move.equipment.product.template.maintenance_required

                if (not valid):
                    continue

                template = move.equipment.product.template
                maintenance = Maintenance(
                    service_maintenance=maintenanceService.id,
                    maintenance_type='initial',
                    propietary=shipment.customer.id,
                    equipment_calibrate=(
                        True if move.equipment.product.calibration else False
                    ),
                    propietary_address=shipment.delivery_address.id,
                    equipment=move.equipment.id,
                    initial_operation=move.equipment.product.initial_operation,
                    check_equipment=template.check_equipment,
                    check_electric_system=template.check_electric_system,
                    clean_int_ext=template.clean_int_ext,
                    clean_eyes=template.clean_eyes,
                    check_calibration=template.check_calibration,
                    temperature_min=maintenanceService.temperature_min,
                    temperature_max=maintenanceService.temperature_max,
                    temperature_uom=maintenanceService.temperature_uom.id,
                    moisture_min=maintenanceService.moisture_min,
                    moisture_max=maintenanceService.moisture_max,
                    moisture_uom=maintenanceService.moisture_uom.id,
                )
                maintenance.save()

            shipment.service_maintenance_initial = True
            shipment.save()


class ShipmentInternal(metaclass=PoolMeta):
    'Shipment Interncal'
    __name__ = 'stock.shipment.internal'

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    @set_employee('done_by')
    def done(cls, shipments):
        pool = Pool()
        Move = pool.get('stock.move')
        Date = pool.get('ir.date')

        for shipment in shipments:
            for move in shipment.moves:
                if move.equipment:
                    move.equipment.location = shipment.to_location
                    move.equipment.save()

        Move.do([m for s in shipments for m in s.incoming_moves])
        cls.write(
            [s for s in shipments if not s.effective_date],
            {
                'effective_date': Date.today(),
            },
        )


class ShipmentOutReturn(metaclass=PoolMeta):
    'Customer Shipment Return'
    __name__ = 'stock.shipment.out.return'

    service_maintenance_initial = fields.Boolean(
        'Maintenance Initial', states={'readonly': True}
    )
    sale_type = fields.Char('Type sale origin')

    @classmethod
    @ModelView.button
    @Workflow.transition('received')
    @set_employee('received_by')
    def receive(cls, shipments):
        Move = Pool().get('stock.move')
        Equipments = Pool().get('optical_equipment.equipment')
        Move.do([m for s in shipments for m in s.incoming_moves])
        for s in shipments:
            for m in s.incoming_moves:
                if not m.equipment:
                    continue

                equipment = m.equipment
                Id = equipment.id
                equipment = Equipments.search(['id', '=', Id])[0]
                equipment.propietary = s.company.party.id
                equipment.propietary_address = s.company.party.addresses[0].id
                equipment.location = m.to_location.id
                equipment.state = 'registred'
                equipment.save()

        cls.create_inventory_moves(shipments)
        # Set received state to allow done transition
        cls.write(shipments, {'state': 'received'})
        to_do = [
            s for s in shipments if s.warehouse_storage == s.warehouse_input]

        if to_do:
            cls.done(to_do)


class PickingListDeliveryReport(CompanyReport):
    __name__ = 'stock.shipment.out.picking_list1'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(PickingListDeliveryReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        context['today'] = Date.today()

        return context


class CapacitationReport(CompanyReport):
    __name__ = 'stock.shipment.out.capacitation_note'

    @classmethod
    def execute(cls, ids, data):
        with Transaction().set_context(address_with_party=True):
            return super(CapacitationReport, cls).execute(ids, data)

    @classmethod
    def get_context(cls, records, header, data):
        pool = Pool()
        Date = pool.get('ir.date')
        context = super().get_context(records, header, data)
        context['today'] = Date.today()

        return context
