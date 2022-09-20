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
    discount_digits = price_digits


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
        depends=['currency_digits']), 'get_origin_fields')
    discount = fields.Function(fields.Numeric('Discount',
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
        pool = Pool()
        Config = pool.get('stock.configuration')
        Tax = pool.get('account.tax')

        config = Config(1)
        result = {n: {r.id: _ZERO for r in moves} for n in {'gross_unit_price',
                    'amount',  'taxes', 'unit_price_w_tax', 'discount'}}

        def compute_amount_with_tax(move, taxes, amount):
            tax_amount = _ZERO

            if taxes:
                tax_list = Tax.compute(taxes,
                    move.unit_price or Decimal('0.0'),
                    move.quantity or 0.0)
                tax_amount = sum([t['amount'] for t in tax_list],
                    Decimal('0.0'))
            return amount + tax_amount

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

            # amount
            unit_price = None
            amount = _ZERO
            if config.valued_origin and hasattr(origin, 'unit_price'):
                unit_price = (origin.unit_price if origin.unit_price != None
                    else (move.unit_price or _ZERO))
            else:
                unit_price = (move.unit_price if move.unit_price != None
                    else (move.unit_price or _ZERO))
            if unit_price:
                amount = (Decimal(
                    str(move.get_quantity_for_value() or 0)) * (unit_price))
                if move.currency:
                    amount = move.currency.round(amount)
                result['amount'][move.id] = amount

            # taxes
            taxes = []
            if config.valued_origin and hasattr(origin, 'taxes'):
                taxes = origin.taxes
            else:
                pattern = move._get_tax_rule_pattern()
                tax_rule = None
                taxes_used = []
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
                            taxes.extend(Tax.browse(tax_ids))
                        continue
                    taxes.append(tax)
                if tax_rule:
                    tax_ids = tax_rule.apply(None, pattern)
                    if tax_ids:
                        taxes.extend(Tax.browse(tax_ids))
            if taxes:
                result['taxes'][move.id] = [t.id for t in taxes]

            # unit_price_w_tax
            unit_price_w_tax = _ZERO
            if move.quantity and move.quantity != 0:
                amount_w_tax = compute_amount_with_tax(move, taxes, amount)
                unit_price_w_tax = amount_w_tax / Decimal(str(move.quantity))
            result['unit_price_w_tax'][move.id] = unit_price_w_tax

            if 'gross_unit_price' in names:
                gross_unit_price = None
                origin = move.origin
                if isinstance(origin, cls):
                    origin = origin.origin

                if (config.valued_origin and
                        hasattr(origin, 'gross_unit_price')):
                    gross_unit_price = origin.gross_unit_price
                else:
                    gross_unit_price = origin.unit_price
                if gross_unit_price:
                    result['gross_unit_price'][move.id] = gross_unit_price

            if 'discount' in names:
                discount = _ZERO
                if (config.valued_origin and hasattr(origin, 'discount')):
                    discount = origin.discount
                result['discount'][move.id] = discount

        return result

    def get_quantity_for_value(self):
        return self.quantity
