import unittest
from decimal import Decimal

from proteus import Model
from trytond.modules.account.tests.tools import (create_chart,
                                                 create_fiscalyear, create_tax,
                                                 get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    create_payment_term, set_fiscalyear_invoice_sequences)
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install stock_value, sale and purchase Modules
        activate_modules(['stock_valued', 'sale', 'purchase',
            'sale_discount', 'purchase_discount'])

        # Create company
        _ = create_company()
        company = get_company()

        # Create fiscal year
        fiscalyear = set_fiscalyear_invoice_sequences(
            create_fiscalyear(company))
        fiscalyear.click('create_period')

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        revenue = accounts['revenue']
        expense = accounts['expense']

        # Create tax
        tax = create_tax(Decimal('.10'))
        tax.save()

        # Create parties
        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.save()
        customer = Party(name='Customer')
        customer.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        Tax = Model.get('account.tax')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.customer_taxes.append(Tax(tax.id))
        account_category.supplier_taxes.append(Tax(tax.id))
        account_category.save()

        # Create product
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        ProductTemplate = Model.get('product.template')
        template = ProductTemplate()
        template.name = 'product'
        template.default_uom = unit
        template.type = 'goods'
        template.purchasable = True
        template.salable = True
        template.list_price = Decimal('10')
        template.cost_price_method = 'fixed'
        template.account_category = account_category
        product, = template.products
        product.cost_price = Decimal('5')
        template.save()
        product, = template.products

        # Create payment term
        payment_term = create_payment_term()
        payment_term.save()

        # Purchase 5 products
        Purchase = Model.get('purchase.purchase')
        purchase = Purchase()
        purchase.party = supplier
        purchase.payment_term = payment_term
        purchase.invoice_method = 'order'
        purchase_line = purchase.lines.new()
        purchase.lines.append(purchase_line)
        purchase_line.product = product
        purchase_line.quantity = 5.0
        purchase_line.base_price = product.cost_price
        purchase_line.discount_rate = Decimal('0.10')
        self.assertEqual(purchase_line.unit_price, Decimal('4.5000'))
        self.assertEqual(len(purchase_line.taxes), 1)
        purchase.click('quote')
        purchase.click('confirm')
        purchase.click('process')
        self.assertEqual(purchase.untaxed_amount, Decimal('22.50'))
        self.assertEqual(purchase.tax_amount, Decimal('2.25'))
        self.assertEqual(purchase.total_amount, Decimal('24.75'))
        self.assertEqual(purchase.state, 'processing')
        self.assertEqual(len(purchase.moves), 1)
        self.assertEqual(len(purchase.shipment_returns), 0)
        self.assertEqual(len(purchase.invoices), 1)

        # Create Supplier Shipment from purchase
        Move = Model.get('stock.move')
        ShipmentIn = Model.get('stock.shipment.in')
        shipment = ShipmentIn()
        shipment.supplier = supplier
        for move in purchase.moves:
            incoming_move = Move(id=move.id)
            shipment.incoming_moves.append(incoming_move)
        shipment.save()
        self.assertEqual(shipment.origins, purchase.rec_name)
        self.assertEqual(shipment.untaxed_amount, purchase.untaxed_amount)
        self.assertEqual(shipment.tax_amount, purchase.tax_amount)
        self.assertEqual(shipment.total_amount, purchase.total_amount)

        move, = shipment.incoming_moves
        line, = purchase.lines
        self.assertEqual(move.amount, line.amount)
        self.assertEqual(move.unit_price, line.unit_price)
        self.assertEqual(move.base_price, line.base_price)
        self.assertEqual(move.discount_rate, line.discount_rate)
        self.assertEqual(move.discount, line.discount)
        self.assertEqual(len(move.taxes), 1)

        # change unit_price incoming moves and shipment valued not equal to purchase
        move.unit_price = Decimal('4.1200')
        move.save()
        shipment.reload()
        self.assertNotEqual(shipment.untaxed_amount, purchase.untaxed_amount)
        self.assertNotEqual(shipment.tax_amount, purchase.tax_amount)
        self.assertNotEqual(shipment.total_amount, purchase.total_amount)

        shipment.click('receive')
        shipment.click('do')
        self.assertEqual(shipment.untaxed_amount, Decimal('20.60'))
        self.assertEqual(shipment.tax_amount, Decimal('2.06'))
        self.assertEqual(shipment.total_amount, Decimal('22.66'))
        self.assertEqual(len(purchase.shipments), 1)
        self.assertEqual(len(purchase.shipment_returns), 0)

        # Sale 5 products and test it's shipment has the valued amounts
        Sale = Model.get('sale.sale')
        sale = Sale()
        sale.party = customer
        sale.payment_term = payment_term
        sale.invoice_method = 'order'
        sale_line = sale.lines.new()
        sale_line.product = product
        sale_line.quantity = 5.0
        sale_line.discount_rate = Decimal('0.10')
        self.assertEqual(sale_line.base_price, Decimal('10.00'))
        self.assertEqual(sale_line.unit_price, Decimal('9.00'))
        self.assertEqual(sale_line.amount, Decimal('45.00'))
        self.assertEqual(len(sale_line.taxes), 1)
        sale.click('quote')
        sale.click('confirm')
        sale.click('process')
        self.assertEqual(sale.untaxed_amount, Decimal('45.00'))
        self.assertEqual(sale.tax_amount, Decimal('4.50'))
        self.assertEqual(sale.total_amount, Decimal('49.50'))
        self.assertEqual(sale.state, 'processing')
        self.assertEqual(len(sale.shipments), 1)
        self.assertEqual(len(sale.shipment_returns), 0)
        self.assertEqual(len(sale.invoices), 1)

        shipment, = sale.shipments
        self.assertEqual(shipment.untaxed_amount, Decimal('45.00'))
        self.assertEqual(shipment.tax_amount, Decimal('4.50'))
        self.assertEqual(shipment.total_amount, Decimal('49.50'))
        line, = sale.lines
        move, = shipment.outgoing_moves
        self.assertEqual(move.amount, line.amount)
        self.assertEqual(move.unit_price, line.unit_price)
        self.assertEqual(move.base_price, line.base_price)
        self.assertEqual(move.discount_rate, line.discount_rate)
        self.assertEqual(move.discount, line.discount)
        self.assertEqual(len(move.taxes), 1)
        shipment.click('assign_try')
        shipment.click('pick')
        shipment.click('pack')
        shipment.click('do')
        self.assertEqual(shipment.state, 'done')
        self.assertEqual(shipment.untaxed_amount, Decimal('45.00'))
        self.assertEqual(shipment.tax_amount, Decimal('4.50'))
        self.assertEqual(shipment.total_amount, Decimal('49.50'))

        # Create Supplier Shipment
        Location = Model.get('stock.location')
        supplier_loc, = Location.find([('type', '=', 'supplier')], limit=1)
        shipment = ShipmentIn()
        shipment.supplier = supplier
        incoming_move = Move()
        shipment.incoming_moves.append(incoming_move)
        incoming_move.product = product
        incoming_move.unit = unit
        incoming_move.quantity = 1
        incoming_move.from_location = supplier_loc
        incoming_move.to_location = shipment.warehouse.input_location
        incoming_move.company = company
        incoming_move.unit_price = Decimal('1')
        incoming_move.currency = company.currency
        shipment.save()
        self.assertEqual(shipment.untaxed_amount, Decimal('1.00'))
        # incoming move has not origin; not taxes
        self.assertEqual(shipment.tax_amount, Decimal('0'))
        self.assertEqual(shipment.total_amount, Decimal('1.00'))
        move, = shipment.incoming_moves
        self.assertEqual(move.amount, Decimal('1.00'))
        self.assertEqual(move.base_price, None)
        self.assertEqual(len(move.taxes), 0)

        # Create Customer Shipment
        ShipmentOut = Model.get('stock.shipment.out')
        customer_loc, = Location.find([('type', '=', 'customer')], limit=1)
        shipment = ShipmentOut()
        shipment.customer = customer
        outgoing_move = Move()
        shipment.outgoing_moves.append(outgoing_move)
        outgoing_move.product = product
        outgoing_move.unit = unit
        outgoing_move.quantity = 1
        outgoing_move.from_location = shipment.warehouse.output_location
        outgoing_move.to_location = customer_loc
        outgoing_move.company = company
        outgoing_move.unit_price = Decimal('1')
        outgoing_move.currency = company.currency
        shipment.save()
        self.assertEqual(shipment.untaxed_amount, Decimal('1.00'))
        self.assertEqual(shipment.tax_amount, Decimal('0'))
        self.assertEqual(shipment.total_amount, Decimal('1.00'))

        move, = shipment.outgoing_moves
        self.assertEqual(move.amount, Decimal('1.00'))
        self.assertEqual(move.unit_price, Decimal('1.00'))
        self.assertEqual(move.base_price, None)
        self.assertEqual(move.discount_rate, None)

        # Create Customer Return Shipment
        ShipmentOutReturn = Model.get('stock.shipment.out.return')
        shipment = ShipmentOutReturn()
        shipment.customer = customer
        incoming_move = Move()
        shipment.incoming_moves.append(incoming_move)
        incoming_move.product = product
        incoming_move.unit = unit
        incoming_move.quantity = 1
        incoming_move.from_location = customer_loc
        incoming_move.to_location = shipment.warehouse.input_location
        incoming_move.company = company
        incoming_move.unit_price = Decimal('1')
        incoming_move.currency = company.currency
        shipment.save()
        self.assertEqual(shipment.untaxed_amount, Decimal('1.00'))
        # incoming move has not origin; not taxes
        self.assertEqual(shipment.tax_amount, Decimal('0'))
        self.assertEqual(shipment.total_amount, Decimal('1.00'))
        move, = shipment.incoming_moves
        self.assertEqual(move.amount, Decimal('1.00'))
        self.assertEqual(move.base_price, None)
        self.assertEqual(len(move.taxes), 0)

        # Create Internal Shipment
        storage_location, = Location.find([('type', '=', 'storage')], limit=1)
        new_loc = Location()
        new_loc.name = 'A1'
        new_loc.parent = storage_location
        new_loc.type = 'storage'
        new_loc.save()

        ShipmentInternal = Model.get('stock.shipment.internal')
        shipment = ShipmentInternal()
        shipment.from_location = storage_location
        shipment.to_location = new_loc
        move = Move()
        shipment.moves.append(move)
        move.product = product
        move.unit = unit
        move.quantity = 1
        move.from_location = storage_location
        move.to_location = new_loc
        move.company = company
        shipment.save()
        move, = shipment.moves
        self.assertEqual(move.amount, Decimal('0'))
        # self.assertEqual(move.unit_price_w_tax, Decimal('0'))
        self.assertEqual(move.base_price, None)
