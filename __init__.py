# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import move
from . import shipment


def register():
    Pool.register(
        move.Move,
        shipment.ShipmentIn,
        shipment.ShipmentOut,
        module='stock_valued', type_='model')
