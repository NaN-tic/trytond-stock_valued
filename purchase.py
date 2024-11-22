# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import PoolMeta


class PurchaseLineDiscount(metaclass=PoolMeta):
    __name__ = 'purchase.line'

    def get_move(self, move_type):
        move = super().get_move(move_type)
        if move:
            move.base_price = self.base_price
        return move
