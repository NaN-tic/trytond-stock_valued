# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from . import move
from . import shipment
from . import sale
from . import purchase

def register():
    Pool.register(
        move.Move,
        shipment.ShipmentIn,
        shipment.ShipmentOut,
        shipment.ShipmentOutReturn,
        module='stock_valued', type_='model')
    Pool.register(
        sale.SaleLineDiscount,
        depends=['sale_discount'],
        module='stock_valued', type_='model')
    Pool.register(
        purchase.PurchaseLineDiscount,
        depends=['purchase_discount'],
        module='stock_valued', type_='model')
