# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond import backend
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.modules.account.tax import TaxableMixin
from trytond.modules.currency.fields import Monetary

__all__ = ['ShipmentIn', 'ShipmentOut', 'ShipmentOutReturn']

MOVES = {
    'stock.shipment.in': 'incoming_moves',
    'stock.shipment.in.return': 'moves',
    'stock.shipment.out': 'outgoing_moves',
    'stock.shipment.out.return': 'incoming_moves',
    }
TAX_TYPE = {
    'stock.shipment.in': 'invoice',
    'stock.shipment.in.return': 'credit_note',
    'stock.shipment.out': 'invoice',
    'stock.shipment.out.return': 'credit_note',
    }
_ZERO = Decimal('0.0')


class ShipmentValuedMixin(TaxableMixin):
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'on_change_with_currency')
    untaxed_amount_cache = Monetary('Untaxed Cache',
        digits='currency', currency='currency', readonly=True)
    tax_amount_cache = Monetary('Tax Cache',
        digits='currency', currency='currency', readonly=True)
    total_amount_cache = Monetary('Total Cache',
        digits='currency', currency='currency', readonly=True)
    untaxed_amount = fields.Function(Monetary('Untaxed',
        digits='currency', currency='currency'), 'get_amounts')
    tax_amount = fields.Function(Monetary('Tax',
        digits='currency', currency='currency'), 'get_amounts')
    total_amount = fields.Function(Monetary('Total',
        digits='currency', currency='currency'), 'get_amounts')

    @fields.depends('company')
    def on_change_with_currency(self, name=None):
        currency_id = None
        if self.valued_moves:
            for move in self.valued_moves:
                if move.currency:
                    currency_id = move.currency.id
                    break
        if currency_id is None and self.company:
            currency_id = self.company.currency.id
        return currency_id

    @property
    def valued_moves(self):
        Move = Pool().get('stock.move')

        origins = Move._get_origin()
        keep_origin = True if 'stock.move' in origins else False
        move_field = MOVES.get(self.__name__)
        if (
            (keep_origin and self.__name__ == 'stock.shipment.out')
            and (moves := getattr(self, 'outgoing_moves', []))
        ):
            return moves
        return getattr(self, move_field, [])

    @property
    def tax_type(self):
        return TAX_TYPE.get(self.__name__)

    @property
    def taxable_lines(self):
        pool = Pool()
        Config = pool.get('stock.configuration')
        Move = pool.get('stock.move')

        config = Config(1)
        valued_origin = config.valued_origin

        taxable_lines = []
        for move in self.valued_moves:
            if move.state == 'cancelled':
                continue

            origin = move.origin
            if isinstance(origin, Move):
                origin = origin.origin
            if valued_origin and hasattr(origin, 'unit_price'):
                if origin.unit_price is not None:
                    unit_price = origin.unit_price
                elif move.unit_price is not None:
                    unit_price = move.unit_price
                else:
                    unit_price = origin.product.list_price or _ZERO
            else:
                unit_price = move.unit_price or move.unit_price or _ZERO

            taxable_lines.append((
                    getattr(move, 'taxes', None) or [],
                    unit_price,
                    getattr(move, 'quantity', None) or 0,
                    None,
                    ))
        return taxable_lines

    def calc_amounts(self):
        untaxed_amount = sum((m.amount for m in self.valued_moves if m.amount),
            Decimal(0))
        taxes = self._get_taxes()
        untaxed_amount = self.company.currency.round(untaxed_amount)
        tax_amount = sum((self.company.currency.round(tax['amount'])
                for tax in taxes.values()), Decimal(0))
        return {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount if untaxed_amount else Decimal(0),
            'total_amount': (untaxed_amount + tax_amount
                if untaxed_amount else Decimal(0)),
            }

    @classmethod
    def get_amounts(cls, shipments, names):
        untaxed_amount = dict((i.id, Decimal(0)) for i in shipments)
        tax_amount = dict((i.id, Decimal(0)) for i in shipments)
        total_amount = dict((i.id, Decimal(0)) for i in shipments)

        for shipment in shipments:
            if (shipment.state in cls._states_valued_cached
                    and shipment.untaxed_amount_cache is not None
                    and shipment.tax_amount_cache is not None
                    and shipment.total_amount_cache is not None):
                untaxed_amount[shipment.id] = shipment.untaxed_amount_cache
                tax_amount[shipment.id] = shipment.tax_amount_cache
                total_amount[shipment.id] = shipment.total_amount_cache
            else:
                res = shipment.calc_amounts()
                untaxed_amount[shipment.id] = res['untaxed_amount']
                tax_amount[shipment.id] = res['tax_amount']
                total_amount[shipment.id] = res['total_amount']
        result = {
            'untaxed_amount': untaxed_amount,
            'tax_amount': tax_amount,
            'total_amount': total_amount,
            }
        for key in list(result.keys()):
            if key not in names:
                del result[key]
        return result

    @classmethod
    def store_cache(cls, shipments):
        for shipment in shipments:
            shipment.untaxed_amount_cache = shipment.untaxed_amount
            shipment.tax_amount_cache = shipment.tax_amount
            shipment.total_amount_cache = shipment.total_amount
        cls.save(shipments)

    @classmethod
    def reset_cache(cls, shipments):
        for shipment in shipments:
            shipment.untaxed_amount_cache = None
            shipment.tax_amount_cache = None
            shipment.total_amount_cache = None
        cls.save(shipments)


class ShipmentIn(ShipmentValuedMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.in'

    @classmethod
    def __setup__(cls):
        super(ShipmentIn, cls).__setup__()
        # The states where amounts are cached
        cls._states_valued_cached = ['done', 'cancelled']

    @classmethod
    def __register__(cls, module_name):
        table = backend.TableHandler(cls, module_name)

        if table.column_exist('untaxed_amount'):
            table.column_rename('untaxed_amount', 'untaxed_amount_cache')
            table.column_rename('tax_amount', 'tax_amount_cache')
            table.column_rename('total_amount', 'total_amount_cache')

        super(ShipmentIn, cls).__register__(module_name)

    @classmethod
    def cancel(cls, shipments):
        super(ShipmentIn, cls).cancel(shipments)
        cls.store_cache(shipments)

    @classmethod
    def done(cls, shipments):
        super(ShipmentIn, cls).done(shipments)
        cls.store_cache(shipments)


class ShipmentOut(ShipmentValuedMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out'

    @classmethod
    def __setup__(cls):
        super(ShipmentOut, cls).__setup__()
        # The states where amounts are cached
        cls._states_valued_cached = ['done', 'cancelled']

    @classmethod
    def __register__(cls, module_name):
        table = backend.TableHandler(cls, module_name)

        if table.column_exist('untaxed_amount'):
            table.column_rename('untaxed_amount', 'untaxed_amount_cache')
            table.column_rename('tax_amount', 'tax_amount_cache')
            table.column_rename('total_amount', 'total_amount_cache')

        super(ShipmentOut, cls).__register__(module_name)

    @classmethod
    def cancel(cls, shipments):
        super(ShipmentOut, cls).cancel(shipments)
        cls.store_cache(shipments)

    @classmethod
    def done(cls, shipments):
        super(ShipmentOut, cls).done(shipments)
        cls.store_cache(shipments)


class ShipmentOutReturn(ShipmentValuedMixin, metaclass=PoolMeta):
    __name__ = 'stock.shipment.out.return'

    @classmethod
    def __setup__(cls):
        super(ShipmentOutReturn, cls).__setup__()
        # The states where amounts are cached
        cls._states_valued_cached = ['done', 'cancelled']

    @classmethod
    def cancel(cls, shipments):
        super(ShipmentOutReturn, cls).cancel(shipments)
        cls.store_cache(shipments)

    @classmethod
    def done(cls, shipments):
        super(ShipmentOutReturn, cls).done(shipments)
        cls.store_cache(shipments)
