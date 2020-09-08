# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Equal, Eval, Not
from trytond.transaction import Transaction
from trytond.modules.product import price_digits
try:
    from trytond.modules.account_invoice_discount import discount_digits
except ImportError:
    discount_digits = None


__all__ = ['Move']

_ZERO = Decimal('0.0')
STATES = {
    'invisible': Not(Equal(Eval('state', ''), 'done')),
    }
PARTIES = {
    'stock.shipment.in': 'supplier',
    'stock.shipment.in.return': 'supplier',
    'stock.shipment.out': 'customer',
    'stock.shipment.out.return': 'customer',
    'stock.shipment.internal': 'company',
    }


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'on_change_with_currency_digits')
    gross_unit_price = fields.Function(fields.Numeric('Gross Price',
            digits=price_digits, states=STATES, depends=['state']),
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
        if discount_digits:
            cls.discount = fields.Function(fields.Numeric('Discount',
                    digits=discount_digits, states=STATES, depends=['state']),
                'get_origin_fields')

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

    def _get_tax_rule_pattern(self):
        '''
        Get tax rule pattern
        '''
        return {}

    @classmethod
    def get_origin_fields(cls, moves, names):
        Config = Pool().get('stock.configuration')
        config = Config(1)

        result = {}
        for fname in names:
            result[fname] = {}
        for move in moves:
            origin = move.origin
            if isinstance(origin, cls):
                origin = origin.origin
            shipment = move.shipment or None

            party = (getattr(shipment, PARTIES.get(shipment.__name__))
                if shipment and PARTIES.get(shipment.__name__) else None)
            if shipment and shipment.__name__ == 'stock.shipment.internal':
                # party is from company.party
                party = party.party

            for name in names:
                result[name][move.id] = _ZERO

            if 'amount' in names:
                unit_price = None
                if config.valued_origin and hasattr(origin, 'unit_price'):
                    unit_price = (origin.unit_price if origin.unit_price != None
                        else (move.unit_price or _ZERO))
                else:
                    unit_price = (move.unit_price if move.unit_price != None
                        else (move.unit_price or _ZERO))
                if unit_price:
                    value = (Decimal(
                        str(move.get_quantity_for_value() or 0)) * (unit_price))
                    if move.currency:
                        value = move.currency.round(value)
                    result['amount'][move.id] = value

            if 'gross_unit_price' in names:
                gross_unit_price = None
                if (config.valued_origin and
                        hasattr(origin, 'gross_unit_price')):
                    gross_unit_price = origin.gross_unit_price
                else:
                    gross_unit_price = move.unit_price_w_tax
                if gross_unit_price:
                    result['gross_unit_price'][move.id] = gross_unit_price

            if 'taxes' in names:
                taxes = []
                if config.valued_origin and hasattr(origin, 'taxes'):
                    taxes = [t.id for t in origin.taxes]
                else:
                    pattern = move._get_tax_rule_pattern()
                    tax_rule = None
                    taxes_used = None
                    if shipment:
                        if shipment.__name__.startswith('stock.shipment.out'):
                            tax_rule = party and party.customer_tax_rule or None
                            taxes_used = (move.product.customer_taxes_used
                                if party else [])
                        elif shipment.__name__.startswith('stock.shipment.in'):
                            tax_rule = party and party.supplier_tax_rule or None
                            taxes_used = (move.product.supplier_taxes_used
                                if party else [])

                    for tax in taxes_used:
                        if tax_rule:
                            tax_ids = tax_rule.apply(tax, pattern)
                            if tax_ids:
                                taxes.extend(tax_ids)
                            continue
                        taxes.append(tax.id)
                    if tax_rule:
                        tax_ids = tax_rule.apply(None, pattern)
                        if tax_ids:
                            taxes.extend(tax_ids)
                if taxes:
                    result['taxes'][move.id] = taxes

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
                tax_amount = sum([t['amount'] for t in tax_list],
                    Decimal('0.0'))
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
