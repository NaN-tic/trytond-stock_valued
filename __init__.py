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
    Pool.register(
        move.MoveDiscountFormula,
        depends=['discount_formula'],
        module='stock_valued', type_='model')
    Pool.register(
        purchase.PurchaseLineDiscountFormula,
        depends=['discount_formula', 'purchase_discount'],
        module='stock_valued', type_='model')
    Pool.register(
        sale.SaleLineDiscountFormula,
        depends=['discount_formula', 'sale_discount'],
        module='stock_valued', type_='model')
