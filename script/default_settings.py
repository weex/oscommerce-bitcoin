#!/usr/bin/env python

#
#  settings.py - settings for simple merchant script 
#

#  OS Commerce database information
DBHOST = 'localhost'
DBUSER = ''
DBPASSWD = ''
DBNAME = 'oscommerce'


#  If a forwarding address is set, the script will send all bitcoins to
#  this address once 6 confirmations have elapsed.
FORWARDING_ADDRESS = ''

#  The path to the script without trailing slash
#    for example monitor.py would be at /path/to/this/script/monitor.py
#    if BASE_PATH = "/path/to/this/script"
BASE_PATH = "/path/to/this/script"   

#  The time in seconds to wait before checking bitcoind again.
REFRESH_PERIOD = 30
