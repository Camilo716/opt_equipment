# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval, If

#from . import equipment

_CUSTOMER_TYPE = [('ips', 'IPS'),
                ('optica', 'Optica'),
                ('otro', 'Otro')]

class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    customer_type = fields.Selection(_CUSTOMER_TYPE, "Customer Type")

    
class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    campus = fields.Boolean("Campus")
    party_related = fields.Many2One('party.party', "Party Related",
                                    states ={ 'invisible': (~Eval("campus"))})
