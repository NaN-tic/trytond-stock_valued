# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.modules.account.tax import TaxableMixin

__all__ = ['ShipmentIn', 'ShipmentOut']

MOVES = {
    'stock.shipment.in': 'incoming_moves',
    'stock.shipment.in.return': 'moves',
    'stock.shipment.out': 'outgoing_moves',
    'stock.shipment.out.return': 'incoming_moves',
    }


class ShipmentValuedMixin(TaxableMixin):
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

    @property
    def valued_moves(self):
        return getattr(self, MOVES.get(self.__name__), [])

    @property
    def taxable_lines(self):
        taxable_lines = []
        # In case we're called from an on_change we have to use some sensible
        # defaults
        for move in self.valued_moves:
            if move.state == 'cancelled':
                continue
            taxable_lines.append(tuple())
            for attribute, default_value in [
                    ('taxes', []),
                    ('unit_price', Decimal(0)),
                    ('quantity', 0.),
                    ]:
                value = getattr(move, attribute, None)
                taxable_lines[-1] += (
                    value if value is not None else default_value,)
        return taxable_lines

    def calc_amounts(self):
        untaxed_amount = sum((m.untaxed_amount for m in self.valued_moves),
            Decimal(0))
        taxes = self._get_taxes()
        untaxed_amount = self.company.currency.round(untaxed_amount)
        tax_amount = sum((self.company.currency.round(tax['amount'])
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
    __metaclass__ = PoolMeta

    @classmethod
    def create(cls, shipments):
        shipments = super(ShipmentIn, cls).create(shipments)
        to_write = []
        for shipment in shipments:
            to_write.extend(([shipment], shipment.calc_amounts()))
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
    __metaclass__ = PoolMeta

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
