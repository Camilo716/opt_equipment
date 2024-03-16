from trytond.pool import PoolMeta
from trytond.model import fields


class Employee(metaclass=PoolMeta):
    'Company'
    __name__ = 'company.employee'

    invima = fields.Char('Invima')
