# Canary homepage kit

A canary landing page and logging server using only the Python standard library. No extra packages are required.

## Customize for your environment

The included page is a test sample that clearly identifies itself as a canary. For deployment, adapt its appearance, placement and recorded data to your organization, users and monitoring goals. An explicit canary notice can tell a visitor that access was detected and prompt reassessment or delay. A page that blends into ordinary workflows may support continued contact logging, but visitors may not contact it if they recognize it. Choose the approach based on your operational purpose, accidental-contact impact and privacy requirements.

This sample does not send email or Teams notifications. If alerts are needed, design and test them with organization-approved email or Teams destinations, minimal event data, false-positive handling and a plan for notification failures.

## Run locally

1. Install Python 3.10 or later.
2. Extract the ZIP and run `python server.py` from the extracted folder.
3. Open `http://127.0.0.1:8765/` in a browser.
4. Each visit is recorded in `logs/contacts.jsonl`. Browser and location reports can be matched to the HTTP request by event ID.
5. Stop with Ctrl+C.

## External hosting

The server listens only on `127.0.0.1` by default. Publish it through an HTTPS reverse proxy forwarding to `127.0.0.1:8765`. Do not expose the Python server directly to the internet or bind it to `0.0.0.0`. Browser geolocation requires HTTPS.

Behind a proxy, Python normally sees the proxy IP as the peer address. Use the trusted proxy's access logs if the visitor IP is needed. This sample does not trust the spoofable `X-Forwarded-For` header.

## Recorded information

- HTTP request: UTC time, peer IP, method/version, User-Agent, Accept-Language, Accept, and selected Sec-CH-UA/Sec-Fetch headers.
- Browser values: language, browser/OS details, timezone, screen dimensions, CPU thread count, plugin/MIME types, connection state, WebGL/GPU values, touch support and display preferences when available. Availability varies by browser.
- Location: the page explains the request and asks the browser for permission. Coordinates and accuracy are recorded only if permission is granted. Declining does not block the page.

The kit does not read cookies, page contents, files, camera, microphone or data from other sites. Values can be omitted or falsified; the log cannot prove sandbox use or identify an attacker. JSONL logs are not rotated or deleted automatically. Set access controls, retention, backup and deletion policies. Treat logs and location as sensitive. Use this sample only in your own isolated environment; do not impersonate a third-party site.
