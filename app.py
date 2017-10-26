import os
import datetime
import pymongo
from bson.objectid import ObjectId
import logging

from flask import Flask, redirect, url_for, session, request, jsonify, render_template
from flask_oauthlib.client import OAuth
from flask_login import LoginManager, login_user, logout_user, login_required, current_user

from werkzeug.security import check_password_hash

class User():
    def __init__(self, email, last_login):
        self.email = email
        self.last_login = last_login

    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.email

    @staticmethod
    def validate_login(password_hash, password):
        return check_password_hash(password_hash, password)



# Setup logging
logging.basicConfig(filename="./log.log")

# Setup the databsae connection
client = pymongo.MongoClient()
db = client.freeStuffTagger

# Setup the Flask app
app = Flask(__name__)
app.config['GOOGLE_ID'] = os.environ["FREESTUFF_GOOGLE_ID"]
app.config['GOOGLE_SECRET'] = os.environ["FREESTUFF_GOOGLE_SECRET"]
app.config['GOOGLE_API_SERVER_KEY'] = os.environ["FREESTUFF_GOOGLE_API_SERVER_KEY"]
app.config['GOOGLE_API_CLIENT_KEY'] = os.environ["FREESTUFF_GOOGLE_API_CLIENT_KEY"]
app.secret_key = os.environ["FREESTUFF_SECRET_KEY"]
app.debug = True # TODO: Disable in production
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

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(userid):
    u = db.users.find_one({"email": userid})
    if not u:
        return None
    return User(u["email"], u["last_login"])


@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('index'))


@google.tokengetter
def get_google_oauth_token():
    return session.get('google_token')


@app.route('/login/authorized')
@google.authorized_handler
def authorized(resp):
    #resp = google.authorized_response()
    if resp is None:
        # TODO: More secure error response
        return 'Access denied: reason=%s error=%s' % (
            request.args['error_reason'],
            request.args['error_description']
        )
    session['google_token'] = (resp['access_token'], '')
    user_data = google.get('userinfo').data
    user_data["last_login"] = datetime.datetime.now()
    db.users.update_one({"email": user_data["email"]}, {"$set": user_data}, upsert=True)
    u = db.users.find_one({"email": user_data["email"]})
    login_user(User(u["email"], u["last_login"]))
    return redirect(url_for('entries'))


@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for("entries"))
#    if 'google_token' in session:
#        me = google.get('userinfo')
#        return render_template("test.html", data=me.data, messages=[])
#    return redirect(url_for('login'))
    return render_template("index.html")


@app.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('entries'))
    return google.authorize(callback=url_for('authorized', _external=True))


@app.route('/logout')
@login_required
def logout():
    session.pop('google_token', None)
    logout_user()
    return redirect(url_for('index'))


@app.route('/entries')
@login_required
def entries():
    week_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    week_ago.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago_entries = db.entries.find({"date": {"$gte": week_ago}}).sort([("date", -1)])

    user = db.users.find_one({"email": current_user.email})
    if "last_data_view" in user:
        # TODO: If the previous last login was greater than a week ago don't search for it, just default to the last week of entries
        since_last_view_entries = db.entries.find({"date": {"$gte": user["last_data_view"]}}).sort([("date", -1)])
    user["last_data_view"] = datetime.datetime.now()
    db.users.update_one({"email": user["email"]}, {"$set": user}, upsert=True)

    return render_template("entries.html", entries=week_ago_entries, GOOGLE_MAPS_API_KEY=app.config["GOOGLE_API_CLIENT_KEY"])


@app.route('/entries/delete', methods=['POST'])
@login_required
def delete_entry():
    id = request.form["id"]
    #result = db.entries.delete_one({'_id': ObjectId(id)})
    # TODO: Don't actually delete it, just archive it
    # TODO: Check the result of the delete
    return jsonify(success=True)


@app.route('/entries/viewed', methods=['POST'])
@login_required
def entry_viewed():
    id = request.form["id"]
    result = db.entries.update_one({'_id': ObjectId(id)}, {"$set": { "viewed": True }})
    # TODO: Check the result of the update
    return jsonify(success=True)


if __name__ == '__main__':
    app.run()
