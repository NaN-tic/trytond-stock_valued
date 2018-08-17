# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import Pool, PoolMeta

__all__ = ['Configuration']


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    valued_sale_line = fields.Boolean('Use Valued Sale Line',
        help='If marked valued shipment take amount from sale lines, not '
            'outgoing move shipment')
