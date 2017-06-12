import os
import datetime
import pymongo
from bson.objectid import ObjectId
import logging

from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from flask_oauthlib.client import OAuth


# Setup logging
logging.basicConfig(filename="./log.log")

# Setup the databsae connection
client = pymongo.MongoClient()
db = client.freeStuffTagger

# Setup the Flask app
app = Flask(__name__)
app.config['GOOGLE_ID'] = os.environ["FREESTUFF_GOOGLE_ID"]
app.config['GOOGLE_SECRET'] = os.environ["FREESTUFF_GOOGLE_SECRET"]
app.debug = True
app.secret_key = os.environ["FREESTUFF_SECRET_KEY"]
oauth = OAuth(app)

# Setup OAuth
google = oauth.remote_app(
    'google',
    consumer_key=app.config.get('GOOGLE_ID'),
    consumer_secret=app.config.get('GOOGLE_SECRET'),
    request_token_params={
        'scope': ['email']
    },
    base_url='https://www.googleapis.com/oauth2/v1/',
    request_token_url=None,
    access_token_method='POST',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
)


@app.route('/')
def index():
#    if 'google_token' in session:
#        me = google.get('userinfo')
#        return render_template("test.html", data=me.data, messages=[])
#    return redirect(url_for('login'))
    return render_template("index.html")


@app.route('/login')
def login():
    return google.authorize(callback=url_for('authorized', _external=True))


@app.route('/logout')
def logout():
    session.pop('google_token', None)
    return redirect(url_for('index'))


@app.route('/login/authorized')
def authorized():
    resp = google.authorized_response()
    if resp is None:
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    session['google_token'] = (resp['access_token'], '')
    #me = google.get('userinfo')
    #return render_template("test.html", data=me.data, messages=[])
    return redirect(url_for('entries'))


@app.route('/entries')
def entries():
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    week_ago.replace(hour=0, minute=0, second=0, microsecond=0)
    entries = db.entries.find({"date": {"$gte": week_ago}}).sort([("date", -1)])
    return render_template("emails.html", entries=entries)


@app.route('/entries/delete', methods=['POST'])
def delete_entry():
    id = request.form["id"]
    result = db.entries.delete_one({'_id': ObjectId(id)})
    # TODO: Check the result of the delete
    return jsonify(success=True)

@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')


if __name__ == '__main__':
    app.run()
