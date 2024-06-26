=====================
Stock Valued Scenario
=====================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install stock_value, sale and purchase Modules::

    >>> config = activate_modules(['stock_valued', 'sale', 'purchase'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> Tax = Model.get('account.tax')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.supplier_taxes.append(Tax(tax.id))
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('5')
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Set Use Valued origin::

    >>> Configuration = Model.get('stock.configuration')
    >>> configuration = Configuration(1)
    >>> configuration.valued_origin = True
    >>> configuration.save()

Purchase 5 products::

    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseLine = Model.get('purchase.line')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = PurchaseLine()
    >>> purchase.lines.append(purchase_line)
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5.0
    >>> purchase_line.unit_price = product.cost_price
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> purchase.state
    'processing'
    >>> len(purchase.moves), len(purchase.shipment_returns), len(purchase.invoices)
    (1, 0, 1)

Create Supplier Shipment from purchase::

    >>> Move = Model.get('stock.move')
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> for move in purchase.moves:
    ...     incoming_move = Move(id=move.id)
    ...     shipment.incoming_moves.append(incoming_move)
    >>> shipment.save()
    >>> shipment.origins == purchase.rec_name
    True
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> shipment.click('receive')
    >>> shipment.click('do')
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> len(purchase.shipments), len(purchase.shipment_returns)
    (1, 0)

Sale 5 products and test it's shipment has the valued amounts::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.untaxed_amount, sale.tax_amount, sale.total_amount
    (Decimal('50.00'), Decimal('5.00'), Decimal('55.00'))
    >>> sale.state
    'processing'
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 1)
    >>> shipment, = sale.shipments
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('50.00'), Decimal('5.00'), Decimal('55.00'))
    >>> shipment.click('assign_try')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('50.00'), Decimal('5.00'), Decimal('55.00'))

Create Supplier Shipment::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('type', '=', 'supplier')], limit=1)
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> incoming_move = Move()
    >>> shipment.incoming_moves.append(incoming_move)
    >>> incoming_move.product = product
    >>> incoming_move.unit = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = shipment.warehouse.input_location
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('1')
    >>> incoming_move.currency = company.currency
    >>> shipment.save()
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('1.00'), Decimal('0.10'), Decimal('1.10'))

Create Customer Shipment::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> customer_loc, = Location.find([('type', '=', 'customer')], limit=1)
    >>> shipment = ShipmentOut()
    >>> shipment.customer = customer
    >>> outgoing_move = Move()
    >>> shipment.outgoing_moves.append(outgoing_move)
    >>> outgoing_move.product = product
    >>> outgoing_move.unit = unit
    >>> outgoing_move.quantity = 1
    >>> outgoing_move.from_location = shipment.warehouse.output_location
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('1')
    >>> outgoing_move.currency = company.currency
    >>> shipment.save()
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('1.00'), Decimal('0.10'), Decimal('1.10'))

Create Customer Return Shipment::

    >>> ShipmentOutReturn = Model.get('stock.shipment.out.return')
    >>> shipment = ShipmentOutReturn()
    >>> shipment.customer = customer
    >>> incoming_move = Move()
    >>> shipment.incoming_moves.append(incoming_move)
    >>> incoming_move.product = product
    >>> incoming_move.unit = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = customer_loc
    >>> incoming_move.to_location = shipment.warehouse.input_location
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('1')
    >>> incoming_move.currency = company.currency
    >>> shipment.save()
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('1.00'), Decimal('0.10'), Decimal('1.10'))

Create Internal Shipment::

    >>> storage_location, = Location.find([('type', '=', 'storage')], limit=1)
    >>> new_loc = Location()
    >>> new_loc.name = 'A1'
    >>> new_loc.parent = storage_location
    >>> new_loc.type = 'storage'
    >>> new_loc.save()
    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> shipment = ShipmentInternal()
    >>> shipment.from_location = storage_location
    >>> shipment.to_location = new_loc
    >>> move = Move()
    >>> shipment.moves.append(move)
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = storage_location
    >>> move.to_location = new_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment.save()
    >>> move, = shipment.moves
    >>> move.amount, move.unit_price_w_tax, move.gross_unit_price
    (Decimal('1.00'), Decimal('1.10'), Decimal('1'))
