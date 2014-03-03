#!/usr/bin/env python

#
#    This file is part of osCommerce Bitcoin Payment Module
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re
import subprocess
import MySQLdb
import requests
import psutil
import simplejson as json
from time import sleep
from decimal import Decimal

# our configuration file - copy defaultsettings.py to settings.py and edit
from settings import *

# setup logging
import logging
logger = logging.getLogger('osc-bitcoin-monitor')
hdlr = logging.FileHandler(BASE_PATH + 'monitor.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.INFO)
#logger.setLevel(logging.DEBUG)


# Daemon - handles running bitcoind and getting results back from it
#
class Daemon:
    bitcoind_command = ['bitcoind']     # bitcoind binary
    bitcoind_arguments = ['-daemon']    # commandline arguments
    bitcoind_timeout = 300              # wait for bitcoind api
    bitcoind = False                    # bitcoind process

    def start(self):
        logger.info("Starting bitcoind...")
        command = self.bitcoind_command[:]
        command.extend(self.bitcoind_arguments)
        try:
            subprocess.call(command)
        except (subprocess.CalledProcessError, OSError):
            logger.exception("Failed to start bitcoind")

        sleep(5)  # time for process to spawn
        self.bitcoind = self.get_bitcoind()
        if self.bitcoind:
            logger.info("Bitcoind started (PID: " +
                    str(self.bitcoind.pid) + ")")
        else:
            logger.error("Failed to start bitcoind")

    def check(self):
        # find existing bitcoind process
        self.bitcoind = self.get_bitcoind()

        # run bitcoind
        if not self.bitcoind:
            self.start()

        # wait until bitcoind starts responding to API calls
        timer = 0
        interval = 10  # check every 10 seconds until timeout
        bitcoind_ready = False
        while not bitcoind_ready:
            # API call 'getgenerate' expected to respond: False (json)
            if not self.bitcoind_api_call(['getgenerate']):
                bitcoind_ready = True
            else:
                logger.info("Waiting for bitcoind...")
                sleep(interval)
                timer = timer + interval
                if (timer >= self.bitcoind_timeout):
                    logger.error("Bitcoind not responding to API calls, " +
                            "restarting...")
                    self.terminate()
                    self.start()
                    timer = 0

    # returns bitcoind process object
    def get_bitcoind(self):
        for pid in psutil.get_pid_list():
            # match process name
            if (psutil.Process(pid).name == self.bitcoind_command[0]):
                # match process real uid against this scripts ruid
                if (os.getresuid()[0] == psutil.Process(pid).uids[0]):
                    return psutil.Process(pid)
        return False

    def terminate(self):
        logger.warning("Terminating bitcoind...")
        try:
            self.bitcoind.terminate()  # ask nicely
            self.bitcoind.wait(30)  # give time
            logger.info("Bitcoind terminated succesfully")
        except psutil.AccessDenied:
            logger.exception("Terminating bitcoind - Operation not permitted!")
        except psutil.TimeoutExpired:
            logger.warning("Terminating bitcoind - Timed out, " +
                    "trying kill -9...")
            try:
                self.bitcoind.kill()  # take out the pistol
                self.bitcoind.wait(5)  # it's gonna be over quick
                logger.info("Bitcoind killed succesfully")
            except psutil.AccessDenied:
                logger.exception("Killing bitcoind - Operation not permitted!")
            except psutil.TimeoutExpired:
                logger.error("Could not kill bitcoind!")

    def bitcoind_api_call(self, call):
        command = self.bitcoind_command[:]
        command.extend(call)
        try:
            logger.debug("Calling bitcoind API: " + str(call))
            result = subprocess.check_output(command).strip()
            logger.debug("bitcoind API call reply: " + str(result))
            return json.loads(result)
        except (subprocess.CalledProcessError, OSError, json.JSONDecodeError):
            logger.exception("Error querying bitcoind API!")
        return False

    def list_addresses(self):
        call = ['getaddressesbyaccount', '']
        js = self.bitcoind_api_call(call)
        return js

    def get_transactions(self, number):
        call = ['listtransactions', '', str(number)]
        js = self.bitcoind_api_call(call)
        return js

    def get_receivedbyaddress(self, address, minconf):
        call = ['getreceivedbyaddress', address, str(minconf)]
        js = self.bitcoind_api_call(call)
        return Decimal(str(js))

    def get_balance(self, minconf):
        call = ['getbalance', '*', str(minconf)]
        js = self.bitcoind_api_call(call)
        return Decimal(str(js))

    def send(self, address, amount):
        call = ['sendtoaddress', address, str(amount), 'testing']
        js = self.bitcoind_api_call(call)
        return js


# Sales - checks and informs OSC about payments for bitcoin orders
#
class Sales:
    def __init__(self):
        try:
            self.db = MySQLdb.connect(host=DBHOST, user=DBUSER,
                    passwd=DBPASSWD, db=DBNAME)
            self.cursor = self.db.cursor()
        except MySQLdb.Error:
            logger.exception("Error connecting to MySQL, Exitting.")
            sys.exit(1)

    def check_payments(self):
        d = Daemon()

        try:
            # get notification key
            c = self.db.cursor(cursorclass=MySQLdb.cursors.DictCursor)
            c.execute("""select configuration_value
                    from configuration
                    where configuration_key =
                        'MODULE_PAYMENT_BITCOIN_NOTIFICATION_KEY'""")
            result = c.fetchone()
            result = result['configuration_value']
            notification_key = result

            # get default orders status for a bitcoin payment
            c.execute("""select configuration_value
                    from configuration
                    where configuration_key =
                        'MODULE_PAYMENT_BITCOIN_ORDER_STATUS_ID'""")
            result = c.fetchone()
            result = int(result['configuration_value'])
            default_bitcoin_orders_status = result

            # 0 means default for OSC so we need to go deeper
            if(default_bitcoin_orders_status == 0):
                c.execute("""select configuration_value
                        from configuration
                        where configuration_key =
                            'DEFAULT_ORDERS_STATUS_ID'""")
                result = c.fetchone()
                result = int(result['configuration_value'])
                default_bitcoin_orders_status = result

            # get list of pending orders from osc with amounts and addresses
            c.execute("""select orders.orders_id, comments, title, text
                    from (orders inner join orders_total on
                        orders.orders_id = orders_total.orders_id)
                        inner join orders_status_history on orders.orders_id =
                        orders_status_history.orders_id
                    where orders.orders_status = %d
                        and orders.payment_method like 'Bitcoin Payment'
                        and orders_total.title = 'Total:'"""
                     % (default_bitcoin_orders_status,))
            orders = c.fetchall()
        except MySQLdb.Error:
            logger.exception("MySQL error, Could not fetch list of orders")
            # even if we cannot check for payments, we can still return
            # and continue to update exchange rates and stuff
            return

        # check balance of every pending bitcoin orders payment address
        for order in orders:
            # get order bitcoin payment address
            a = re.search(r"[A-Za-z0-9]{28,}", order['comments'])
            if not a:
                continue
            address = a.group()

            # get order total
            if not order['title'] == 'Total:':
                continue
            t = re.search(r"\d+\.\d+", order['text'])
            if not t:
                continue
            total = Decimal(str(t.group()))

            logger.info("Check for " + str(total) +
                    " BTC to be sent to " + address +
                    " for orders_id = " + str(order['orders_id']))
            received = d.get_receivedbyaddress(address, MINCONF)
            logger.info("Amount still needed: " + str(total - received))
            if (received >= total):  # payment received
                logger.info("Received " + str(received) +
                        " BTC at " + address +
                        " for orders_id = " + str(order['orders_id']))
                url = OSC_URL + '/ext/modules/payment/bitcoin/bpn.php'
                values = {'bpn_key': notification_key,
                          'orders_id': order['orders_id']}
                logger.info("Sending bpn request to: " + url)
                # inform OSC about received payment via bpn.php
                try:
                    r = requests.post(url, data=values)
                except requests.exceptions.RequestException:
                    logger.exception("bpn request Failed!")
                if (r.status_code != requests.codes.ok):
                    logger.error("bpn.php non-ok response code: " +
                            str(r.status_code))


logger.info("-------- Started monitor script --------")

d = Daemon()
s = Sales()
refreshcount = 0


def update_exchange_rate(btcusd_rate, usdbtc_rate):
    db = MySQLdb.connect(host=DBHOST, user=DBUSER,
            passwd=DBPASSWD, db=DBNAME)
    c = db.cursor(cursorclass=MySQLdb.cursors.DictCursor)
    c.execute("""update currencies set value = %f
            where code = 'BTC'""" % (usdbtc_rate,))
    db.close()

while(1):
    # make sure bitcoind is running and responding
    d.check()

    # check orders for payments
    s.check_payments()

    # check the total balance of the wallet
    balance = d.get_balance(6)
    keep_local = Decimal(str(FORWARDING_KEEP_LOCAL))
    forwarding_minimum = Decimal(str(FORWARDING_MINIMUM))
    forwarding_addresses = len(FORWARDING_ADDRESS)
    transaction_fee = Decimal(str(TRANSACTION_FEE))
    amount_to_send = balance - keep_local - transaction_fee
    address = FORWARDING_ADDRESS

    # forward coins to another wallet
    if(keep_local <= forwarding_minimum):
        if(balance > forwarding_minimum and forwarding_addresses > 0):
            if(d.send(address, amount_to_send)):
                logger.info("Forwarded " + str(amount_to_send) +
                        " to address: " + address)
    else:
        logger.info("FORWARDING_KEEP_LOCAL is more than " +
                "FORWARDING_MINIMUM so no funds will be sent")

    # update exchange rate trying bitstamp first, then mtgox
    if(refreshcount % REFRESHES_TO_UPDATE_PRICE == 0):
        url = 'https://www.bitstamp.net/api/ticker/'
        try:
            r = requests.get(url)
            btcusd_rate = Decimal(str(r.json['ask']))
            usdbtc_rate = Decimal(1) / btcusd_rate
            update_exchange_rate(btcusd_rate, usdbtc_rate)
            logger.info("Updated (bitstamp) USDBTC to " +
                    str(usdbtc_rate) + " ( BTCUSD = " +
                    str(btcusd_rate) + " )")
        except Exception:
            logger.exception("Exchange rate update failed! (Bitstamp), " +
                    "Trying MtGox...")

            url = 'https://data.mtgox.com/api/2/BTCUSD/money/ticker'
            try:
                r = requests.get(url)
                btcusd_rate = Decimal(str(r.json['data']['buy']['value']))
                usdbtc_rate = Decimal(1) / btcusd_rate
                logger.info("Updated (mtgox) USDBTC to " +
                        str(usdbtc_rate) + " ( BTCUSD = " +
                        str(btcusd_rate) + " )")
            except Exception:
                logger.exception("Exchange rate update Failed! (MtGox)")

    refreshcount = refreshcount + 1
    sleep(REFRESH_PERIOD)
