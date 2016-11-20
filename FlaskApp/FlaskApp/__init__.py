from flask import Flask, request, send_from_directory, redirect
from pyzipcode import ZipCodeDatabase
from twilio.rest import TwilioRestClient
import csv
import redis
import twilio.twiml
import os

import sqlite3

app = Flask(__name__)
r = redis.Redis('localhost')
dir_path = os.path.dirname(os.path.realpath(__file__))

execfile(os.path.join(dir_path, 'SECRETS.py'))



account_sid = os.environ['TWILIO_SID']
auth_token = os.environ['TWILIO_AUTH']

def updatedb():
	for hsh in ['issues', 'targets']:
		if r.hget('refresh',hsh) !=0:
			with open(dir_path+'/'+hsh+'.csv') as f:
				csv_data = csv.reader(f)
				for row in csv_data:
					[r.hset(row[1],row[i*2],row[i*2+1]) for i in range(1,len(row)/2)]
			r.hset('refresh',hsh, 0)
	for sets in ['arenas',]:
		if r.hget('refresh',sets) !=0:
			with open(dir_path+'/'+sets+'.csv') as f:
				csv_data = csv.reader(f)
				for row in csv_data:
					[r.sadd(row[1],row[i+2]) for i in range(1,len(row)-2)]
			r.hset('refresh',sets, 0)
	return
	

@app.route("/")
def populatelanding():
	#updatedb() # XXX This should not happen here, but is placed to trigger frequently for now
	return app.send_static_file('landing.html')

@app.route("/db")
def dbdump():
	"""
	This DANGEROUS function prints to the browser window and terminal the entirety of the redis database
	"""
	strings = str([(k, r.get(k)) for k in r.keys() if r.type(k)=='string'])
	hashes = str([(k, r.hgetall(k)) for k in r.keys() if r.type(k)=='hash'])
	lists = str([(k, r.lrange(k,0,-1)) for k in r.keys() if r.type(k)=='list'])
	sets = str([(k, r.smembers(k)) for k in r.keys() if r.type(k)=='set'])
	return "Strings:<br>"+strings+"<br><br>Hashes:<br>"+hashes+"<br><br>Lists:<br>"+lists+"<br><br>Sets:<br>"+sets

@app.route("/flush")
def flushdb():
	"""
	This XXX DANGEROUS function deletes all database content
	"""
	r.flushall()
	return redirect('/')

@app.route('/registerNewUser', methods=['GET', 'POST'])
def registerNewUser():
	"""
	This function brings in 
	"""
	conn = sqlite3.connect(os.path.join(dir_path, 'onecall.sqlt'))
	c = conn.cursor()
	zc = request.form.get('zipcode')
	ph = request.form.get('phonenumber')
	try:
		delta = ZipCodeDatabase()[zc].timezone
	except:
		delta=0 # XXX This is invalid, as we won't call them on the right timezone
		# raise UserWarning('Invalid Zip') # do we need to make an actual error class?
	# time = str(int(request.form.get('hour'))-delta)+":"+request.form.get('minute')+" "+request.form.get('ampm') # use the zipcode to change the time to GMT
	
	c.execute("INSERT OR REPLACE INTO callers (phone, zipcode) values(?,?)", (ph,zc))
    #    #format(tn='callers', pn='phone', phonee=ph, z='zipcode',zipcode=zc))
	conn.commit()
	conn.close()
	return redirect('./static/thanks.html')

@app.route("/findcallers")
def findcallers():
	"""
	This function is called by the cron to look for callers.
	"""
	now = "13:00 am"
	callers = [n for n in r.keys() if r.type(n)=='hash' and r.hget(n,'calltime')==now]
	pairs = [[c,r.get(r.hget(c,'zipcode'))] for c in callers if r.get(r.hget(c,'zipcode'))]
	print pairs
	for c, t in pairs:
		print c+" should call "+t+" and hear '"+r.hget(t,'bio')+"'."
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
