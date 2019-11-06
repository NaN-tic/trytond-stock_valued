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

_ZERO = Decimal('0.0')

STATES = {
    'invisible': Not(Equal(Eval('state', ''), 'done')),
    }


class Move:
    __metaclass__ = PoolMeta
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
    unit_price_w_tax = fields.Function(fields.Numeric('Unit Price with Tax',
        digits=(16, Eval('_parent_sale', {}).get('currency_digits',
                Eval('currency_digits', 2))),
        states=STATES,
        depends=['currency_digits']), 'get_price_with_tax')

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
                result[name][move.id] = _ZERO

            if 'gross_unit_price' in names:
                result['gross_unit_price'][move.id] = (origin and
                   hasattr(origin, 'gross_unit_price') and
                   origin.gross_unit_price or _ZERO)
            if 'discount' in names:
                result['discount'][move.id] = (origin and
                    hasattr(origin, 'discount') and
                    origin.discount or _ZERO)
            if 'amount' in names:
                value = (Decimal(str(move.get_quantity_for_value() or 0)) *
                    (move.unit_price or _ZERO))
                if move.currency:
                    value = move.currency.round(value)
                result['amount'][move.id] = value
            if 'taxes' in names:
                result['taxes'][move.id] = (origin and
                    hasattr(origin, 'taxes') and
                    [t.id for t in origin.taxes] or [])
        return result

    def get_quantity_for_value(self):
        return self.quantity

    @classmethod
    def get_price_with_tax(cls, moves, names):
        pool = Pool()
        Tax = pool.get('account.tax')
        amount_w_tax = {}
        unit_price_w_tax = {}

        def compute_amount_with_tax(move):
            tax_amount = Decimal('0.0')
            if move.taxes:
                tax_list = Tax.compute(move.taxes,
                    move.unit_price or Decimal('0.0'),
                    move.quantity or 0.0)
                tax_amount = sum([t['amount'] for t in tax_list], Decimal('0.0'))
            return move.amount + tax_amount

        for move in moves:
            amount = Decimal('0.0')
            unit_price = Decimal('0.0')
            currency = (move.sale.currency if move.sale else move.currency)

            if move.quantity and move.quantity != 0:
                amount = compute_amount_with_tax(move)
                unit_price = amount / Decimal(str(move.quantity))

            if currency:
                amount = currency.round(amount)
            amount_w_tax[move.id] = amount
            unit_price_w_tax[move.id] = unit_price

        result = {
            'unit_price_w_tax': unit_price_w_tax,
            }
        for key in result.keys():
            if key not in names:
                del result[key]
        return result
