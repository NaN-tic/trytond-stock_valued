# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Equal, Eval, Not
from trytond.transaction import Transaction
from trytond.modules.product import price_digits
from trytond.modules.account_invoice_discount import discount_digits


__all__ = ['Move']
__metaclass__ = PoolMeta

_ZERO = Decimal('0.0')
STATES = {
    'invisible': Not(Equal(Eval('state', ''), 'done')),
    }


class Move:
    __name__ = 'stock.move'

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    gross_unit_price = fields.Function(fields.Numeric('Gross Price',
            digits=price_digits, states=STATES, depends=['state']),
        'get_origin_fields')
    discount = fields.Function(fields.Numeric('Discount',
            digits=discount_digits, states=STATES, depends=['state']),
        'get_origin_fields')
    amount = fields.Function(fields.Numeric('Amount',
            digits=(16, Eval('currency_digits', 2)),
            depends=['currency_digits']),
        'get_origin_fields')
    taxes = fields.Function(fields.Many2Many('account.tax', None, None,
            'Taxes'),
        'get_origin_fields')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        unit_price_invisible = cls.unit_price.states.get('invisible')
        if unit_price_invisible:
            cls.unit_price.states['readonly'] = unit_price_invisible
            cls.unit_price.states['invisible'] = {}

    @staticmethod
    def default_currency_digits():
        Company = Pool().get('company.company')
        if Transaction().context.get('company'):
            company = Company(Transaction().context['company'])
            return company.currency.digits
        return 2

    @fields.depends('currency')
    def on_change_with_currency_digits(self, name=None):
        if self.currency:
            return self.currency.digits
        return 2

    @classmethod
    def get_origin_fields(cls, moves, names):
        result = {}
        for fname in names:
            result[fname] = {}
        for move in moves:
            origin = move.origin
            if isinstance(origin, cls):
                origin = origin.origin
            for name in names:
                result[name][move.id] = (origin and
                    hasattr(origin, name) and
                    getattr(origin, name) or _ZERO)
            if 'amount' in names and not result['amount'][move.id]:
                value = (Decimal(str(move.quantity or 0)) *
                    (move.unit_price or _ZERO))
                if move.currency:
                    value = move.currency.round(value)
                result['amount'][move.id] = value
            if 'taxes' in names:
                result['taxes'][move.id] = (origin and
                    hasattr(origin, 'taxes') and
                    [t.id for t in origin.taxes] or [])
        return result
