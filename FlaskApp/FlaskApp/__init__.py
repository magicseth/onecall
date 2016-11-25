from flask import Flask, request, session, g, redirect, url_for, abort, \
     render_template, flash
from pyzipcode import ZipCodeDatabase
from twilio.rest import TwilioRestClient
from oct_constants import NULLNONE, ONEORNONE
from oct_utils import sqlpair, flatten2d, checkNull
from oct_local import dir_path, script_path
import csv
# import redis XXXREDIS
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

### Functions ###
def printall(): # Prints the entire database to the console window
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print '\n'*2
    print '='*100
    for t in tables:
        name = t[0]
        if name != 'sqlite_sequence':
            print 'Name: ', name
            cursor.execute("SELECT * FROM "+name)
            print 'Columns: ', [description[0] for description in cursor.description]
            print 'Data: ', cursor.fetchall()
	    print '-'*100
    return 

def insertR(table, r):
    """
    Standard insert method that uses the insertstr defined in each class
    call this from iinsert(..<class dependent field list>.) in each class
    Note - can pass record as parameters and will auto-convert to id.
    """
    insertstr = {
        "caller":"INSERT INTO caller VALUES (NULL,?,?,NULL,NULL)",
        "campaign": "INSERT INTO campaign VALUES (NULL,?,?,?,?,?)",
        "target": "INSERT INTO target VALUES (NULL,?,?,?,?)",
        "region": "INSERT INTO region VALUES (NULL,?,?)",
        "call": "INSERT INTO call VALUES (NULL,?,?,?)",
    }
    sqlSend(insertstr[table], r)  # Can throw sqlite3.IntegrityError if doesnt match constraint in table structure

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
    rr = curs.fetchall()
    return rr

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
	try:
		delta = ZipCodeDatabase()[zc].timezone
		# ZipCode object fields: zip, city, state, longitude, latitude, timezone, dst
	except:
		delta=0 # XXX This is invalid, as we won't call them on the right timezone
		# raise UserWarning('Invalid Zip') # do we need to make an actual error class?
	# time = str(int(request.form.get('hour'))-delta)+":"+request.form.get('minute')+" "+request.form.get('ampm') # use the zipcode to change the time to GMT
    #    #format(tn='callers', pn='phone', phonee=ph, z='zipcode',zipcode=zc))
	insertR('caller',[ph,zc])
	return redirect('./static/thanks.html')

@app.route("/findcallers")
def findcallers():
	"""
	This function is called by the cron to look for callers.
	"""
	now = "13:00 am"
	print find('caller', NULLNONE, id='1')
	# XXXREDIS
	# callers = [n for n in r.keys() if r.type(n)=='hash' and r.hget(n,'calltime')==now]
	# pairs = [[c,r.get(r.hget(c,'zipcode'))] for c in callers if r.get(r.hget(c,'zipcode'))]
	# print pairs
	# for c, t in pairs:
	# 	print c+" should call "+t+" and hear '"+r.hget(t,'bio')+"'."
	# XXX need to decide how to choose the content they will say to the target
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
