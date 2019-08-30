# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Configuration']


class Configuration(metaclass=PoolMeta):
    __name__ = 'stock.configuration'

    valued_origin = fields.Boolean('Use Valued origin',
        help='If marked valued shipment take amount from origin, not '
            'from the move')

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)

        # Migration from 5.2: rename reference into valued_sale_line
        if (table.column_exist('valued_sale_line')):
            table.column_rename('valued_sale_line', 'valued_origin')

        super(Configuration, cls).__register__(module_name)
