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

def parse_email_tags(payload):
    tags = []
    if "chair" in payload.lower():
        tags.append("chair")
        tags.append("furniture")
    if "sofa" in payload.lower() or "couch" in payload.lower():
        tags.append("sofa")
        tags.append("couch")
        tags.append("furniture")
    if "table" in payload.lower():
        tags.append("table")
        tags.append("furniture")
    if "ikea" in payload.lower():
        tags.append("ikea")
    if "shelf" in payload.lower():
        tags.append("shelf")
        tags.append("furniture")
    if "love seat" in payload.lower():
        tags.append("love seat")
        tags.append("furniture")
    if "curb" in payload.lower():
        tags.append("curb alert")
    if "mattress" in payload.lower():
        tags.append("mattress")
    if "bed" in payload.lower():
        tags.append("bed")
        tags.append("furniture")
    if "christmas" in payload.lower():
        tags.append("christmas")
    if "tv" in payload.lower():
        tags.append("tv")
    if "desk" in payload.lower():
        tags.append("desk")
    if "jean" in payload.lower():
        tags.append("jeans")
        tags.append("clothes")

    if not tags:
        tags = ["unknown"]
    tags = list(set(tags))
    return tags

# Setup logging
logging.basicConfig(filename="/var/tmp/freestuff.log", level=logging.INFO)
#logging.basicConfig(filename="/var/tmp/freestuff.log", level=logging.DEBUG)
#logging.basicConfig(filename="freestuff.log", level=logging.DEBUG)

# Setup the database connection
client = pymongo.MongoClient()
db = client.freeStuffTagger

# Read the email from stdin and parse it
email_input = sys.stdin.read()
msg = email.message_from_string(email_input)

logging.debug("RAW EMAIL INPUT IS: %s" % email_input)

# Parse the payload(s) from the message
if msg.is_multipart():
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload()
else:
    payload = msg.get_payload()

payload = str(payload)
logging.info(payload)

entries = []
if ("alerts@alerts.craigslist.org" in msg["from"]) or ("alerts@alerts.craigslist.org" in payload):
    # Parse Craigslist email
    payload = payload[payload.find("   -"):payload.find("View all the results")]
    for entry in payload.split("   -"):
        entry = entry.strip()
        if entry and "... S N I P .." not in entry:
            e = entry.split("<http://")
            if len(e) != 2:
                logging.error("line could not be split: %s" % entry)
                continue
            obj = {}
            obj["payload"] = e[0][:e[0].rfind("(")].strip()
            if obj["payload"].lower().find("free") == 0:
                obj["payload"] = obj["payload"][4:].strip()
            obj["location"] = e[0][e[0].rfind("(")+1:e[0].rfind(")")].strip()
            obj["tags"] = parse_email_tags(obj["payload"])
            obj["url"] = "http://" + e[1][:-1].strip()
            entries.append(obj)

parsed_entries = []
for entry in entries:
    # Format the data nicely for MongoDB
    new_entry = {
        "from": msg["from"],
        "to": msg["to"],
        "subject": msg["subject"],
        "payload": entry["payload"],
        "date": parse_email_timestamp(msg["date"]),
        "location": entry["location"],
        "tags": entry["tags"],
        "url": entry["url"],
        "raw_input": email_input
    }
    parsed_entries.append(new_entry)


# Log some information to keep track of incoming messages
logging.info("Got email with subject: %s" % msg["subject"])
if len(parsed_entries) > 0:
    db.emails.insert(parsed_entries)
    logging.info("Inserted %s entries into DB" % len(parsed_entries))
else:
    logging.error("No entries found in email!")
