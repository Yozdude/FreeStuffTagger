TODO:
- Handle multiple markers on a single location
- Move map to be static on the right side of the page, while the table scrolls. Page should not scroll (or give the appearance of not scrolling)
- Indicate new emails since last visit (only emails the user has not seen before)
- Add the ability to set alerts for specific triggers (text). Have alerts send a text
- Add better tagging to emails (ML). Consider trying out google NLP.
- Add the ability to upvote/downvote emails to customize what you see and how ordering of emails works
- Live streaming of emails as they arrive

Consider:
- Integrate Vue.js for single-page functionality

Notes:
- Logging goes to `/var/tmp/<logfile>`
- [Google Maps Library](https://github.com/googlemaps/google-maps-services-python)
- Email script-running set in `/etc/aliases`
