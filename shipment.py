# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from copy import copy
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = ['ShipmentIn', 'ShipmentOut']
__metaclass__ = PoolMeta


class ShipmentValuedMixin:
    currency = fields.Function(fields.Many2One('currency.currency',
            'Currency'),
        'on_change_with_currency')
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    untaxed_amount = fields.Numeric('Untaxed',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    tax_amount = fields.Numeric('Tax',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    total_amount = fields.Numeric('Total',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits'])
    untaxed_amount_func = fields.Function(fields.Numeric('Untaxed',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits']), 'get_amounts')
    tax_amount_func = fields.Function(fields.Numeric('Tax',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits']), 'get_amounts')
    total_amount_func = fields.Function(fields.Numeric('Total',
        digits=(16, Eval('currency_digits', 2)),
        readonly=True,
        depends=['currency_digits']), 'get_amounts')

    def get_moves2amount(self):
        return {
            'stock.shipment.in': 'incoming_moves',
            'stock.shipment.in.return': 'moves',
            'stock.shipment.out': 'outgoing_moves',
            'stock.shipment.out.return': 'incoming_moves',
            }

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        if self.company:
            return self.company.currency.id
        return None

    @fields.depends('company')
    def on_change_with_currency_digits(self, name=None):
        if self.company:
            return self.company.currency.digits
        return 2

    def calc_amounts(self):
        Currency = Pool().get('currency.currency')
        Date = Pool().get('ir.date')
        untaxed_amount = Decimal(0)
        taxes = {}
        moves2amount = self.get_moves2amount()
        for move in getattr(self, moves2amount.get(self.__name__)):
            if move.state == 'cancelled':
                continue
            if move.currency and move.currency != self.company.currency:
                # convert wrt currency
                date = self.effective_date or Date.today()
                with Transaction().set_context(date=date):
                    untaxed_amount += Currency.compute(move.currency,
                        move.untaxed_amount, self.company.currency,
                        round=False)
                    for key, value in move._taxes_amount().items():
                        value = Currency.compute(move.currency, value,
                            self.company.currency, round=False)
                        taxes[key] = taxes.get(key, Decimal(0)) + value
            else:
                untaxed_amount += move.untaxed_amount
                for key, value in move._taxes_amount().items():
                    taxes[key] = taxes.get(key, Decimal(0)) + value

        untaxed_amount = self.company.currency.round(untaxed_amount)
        tax_amount = sum((self.company.currency.round(tax)
                for tax in taxes.values()), Decimal(0))
        return {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount,
            'total_amount': untaxed_amount + tax_amount,
            }

    @classmethod
    def get_amounts(cls, shipments, names):
        untaxed_amount = dict((i.id, Decimal(0)) for i in shipments)
        tax_amount = dict((i.id, Decimal(0)) for i in shipments)
        total_amount = dict((i.id, Decimal(0)) for i in shipments)

        for shipment in shipments:
            if shipment.untaxed_amount:
                untaxed_amount[shipment.id] = shipment.untaxed_amount
                tax_amount[shipment.id] = shipment.tax_amount
                total_amount[shipment.id] = shipment.total_amount
            else:
                res = shipment.calc_amounts()
                untaxed_amount[shipment.id] = res['untaxed_amount']
                tax_amount[shipment.id] = res['tax_amount']
                total_amount[shipment.id] = res['total_amount']
        result = {
            'untaxed_amount_func': untaxed_amount,
            'tax_amount_func': tax_amount,
            'total_amount_func': total_amount,
            }
        for key in result.keys():
            if key not in names:
                del result[key]
        return result


class ShipmentIn(ShipmentValuedMixin):
    __name__ = 'stock.shipment.in'

    @classmethod
    def create(cls, shipments):
        shipments = super(ShipmentIn, cls).create(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
        if to_write:
            cls.write(*to_write)
        return shipments

    @classmethod
    def write(cls, *args):
        actions = iter(args)
        to_update = []
        for shipments, values in zip(actions, actions):
            if set(values) & set(['incoming_moves']):
                to_update.extend(shipments)
        super(ShipmentIn, cls).write(*args)
        to_write = []
        for shipment in to_update:
            values = shipment.calc_amounts()
            to_write.extend(([shipment], values))
        if to_write:
            cls.write(*to_write)

    @classmethod
    def receive(cls, shipments):
        super(ShipmentIn, cls).receive(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
        cls.write(*to_write)

    @classmethod
    def done(cls, shipments):
        super(ShipmentIn, cls).done(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
        cls.write(*to_write)


class ShipmentOut(ShipmentValuedMixin):
    __name__ = 'stock.shipment.out'

    @classmethod
    def wait(cls, shipments):
        super(ShipmentOut, cls).wait(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
        cls.write(*to_write)

    @classmethod
    def assign(cls, shipments):
        super(ShipmentOut, cls).assign(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
        cls.write(*to_write)

    @classmethod
    def pack(cls, shipments):
        super(ShipmentOut, cls).pack(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
        cls.write(*to_write)

    @classmethod
    def done(cls, shipments):
        super(ShipmentOut, cls).done(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
        cls.write(*to_write)
