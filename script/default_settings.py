#!/usr/bin/env python

#
#  settings.py - settings for simple merchant script 
#

#  The path to the script with trailing slash
#    for example monitor.py would be at /path/to/this/script/monitor.py
#    if BASE_PATH = "/path/to/this/script/"
BASE_PATH = "/path/to/this/script/"   


#
#  OS Commerce section
#

#  Database information
DBHOST = 'localhost'
DBUSER = ''
DBPASSWD = ''
DBNAME = 'oscommerce'

#  url to osCommerce installation without trailing slash, https is STRONGLY ENCOURAGED
#  if this script will be sending requests across untrusted network connections
#  (i.e. the Internet)
OSC_URL = 'http://localhost/oscommerce/catalog'


#
#  Bitcoin section
#

#  Minimum confirmations to consider a payment received
MINCONF = 6

#  The time in seconds to wait between attempts to process incoming payments
#  With each confirmation taking on average 10 minutes, settings this to
#  MINCONF * 150 is reasonable (25% of expected confirmation time).
REFRESH_PERIOD = 900

#  How often to update exchange rate as a multiple of REFRESH_PERIOD. For 
#  example, if REFRESH_PERIOD is 900 (15 minutes), setting this to 4 will
#  cause the exchange rate to be updated hourly.
REFRESHES_TO_UPDATE_PRICE = 4

#  If a forwarding address is set, the script will send all bitcoins to
#  this address once 6 confirmations have elapsed.
FORWARDING_ADDRESS = ''

#  This script will only forward payments if more than this amount has been received
FORWARDING_MINIMUM = 1

#  Leave this amount on this machine
FORWARDING_KEEP_LOCAL = 0

#  The transaction fee specified in your bitcoin settings
TRANSACTION_FEE = 0
