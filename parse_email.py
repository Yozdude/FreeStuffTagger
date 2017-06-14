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
    if "bike" in payload.lower():
        tags.append("bike")
    if "rug" in payload.lower():
        tags.append("rug")
        tags.append("furniture")

    if not tags:
        tags = ["unknown"]
    tags = list(set(tags))
    return tags

# Setup logging
logging.basicConfig(filename="/var/tmp/freestuff.log", level=logging.INFO)
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
logging.debug("PAYLOAD IS: %s" % payload)

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
            obj["tagline"] = e[0][:e[0].rfind("(")].strip()
            if obj["tagline"].lower().find("free") == 0:
                obj["tagline"] = obj["tagline"][4:].strip()
            obj["location"] = e[0][e[0].rfind("(")+1:e[0].rfind(")")].strip()
            obj["tags"] = parse_email_tags(obj["tagline"])
            obj["url"] = "http://" + e[1][:-1].strip()
            obj["description"] = ""
            obj["source"] = "craigslist"
            entries.append(obj)
            logging.debug(obj)
elif ("email_relay@freecycle.org" in msg["from"]) or ("email_relay@freecycle.org" in payload):
    obj = {}
    obj["tagline"] = msg["subject"][msg["subject"].find("OFFER:")+6:msg["subject"].rfind("(")].strip()
    obj["tags"] = parse_email_tags(obj["tagline"])
    obj["location"] = msg["subject"][msg["subject"].find("[")+1:msg["subject"].find("]")].replace("Freecycle", "").strip()
    obj["location"] = obj["location"] + ", " + msg["subject"][msg["subject"].rfind("(")+1:-1].strip()
    obj["url"] = payload[payload.find("http://groups.freecycle.org")+1:]
    obj["url"] = obj["url"][:obj["url"].find("\n")].strip()
    obj["description"] = payload[:payload.find("An image of this item can be seen at")].replace("\n", " ").strip()
    obj["source"] = "freecycle"
    entries.append(obj)
    logging.debug(obj)
elif ("action@ifttt.com" in msg["from"]) or ("action@ifttt.com" in payload):
    obj = {}
    obj["tagline"] = msg["subject"][:msg["subject"].rfind("(")].replace("New listing:", "").strip()
    obj["tags"] = parse_email_tags(obj["tagline"])
    obj["location"] = msg["subject"][msg["subject"].rfind("(")+1:msg["subject"].rfind(")")].strip()
    obj["url"] = payload[payload.find("via http")+4:]
    obj["url"] = obj["url"][:obj["url"].find("\n")].strip()
    obj["description"] = payload[:payload.find("From search:")].replace("\n", " ").strip()
    obj["source"] = "ifttt"
    entries.append(obj)
    logging.debug(obj)

parsed_entries = []
for entry in entries:
    # Format the data nicely for MongoDB
    new_entry = {
        "from": msg["from"],
        "to": msg["to"],
        "subject": msg["subject"],
        "tagline": entry["tagline"],
        "date": parse_email_timestamp(msg["date"]),
        "location": entry["location"],
        "tags": entry["tags"],
        "url": entry["url"],
        "description": entry["description"],
        "source": entry["source"]
    }
    parsed_entries.append(new_entry)


# Log some information to keep track of incoming messages
logging.info("Got email with %s entities from %s: %s" % (len(parsed_entities), msg["from"], msg["subject"]))
if len(parsed_entries) > 0:
    db.entries.insert(parsed_entries)
else:
    logging.error("No entries found in email!")
