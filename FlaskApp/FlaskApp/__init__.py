from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash
from pyzipcode import ZipCodeDatabase
from urllib2 import Request, urlopen, URLError
from twilio.rest import TwilioRestClient
from oct_constants import NULLNONE, ONEORNONE, ACTIVE
from oct_utils import sqlpair, flatten2d, checkNull
from oct_local import dir_path, script_path
from datetime import datetime
from time import time
import csv
import json
import twilio.twiml
import os

import sqlite3

app = Flask(__name__)
# r = redis.Redis('localhost') XXXREDIS
execfile(os.path.join(dir_path, 'SECRETS.py'))

account_sid = os.environ['TWILIO_SID']
auth_token = os.environ['TWILIO_AUTH']

### DB Maintenance ###

def connect_db():
    databasefile = os.path.join(dir_path, 'onecall.sqlt')
    # The sqlite3.PARSE_DECLTYPES is so that a timestamp column will get parsed correctly.
    rv = sqlite3.connect(databasefile, detect_types=sqlite3.PARSE_DECLTYPES)
    rv.execute('pragma foreign_keys = on')
    # Dont wait for operating system http://www.sqlite.org/pragma.html#pragma_synchronous
    #http://web.utk.edu/~jplyon/sqlite/SQLite_optimization_FAQ.html#pragma-synchronous
    rv.execute('pragma synchronous = off')
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

def init_db():
    db = get_db()
    with app.open_resource('db.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

def populateTestDB():
	insertR('caller',['1000000000', '94107', '2016-11-26 13:00:00', 1])
	insertR('caller',['1000000001', '10001', '2016-11-26 13:00:00', 1])
	insertR('caller',['1000000002', '25443', '2016-11-26 14:00:00', 1])
	insertR('caller',['1000000003', '10001', '2016-11-26 13:00:00', 0])
	
	insertR('campaign',['Gun control is super important', 0, 1480153004+604800, 1000, 'legislatorLowerBody, legislatorUpperBody', 'Republican, Democratic'])
	insertR('campaign',['Civil rights are super important', 0, 1480153004+604800, 1000, 'legislatorLowerBody', 'Republican'])
	insertR('campaign',['Freedom of speech is super important', 1480153004+604800, 1480153004+604801, 1000, 'headOfState, deputyHeadOfGovernment', 'Republican'])

	insertR('call',[datetime.now(), '1', '1', '(202) 225-4965', 'Nancy Pelosi', 'United States House of Representatives CA-12'])
	insertR('call',[datetime.now(), '1', '2', '(202) 224-3553', 'Barbara Boxer', 'United States Senate'])


@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print 'Initialized the database.'

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
### URL Calls ###
def insertR(table, r, update=False):
    """
    Standard insert method that uses the insertstr defined in each class
    call this from iinsert(..<class dependent field list>.) in each class
    Note - can pass record as parameters and will auto-convert to id.
    """
    insertstr = {
        "caller":"INSERT INTO caller VALUES (NULL,?,?,?,?)",
        "campaign": "INSERT INTO campaign VALUES (NULL,?,?,?,?,?)",
        "target": "INSERT INTO target VALUES (NULL,?,?,?,?)",
        "region": "INSERT INTO region VALUES (NULL,?,?)",
        "call": "INSERT INTO call VALUES (NULL,?,?,?)",
    }
    if update and table=='caller':
    	c = find(table, ONEORNONE, phone=r[0])
    	if c:
    		idUpdateFields(table, c[0], phone=r[0], zipcode=r[1], calltime=r[2], active=r[3])
    		return c[0] # Return the ID of the object
	curs = sqlSend(insertstr[table], r)  # Can throw sqlite3.IntegrityError if doesnt match constraint in table structure
	return curs.lastrowid

def idUpdateFields(table, id, _skipNone=False, **kwargs):
    """
    Update Class[id][field]= newvalue for all (field, newvalue) in kwargs
    Note that kwargs values may be any subclass of Record and it should be logged appropriately
    """
    ## Note that keys and values are guaranteed to be same order, since the dict is not
    ## modified in between
    ## Take care here, because its valid to set tags to None, so absence of kwargs["tags"] is not same as it being None
    if isinstance(id,(list,tuple)) and len(id) == 0:
        return # Nothing to change - saves callers checking for empty list always
    if _skipNone:
        kwargs = {k:v for k,v in kwargs.items() if v}  # Ignore non None
    keys = kwargs.keys()
    values = kwargs.values()
    field_update = ", ".join("%s = ?" % k for k in keys)
    where,ids = sqlpair("id",id)
    updatesql = "UPDATE %s SET %s WHERE %s" % (table, field_update, where)
    values = values + ids
    # print "XXX@921", updatesql, values
    curs = sqlSend(updatesql, values)
    if curs.rowcount >0: pass
    else:
            raise Error("Failed to update - rowcount=%s sql=%s"
                    % (rowcount, updatesql))

def sqlSend(sql, parms=None):
    """
    Encapsulate most access to the sql server
    Send a sql string to a server, with parms if supplied

    sql: sql statement that may contain usual "?" characters
    parms[]: array or list of parameters to sql
    ERR: IntegrityError (FOREIGN KEY constraint failed)
    should catch database is locked errors and delay - may need to catch other errors but watch logs for them
    """
    db = get_db()
    retrytime = 0.001       # Start with 1mS, might be far too short
    while retrytime < 60: # Allows up to about 60 seconds of delay
        try:
            if parms is None:
                curs = db.execute(sql)
                db.commit()
            else:  # parms supplied as array
                curs = db.execute(sql, parms)
                db.commit()
        except sqlite3.OperationalError as e:
            if 'database is locked' not in str(e):
                break   # Drop out of loop and raise error
            time.sleep(retrytime)
            retrytime *= 2          # Try twice as long each iteration
        except Exception as e:
            break   # Drop out of loop and raise error
        else: # No exception
        	return curs
    raise e

def sqlFetch(sql, parms=None):
    """
    Encapsulate most access to the sql server
    Send a sql string to a server, with parms if supplied

    sql: sql statement that may contain usual "?" characters
    parms[]: array or list of parameters to sql

	returns array (possibly empty) of Rows (each of which behaves like a dict) as supplied by fetchall
	"""
	curs = sqlSend(sql, parms)  # Will always return -1 on SELECT
	dd = [dict((curs.description[i][0], value) \
               for i, value in enumerate(row)) for row in curs.fetchall()]
	return dd

def find(table, nullbehavior, _skipNone=False, **kwargs):
    """
    Generic find
    Searches a sql table, knows about "IS NULL" and tags.
    """
    # Preprocess vals
    keys,val1 = zip(*[sqlpair(key, val) for key,val in kwargs.iteritems() if not (_skipNone and val is None)])
    vals = flatten2d(val1)
    sql = "SELECT * FROM %s WHERE %s" % (table, " AND ".join(keys))
    return findAndCheckNull(sql,vals,"record matches fields", nullbehavior)

def findAndCheckNull(sql, parm, where, nullbehavior):
    """
    Do a SQL SELECT and
    Handle the generic nullbehavior based on the length of the retrieved obj
    sql is a SQL SELECT string to execute
    parm is array of parameters to sql
    where is the inner part of an error message
    nullbehavior controls behavior if field doesn't point to anything
    NULLERR Err 52; NULLNONE - return [ ]  -
    ONLYONE says only ok if exactly one found, and return that err 63 if >1 or 52 if none
    ONEORNONE says return obj if found, or None if not, err 63 if >1
    FINDERR - Err 51 if found
    All of these errors should be caught before the user sees them - 51 is (except in createNewAgent),
    52 and 63 still need tracing

    ERR 51,52,63

    Subclassed by Deal to handle subtypes
    """
    rr = sqlFetch(sql,parm)
    return checkNull(rr, where, nullbehavior)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
### URL Calls ###

@app.route("/")
def populatelanding():
	return app.send_static_file('landing.html')

@app.route("/dump")
def dumpdb():
	"""
	This DANGEROUS function prints to the browser window the entirety of the redis database
	"""
	print printall()
	return redirect('/')

@app.route("/flush")
def flushdb():
	"""
	This XXX DANGEROUS function deletes all database content
	"""
	os.system('flask initdb')
	return redirect('/')

@app.route('/registerNewUser', methods=['GET', 'POST'])
def registerNewUser():
	"""
	This function brings in a new user
	"""
	zc = request.form.get('zipcode')
	ph = request.form.get('phonenumber')
	ampm = int(request.form.get('ampm'))
	hh = int(request.form.get('hour'))
	mm = int(request.form.get('minute'))
	try:
		delta = ZipCodeDatabase()[zc].timezone
		# ZipCode object fields: zip, city, state, longitude, latitude, timezone, dst
	except:
		raise UserWarning('Invalid Zip') # do we need to make an actual error class?
	calltime = datetime.today().replace(hour=(ampm+hh-delta)%24, minute=mm, second=0, microsecond=0) # Everything stored in UTC timezone!
	insertR('caller',[ph,zc,calltime,ACTIVE],update=True)
	return redirect('./static/thanks.html')

@app.route("/findcallers")
def findcallers():
	"""
	This function is called by the cron to look for callers.
	"""
	now = datetime.now().replace(hour=13, minute=0) # replace is for testing only. Try hour=13 and hour=14 to see two test cases
	for c in find('caller', NULLNONE, calltime="%"+now.strftime(" %H:%M")+"%", active=ACTIVE):
		campaigns = listCampaigns(c)
		targets = listTargets(campaigns[0],c) if campaigns else []
		if targets: 
			print c['phone'], ' should call ', targets[0]['name'], ' of ', targets[0]['office'], ' at ', targets[0]['phones'], ' about ', campaigns[0]['message']
	return redirect('/')

@app.route("/callpaul", methods=['GET', 'POST'])
def hello_monkey():
    """Respond to incoming requests."""
    resp = twilio.twiml.Response()
    resp.say("It's time to call Jona")
    # Dial (310) 555-1212 - connect that number to the incoming caller.
    resp.dial("+16178432883")
    return str(resp)

@app.route("/textseth", methods=['GET'])
def text_seth():
	"Send a text message to seth"
	client = TwilioRestClient(account_sid, auth_token)
	message = client.messages.create(to="+16177107496", from_="+16179256394",
                                     body="Hello there!")
	return "success"



if __name__ == "__main__":
    app.run(debug=True) # Set debug=True so that saving this file automatically restarts the flask app
