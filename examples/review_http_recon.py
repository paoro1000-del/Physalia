"""Review Nginx JSON access logs for reconnaissance and auth-path bursts.

This local, read-only helper emits review signals only. It never prints client
IP addresses, request paths, query strings, or blocks traffic. See
nginx-recon-log.conf and the deployment guide for the expected input schema.
"""
import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import heapq
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import sys
import unicodedata
from urllib.parse import unquote

from access_events import open_input_file, unique_object

MAX_RECORDS = 250_000
MAX_INPUT_BYTES = 1024 * 1024 * 1024
MAX_FINDINGS = 10_000


def safe_display(value):
    """Escape terminal controls and bidi formatting in OS error text."""
    printable = "".join(
        character if character.isprintable() else
        (f"\\u{ord(character):04x}" if ord(character) <= 0xFFFF else f"\\U{ord(character):08x}")
        for character in str(value))
    return json.dumps(printable, ensure_ascii=False)[1:-1]


MAX_LINE_BYTES = 16_384
WINDOW_SECONDS = 300
MAX_PATH_DECODE_PASSES = 8
DISTRIBUTED_MIN_404_PATHS = 20
DISTRIBUTED_MIN_SOURCES = 3
AUTH_FAILURE_STATUSES = frozenset({400, 401, 403, 404, 429})
SINGLE_SOURCE_AUTH_FAILURES = 10
SINGLE_SOURCE_RECOVERY_REQUESTS = 6
DISTRIBUTED_AUTH_FAILURES = 25
DISTRIBUTED_RECOVERY_REQUESTS = 15
SENSITIVE_CATEGORIES = {
    "environment_file", "vcs_metadata", "source_map", "api_description",
    "runtime_configuration", "private_metadata", "database_or_backup", "debug_endpoint",
}
PRIVATE_CONFIG_DIRECTORIES = frozenset({
    (".config", "gcloud"), (".config", "gh"), (".config", "containers"),
})


def parse_time(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def normalized_path(value):
    """Normalize a path for bounded classification, never for routing."""
    if not isinstance(value, str) or len(value) > 4096 or not value.startswith("/"):
        return None
    path = value.split("?", 1)[0].split("#", 1)[0]
    # Some proxy/application stacks decode more than once or accept encoded
    # backslash separators. Normalize a bounded number of times for review;
    # this is deliberately a signal, not a claim about the server's routing.
    for _ in range(MAX_PATH_DECODE_PASSES):
        decoded = unquote(path, errors="replace")
        if decoded == path:
            break
        path = decoded
    # Some legacy path handlers treat an encoded NUL as an end marker. Include
    # the prefix as a candidate for review without claiming how the site routed it.
    path = path.split("\x00", 1)[0]
    # Normalize compatibility characters and ignore invisible formatting
    # controls only for coarse classification, never for routing decisions.
    if not path.isascii():
        path = unicodedata.normalize("NFKC", path)
        path = "".join(character for character in path
                        if unicodedata.category(character) != "Cf")
    return path.replace("\\", "/").casefold()


def classify_path(value):
    """Return a coarse category without retaining the path in report output."""
    path = normalized_path(value)
    if path is None:
        return ""
    # Treat matrix parameters and filesystem-style trailing dots/spaces as
    # possible aliases for review only. Real proxy/application routing varies.
    segments = [segment.split(";", 1)[0].rstrip(" .") for segment in path.split("/")]
    path = "/".join(segments)
    # Frameworks commonly use stacked suffixes such as .env.production.local.
    if any(re.fullmatch(r"\.env(?:\.[a-z0-9_-]+)*", part) for part in segments):
        return "environment_file"
    if any(part in (".envrc", ".flaskenv", ".npmrc", ".pypirc", ".netrc",
                    ".dockercfg", ".git-credentials", "id_rsa", "id_ed25519", "terraform.tfstate")
           or part.endswith(".tfstate") for part in segments):
        return "private_metadata"
    if any(part in (".git", ".svn", ".hg") for part in segments):
        return "vcs_metadata"
    if any(part in (".aws", ".azure", ".ssh", ".kube", ".docker") for part in segments):
        return "private_metadata"
    if any(tuple(segments[index:index + 2]) in PRIVATE_CONFIG_DIRECTORIES
           for index in range(len(segments) - 1)):
        return "private_metadata"
    if path.endswith(".map"):
        return "source_map"
    leaf = segments[-1]
    if (leaf in ("env.js", "env.json", "config.js", "config.json", "runtime-config.js",
                 "runtime-config.json", "config.php", "wp-config.php", "configuration.php",
                 "settings.py", "local.settings.json", "credentials.json", "secrets.json",
                 "secrets.yaml", "secrets.yml", "database.yml", "database.yaml", "web.config")
            or re.fullmatch(r"appsettings(?:\.[a-z0-9_-]+)?\.json", leaf)
            or re.fullmatch(r"application(?:[-.][a-z0-9_-]+)?\.(?:properties|ya?ml|json)", leaf)
            or re.fullmatch(r"firebase-adminsdk[a-z0-9_-]*\.json", leaf)):
        return "runtime_configuration"
    if (re.search(r"(?:^|/)(?:swagger|openapi|api-docs)(?:/|\.|$)", path)
            or path.endswith(("/openapi.json", "/openapi.yaml", "/swagger.json", "/swagger.yaml"))):
        return "api_description"
    if path.endswith((".db", ".sqlite", ".sqlite3", ".sql", ".bak", ".backup", ".old", ".orig",
                      ".dump", ".zip", ".tar", ".tgz", ".gz", ".7z", ".rar")):
        return "database_or_backup"
    if (re.search(r"(?:^|/)(?:debug|actuator|server-status|metrics|pprof)(?:/|$)", path)
            or re.search(r"(?:^|/)phpinfo(?:\.php)?(?:/|$)", path)):
        return "debug_endpoint"
    return ""


def classify_auth_path(value):
    """Classify common sign-in and account-recovery routes as review signals."""
    path = normalized_path(value)
    if path is None:
        return ""
    segments = [re.sub(r"[-_]", "", part.split(";", 1)[0].rstrip(" ."))
                for part in path.split("/")]
    joined = "".join(segments)
    if any(marker in joined for marker in (
            "forgotpassword", "passwordreset", "resetpassword", "recoveraccount",
            "accountrecovery", "generatereset", "validateusername")):
        return "account_recovery"
    if any(part in {"login", "signin", "signon", "oauth", "sso", "authorize",
                    "authorization", "callback", "token"} for part in segments):
        return "authentication"
    return ""


def auth_event_qualifies(event):
    category = event[7]
    return (category == "account_recovery"
            or (category == "authentication" and event[2] in AUTH_FAILURE_STATUSES))


def load_records(source, maximum, run_key):
    records = []
    skipped = defaultdict(int)
    line_number = 0
    total_bytes = 0

    def read_line():
        nonlocal total_bytes
        raw_line = source.readline(MAX_LINE_BYTES + 1)
        total_bytes += len(raw_line)
        if total_bytes > MAX_INPUT_BYTES:
            raise ValueError(f"Input exceeds the {MAX_INPUT_BYTES // (1024 * 1024 * 1024)} GiB scan limit; split the log into smaller time ranges.")
        return raw_line

    while True:
        raw = read_line()
        if not raw:
            break
        line_number += 1
        if line_number > maximum * 2:
            raise ValueError(f"Input exceeds the {maximum * 2:,}-line scan limit; split the log into smaller time ranges.")
        # readline requests one extra byte, so an unterminated final record
        # exactly at the cap is distinguishable from an oversized record.
        if len(raw) > MAX_LINE_BYTES:
            while raw and not raw.endswith(b"\n"):
                raw = read_line()
            skipped["oversized_record"] += 1
            continue
        try:
            row = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object)
        except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError):
            skipped["malformed_json"] += 1
            continue
        if not isinstance(row, dict):
            skipped["not_json_object"] += 1
            continue
        when = parse_time(row.get("time"))
        try:
            raw_client = row.get("client", "")
            if not isinstance(raw_client, str):
                skipped["invalid_client_address"] += 1
                continue
            client = ipaddress.ip_address(raw_client).compressed
        except ValueError:
            skipped["invalid_client_address"] += 1
            continue
        raw_host = row.get("host", "")
        if not isinstance(raw_host, str) or len(raw_host) > 253:
            skipped["invalid_host"] += 1
            continue
        host = raw_host.casefold().rstrip(".")
        path = row.get("uri")
        status = row.get("status")
        if (when is None or not isinstance(path, str) or len(path) > 4096
                or not path.startswith("/") or isinstance(status, bool)
                or not isinstance(status, (int, str)) or not re.fullmatch(r"[1-5][0-9]{2}", str(status))):
            skipped["invalid_event_fields"] += 1
            continue
        if any(ord(char) < 0x20 or 0x7F <= ord(char) <= 0x9F for char in path + host):
            skipped["control_character"] += 1
            continue
        # Query values often contain tokens or user data and are not part of
        # route identity. Drop them even when input did not come from the
        # supplied Nginx map; fragments are never sent in an HTTP request.
        route = path.split("?", 1)[0].split("#", 1)[0]
        if not route:
            skipped["empty_route"] += 1
            continue
        try:
            route_bytes = route.encode("utf-8")
            host.encode("utf-8")
        except UnicodeEncodeError:
            # JSON can represent lone UTF-16 surrogates with \u escapes even
            # though the surrounding input file is valid UTF-8.
            skipped["invalid_unicode"] += 1
            continue
        status = int(status)
        category = classify_path(route)
        auth_category = classify_auth_path(route)
        method = row.get("method", "")
        if not isinstance(method, str) or method.upper() not in (
                "GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            method = "OTHER"
        else:
            method = method.upper()
        if len(records) >= maximum:
            raise ValueError(f"Input exceeds the {maximum:,}-record limit; split the log into smaller time ranges.")
        path_id = hmac.new(run_key, route_bytes, hashlib.sha256).digest()
        records.append((when, client, status, category, path_id, line_number, host,
                        auth_category, method))
    return records, dict(sorted(skipped.items()))


def review(records, run_key):
    by_client = defaultdict(list)
    for event in records:
        # Keep activity on separate virtual hosts from inflating one another's
        # path-enumeration counts. Older input without `host` uses an empty host.
        by_client[(event[1], event[6])].append(event)
    findings = []
    findings_truncated = False
    findings_seen = 0

    def retain_finding(finding):
        nonlocal findings_truncated, findings_seen
        findings_seen += 1
        order = (finding.get("time_start", finding.get("time", "")), finding["rule"])
        entry = (*order, findings_seen, finding)
        if len(findings) < MAX_FINDINGS:
            heapq.heappush(findings, entry)
            return
        findings_truncated = True
        if entry[:2] > findings[0][:2] or (entry[:2] == findings[0][:2] and entry[2] > findings[0][2]):
            heapq.heapreplace(findings, entry)

    for (client, host), events in by_client.items():
        events.sort(key=lambda event: (event[0], event[5]))
        source_key = f"{client}\0{host}".encode("utf-8")
        source_id = hmac.new(run_key, source_key, hashlib.sha256).hexdigest()[:20]
        left = 0
        missing_paths = defaultdict(int)
        categories = defaultdict(int)
        last_enumeration_alert = None
        last_enumeration_success_alert = None
        last_sensitive_alert = {}
        for right, current in enumerate(events):
            when = current[0]
            if current[2] == 404:
                missing_paths[current[4]] += 1
            if current[3] in SENSITIVE_CATEGORIES:
                categories[current[3]] += 1
            while (when - events[left][0]).total_seconds() > WINDOW_SECONDS:
                old = events[left]
                if old[2] == 404:
                    missing_paths[old[4]] -= 1
                    if missing_paths[old[4]] == 0:
                        del missing_paths[old[4]]
                if old[3] in SENSITIVE_CATEGORIES:
                    categories[old[3]] -= 1
                    if categories[old[3]] == 0:
                        del categories[old[3]]
                left += 1
            sensitive = sorted(categories)
            if len(missing_paths) >= 12 and (last_enumeration_alert is None
                    or (when - last_enumeration_alert).total_seconds() >= WINDOW_SECONDS):
                retain_finding({
                    "rule": "http_path_enumeration", "time_start": events[left][0].isoformat(),
                    "time_end": when.isoformat(), "requests": right - left + 1,
                    "distinct_404_paths": len(missing_paths), "sensitive_categories": sensitive,
                    "source_id": source_id,
                    "input_line_start": min(event[5] for event in events[left:right + 1]),
                    "input_line_end": max(event[5] for event in events[left:right + 1]),
                })
                last_enumeration_alert = when
            # A non-error response after a burst of distinct misses may mean
            # the scan found a real route. Treat redirects and SPA fallbacks
            # as review candidates too; this signal is not proof of access.
            if (len(missing_paths) >= 12 and 200 <= current[2] < 400
                    and (last_enumeration_success_alert is None
                         or (when - last_enumeration_success_alert).total_seconds() >= WINDOW_SECONDS)):
                retain_finding({
                    "rule": "enumeration_followed_by_success_candidate",
                    "time_start": events[left][0].isoformat(), "time_end": when.isoformat(),
                    "response_status": current[2], "distinct_404_paths": len(missing_paths),
                    "sensitive_categories": sensitive,
                    "source_id": source_id,
                    "input_line_start": min(event[5] for event in events[left:right + 1]),
                    "input_line_end": max(event[5] for event in events[left:right + 1]),
                })
                last_enumeration_success_alert = when
            # Surface sensitive-path probes even when they do not meet the
            # broader enumeration threshold; emit at most one per category
            # from a source in each five-minute interval.
            if current[3] in SENSITIVE_CATEGORIES and (current[3] not in last_sensitive_alert
                    or (when - last_sensitive_alert[current[3]]).total_seconds() >= WINDOW_SECONDS):
                retain_finding({
                    "rule": "sensitive_endpoint_probe", "time": when.isoformat(),
                    "category": current[3], "http_status": current[2],
                    "source_id": source_id,
                    "input_line": current[5],
                })
                last_sensitive_alert[current[3]] = when
        # Surface repeated failed sign-in endpoint requests and account
        # recovery traffic. Endpoint matching is heuristic, and logs do not
        # identify the account being targeted; findings are triage candidates.
        for auth_category in ("authentication", "account_recovery"):
            threshold = (SINGLE_SOURCE_AUTH_FAILURES if auth_category == "authentication"
                         else SINGLE_SOURCE_RECOVERY_REQUESTS)
            window = deque()
            last_auth_alert = None
            for current in events:
                when = current[0]
                while window and (when - window[0][0]).total_seconds() > WINDOW_SECONDS:
                    window.popleft()
                if current[7] != auth_category or not auth_event_qualifies(current):
                    continue
                window.append(current)
                if len(window) < threshold or (last_auth_alert is not None
                        and (when - last_auth_alert).total_seconds() < WINDOW_SECONDS):
                    continue
                statuses, methods = defaultdict(int), defaultdict(int)
                for item in window:
                    statuses[str(item[2])] += 1
                    methods[item[8]] += 1
                retain_finding({
                    "rule": ("authentication_failures_burst" if auth_category == "authentication"
                             else "account_recovery_request_burst"),
                    "category": auth_category, "time_start": window[0][0].isoformat(),
                    "time_end": when.isoformat(), "requests": len(window),
                    "http_statuses": dict(sorted(statuses.items())),
                    "methods": dict(sorted(methods.items())), "source_id": source_id,
                    "input_line_start": min(item[5] for item in window),
                    "input_line_end": max(item[5] for item in window),
                })
                last_auth_alert = when
    # A single-source threshold misses scanners that rotate VPNs or spread
    # requests across disposable hosts. Add a separate, deliberately higher
    # host-wide signal without emitting raw addresses or paths. This can also
    # match several unrelated scanners on a busy public site, so it is only a
    # review candidate.
    by_host = defaultdict(list)
    for event in records:
        by_host[event[6]].append(event)
    for host, events in by_host.items():
        # Without Host, virtual-host boundaries are unknown; do not merge
        # unrelated sites into a potentially misleading distributed finding.
        if not host:
            continue
        events.sort(key=lambda event: (event[0], event[5]))
        window = deque()
        missing_paths = defaultdict(int)
        sources = defaultdict(int)
        last_alert = None
        for current in events:
            when = current[0]
            while window and (when - window[0][0]).total_seconds() > WINDOW_SECONDS:
                old = window.popleft()
                missing_paths[old[4]] -= 1
                if missing_paths[old[4]] == 0:
                    del missing_paths[old[4]]
                sources[old[1]] -= 1
                if sources[old[1]] == 0:
                    del sources[old[1]]
            if current[2] != 404:
                continue
            window.append(current)
            missing_paths[current[4]] += 1
            sources[current[1]] += 1
            if (len(missing_paths) >= DISTRIBUTED_MIN_404_PATHS
                    and len(sources) >= DISTRIBUTED_MIN_SOURCES
                    and (last_alert is None
                         or (when - last_alert).total_seconds() >= WINDOW_SECONDS)):
                retain_finding({
                    "rule": "distributed_http_path_enumeration",
                    "time_start": window[0][0].isoformat(), "time_end": when.isoformat(),
                    "requests": len(window), "distinct_404_paths": len(missing_paths),
                    "distinct_sources": len(sources),
                    "host_id": hmac.new(run_key, host.encode("utf-8"), hashlib.sha256).hexdigest()[:20],
                    "input_line_start": min(event[5] for event in window),
                    "input_line_end": max(event[5] for event in window),
                })
                last_alert = when
        # Aggregate the same endpoint signals across source addresses. This
        # can surface IP rotation, but shared public services can also meet
        # the thresholds through unrelated users.
        for auth_category in ("authentication", "account_recovery"):
            threshold = (DISTRIBUTED_AUTH_FAILURES if auth_category == "authentication"
                         else DISTRIBUTED_RECOVERY_REQUESTS)
            window = deque()
            source_counts = defaultdict(int)
            last_auth_alert = None
            for current in events:
                when = current[0]
                while window and (when - window[0][0]).total_seconds() > WINDOW_SECONDS:
                    old = window.popleft()
                    source_counts[old[1]] -= 1
                    if source_counts[old[1]] == 0:
                        del source_counts[old[1]]
                if current[7] != auth_category or not auth_event_qualifies(current):
                    continue
                window.append(current)
                source_counts[current[1]] += 1
                if (len(window) < threshold or len(source_counts) < DISTRIBUTED_MIN_SOURCES
                        or (last_auth_alert is not None
                            and (when - last_auth_alert).total_seconds() < WINDOW_SECONDS)):
                    continue
                statuses, methods = defaultdict(int), defaultdict(int)
                for item in window:
                    statuses[str(item[2])] += 1
                    methods[item[8]] += 1
                retain_finding({
                    "rule": ("distributed_authentication_failures_candidate"
                             if auth_category == "authentication"
                             else "distributed_account_recovery_candidate"),
                    "category": auth_category, "time_start": window[0][0].isoformat(),
                    "time_end": when.isoformat(), "requests": len(window),
                    "distinct_sources": len(source_counts),
                    "http_statuses": dict(sorted(statuses.items())),
                    "methods": dict(sorted(methods.items())),
                    "host_id": hmac.new(run_key, host.encode("utf-8"), hashlib.sha256).hexdigest()[:20],
                    "input_line_start": min(item[5] for item in window),
                    "input_line_end": max(item[5] for item in window),
                })
                last_auth_alert = when
    findings = [entry[3] for entry in sorted(findings, key=lambda entry: entry[:3])]
    return findings, findings_truncated


def main():
    parser = argparse.ArgumentParser(description=(
        "Locally review Nginx JSON logs for reconnaissance and authentication-path bursts "
        "(bounded to 250,000 records, 500,000 lines and 1 GiB; 16 KiB per line)."))
    parser.add_argument("--input", help="saved JSONL file; otherwise read standard input")
    parser.add_argument("--max-records", type=int, default=MAX_RECORDS,
                        help=(f"maximum valid records to keep in memory; also scans at most twice this many JSONL lines "
                              f"(default: {MAX_RECORDS:,}; maximum: {MAX_RECORDS:,})"))
    args = parser.parse_args()
    if not 1 <= args.max_records <= MAX_RECORDS:
        parser.error(f"--max-records must be between 1 and {MAX_RECORDS:,}")
    try:
        source = open_input_file(args.input) if args.input else sys.stdin.buffer
        try:
            run_key = secrets.token_bytes(32)
            records, skipped = load_records(source, args.max_records, run_key)
        finally:
            if args.input:
                source.close()
        findings, findings_truncated = review(records, run_key)
    except (OSError, ValueError) as exc:
        parser.error(safe_display(exc))
    print(json.dumps({"records_reviewed": len(records), "records_skipped": sum(skipped.values()),
                      "skip_reasons": skipped, "findings": findings,
                      "findings_truncated": findings_truncated},
                     ensure_ascii=True, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
