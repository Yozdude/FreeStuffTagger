#!/usr/bin/env python3
import os
import sys
import email
import email.utils
import pymongo
import datetime
import logging
import googlemaps
import redis


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

def location_to_lat_long(location):
    ''' Free version, with some restrtictions. See http://wiki.openstreetmap.org/wiki/Nominatim
    from geopy import geocoders

    geocoder = geocoders.Nominatim()

    location = geocoder.geocode("palo alto, ca", timeout=10)
    print(location.address)
    print((location.latitude, location.longitude))
    print(location.raw)
    '''

    # Connect to Redis to handle location geocoding
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    if r.exists(location):
        lat_lng = r.lrange(location, 0, 1)
        return (lat_lng[0], lat_lng[1])

    # Setup the Google Maps API
    try:
        gmaps = googlemaps.Client(key=GOOGLE_API_SERVER_KEY)
        geocode = gmaps.geocode(location)
        if geocode:
            lat = float(geocode[0]["geometry"]["location"]["lat"])
            lng = float(geocode[0]["geometry"]["location"]["lng"])
            r.rpush(location, lat)
            r.rpush(location, lng)
            return (lat, lng)
    except:
        pass

    # No idea where it is
    return (None, None)

# Setup logging
logging.basicConfig(filename="/var/tmp/freestuff.log", level=logging.WARNING)
#logging.basicConfig(filename="freestuff.log", level=logging.INFO)
#logging.basicConfig(filename="freestuff.log", level=logging.DEBUG)

GOOGLE_API_SERVER_KEY = "secret"

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
            obj["tagline"] = unicode(e[0][:e[0].rfind("(")].strip())
            if obj["tagline"].lower().find("free") == 0:
                obj["tagline"] = obj["tagline"][4:].strip()
            obj["location"] = unicode(e[0][e[0].rfind("(")+1:e[0].rfind(")")].strip())
            obj["tags"] = parse_email_tags(obj["tagline"])
            obj["url"] = unicode("http://" + e[1][:-1].strip())
            obj["description"] = ""
            obj["source"] = "craigslist"
            entries.append(obj)
            logging.debug(obj)
elif ("email_relay@freecycle.org" in msg["from"]) or ("email_relay@freecycle.org" in payload):
    obj = {}
    obj["tagline"] = unicode(msg["subject"][msg["subject"].find("OFFER:")+6:msg["subject"].rfind("(")].strip())
    obj["tags"] = unicode(parse_email_tags(obj["tagline"]))
    obj["location"] = msg["subject"][msg["subject"].find("[")+1:msg["subject"].find("]")].replace("Freecycle", "").strip()
    obj["location"] = obj["location"] + ", " + msg["subject"][msg["subject"].rfind("(")+1:-1].strip()
    obj["location"] = unicode(obj["location"].replace("\n", ""))
    obj["url"] = payload[payload.find("http://groups.freecycle.org"):]
    obj["url"] = unicode(obj["url"][:obj["url"].find("\n")].strip())
    obj["description"] = unicode(payload[:payload.find("An image of this item can be seen at")].replace("\n", " ").strip())
    obj["source"] = "freecycle"
    entries.append(obj)
    logging.debug(obj)
elif ("action@ifttt.com" in msg["from"]) or ("action@ifttt.com" in payload):
    obj = {}
    obj["tagline"] = unicode(msg["subject"][:msg["subject"].rfind("(")].replace("New listing:", "").strip())
    obj["tags"] = parse_email_tags(obj["tagline"])
    obj["location"] = msg["subject"][msg["subject"].rfind("(")+1:msg["subject"].rfind(")")].strip()
    obj["location"] = unicode(obj["location"].replace("\n", ""))
    obj["url"] = payload[payload.find("via http")+4:]
    obj["url"] = unicode(obj["url"][:obj["url"].find("\n")].strip())
    obj["description"] = unicode(payload[:payload.find("From search:")].replace("\n", " ").strip())
    obj["source"] = "ifttt"
    entries.append(obj)
    logging.debug(obj)

parsed_entries = []
for entry in entries:
    # Get the lat long for displaying on a map
    try:
        lat_long = location_to_lat_long(entry["location"])
        lat_long = [float(lat_long[0]), float(lat_long[1])]
    except Exception as e:
        logging.error("Exception getting lat long")
        logging.exception(e)
        lat_long = (None, None)

    # Format the data nicely for MongoDB
    new_entry = {
        "from": msg["from"],
        "to": msg["to"],
        "subject": msg["subject"],
        "tagline": entry["tagline"],
        "date": parse_email_timestamp(msg["date"]),
        "location": entry["location"],
        "lat": lat_long[0],
        "long": lat_long[1],
        "tags": entry["tags"],
        "url": entry["url"],
        "description": entry["description"],
        "source": entry["source"],
        "visited": False
    }
    parsed_entries.append(new_entry)


# Log some information to keep track of incoming messages
logging.info("Got email with %s entities from %s: %s" % (len(parsed_entries), msg["from"], msg["subject"]))
if len(parsed_entries) > 0:
    db.entries.insert(parsed_entries)
else:
    logging.error("No entries found in email!")
