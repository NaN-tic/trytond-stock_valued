# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal
from trytond.model import fields
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Equal, Eval, Not
from trytond.modules.product import price_digits, round_price
from trytond.modules.currency.fields import Monetary
from trytond.modules.discount_formula.discount import DiscountMixin

_ZERO = Decimal(0)
STATES = {
    'invisible': Not(Equal(Eval('state', ''), 'done')),
    }


class Move(metaclass=PoolMeta):
    __name__ = 'stock.move'

    base_price = Monetary(
        "Base Price", currency='currency', digits=price_digits,
        states={
            'invisible': ~Eval('unit_price_required'),
            'readonly': Eval('state') != 'draft',
            })
    discount_rate = fields.Function(fields.Numeric(
            "Discount Rate", digits=(16, 4),
            states={
                'invisible': ~Eval('unit_price_required'),
                'readonly': Eval('state') != 'draft',
                }),
        'on_change_with_discount_rate', setter='set_discount_rate')
    discount_amount = fields.Function(Monetary(
            "Discount Amount", currency='currency', digits=price_digits,
            states={
                'invisible': ~Eval('unit_price_required'),
                'readonly': Eval('state') != 'draft',
                }),
        'on_change_with_discount_amount', setter='set_discount_amount')
    discount = fields.Function(fields.Char(
            "Discount",
            states={
                'invisible': ~Eval('discount'),
                }),
        'on_change_with_discount')
    taxes = fields.Function(fields.Many2Many('account.tax', None, None,
        'Taxes'), 'get_taxes')
    amount = fields.Function(Monetary('Amount', digits='currency',
        currency='currency'), 'on_change_with_amount')

    @classmethod
    def view_attributes(cls):
        return super().view_attributes() + [
            ('//label[@id="discount"]', 'states', {
                'invisible': ~Eval('unit_price_required'),
                }),
            ]

    @fields.depends('unit_price', 'base_price')
    def on_change_with_discount_rate(self, name=None):
        if self.unit_price is None or not self.base_price:
            return
        rate = 1 - self.unit_price / self.base_price
        return rate.quantize(
            Decimal(1) / 10 ** self.__class__.discount_rate.digits[1])

    @fields.depends(
        'base_price', 'discount_rate',
        methods=['on_change_with_discount_amount', 'on_change_with_discount',
            'on_change_with_amount'])
    def on_change_discount_rate(self):
        if self.base_price is not None and self.discount_rate is not None:
            self.unit_price = round_price(
                self.base_price * (1 - self.discount_rate))
            self.discount_amount = self.on_change_with_discount_amount()
            self.discount = self.on_change_with_discount()
            self.amount = self.on_change_with_amount()

    @classmethod
    def set_discount_rate(cls, lines, name, value):
        pass

    @fields.depends('unit_price', 'base_price')
    def on_change_with_discount_amount(self, name=None):
        if self.unit_price is None or self.base_price is None:
            return
        return round_price(self.base_price - self.unit_price)

    @fields.depends(
        'base_price', 'discount_amount',
        methods=['on_change_with_discount_rate', 'on_change_with_discount',
            'on_change_with_amount'])
    def on_change_discount_amount(self):
        if self.base_price is not None and self.discount_amount is not None:
            self.unit_price = round_price(
                self.base_price - self.discount_amount)
            self.discount_rate = self.on_change_with_discount_rate()
            self.discount = self.on_change_with_discount()
            self.amount = self.on_change_with_amount()

    @classmethod
    def set_discount_amount(cls, lines, name, value):
        pass

    @fields.depends('currency',
        methods=[
            'on_change_with_discount_rate', 'on_change_with_discount_amount'])
    def on_change_with_discount(self, name=None):
        pool = Pool()
        Lang = pool.get('ir.lang')
        lang = Lang.get()
        rate = self.on_change_with_discount_rate()
        if not rate or rate % Decimal('0.01'):
            amount = self.on_change_with_discount_amount()
            if amount and self.currency:
                return lang.currency(
                    amount, self.currency, digits=price_digits[1])
        else:
            return lang.format('%i', rate * 100) + '%'

    def get_taxes(self, name):
        taxes = []
        if self.origin and self.origin != self and hasattr(self.origin, 'taxes'):
            for tax in self.origin.taxes:
                taxes.append(tax.id)
        elif self.product and self.from_location.type == 'supplier':
            for tax in self.product.supplier_taxes_used:
                taxes.append(tax.id)
        return taxes

    @fields.depends('quantity', 'unit_price', 'currency')
    def on_change_with_amount(self, name=None):
        amount = (Decimal(str(self.quantity or 0))
            * (self.unit_price or Decimal(0)))
        if self.currency:
            amount = self.currency.round(amount)
        return amount


class MoveDiscountFormula(DiscountMixin, metaclass=PoolMeta):
    __name__ = 'stock.move'
