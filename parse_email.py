#!/usr/bin/env python3
import sys
import email
import email.utils
import pymongo
import datetime
import logging


def parse_email_timestamp(timestamp):
    date_tuple = email.utils.parsedate_tz(timestamp)
    date_time = email.utils.mktime_tz(date_tuple)
    return datetime.datetime.fromtimestamp(date_time)

# Setup logging
logging.basicConfig(filename="/var/tmp/freestuff.log")

# Setup the database connection
client = pymongo.MongoClient()
db = client.freeStuffTagger
emails = db.emails

# Read the email from stdin and parse it
email_input = sys.stdin.read()
msg = email.message_from_string(email_input)

# Parse the payload(s) from the message
payloads = []
if msg.is_multipart():
    for payload in msg.get_payload():
        payloads.append(payload.get_payload())
else:
    payloads = [msg.get_payload()]

# Format the data nicely for MongoDB
data = {
    "from": msg["from"],
    "to": msg["to"],
    "subject": msg["subject"],
    "payload": "\n".join(payloads),
    "date": parse_email_timestamp(msg["date"])
}

# Log some information to keep track of incoming messages
logging.info("Got email with subject: %s" % data["subject"])
email_id = emails.insert_one(data).inserted_id
logging.info("Inserted email into DB with ID: %s" % email_id)
