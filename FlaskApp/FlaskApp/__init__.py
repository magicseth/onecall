from flask import Flask
import redis
import twilio.twiml

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello, I love Digital Ocean!"

@app.route("/database")
def redisexample():
    r = redis.Redis('localhost')
    r.set('key', 'special_value')

    return r.get('key')


@app.route("/callpaul", methods=['GET', 'POST'])
def hello_monkey():
    """Respond to incoming requests."""
    resp = twilio.twiml.Response()
    resp.say("It's time to call Jona")
    # Dial (310) 555-1212 - connect that number to the incoming caller.
    resp.dial("+16178432883")

    return str(resp)






if __name__ == "__main__":
    app.run()


