from flask import Flask, request, session, g, redirect, url_for, \
	render_template, send_from_directory
from functools import wraps
from pyzipcode import ZipCodeDatabase
from passlib.apps import custom_app_context as pwd_context
from urllib2 import Request, urlopen, URLError
from twilio.rest import TwilioRestClient
from oct_constants import NULLNONE, ONEORNONE, ONLYONE, ACTIVE
from oct_utils import sqlpair, flatten2d, checkNull
from oct_local import dir_path
from datetime import datetime, timedelta
from time import time
import csv
import json
import twilio.twiml
import os
import re
import sqlite3

app = Flask(__name__)
app.config.from_object(__name__)
# Load default config and override config from an environment variable
app.config.update({
	'DATABASE': os.path.join(app.root_path, 'onecall.sqlt'),
	'SECRET_KEY':'development key',
	})

execfile(os.path.join(dir_path, 'SECRETS.py'))

account_sid = os.environ['TWILIO_SID']
auth_token = os.environ['TWILIO_AUTH']


### CLASSES ###
class DisplayError(Exception):
	def __init__(self, message, html, payload=None):
		Exception.__init__(self)
		self.message = message
		self.html = html
		self.payload = payload

	def to_dict(self):
		rv = dict(self.payload or ())
		rv['message'] = self.message
		rv['html'] = self.html
		return rv

@app.errorhandler(DisplayError)
def handle_error_for_display(error):
	response = error.to_dict()
	return render_template(response['html'], error = response['message'])

def must_login():
	def wrapper(f):
		@wraps(f)
		def wrapped(*args, **kwargs):
			if not session.get('logged_in'):
				raise DisplayError("Must be logged in to execute this action", 'login.html')
			return f(*args, **kwargs)
		return wrapped
	return wrapper

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
	insertR('login',[None, 'admin', encrypt('admin')])

	insertR('caller',[None, formatphonenumber('1000000000'), '94107', '2016-11-26 13:00:00', 1])
	insertR('caller',[None, formatphonenumber('1000000001'), '10001', '2016-11-26 13:00:00', 1])
	insertR('caller',[None, formatphonenumber('1000000002'), '25443', '2016-11-26 14:00:00', 1])
	insertR('caller',[None, formatphonenumber('1000000003'), '10001', '2016-11-26 13:00:00', 0])
	insertR('caller',[None, formatphonenumber('1000000003'), '10002', '2016-11-26 13:00:00', 0],'landing.html')

	insertR('campaign',[None, 'Sample script: Hello, my name is John or Jane Smith and I\'m calling from ABC organization in PDQ state regarding XYZ issue. Gun control is super important', 0, int(time()+604800, 1000, 'legislatorLowerBody, legislatorUpperBody', 'Republican, Democratic', None, None])
	insertR('campaign',[None, 'Civil rights are super important', 0, int(time())+604800, 1000, 'legislatorLowerBody', 'Republican', None, None])
	insertR('campaign',[None, 'Freedom of speech is super important', int(time())+604800, int(time())+604801, 1000, 'headOfState, deputyHeadOfGovernment', 'Republican', None, None])
	insertR('campaign',[None, 'Calling Jona is super important', 0, int(time())+604800, 1000, 'Office of Important Matters', None, 'Jona Raphael', formatphonenumber('16178432883')])

	insertR('call',[None, datetime.now(), '1', '1', formatphonenumber('(202) 225-4965'), 'Nancy Pelosi', 'United States House of Representatives CA-12'])
	insertR('call',[None, datetime.now(), '1', '2', formatphonenumber('(202) 224-3553'), 'Barbara Boxer', 'United States Senate'])


@app.cli.command('initdb')
def initdb_command():
	"""Initializes the database."""
	init_db()
	print 'Initialized the database.'
	populateTestDB()

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
	update = True If we want to write over existing entries rather than create a new one. Note that there is a uniqueness constraint on the caller.phone.
	"""
	insertstr = {
		"caller":"INSERT INTO caller VALUES (NULL,?,?,?,?)",
		"campaign": "INSERT INTO campaign VALUES (NULL,?,?,?,?,?,?,?,?)",
		"call": "INSERT INTO call VALUES (NULL,?,?,?,?,?,?)",
		"login": "INSERT INTO login VALUES (NULL,?,?)",
	}
	if update and table=='caller': # Enforce uniqueness on caller phone numbers
		c = find(table, ONEORNONE, phone=r[1])
		if c:
			r[0] = c['id'] # Note ignores provided Replace Existing ID if a row is found with the same phone number
	if r[0]>0: # If a valid ID is provided, try looking it up
		existr = find(table, ONEORNONE, id=r[0])
		if existr: # Found a row with that ID
			cols = sqlSend('select * from '+table).fetchone().keys() # Get the column order for the table
			newr = dict(zip(cols[1:], r[1:])) # Align and create a dictionary of the provided array and the column names
			idUpdateFields(table, r[0], **newr)
			return r[0]
	curs = sqlSend(insertstr[table], r[1:])  # Can throw sqlite3.IntegrityError if doesnt match constraint in table structure
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
		raise Error("Failed to update - rowcount=%s sql=%s" % (rowcount, updatesql))

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
	retrytime = 0.001	   # Start with 1mS, might be far too short
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
			retrytime *= 2		  # Try twice as long each iteration
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
	dd = sqlFetch(sql,parm)
	return checkNull(dd, where, nullbehavior)

#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
### Functions ###

def printall(): # Prints the entire database to the console window
	db = get_db()
	cursor = db.cursor()
	cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
	tables = cursor.fetchall()
	text = '<br>'*2
	for t in tables:
		name = t[0]
		if name != 'sqlite_sequence':
			text = text+'<br>'+'Name: '+name+'<br>'
			cursor.execute("SELECT * FROM "+name)
			text = text+'Columns: '+'<br>'+' | '.join([description[0] for description in cursor.description])+'<br>'
			text = text+'Data: '+'<br>'+'<br>'.join([' | '.join([str(f) for f in row]) for row in cursor.fetchall()])+'<br>'
		text = text+'-'*100
	return text

def getCivicData(address):
	# https://developers.google.com/civic-information/docs/v2/representatives/representativeInfoByAddress
	# https://developers.google.com/civic-information/docs/v2/representatives#resource
	# https://developers.google.com/resources/api-libraries/documentation/civicinfo/v2/python/latest/civicinfo_v2.representatives.html#representativeInfoByAddress
	civicapikey = 'AIzaSyCjQMFoXcL1iO6eX_ixCZ1uDLJeqUttQMU' # from https://console.developers.google.com/apis/library?project=one-call-today-1480143256556
	url = 'https://www.googleapis.com/civicinfo/v2/representatives?address='+str(address)+'&alt=json&key='+civicapikey
	req = Request(url)
	try:
		response = urlopen(req)
	except URLError as e:
		if hasattr(e, 'reason'):
			raise DisplayError(e.reason, 'landing.html')
		elif hasattr(e, 'code'):
			raise DisplayError("The server couldn't fulfill the request", 'landing.html')
		return None  # Error
	else: # everything is fine
		return json.loads(response.read().decode('utf8'))

def listTargets(campaign, caller):
	"""
	Takes in a campaign and address, and suggests who should be called with phone numbers in the form:
	{u'Joe Manchin III': [u'(202) 224-3954'], u'Shelley Moore Capito': [u'(202) 224-6472', u'(304) 347-5372', u'(304) 262-9285']}
	"""
	targets = []
	if campaign['targetname'] and campaign['targetphone']:
		targets = [{'name':campaign['targetname'], 'phones':[campaign['targetphone']], 'office': campaign['offices'] or 'N/A'}]
	else:
		cd = getCivicData(caller['zipcode'])
		officialsenum = [(k['officialIndices'],k['name']) for k in cd['offices'] if ('roles' in k) and ([i for i in k['roles'] if i in campaign['offices']])]
		for indices,office in officialsenum:
			for i in indices:
				if ('phones' in cd['officials'][i]) and (cd['officials'][i]['party'] in campaign['targetparties']):
					targets = targets+[{'name':cd['officials'][i]['name'], 'phones':[formatphonenumber(ph) for ph in cd['officials'][i]['phones']], 'office':office}]
	return targets

def listCampaigns(caller):
	"""
	Takes in a caller, returns a list of campaign dicts that the caller has NOT yet called about, but which are ongoing right now.
	"""
	calls = [call['campaignid'] for call in find('call', NULLNONE, callerid=caller['id'])]
	return [camp for camp in find('campaign', NULLNONE, id='%%', startdate='< '+str(time()), enddate='> '+str(time())) if camp['id'] not in calls]

def caller(id, nullbehavior=ONLYONE):
	"""
	Takes an ID, returns a dict object from the corresponding database row
	Default is ONLYONE: will ERROR if no object found.
	Set to nullbehavior to ONEORNONE if you want return None instead of erroring
	"""
	return find('caller', nullbehavior, id=id)

def call(id, nullbehavior=ONLYONE):
	"""
	Takes an ID, returns a dict object from the corresponding database row
	Default is ONLYONE: will ERROR if no object found.
	Set to nullbehavior to ONEORNONE if you want return None instead of erroring
	"""
	return find('call', nullbehavior, id=id)

def campaign(id, nullbehavior=ONLYONE):
	"""
	Takes an ID, returns a dict object from the corresponding database row
	Default is ONLYONE: will ERROR if no object found.
	Set to nullbehavior to ONEORNONE if you want return None instead of erroring
	"""
	return find('campaign', nullbehavior, id=id)

def formatphonenumber(ph, raiseerr=False):
	num = re.sub("\D", "", str(ph))
	if len(num) == 10:
		num = "+1"+num
	elif len(num) == 11 and num[0] == "1":
		num = "+"+num
	elif raiseerr:
		raise DisplayError("Invalid phone number", raiseerr)
	return num

def checkpw(username, password):
	# Check a password against previously generated hash
	user = find('login', ONEORNONE, username=username)
	if user is None:
		raise DisplayError("Unrecognized Username", 'login.html')

	if password is None:
		raise DisplayError("Password required", 'login.html')

	ver = pwd_context.verify(password, user['passhash'])
	if ver is False:
		raise DisplayError("Password not recognized",'login.html')
	return True

def encrypt(password):
	"""
	Hash the password before storing in the database
	"""
	return None if password is None else pwd_context.encrypt(password)


#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
### URL Calls ###

@app.route("/")
def populatelanding():
	if not session.get('logged_in'):
		return render_template('landing.html')
	else:
		return render_template('dashboard.html')

@app.route("/login")
def login():
	if not session.get('logged_in'):
		return render_template('login.html')
	else:
		return render_template('dashboard.html')

@app.route('/checkLogin', methods=['GET', 'POST'])
def checkLogin():
	if checkpw(request.form['username'], request.form['password']): # Will raise DisplayError if fails
		session['logged_in'] = True
		return redirect('/dashboard')

@app.route("/dashboard")
@must_login()
def dashboard():
	return render_template('dashboard.html')

@app.route('/logout')
def logout():
	session.pop('logged_in', None)
	return render_template('landing.html')

@app.route("/dump")
@must_login()
def dumpdb():
	"""
	This DANGEROUS function prints to the browser window the entirety of the redis database
	"""
	print printall().replace("<br>", "\n")
	return printall()

@app.route("/flush")
@must_login()
def flushdb():
	"""
	This XXX DANGEROUS function deletes all database content
	"""
	os.system('cp -n onecall.sqlt ./backups/onecall_flushed_'+datetime.now().strftime('%Y-%m-%d')+'.sqlt') # copy to backup file
	os.system('flask initdb')
	return redirect('/dashboard')

@app.route("/backup")
@must_login()
def backup():
	"""
	This backsup all database content
	"""
	os.system('cp -f onecall.sqlt ./backups/onecall_'+datetime.now().strftime('%Y-%m-%d')+'.sqlt') # copy to backup file
	return redirect('/dashboard')

@app.route("/downloaddb")
@must_login()
def downloaddb():
	"""
	This downloads all database content for local testing
	"""
	return send_from_directory(directory='.', filename='onecall.sqlt')

@app.route('/registerNewUser', methods=['GET', 'POST'])
def registerNewUser():
	"""
	This function brings in a new user
	"""
	if request.form.get('callerid'): 
		callerid = int(request.form.get('callerid'))
	else: 
		callerid = None
	zc = request.form.get('zipcode')
	ph = formatphonenumber(request.form.get('phonenumber'),'landing.html')
	ampm = int(request.form.get('ampm'))
	hh = int(request.form.get('hour'))
	mm = int(request.form.get('minute'))
	try:
		delta = ZipCodeDatabase()[zc].timezone
		# ZipCode object fields: zip, city, state, longitude, latitude, timezone, dst
	except:
		raise DisplayError("Unrecognized Zipcode", 'landing.html')
	calltime = datetime.today().replace(hour=(ampm+hh-delta)%24, minute=mm, second=0, microsecond=0) # Everything stored in UTC timezone!
	insertR('caller',[callerid,ph,zc,calltime,ACTIVE],update=True)
	return render_template('thanks.html')

@app.route('/registerNewCampaign', methods=['GET', 'POST'])
@must_login()
def registerNewCampaign():
	"""
	This function brings in a new campaign
	"""
	if request.form.get('campaignid'): 
		campaignid = int(request.form.get('campaignid'))
	else: 
		campaignid = None	
	message = request.form.get('message')
	startdate = int(time())+int(request.form.get('startdate') or 0)*24*60*60 # Defaults campaign start date to right now
	enddate = startdate+int(request.form.get('enddate') or 30)*24*60*60 # Defaults campaign lifespan to 30 days
	callobjective = int(request.form.get('callobjective') or 1000)  # Defaults to 1000 call objective
	offices = ', '.join(request.form.getlist('offices[]'))
	targetparties = ', '.join(request.form.getlist('targetparties[]'))
	
	required = 'dashboard.html' if (offices=='' or targetparties=='') else False # If there is no office or party selected, then it must be a targeted campaign
	targetname = request.form.get('targetname')
	targetphone = formatphonenumber(request.form.get('targetphone'), raiseerr=required)

	if required and (targetname==''): # Must be a targeted campaign, but no name provided
		raise DisplayError("Name required for targeted campaigns", 'dashboard.html')

	insertR('campaign',[campaignid,message,startdate,enddate,callobjective,offices,targetparties,targetname,targetphone])
	return render_template('thanks.html')

@app.route('/registerNewLogin', methods=['GET', 'POST'])
@must_login()
def registerNewLogin():
	"""
	This function brings in a new login (admin level until permissions are defined)
	"""
	username = request.form.get('username')
	password = request.form.get('password')
	if (username=='') or (password==''): 
		raise DisplayError("Both Username and Password required", 'dashboard.html')

	insertR('login',[None,username, encrypt(password)])
	return render_template('thanks.html')

@app.route('/editTableValue', methods=['GET', 'POST'])
@must_login()
def editTableValue():
	"""
	This function edits a single table:field:value
	"""
	table = request.form.get('table')
	id = request.form.get('id')
	field = request.form.get('field')
	value = request.form.get('value')
	if (table=='') or (id=='') or (field==''): 
		raise DisplayError("Table, ID, and Field all required", 'dashboard.html')
	if (value==''):
		value = None
	if table=='login':
		value = encrypt(value)
	if field in ['id','calltime','tstamp']:
		raise DisplayError("ID, Calltime, and Tstamp are not supported yet", 'dashboard.html')

	idUpdateFields(table, id, **{field:value})
	return render_template('thanks.html')

@app.route('/thanks')
def thanksredirect():
	if not session.get('logged_in'):
		return redirect('/')
	else:
		return redirect('/dashboard')

@app.route("/findcallers")
@must_login()
def findcallers():
	"""
	This function is called by the cron to look for callers. 
	It takes no arguments, but searches the entire caller database for anyone who wants to be called at the current timestamp.
	It then finds all the campaigns a caller hasn't yet called
	It then finds all the targets for those campaigns
	Finally, it prints the results to screen (XXX SHOULD execute call instead)
	"""
	now = datetime.now().replace(hour=13, minute=0)+timedelta(1) # replace is for testing only. Try hour=13 and hour=14 to see two test cases
	text = str(now)+'<br>'
	for c in find('caller', NULLNONE, calltime="%"+now.strftime(" %H:%M")+"%", active=ACTIVE):
		campaigns = listCampaigns(c)
		for campaign in campaigns:
			targets = listTargets(campaign,c) if campaigns else []
			for target in targets: 
				text = text+ c['phone']+' should call '+target['name']+' of '+target['office']+' at '+' or '.join(target['phones'])+' about '+campaign['message']+'<br>'
	text = text+"NO MORE CALLS TO BE MADE"+'<br>'
	print text.replace("<br>", "\n")
	return text

@app.route("/callpaul", methods=['GET', 'POST'])
@must_login()
def hello_monkey():
	"""Respond to incoming requests."""
	resp = twilio.twiml.Response()
	resp.say("It's time to call Jona")
	# Dial (310) 555-1212 - connect that number to the incoming caller.
	resp.dial("+16178432883")
	return str(resp)

@app.route("/textseth", methods=['GET'])
@must_login()
def text_seth():
	"Send a text message to seth"
	client = TwilioRestClient(account_sid, auth_token)
	message = client.messages.create(to="+16177107496", from_="+16179256394",
									 body="Hello there!")
	return "success"

@app.route("/campaignseth", methods=['GET'])
def start_campaign():
	# XXXSETH how do we protect our twilio service from being accessed by arbitrary calls to our exposed functions?
	# XXXSETH this is currently calling me and saying "we are sorry an application error has occured, goodbye"
	# XXXSETH we need to be careful--this can accidentally be run on dev platform during testing or debug and it will make the actual calls... When live, it will be important to make it only execute calls from the actual live server.
	campaignid = 1
	callerid = 1
	# caller = caller(callerid)

	client = TwilioRestClient(account_sid, auth_token)
	call = client.calls.create(to="(617)7107496",  # Any phone number
		from_="+16179256394 ", # Must be a valid Twilio number
		if_machine="Hangup",
		url="http://onecall.today/callscript?campaignid=" + str(campaignid) + "&callerid=" + str(callerid))
	return(call.sid)

@app.route("/callscript", methods=['GET'])
def callscript():
	# XXXSETH this function needs to only respond if the request is coming from TWILIO
	camp = campaign(request.args.get('campaignid'))
	clr = caller(request.args.get('callerid'))
	targets = listTargets(camp, clr) # XXXSETH is it possible to connect to the next target (same campaign) if the caller presses '#'?
	resp = twilio.twiml.Response()
	resp.say(camp['message'],voice='woman')
	resp.pause(length="1")
	if targets:
		resp.say("If you'd like to be connected to " + targets[0]['name'] +" remain on the line")
		resp.pause(length="4")
		# Dial (310) 555-1212 - connect that number to the incoming caller.
		resp.say("Connecting you to " + targets[0]['name'] + ' of ' + targets[0]['office'])
		resp.dial(targets[0]['phones'][0])
		insertR('call',[None,datetime.now(),clr['id'],camp['id'],targets[0]['phone'],targets[0]['name'],targets[0]['office'],])
	else:
		# XXX The campaign should not get this far, if the caller has no targets for it.
		resp.say("Sorry we couldn't find anyone in your area to call about today's campaign. We'll try again tomorrow with another issue!")		

	return str(resp)
	# return ("campaign " + str(camp) )


if __name__ == "__main__":
	app.run(debug=True) # Set debug=True so that saving this file automatically restarts the flask app
