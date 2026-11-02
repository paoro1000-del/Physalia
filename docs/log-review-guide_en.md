# Recording and Manually Reviewing Canary Contacts

This guide explains how an operator can record contacts with canary URLs or decoy content they control, then review those records in an existing web server or logging system. Physalia's Canary contacts page displays requests to its local URL on this PC. It does not ingest or automatically classify an operator's existing logs and provides no ingestion API, parser or detection rules. The Infinite Stream sample writes its own operational events to standard output.

## What to record

Start with the smallest set of metadata needed for an investigation.

| Field | Purpose | Caution |
| --- | --- | --- |
| `time` | Contact timeline | Use UTC or an explicit timezone and keep clocks synchronized |
| `event` | Event type | For example, `decoy_contact` |
| `decoy_id` | Which decoy received a request | Use an opaque ID from the operator inventory, never the URL or secret token |
| `request_id` | Correlate a request within your serving logs | A server-generated random ID; it does not identify a person |
| `method`, `status` | Request method and server response | A response code alone does not prove the file was fully retrieved |
| `bytes_sent`, `request_seconds` | Server-side response volume and duration | These do not prove the client received the complete content |
| `source_ip` | Correlation within your own logs, when necessary | Treat as potentially identifying; define necessity, access and retention. Omit if not needed |
| `user_agent` | Clue about automated retrieval or client type | It can be forged and cannot identify a person or prove malicious intent. Omit unless needed |

**Do not record:** passwords, cookies, Authorization headers, request bodies, customer data, full canary URLs, URL query strings or fragments. Raw access logs can contain secret canary tokens; do not share or forward them unchanged. Use your existing web server or monitoring provider to map a URL to an opaque `decoy_id`. Keep that mapping separate from logs and restrict it to operators.

## JSON Lines example

The following is fictional. `192.0.2.0/24` is reserved for documentation. Include `source_ip` only when necessary.

```jsonl
{"time":"2026-10-20T01:12:04Z","event":"decoy_contact","decoy_id":"cfg-backup-01","request_id":"req-7a31","method":"GET","status":200,"bytes_sent":894,"request_seconds":0.018}
{"time":"2026-10-20T01:13:19Z","event":"decoy_contact","decoy_id":"cfg-backup-01","request_id":"req-7a32","method":"HEAD","status":200,"bytes_sent":0,"request_seconds":0.006,"source_ip":"192.0.2.44"}
```

If you define your own log format, map the path without its query string to a random `decoy_id` and emit only that ID. Do not put real secret paths into examples or Git-tracked configuration. Behind a proxy, trust source addresses only when supplied by a proxy you explicitly trust; do not trust arbitrary `X-Forwarded-For` values.

The included `examples/nginx-decoy.conf` is a sample that records time, event, a fixed decoy ID, request ID, method, response status, bytes sent and duration as JSON. It omits the path and source IP. Use a distinct ID for each separately monitored decoy and set access and retention controls on the log file.

## Manual review

1. **Check expected automated access.** Compare deployment time with mail security scanners, link previews, internal monitoring and backup jobs that may fetch URLs.
2. **Sort by time.** For each `decoy_id`, review the sequence of methods such as GET and HEAD, status codes, intervals and server-side response volume. Repeated or unusual sequences are leads for review.
3. **Correlate only with logs you control.** If needed, an operator can check the same `request_id` or time window in your own web-server and identity-provider logs. Do not log in to another organization’s systems or connect to the source to investigate it.
4. **Record evidence and uncertainty.** “A URL request arrived” and “the server responded” differ from “a person read the file,” “the content was saved,” or “a system was compromised.” HTTP 200 and bytes sent do not establish completion, identity or compromise.
5. **Preserve relevant records and notify the responsible person.** Keep originals in an access-controlled log system and record the time, timezone, reviewer and rationale. Check for legitimate users and automated scanners before following your incident-response process.

## Privacy and legal considerations in Japan

IP addresses, user IDs and User-Agent values may identify a person when combined with other information. Limit use to defense and incident response, and define fields, access, storage, retention and deletion. Restrict readers and protect logs from alteration and disclosure. Do not collect communication contents or authentication secrets. Before sending logs to an external service, separately review the recipient, outsourcing or third-party provision, contract terms and any cross-border transfer.

Japan’s Personal Information Protection Commission lists access control, prevention of unauthorized access and periodic log analysis among examples of technical safeguards for systems handling personal data. Whether a particular log is personal information, and what notice, purpose or retention requirements apply, depends on its contents and the business context. This is general operational guidance, not a legal guarantee. [PPC Guidelines (General Rules)](https://www.ppc.go.jp/personalinfo/legal/guidelines_tsusoku/) / [PPC FAQ on log-file management](https://www.ppc.go.jp/all_faq_index/faq4-q802/)

**Do not:** intrude into, scan, distribute malware to or track a source device without authorization; log in to third-party accounts or systems; publish collected information or use it for extortion; or collect personal data beyond a defined need. Contact with a decoy does not authorize retaliation or access to another system.
