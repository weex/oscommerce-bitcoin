#!/usr/bin/env python

#
#  settings.py - settings for simple merchant script 
#

#  osCommerce database information
DBHOST = 'localhost'
DBUSER = ''
DBPASSWD = ''
DBNAME = 'oscommerce'

#  url to osCommerce installation without trailing slash, https is STRONGLY ENCOURAGED
#  if this script will be sending requests across untrusted network connections
#  (i.e. the Internet)
OSC_URL = 'http://localhost/oscommerce/catalog'

#  If a forwarding address is set, the script will send all bitcoins to
#  this address once 6 confirmations have elapsed.
FORWARDING_ADDRESS = ''

#  The path to the script without trailing slash
#    for example monitor.py would be at /path/to/this/script/monitor.py
#    if BASE_PATH = "/path/to/this/script"
BASE_PATH = "/path/to/this/script"   

#  The time in seconds to wait before checking bitcoind again.
REFRESH_PERIOD = 30
