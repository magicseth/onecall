from flask import Flask, request, send_from_directory, redirect
from pyzipcode import ZipCodeDatabase
import csv
import redis
import twilio.twiml

app = Flask(__name__)
r = redis.Redis('localhost')
if not r.get('loaded')=='True':
	with open('./issues.csv') as f:
		csv_data = csv.reader(f)
		for row in csv_data:
			[r.hset(row[1],row[i*2],row[i*2+1]) for i in range(1,len(row)/2)]
	r.set('loaded', 'True')

@app.route("/")
def populatelanding():
	return app.send_static_file('landing.html')

@app.route("/hi")
def hello():
    return "Hello, I love Digital Ocean!"

@app.route("/db")
def dbdump():
	strings = str([(k, r.get(k)) for k in r.keys() if r.type(k)=='string'])
	hashes = str([(k, r.hgetall(k)) for k in r.keys() if r.type(k)=='hash'])
	lists = str([(k, r.lrange(k,0,-1)) for k in r.keys() if r.type(k)=='list'])
	sets = str([(k, r.smembers(k)) for k in r.keys() if r.type(k)=='set'])
	return strings+hashes+lists+sets

@app.route("/flush")
def flushdb():
	r.flushall()
	return redirect('/')

@app.route('/registerNewUser', methods=['GET', 'POST'])
def registerNewUser():
	zc = request.form.get('zipcode')
	ph = request.form.get('phonenumber')
	try:
		delta = ZipCodeDatabase()[zc].timezone
	except:
		delta=0 # This is invalid, as we won't call them on the right timezone
		# raise UserWarning('Invalid Zip') # do we need to make an actual error class?
	time = str(int(request.form.get('hour'))-delta)+":"+request.form.get('minute')+" "+request.form.get('ampm') # use the zipcode to change the time to GMT
	r.hset(ph,'zipcode',zc)
	r.hset(ph,'calltime',time)
	return redirect('/')

@app.route("/callpaul", methods=['GET', 'POST'])
def hello_monkey():
    """Respond to incoming requests."""
    resp = twilio.twiml.Response()
    resp.say("It's time to call Jona")
    # Dial (310) 555-1212 - connect that number to the incoming caller.
    resp.dial("+16178432883")

    return str(resp)







if __name__ == "__main__":
    app.run(debug=True) # Set debug=True so that saving this file automatically restarts the flask app