# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta


class SaleLineDiscount(metaclass=PoolMeta):
    __name__ = 'sale.line'

    def get_move(self, shipment_type):
        move = super().get_move(shipment_type)
        if move:
            move.base_price = self.base_price
        return move
