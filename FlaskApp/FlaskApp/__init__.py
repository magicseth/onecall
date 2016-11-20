from flask import Flask, request, send_from_directory, redirect
from pyzipcode import ZipCodeDatabase
from twilio.rest import TwilioRestClient
from oct_utils import sqlSend, connectDB, disconnectDB, insertR, printall
import oct_constants
from oct_local import dir_path
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

def updatedb():
	# XXXREDIS
	# for hsh in ['issues', 'targets']:
	# 	if r.hget('refresh',hsh) !=0:
	# 		with open(dir_path+'/'+hsh+'.csv') as f:
	# 			csv_data = csv.reader(f)
	# 			for row in csv_data:
	# 				[r.hset(row[1],row[i*2],row[i*2+1]) for i in range(1,len(row)/2)]
	# 		r.hset('refresh',hsh, 0)
	# for sets in ['arenas',]:
	# 	if r.hget('refresh',sets) !=0:
	# 		with open(dir_path+'/'+sets+'.csv') as f:
	# 			csv_data = csv.reader(f)
	# 			for row in csv_data:
	# 				[r.sadd(row[1],row[i+2]) for i in range(1,len(row)-2)]
	# 		r.hset('refresh',sets, 0)
	return

@app.route("/")
def populatelanding():
	print printall()
	return app.send_static_file('landing.html')

@app.route("/db")
def dbdump():
	"""
	This DANGEROUS function prints to the browser window the entirety of the redis database
	"""
	return str(printall())

@app.route("/flush")
def flushdb():
	"""
	This XXX DANGEROUS function deletes all database content
	"""
	# XXXREDIS
	# r.flushall()
	return redirect('/')

@app.route('/registerNewUser', methods=['GET', 'POST'])
def registerNewUser():
	"""
	This function brings in 
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
