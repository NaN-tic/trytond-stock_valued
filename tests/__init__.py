# This file is part stock_valued module for Tryton.  The COPYRIGHT file at the
# top level of this repository contains the full copyright notices and license
# terms.
try:
    from trytond.modules.stock_valued.tests.test_stock_valued import suite
except ImportError:
    from .test_stock_valued import suite

__all__ = ['suite']
