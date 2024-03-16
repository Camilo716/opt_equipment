# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import ModelView, fields
from trytond.wizard import Wizard, StateView, Button, StateReport
from trytond.report import Report
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval
from trytond.exceptions import UserError

__all__ = ['BalanceSalePartyStart',
    'PrintBalanceSaleParty', 'BalanceSaleParty']


class BalanceSalePartyStart(ModelView):
    'Balance Party Start'
    __name__ = 'optical_equipment.print_balance_sale_party.start'

    party = fields.Many2One('party.party', 'Party', required=True)
    start_period = fields.Many2One(
        'account.period',
        'Start Period',
        domain=[
            ('start_date', '<=', (Eval('end_period'), 'start_date')),
        ],
        depends=['fiscalyear', 'end_period'],
    )
    end_period = fields.Many2One(
        'account.period',
        'End Period',
        domain=[('start_date', '>=', (Eval('start_period'), 'start_date'))],
        depends=['start_period'],
    )
    company = fields.Many2One('company.company', 'Company', required=True)
    party_type = fields.Selection(
        [('out', 'Customer')], 'Party Type', required=True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_party_type():
        return 'out'


class PrintBalanceSaleParty(Wizard):
    'Print Balance Sale Party'
    __name__ = 'optical_equipment.print_balance_sale_party'

    start = StateView(
        'optical_equipment.print_balance_sale_party.start',
        'optical_equipment.print_balance_sale_party_start_view_form',
        [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Print', 'print_', 'tryton-print', default=True),
        ],
    )

    print_ = StateReport('optical_equipment.balance_sale_party')

    def default_start(self, fields):
        if len(self.records) > 0:
            default = {'party': self.records[0].party.id}
        else:
            default = {'party': None}
        return default

    def do_print_(self, action):
        party = None
        party_type = None

        if self.start.party:
            party = self.start.party.id
        if self.start.party_type:
            party_type = self.start.party_type

        data = {
            'company': self.start.company.id,
            'party': party,
            'party_type': party_type,
            'start_period': (
                self.start.start_period.id if self.start.start_period else None
            ),
            'end_period':
                self.start.end_period.id if self.start.end_period else None,
        }
        return action, data

    def transition_print_(self):
        return 'end'


class BalanceSaleParty(Report):
    __name__ = 'optical_equipment.balance_sale_party'

    @classmethod
    def get_context(cls, records, header, data):
        report_context = super(BalanceSaleParty, cls).get_context(
            records, header, data)
        pool = Pool()
        Company = pool.get('company.company')
        Period = pool.get('account.period')
        Sale = pool.get('sale.sale')
        Party = pool.get('party.party')
        start_period = None
        end_period = None
        party = None
        company = Company(data['company'])
        dom_sale = [('state', 'in', ['processing', 'done'])]

        if data.get('party'):
            party = data['party']
            dom_sale.append(('party', '=', party))

        if data.get('start_period'):
            start_period = Period(data['start_period'])
            dom_sale.append(('sale_date', '>=', start_period.start_date))
        if data.get('end_period'):
            end_period = Period(data['end_period'])
            dom_sale.append(('sale_date', '<=', end_period.start_date))

        sales = Sale.search(
            dom_sale,
            order=[('sale_date', 'DESC'), ('id', 'DESC')],
        )

        res = {}

        id_ = party
        party_ = Party.search(['id', '=', party])[0]
        name = party_.rec_name

        try:
            if party_.identifiers:
                id_number = party_.identifiers[0].code
            else:
                id_number = ''
        except IndexError:
            pass

        res[id_] = {'name': name, 'id_number': id_number, 'party': party_}

        if (not sales):
            err = 'Este Tercero no Cuenta Con Ventas en Proceso ó Confirmadas.'
            raise UserError(str(err))

        res[id_]['sales'] = sales

        report_context['records'] = res.values()
        report_context['start_period'] =\
            start_period.name if start_period else '*'
        report_context['end_period'] = end_period.name if end_period else '*'
        report_context['company'] = company

        residual_amount = 0
        for sale in sales:
            residual_amount += sale.residual_amount
        report_context['residual_amount'] = residual_amount

        return report_context
