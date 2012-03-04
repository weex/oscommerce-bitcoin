#!/usr/bin/env python

import sys,os,time
import MySQLdb
import re
import urllib
import urllib2
from time import sleep 
from pprint import pprint
from subprocess import Popen, PIPE, STDOUT;
from StringIO import StringIO
from decimal import *
import simplejson as json

# our configuration file - copy defaultsettings.py to settings.py and edit
from settings import * 

BASE_PATH = '/home/dsterry/code/osCommerce-Bitcoin-Payment-Module/script'

# setup logging
import logging
logger = logging.getLogger('osc-bitcoin-monitor')
hdlr = logging.FileHandler(BASE_PATH+'/monitor.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr) 
logger.setLevel(logging.INFO)

# Daemon - handles running bitcoind and getting results back from it
#
class Daemon :
	bitcoind_command  = ['bitcoind']

	def check(self):
		command = self.bitcoind_command[:]
		command.extend(['getgenerate'])
		p = Popen(command, stdout=PIPE)
		io = p.communicate()[0]
		if io.strip() != 'false':
			os.system("kill -9 `ps -ef | grep bitcoind | grep -v grep | awk '{print $2}'`")
			os.system("bitcoind &")
			logger.warning('Restarted bitcoind')
			sleep(60)

	def list_addresses(self):
		command = self.bitcoind_command[:]
		command.extend(['getaddressesbyaccount',''])
		p = Popen(command, stdout=PIPE)
		io = p.communicate()[0]
		return json.loads(io)

	def get_transactions(self,number):
		command = self.bitcoind_command[:]
		command.extend(['listtransactions','',str(number)])
		p = Popen(command, stdout=PIPE)
		io = p.communicate()[0]
		return json.loads(io)

	def get_receivedbyaddress(self,address,minconf):
		command = self.bitcoind_command[:]
		command.extend(['getreceivedbyaddress',address,str(minconf)])
		p = Popen(command, stdout=PIPE)
		io = p.communicate()[0]
		return json.loads(io)

	def send(self,address,amount):
		command = self.bitcoind_command[:]
		command.extend(['sendtoaddress',address,str(amount),'testing'])
		#print self.command
		p = Popen(command, stdout=PIPE)
		io = p.communicate()[0]
		return p.returncode  

class Sales :
	def __init__(self):
                self.db = MySQLdb.connect(host = DBHOST,user = DBUSER,passwd = DBPASSWD,db = DBNAME)
                self.cursor = self.db.cursor()

        def enter_deposits(self):
                d = Daemon()

		# get notification key
		c = self.db.cursor(cursorclass=MySQLdb.cursors.DictCursor)
		c.execute("SELECT configuration_value from configuration where configuration_key = 'MODULE_PAYMENT_BITCOIN_NOTIFICATION_KEY'")
		result = c.fetchone()
		notification_key = result['configuration_value']


		# get default orders status for a bitcoin payment
		c.execute("SELECT configuration_value from configuration where configuration_key = 'MODULE_PAYMENT_BITCOIN_ORDER_STATUS_ID'")
		result = c.fetchone()
		default_bitcoin_orders_status = int(result['configuration_value'])

		# 0 means default for OSC so we need to go deeper
		if( default_bitcoin_orders_status == 0 ):
			c.execute("SELECT configuration_value from configuration where configuration_key = 'DEFAULT_ORDERS_STATUS_ID'")
			result = c.fetchone()
			default_bitcoin_orders_status = int(result['configuration_value'])

		# get list of pending orders from osc with amounts and addresses
		c.execute("""SELECT orders.orders_id, comments, title, text 
				from (orders inner join orders_total on orders.orders_id = orders_total.orders_id) 
					inner join orders_status_history on orders.orders_id = orders_status_history.orders_id 
				where orders.orders_status = %d 
					and orders.payment_method like 'Bitcoin Payment' 
					and orders_total.title = 'Total:'"""
				 % (default_bitcoin_orders_status,) )
		orders = c.fetchall()		
		
		for order in orders:
			# get total out
			if "Total:" == order['title'] :
				t = re.search(r"\d+\.\d+",order['text'])
				if t:
					total = Decimal(t.group())
			
				# get address
				a = re.search(r"[A-Za-z0-9]{28,}",order['comments'])
				if a:
					address = a.group()

					print "Check for " + str(total) + " BTC to be sent to " + address
					print d.get_receivedbyaddress(address,0)
					if( d.get_receivedbyaddress(address,0) >= total ):
						# ping bpn.php which should be via ssl or through the same server
						
						url = OSC_URL + '/ext/modules/payment/bitcoin/bpn.php'
						values = {'bpn_key' : notification_key ,
							  'orders_id' : order['orders_id'] }
						data = urllib.urlencode(values)
						req = urllib2.Request(url, data)
						response = urllib2.urlopen(req)					
						#print "paid!"		

#                txlist = d.get_transactions(100)
 #               for tx in txlist:
  #                      if( tx['category'] != 'receive' ): continue
                        
			#print "%s %s %s" % (tx['txid'], tx['amount'], tx['confirmations'])
   #                     c.execute("""INSERT INTO deposit (txid, address, amount, created, confirmations)
 #                                                       VALUES ('%s','%s', %f, now(), %d)

#						ON DUPLICATE KEY UPDATE confirmations = %d"""
  #                                                                      % ( tx['txid'], tx['address'], tx['amount'], tx['confirmations'], tx['confirmations'], ) )
#			self.db.commit()


if __name__ == "__main__":
	logger.info("Started monitor script")

	d = Daemon()
	s = Sales()
#	while(1):
	d.check()

		# log all deposits
	s.enter_deposits()

	
		# check pending addresses
		#  since addresses will be reused, we want to make sure we do
		#  not mistakenly allow an old transaction to unlock a download
		#  if we assume all addresses in the pool have been used before
		#  then we are safe as long as we only check the last 
		#  address_count - pending_count transactions. We subtract 1 
		#  as a small cushion.
		#s.create_orders()

		#sleep(REFRESH_PERIOD)
