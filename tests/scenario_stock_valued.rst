=====================
Stock Valued Scenario
=====================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard, Report
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from.trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock_value, sale and purchase Modules::

    >>> Module = Model.get('ir.module')
    >>> modules = Module.find([('name', 'in', ['stock_valued', 'sale', 'purchase'])])
    >>> Module.click(modules, 'install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

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

    >>> Journal = Model.get('account.journal')
    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> cash_journal.credit_account = cash
    >>> cash_journal.debit_account = cash
    >>> cash_journal.save()

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> Tax = Model.get('account.tax')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.customer_taxes.append(tax)
    >>> template.supplier_taxes.append(Tax(tax.id))
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Purchase 5 products::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.payment_term = payment_term
    >>> purchase.invoice_method = 'order'
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.quantity = 5.0
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> purchase.untaxed_amount, purchase.tax_amount, purchase.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> purchase.state
    u'processing'
    >>> len(purchase.moves), len(purchase.shipment_returns), len(purchase.invoices)
    (1, 0, 1)

Create Shipment::

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
    >>> shipment.click('done')
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('25.00'), Decimal('2.50'), Decimal('27.50'))
    >>> purchase.reload()
    >>> len(purchase.shipments), len(purchase.shipment_returns)
    (1, 0)
    >>> inventory_move, = shipment.inventory_moves
    >>> inventory_move.unit_price == product.template.cost_price
    True

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
    u'processing'
    >>> len(sale.shipments), len(sale.shipment_returns), len(sale.invoices)
    (1, 0, 1)
    >>> shipment, = sale.shipments
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('50.00'), Decimal('5.00'), Decimal('55.00'))
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.untaxed_amount, shipment.tax_amount, shipment.total_amount
    (Decimal('50.00'), Decimal('5.00'), Decimal('55.00'))
    >>> inventory_move, = shipment.inventory_moves
    >>> inventory_move.unit_price == product.template.list_price
    True

Create other product::

    >>> product2 = Product()
    >>> template2 = ProductTemplate()
    >>> template2.name = 'product2'
    >>> template2.default_uom = unit
    >>> template2.type = 'goods'
    >>> template2.purchasable = True
    >>> template2.salable = True
    >>> template2.list_price = Decimal('20')
    >>> template2.cost_price = Decimal('10')
    >>> template2.cost_price_method = 'fixed'
    >>> template2.account_expense = expense
    >>> template2.account_revenue = revenue
    >>> template2.save()
    >>> product2.template = template2
    >>> product2.save()

Create Shipment In::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> StockMove = Model.get('stock.move')
    >>> shipment_in = ShipmentIn()
    >>> shipment_in.supplier = supplier
    >>> shipment_in.planned_date = today
    >>> shipment_in.warehouse = warehouse_loc
    >>> shipment_in.company = company
    >>> move = StockMove()
    >>> shipment_in.incoming_moves.append(move)
    >>> move.from_location = supplier_loc
    >>> move.to_location = shipment_in.warehouse.input_location
    >>> move.product = product
    >>> move.quantity = 1.0
    >>> move.unit_price == product.template.cost_price
    True
    >>> shipment_in.save()

Create Shipment Out::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> StockMove = Model.get('stock.move')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.customer = customer
    >>> shipment_out.planned_date = today
    >>> shipment_out.warehouse = warehouse_loc
    >>> shipment_out.company = company
    >>> move = StockMove()
    >>> shipment_out.outgoing_moves.append(move)
    >>> move.from_location = shipment_out.warehouse.output_location
    >>> move.to_location = customer_loc
    >>> move.product = product
    >>> move.quantity = 1.0
    >>> shipment_out.click('wait')
    >>> shipment_out.state
    u'waiting'
    >>> inventory_move, = shipment_out.inventory_moves
    >>> inventory_move.unit_price == product.template.list_price
    True
    >>> inventory_move.product = product2
    >>> inventory_move.unit_price == product2.template.list_price
    True

Create Shipment Out Return::

    >>> ShipmentOutReturn = Model.get('stock.shipment.out.return')
    >>> StockMove = Model.get('stock.move')
    >>> shipment_out_return = ShipmentOutReturn()
    >>> shipment_out_return.customer = customer
    >>> shipment_out_return.planned_date = today
    >>> shipment_out_return.warehouse = warehouse_loc
    >>> shipment_out_return.company = company
    >>> move = StockMove()
    >>> shipment_out_return.incoming_moves.append(move)
    >>> move.from_location = customer_loc
    >>> move.to_location = shipment_out_return.warehouse.input_location
    >>> move.product = product
    >>> move.quantity = 1.0
    >>> move.unit_price == product.template.list_price
    True
    >>> shipment_out_return.save()
