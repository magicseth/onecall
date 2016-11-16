from flask import Flask
import redis

app = Flask(__name__)

@app.route("/")
def hello():
    return "Hello, I love Digital Ocean!"

@app.route("/database")
def redisexample():
    r = redis.Redis('localhost')
    r.set('key', 'special_value')

    return r.get('key')








if __name__ == "__main__":
    app.run()


