# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
# -*- coding: utf-8 -*-

import argparse
import logging
import sys
from proteus import config as pconfig, Model
from trytond.exceptions import UserError


def __parse_args(args=None, namespace=None):

    parser = argparse.ArgumentParser(description='Shipment Amounts updater')
    parser.add_argument('--version', action='version',
        version='%(prog)s 0.0.1 - NaN-tic 2018')
    parser.add_argument('-v', '--verbose', help='Increase output verbosity.',
        action='store_true')
    parser.add_argument('database', type=str, help='Tryton database')
    parser.add_argument('--config-file', '-c', type=str,
        help='Tryton config file')

    return parser.parse_args(args, namespace)


def progress(count, total, status=''):
        """
        GUI Progress bar
        :param count: Integer with the current progress value.
        :param total: Integer with the total value of the progress.
        :param status: String message that will be printed next to the progress
        bar.
        :return:
        """
        bar_len = 60
        filled_len = int(round(bar_len * count / float(total)))

        percents = round(100.0 * count / float(total), 1)
        bar = '=' * filled_len + '-' * (bar_len - filled_len)

        sys.stdout.write('\t[%s] %s%s ...%s\r' % (bar, percents, '%', status))


def prepare(model):
    to_update = []
    shimpents = model.find([])
    n_rows = len(shimpents)
    curr_processed_rows = 0
    for shipment in shimpents:
        progress(curr_processed_rows, n_rows)
        if shipment.state in ('done', 'cancelled'):
            shipment.untaxed_amount = shipment.untaxed_amount_func
            shipment.tax_amount = shipment.tax_amount_func
            shipment.total_amount = shipment.untaxed_amount + \
                shipment.tax_amount
            to_update.append(shipment)
        curr_processed_rows += 1
    progress(n_rows, n_rows)
    sys.stdout.write('\n')
    return to_update


def update(model, to_update):
    """
    Row by row update of a model
    :param model: Model to update
    :param to_update: List of instances to update
    :return:
    """
    n_rows = len(to_update)
    curr_processed_rows = 0
    for shipment in to_update:
        progress(curr_processed_rows, n_rows)
        try:
            shipment.save()
            curr_processed_rows += 1
        except UserError:
            continue

    progress(n_rows, n_rows)
    sys.stdout.write('\n')
    return n_rows


args = __parse_args()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

uri = 'postgresql:///%s' % args.database
pconfig.set_trytond(uri, config_file=args.config_file)
logger.info('Connected to %s' % args.database)
ShipmentIn = Model.get('stock.shipment.in')
ShipmentOut = Model.get('stock.shipment.out')

for classname in ('ShipmentIn', 'ShipmentOut'):
    logger.info(classname)
    logger.info('Preparing updates...')
    to_update = prepare(eval(classname))
    logger.info('Updating...')
    updated = update(eval(classname), to_update)
    logger.info('Updated %s shipments' % updated)
    logger.info('Done')
