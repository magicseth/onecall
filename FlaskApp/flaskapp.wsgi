#!/usr/bin/python
import sys
import logging
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,"/var/home/onecall/FlaskApp/")

from FlaskApp import app as application
application.secret_key = 'Add your secret key'

