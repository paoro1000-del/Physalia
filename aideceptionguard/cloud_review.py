"""Local, bounded review of explicitly supplied Azure Monitor records.

The rules identify review candidates, not confirmed attacks. No network access,
log storage, credential handling, or automatic containment is performed.
"""
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
from urllib.parse import unquote, urlsplit
import re
import unicodedata

from aideceptionguard.i18n import translate

MAX_RECORDS = 10000
MAX_FINDINGS = 500
# Rank review signals so credential/permission changes and correlated access
# are not hidden by a large volume of lower-priority decoy contacts.
FINDING_PRIORITY = {
    "credential_change": 0,
    "application_control_change": 0,
    "role_assignment": 0,
    "app_permission": 0,
    "identity_security_change": 0,
    "security_policy_change": 0,
    "app_signin_then_graph": 1,
    "signin_after_failures": 1,
    "agentic_signin": 2,
    "distributed_signin_spray": 3,
    "signin_burst": 3,
    "targeted_signin_failures": 3,
    "stream_auth_failure_summary": 3,
    "decoy_contact": 4,
}
AUDIT_RULES = {
    "update application - certificates and secrets management": "credential_change",
    "add service principal credentials": "credential_change",
    "remove service principal credentials": "credential_change",
    "add application": "application_control_change",
    "delete application": "application_control_change",
    "hard delete application": "application_control_change",
    "add service principal": "application_control_change",
    "remove service principal": "application_control_change",
    "hard delete service principal": "application_control_change",
    "add owner to application": "application_control_change",
    "remove owner from application": "application_control_change",
    "add owner to service principal": "application_control_change",
    "remove owner from service principal": "application_control_change",
    "add policy to application": "application_control_change",
    "remove policy from application": "application_control_change",
    "add policy to service principal": "application_control_change",
    "remove policy from service principal": "application_control_change",
    "add member to role": "role_assignment",
    "remove member from role": "role_assignment",
    "add eligible member to role": "role_assignment",
    "remove eligible member from role": "role_assignment",
    "add scoped member to role": "role_assignment",
    "remove scoped member from role": "role_assignment",
    "remove member from role scoped over restricted management administrative unit": "role_assignment",
    "remove role assignment from role definition": "role_assignment",
    "disable account": "identity_security_change",
    "enable account": "identity_security_change",
    "reset password": "identity_security_change",
    "reset password (by admin)": "identity_security_change",
    "reset password (self-service)": "identity_security_change",
    "change password (self-service)": "identity_security_change",
    "create application password for user": "identity_security_change",
    "delete application password for user": "identity_security_change",
    "update stsrefreshtokenvalidfrom timestamp": "identity_security_change",
    "add passkey (device-bound)": "identity_security_change",
    "delete passkey (device-bound)": "identity_security_change",
    "add windows hello for business credential": "identity_security_change",
    "delete windows hello for business credential": "identity_security_change",
    "add passwordless phone sign-in credential": "identity_security_change",
    "delete passwordless phone sign-in credential": "identity_security_change",
    "add platform credential": "identity_security_change",
    "delete platform credential": "identity_security_change",
    "add conditional access policy": "security_policy_change",
    "update conditional access policy": "security_policy_change",
    "delete conditional access policy": "security_policy_change",
    "update security defaults": "security_policy_change",
    "update sign-in risk policy": "security_policy_change",
    "update user risk and mfa registration policy": "security_policy_change",
    "add bypass user": "security_policy_change",
    "remove bypassed user": "security_policy_change",
    "add app role assignment to service principal": "app_permission",
    "remove app role assignment from service principal": "app_permission",
    "add delegated permission grant": "app_permission",
    "remove delegated permission grant": "app_permission",
    "consent to application": "app_permission",
}


def audit_activity(value):
    """Normalize punctuation and spacing in Azure audit activity labels."""
    label = unicodedata.normalize("NFKC", string(value, 160)).casefold()
    # Azure exports and KQL/editor copies can use visually similar Unicode
    # dash characters. Normalize them so a label variation does not silently
    # suppress a credential or role-change finding.
    label = re.sub(r"[\u2010-\u2015\u2212]", "-", label)
    # Invisible formatting controls can be inserted into copied or altered
    # log labels. Treat them as separators before matching known activities.
    label = "".join(" " if unicodedata.category(char) in ("Cc", "Cf", "Cs", "Zl", "Zp") else char
                    for char in label)
    return " ".join(label.split())
GRAPH_PATHS = (
    (re.compile(r"/(\$batch)(/|$)", re.I), "batch"),
    (re.compile(r"/(messages|mailfolders)(/|$)", re.I), "mail"),
    (re.compile(r"/(drives|drive|sites)(/|$)", re.I), "files"),
    (re.compile(r"/(rolemanagement|directoryroles|roleassignments)(/|$)", re.I), "roles"),
    (re.compile(r"/(oauth2permissiongrants|approleassignments|approleassignedto)(/|$)", re.I), "application_permissions"),
    (re.compile(r"/(authenticationmethodspolicies|authenticationmethodspolicy|authenticationmethods)(/|$)", re.I), "authentication"),
    (re.compile(r"/(identitygovernance|privilegedaccess)(/|$)", re.I), "privileged_access"),
    (re.compile(r"/(devicemanagement|manageddevices|devicecompliancepolicies)(/|$)", re.I), "device_management"),
    (re.compile(r"/(security)(/|$)", re.I), "security"),
    # Microsoft Graph MCP Server for Enterprise requests use /enterprise.
    (re.compile(r"/(enterprise)(/|$)", re.I), "agent_mcp"),
    (re.compile(r"/(applications|serviceprincipals)(/|$)", re.I), "applications"),
    (re.compile(r"/(users|groups|contacts|orgcontacts|organization|devices|teams|directoryobjects|administrativeunits|domains|subscribedskus)(/|$)", re.I), "directory"),
)
GRAPH_HOSTS = frozenset((
    "graph.microsoft.com", "graph.microsoft.us", "dod-graph.microsoft.us",
    "microsoftgraph.chinacloudapi.cn",
))
UNSAFE_PATH_CATEGORIES = frozenset(("Cc", "Cf", "Cs", "Zl", "Zp"))
ROUTE_IDENTIFIER = re.compile(r"/(?:sha256|hmac-sha256)/[0-9a-f]{64}\Z")
MAX_GRAPH_PATH_DECODE_PASSES = 8


def visible_path(value, maximum=512):
    output, length = [], 0
    for char in value:
        visible = f"<U+{ord(char):04X}>" if unicodedata.category(char) in UNSAFE_PATH_CATEGORIES else char
        if length + len(visible) > maximum:
            break
        output.append(visible)
        length += len(visible)
    return "".join(output)


def route_identifier(path):
    """Hide a raw decoy route. Hashed route IDs use a separate input field."""
    digest = hashlib.sha256(path.encode("utf-8", errors="surrogatepass")).hexdigest()
    return "/sha256/" + digest


def field(row, name, default=None):
    if name in row:
        return row[name]
    return next((value for key, value in row.items() if isinstance(key, str) and key.casefold() == name.casefold()), default)


def string(value, maximum=200):
    if not isinstance(value, str):
        return ""
    # Log exports can contain lone UTF-16 surrogates. Normalize them before
    # findings are serialized as UTF-8 so one malformed field cannot fail the
    # entire local review response.
    return value.encode("utf-8", errors="replace").decode("utf-8").strip()[:maximum]


def timestamp(value):
    value = string(value, 64)
    if not value:
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def nonnegative_metric(value, maximum):
    """Parse a bounded nonnegative log metric, including CSV numeric strings."""
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or len(value) > 32 or not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
            return None
        try:
            value = float(value) if "." in value else int(value)
        except (ValueError, OverflowError):
            return None
    if not isinstance(value, (int, float)) or value < 0 or value > maximum:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def finding_sort_key(finding):
    """Keep rule priority, then show the newest timestamp within each priority."""
    when = timestamp(finding.get("time"))
    if when is None:
        chronological = 0
        missing_time = 1
    else:
        # Integer UTC microseconds avoid platform timestamp limits and float
        # precision loss for dates far from the Unix epoch.
        chronological = (((when.toordinal() * 24 + when.hour) * 60 + when.minute) * 60
                         + when.second) * 1_000_000 + when.microsecond
        missing_time = 0
    record = finding.get("record", 0)
    if isinstance(record, bool) or not isinstance(record, int):
        record = 0
    return (FINDING_PRIORITY.get(finding["rule"], 10), missing_time, -chronological, -record)


def tenant(row):
    # TenantId in Graph/Log Analytics is the workspace ID, not the Entra tenant.
    return string(field(row, "AADTenantId"), 128).lower()


def normalized_ip(value):
    """Canonicalize valid IP literals so equivalent IPv6 forms count once."""
    raw = string(value, 128)
    if not raw:
        return ""
    try:
        address = ipaddress.ip_address(raw)
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
            address = address.ipv4_mapped
        return address.compressed.lower()
    except ValueError:
        return ""


def sign_in_result(row):
    value = field(row, "ResultType")
    if value is None:
        status = field(row, "Status")
        value = field(status, "errorCode") if isinstance(status, dict) else None
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, str) and value.strip().casefold() in ("success", "failure"):
        return value.strip().casefold() == "success"
    if isinstance(value, int):
        return value == 0
    if not isinstance(value, str) or not re.fullmatch(r"[+-]?\d{1,10}", value.strip()):
        return None
    return int(value.strip()) == 0


def agent_details_present(value):
    """Treat nonempty scalar or dynamic Agent metadata as present without exposing it."""
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return False
        # Agent metadata is only measured as present/populated. Avoid parsing
        # attacker-controlled multi-megabyte JSON when its contents are not used.
        if len(value) > 8192:
            # Preserve the empty-container meaning without parsing a potentially
            # huge serialized value containing only whitespace.
            if ((value.startswith("{") and value.endswith("}")
                 or value.startswith("[") and value.endswith("]"))
                    and not value[1:-1].strip()):
                return False
            return True
        # KQL exports dynamic objects as JSON text; distinguish empty JSON
        # containers from nonempty metadata without inspecting its contents.
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, RecursionError):
            return True
        if parsed is None or parsed is False or parsed == "":
            return False
        if isinstance(parsed, (dict, list)):
            return bool(parsed)
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, (dict, list)):
        return bool(value)
    return False


def graph_request_path(value):
    """Return a classifiable path for HTTP(S) or relative Graph request URIs."""
    uri = string(value, 2048)
    if (not uri or "\\" in uri
            or any(ord(character) < 0x20 or ord(character) == 0x7f for character in uri)):
        return ""
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return ""
    # The browser projection accepts relative request paths and HTTP(S) URLs.
    # Keep the local analyzer consistent when callers use its API directly;
    # schemes such as javascript: must not be mistaken for Graph endpoints.
    if parsed.scheme and parsed.scheme.casefold() != "https":
        return ""
    if parsed.scheme and not parsed.netloc:
        return ""
    if parsed.netloc and not parsed.scheme:
        # Authority-relative URLs (for example //other-host/users) are not
        # Graph request paths, even though urlsplit exposes a classifiable path.
        return ""
    if parsed.netloc:
        try:
            host = (parsed.hostname or "").encode("idna").decode("ascii").rstrip(".").lower()
            port = parsed.port
        except (UnicodeError, ValueError):
            return ""
        if (host not in GRAPH_HOSTS or parsed.username is not None or parsed.password is not None
                or (port is not None and port != 443)):
            return ""
    path = parsed.path
    # Graph gateways and upstream components may normalize percent-encoded
    # route characters before matching. Decode only for categorization and
    # stop after the bounded pass count; the raw URI is never returned in findings.
    for _ in range(MAX_GRAPH_PATH_DECODE_PASSES):
        try:
            decoded = unquote(path, errors="strict")
        except UnicodeDecodeError:
            return ""
        if decoded == path:
            break
        path = decoded
    # Compatibility forms and invisible format characters can obscure route
    # names in exported logs. Normalize only for category matching; findings
    # still contain the category, never this path.
    if not path.isascii():
        path = unicodedata.normalize("NFKC", path)
        path = "".join(character for character in path
                        if unicodedata.category(character) != "Cf")
    # Percent-encoded backslashes are unambiguous path data at this point;
    # normalize them as separators to avoid dropping suspicious route variants.
    path = path.replace("\\", "/")
    if any(ord(character) < 0x20 or 0x7f <= ord(character) <= 0x9f for character in path):
        return ""
    return path


def analyze(records, language="ja"):
    if not isinstance(records, list) or len(records) > MAX_RECORDS:
        raise ValueError(translate("analysis_records_error", language))
    findings, signins, signins_by_token, graphs = [], defaultdict(list), defaultdict(list), []
    ip_sprays, tenant_sprays, account_sprays, user_signin_events = (
        defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list))
    coverage = {name: 0 for name in ("SigninLogs", "AADNonInteractiveUserSignInLogs", "AADServicePrincipalSignInLogs", "AADManagedIdentitySignInLogs", "AuditLogs", "MicrosoftGraphActivityLogs", "decoy_contact", "stream_auth_failure_summary")}
    incomplete = {name: 0 for name in coverage}
    skipped = duplicates = 0
    agent_field = {
        "user_signin": {"records": 0, "provided": 0, "populated": 0},
        "service_principal": {"records": 0, "provided": 0, "populated": 0},
        "managed_identity": {"records": 0, "provided": 0, "populated": 0},
    }
    seen_signins = set()
    for index, row in enumerate(records, 1):
        if not isinstance(row, dict):
            skipped += 1
            continue
        normalized_keys = set()
        for key in row:
            if isinstance(key, str):
                normalized = key.casefold()
                if normalized in normalized_keys:
                    raise ValueError(translate("analysis_duplicate_fields_error", language))
                normalized_keys.add(normalized)
        kind = string(field(row, "Type"), 80)
        event_name = string(field(row, "event"), 80).casefold()
        if event_name in ("decoy_contact", "stream_auth_failure_summary"):
            kind = event_name
        if kind not in coverage:
            skipped += 1
            continue
        coverage[kind] += 1
        when = timestamp(field(row, "CreatedDateTime") or field(row, "ActivityDateTime") or field(row, "TimeGenerated") or field(row, "time") or field(row, "timestamp"))
        tenant_id = tenant(row)
        app_id = string(field(row, "AppId"), 128).lower()
        principal = string(field(row, "ServicePrincipalId"), 128).lower()
        if kind == "stream_auth_failure_summary":
            scope = string(field(row, "scope"), 16).casefold()
            method = string(field(row, "method"), 8).upper()
            failures_total = field(row, "failures_total")
            # CSV readers produce strings for every column. Accept only a
            # plain decimal integer in that format; JSON booleans, floats,
            # signs, exponents and whitespace-padded values remain invalid.
            if isinstance(failures_total, str) and re.fullmatch(r"[0-9]{1,16}", failures_total):
                failures_total = int(failures_total)
            method_valid = ((scope == "stream" and method in ("GET", "HEAD"))
                            or (scope == "admin" and method in ("GET", "POST")))
            if (not when or not method_valid or isinstance(failures_total, bool)
                    or not isinstance(failures_total, int) or not 1 <= failures_total <= 2**53 - 1):
                incomplete[kind] += 1
                continue
            finding = {"rule": "stream_auth_failure_summary", "record": index,
                       "time": when.isoformat(), "scope": scope, "method": method,
                       "failures": failures_total}
            run_id = field(row, "run_id")
            if isinstance(run_id, str) and re.fullmatch(r"[0-9a-fA-F]{16}", run_id):
                finding["run_id"] = run_id.lower()
            findings.append(finding)
        elif kind == "decoy_contact":
            method = string(field(row, "method"), 8).upper()
            http_status = field(row, "http_status")
            if http_status is None:
                http_status = field(row, "status")
            if isinstance(http_status, str) and re.fullmatch(r"[0-9]{3}", http_status.strip()):
                http_status = int(http_status.strip())
            route_id = field(row, "route_id")
            if route_id is not None:
                # The converter's pseudonymous route identifier is a distinct
                # schema field. Never infer that a raw route is safe to expose
                # merely because it resembles a digest.
                path = route_id if isinstance(route_id, str) and ROUTE_IDENTIFIER.fullmatch(route_id) else ""
            else:
                path = string(field(row, "path"), 512).split("?", 1)[0].split("#", 1)[0]
                path = route_identifier(path) if path.startswith("/") else ""
            if not when or type(http_status) is not int or not 100 <= http_status <= 599 or not path:
                incomplete[kind] += 1
            outcome = field(row, "outcome")
            if outcome not in ("response_2xx", "response_non_2xx"):
                outcome = ""
            finding = {"rule": "decoy_contact", "record": index,
                       "time": when.isoformat() if when else "",
                       "outcome": outcome,
                       "path": path}
            request_id = field(row, "request_id")
            if isinstance(request_id, str) and re.fullmatch(r"[0-9A-Fa-f]{32}", request_id):
                finding["request_id"] = request_id.lower()
            completed_at = timestamp(field(row, "request_completed_at"))
            if completed_at:
                finding["request_completed_at"] = completed_at.isoformat()
            body_bytes = nonnegative_metric(field(row, "body_bytes_sent"), 2**53 - 1)
            request_seconds = nonnegative_metric(field(row, "request_seconds"), 10**9)
            if body_bytes is not None:
                finding["body_bytes_sent"] = body_bytes
            if request_seconds is not None:
                finding["request_seconds"] = request_seconds
            rate_limit_status = field(row, "rate_limit_status")
            if rate_limit_status in ("PASSED", "DELAYED", "REJECTED", "DELAYED_DRY_RUN", "REJECTED_DRY_RUN"):
                finding["rate_limit_status"] = rate_limit_status
            connection_limit_status = field(row, "connection_limit_status")
            if connection_limit_status in ("PASSED", "REJECTED", "REJECTED_DRY_RUN"):
                finding["connection_limit_status"] = connection_limit_status
            if method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
                finding["method"] = method
            if type(http_status) is int and 100 <= http_status <= 599:
                finding["http_status"] = http_status
            findings.append(finding)
        elif kind == "AuditLogs":
            activity = audit_activity(field(row, "ActivityDisplayName"))
            result = string(field(row, "Result"), 40).casefold()
            rule = AUDIT_RULES.get(activity)
            if not activity or not result or not when:
                incomplete[kind] += 1
            if rule and result == "success":
                findings.append({"rule": rule, "record": index, "time": when.isoformat() if when else "", "tenant": tenant_id, "activity": activity})
        elif kind in ("SigninLogs", "AADNonInteractiveUserSignInLogs"):
            event_id = string(field(row, "Id"), 128)
            if event_id and tenant_id:
                # IDs are only assumed unique inside one source table. Keep
                # interactive and non-interactive events distinct if an export
                # happens to reuse an ID across tables.
                key = (kind, tenant_id, event_id.casefold())
                if key in seen_signins:
                    duplicates += 1
                    continue
                seen_signins.add(key)
            agent_metrics = agent_field["user_signin"]
            agent_metrics["records"] += 1
            agent_field_present = any(isinstance(key, str) and key.casefold() == "agent" for key in row)
            if agent_field_present:
                agent_metrics["provided"] += 1
            agent_is_populated = agent_details_present(field(row, "Agent"))
            if agent_is_populated:
                agent_metrics["populated"] += 1
            success = sign_in_result(row)
            ip = normalized_ip(field(row, "IPAddress"))
            user_id = string(field(row, "UserId"), 200).lower()
            user_upn = string(field(row, "UserPrincipalName"), 200).lower()
            user = f"id:{user_id}" if user_id else f"upn:{user_upn}" if user_upn else ""
            if success is None or not tenant_id or not ip or not user or not when:
                incomplete[kind] += 1
            if success is not None and tenant_id and user and when:
                user_signin_events[(tenant_id, user)].append((when, index, success, ip))
            if success is False and tenant_id and ip and user and when:
                ip_sprays[(tenant_id, ip)].append((index, user, when))
                tenant_sprays[tenant_id].append((index, user, ip, when))
                account_sprays[(tenant_id, user)].append((index, ip, when))
            if success is True and agent_is_populated and when:
                finding = {"rule": "agentic_signin", "record": index, "time": when.isoformat(),
                           "identity_type": "user_signin"}
                if tenant_id:
                    finding["tenant"] = tenant_id
                if app_id:
                    finding["app_id"] = app_id
                findings.append(finding)
        elif kind in ("AADServicePrincipalSignInLogs", "AADManagedIdentitySignInLogs"):
            event_id = string(field(row, "Id"), 128)
            if event_id and tenant_id:
                key = (kind, tenant_id, event_id.casefold())
                if key in seen_signins:
                    duplicates += 1
                    continue
                seen_signins.add(key)
            agent_metrics = agent_field["managed_identity" if kind == "AADManagedIdentitySignInLogs" else "service_principal"]
            agent_metrics["records"] += 1
            agent_field_present = any(isinstance(key, str) and key.casefold() == "agent" for key in row)
            if agent_field_present:
                agent_metrics["provided"] += 1
            agent_details = field(row, "Agent")
            agent_value_present = agent_details_present(agent_details)
            if agent_value_present:
                agent_metrics["populated"] += 1
            success = sign_in_result(row)
            unique_token = string(field(row, "UniqueTokenIdentifier"), 256)
            if success is None or not tenant_id or not app_id or not principal or not when:
                incomplete[kind] += 1
            if success is True and tenant_id and app_id and principal and when:
                key = (tenant_id, app_id, principal)
                signins[key].append((when, index, unique_token))
                if unique_token:
                    signins_by_token[(key, unique_token)].append((when, index, unique_token))
            if success is True and agent_value_present and when:
                finding = {"rule": "agentic_signin", "record": index, "time": when.isoformat(),
                           "identity_type": "managed_identity" if kind == "AADManagedIdentitySignInLogs" else "service_principal"}
                if tenant_id:
                    finding["tenant"] = tenant_id
                if app_id:
                    finding["app_id"] = app_id
                if principal:
                    finding["service_principal_id"] = principal
                # Agent details may contain implementation-specific metadata;
                # use only their presence as a review signal, never echo them.
                findings.append(finding)
        elif kind == "MicrosoftGraphActivityLogs":
            status = field(row, "ResponseStatusCode")
            try:
                status = int(status) if not isinstance(status, bool) else 0
            except (ValueError, TypeError, OverflowError):
                status = 0
            uri = string(field(row, "RequestUri"), 2048)
            # Only retain a category; never put paths, query strings or tokens in findings.
            path = graph_request_path(uri)
            category = next((label for pattern, label in GRAPH_PATHS if pattern.search(path)), "")
            operation_id = visible_path(string(field(row, "OperationId"), 128), 128)
            request_id = visible_path(string(field(row, "RequestId"), 128), 128)
            sign_in_activity_id = string(field(row, "SignInActivityId"), 256)
            request_method = string(field(row, "RequestMethod"), 16).upper()
            if not status or not uri or not tenant_id or not app_id or not principal or not when:
                incomplete[kind] += 1
            if category and 200 <= status < 300 and tenant_id and app_id and principal and when:
                graphs.append(((tenant_id, app_id, principal), when, index, category, operation_id, request_id,
                               sign_in_activity_id, request_method))
    # Use an exact sliding window so failures just before and after a UTC
    # quarter-hour boundary are not split into separate, sub-threshold bins.
    for (tenant_id, ip), events in ip_sprays.items():
        events.sort(key=lambda event: (event[2], event[0]))
        users = defaultdict(int)
        left = 0
        last_alert = None
        for right, event in enumerate(events):
            _, user, when = event
            users[user] += 1
            while (when - events[left][2]).total_seconds() > 900:
                _, old_user, _ = events[left]
                users[old_user] -= 1
                if users[old_user] == 0:
                    del users[old_user]
                left += 1
            failures = right - left + 1
            if (failures >= 10 and len(users) >= 5
                    and (last_alert is None or (when - last_alert).total_seconds() >= 900)):
                findings.append({"rule": "signin_burst", "record": event[0], "time": when.isoformat(),
                                 "window_start": events[left][2].isoformat(), "tenant": tenant_id,
                                 "source_ip": ip, "failures": failures, "distinct_users": len(users)})
                last_alert = when
    # Catch coordinated sprays spread across rotating source IPs. This is a
    # review signal only: legitimate VPNs and shared identity providers can
    # produce the same pattern. A sliding window avoids fixed-bucket edges.
    for tenant_id, events in tenant_sprays.items():
        events.sort(key=lambda event: (event[3], event[0]))
        users, ips = defaultdict(int), defaultdict(int)
        left = 0
        last_alert = None
        for right, event in enumerate(events):
            _, user, ip, when = event
            users[user] += 1
            ips[ip] += 1
            while (when - events[left][3]).total_seconds() > 900:
                _, old_user, old_ip, _ = events[left]
                users[old_user] -= 1
                ips[old_ip] -= 1
                if users[old_user] == 0:
                    del users[old_user]
                if ips[old_ip] == 0:
                    del ips[old_ip]
                left += 1
            failures = right - left + 1
            if failures >= 10 and len(users) >= 5 and len(ips) >= 2:
                if last_alert is None or (when - last_alert).total_seconds() >= 900:
                    findings.append({"rule": "distributed_signin_spray", "record": event[0],
                                     "time": when.isoformat(), "window_start": events[left][3].isoformat(),
                                     "tenant": tenant_id, "failures": failures,
                                     "distinct_users": len(users), "distinct_source_ips": len(ips)})
                    last_alert = when
    # Detect concentrated failures against a single identity, including
    # attempts from one source IP that do not meet the multi-user rules.
    # The account name is intentionally omitted; the record index points back
    # to the operator's source log when identity-level review is needed.
    for (tenant_id, _), events in account_sprays.items():
        events.sort(key=lambda event: (event[2], event[0]))
        ips = defaultdict(int)
        left = 0
        last_alert = None
        for right, event in enumerate(events):
            _, ip, when = event
            ips[ip] += 1
            while (when - events[left][2]).total_seconds() > 900:
                _, old_ip, _ = events[left]
                ips[old_ip] -= 1
                if ips[old_ip] == 0:
                    del ips[old_ip]
                left += 1
            failures = right - left + 1
            if failures >= 20 and (last_alert is None or (when - last_alert).total_seconds() >= 900):
                findings.append({"rule": "targeted_signin_failures", "record": event[0],
                                 "time": when.isoformat(), "window_start": events[left][2].isoformat(),
                                 "tenant": tenant_id, "failures": failures, "distinct_users": 1,
                                 "distinct_source_ips": len(ips)})
                last_alert = when
    # A success after repeated failures on the same identity is a stronger
    # review signal than either event alone. Identity values are used only in
    # memory and never included in the finding.
    for (tenant_id, _), events in user_signin_events.items():
        events.sort(key=lambda event: (event[0], event[1]))
        active_failures = []
        failure_start = 0
        last_alert = None
        position = 0
        while position < len(events):
            when = events[position][0]
            group_end = position + 1
            while group_end < len(events) and events[group_end][0] == when:
                group_end += 1
            while (failure_start < len(active_failures)
                   and (when - active_failures[failure_start][0]).total_seconds() > 900):
                failure_start += 1
            if failure_start and failure_start >= len(active_failures) // 2:
                active_failures = active_failures[failure_start:]
                failure_start = 0
            # Events sharing a timestamp have no proven ordering. Evaluate all
            # successes against strictly earlier failures, then add this
            # timestamp's failures for later events.
            for _, index, success, ip in events[position:group_end]:
                if not success:
                    continue
                failures = len(active_failures) - failure_start
                if failures >= 5 and (last_alert is None or (when - last_alert).total_seconds() >= 900):
                    recent = active_failures[failure_start:]
                    finding = {"rule": "signin_after_failures", "record": index,
                               "time": when.isoformat(), "window_start": recent[0][0].isoformat(),
                               "tenant": tenant_id, "failures": failures,
                               "distinct_source_ips": len({event[2] for event in recent if event[2]})}
                    if ip:
                        finding["source_ip"] = ip
                    findings.append(finding)
                    last_alert = when
            active_failures.extend((when, index, ip) for _, index, success, ip in events[position:group_end]
                                   if not success)
            position = group_end
    for key in signins:
        signins[key].sort()
    for key in signins_by_token:
        signins_by_token[key].sort()
    for key, when, index, category, operation_id, request_id, sign_in_activity_id, request_method in graphs:
        matches = signins.get(key, [])
        match = None
        correlation = "time_window"
        if sign_in_activity_id:
            token_events = signins_by_token.get((key, sign_in_activity_id), [])
            token_pos = bisect_right(token_events, (when, len(records) + 1, "")) - 1
            if token_pos >= 0:
                candidate = token_events[token_pos]
                if 0 <= (when - candidate[0]).total_seconds() <= 3600:
                    match = candidate
            if match:
                correlation = "token_id"
        if match is None:
            pos = bisect_right(matches, (when, len(records) + 1)) - 1
            if pos >= 0 and 0 <= (when - matches[pos][0]).total_seconds() <= 3600:
                candidate = matches[pos]
                # If both sides carry token IDs and they differ, do not turn
                # a known mismatch into a time-only correlation.
                if not (sign_in_activity_id and candidate[2]):
                    match = candidate
        if match:
            finding = {"rule": "app_signin_then_graph", "record": index, "related_record": match[1],
                       "time": when.isoformat(), "tenant": key[0], "app_id": key[1], "service_principal_id": key[2],
                       "category": category, "correlation": correlation}
            if operation_id:
                finding["operation_id"] = operation_id
            if request_id:
                finding["request_id"] = request_id
            if request_method in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
                finding["method"] = request_method
            findings.append(finding)
    # A noisy stream of low-priority contacts must not hide account or
    # permission changes merely because they appeared later in the input.
    prioritized = sorted(findings, key=finding_sort_key)
    return {"input_records": len(records), "coverage": coverage, "incomplete": incomplete, "agent_field": agent_field, "skipped": skipped, "duplicates": duplicates,
            "finding_count": len(findings), "findings": prioritized[:MAX_FINDINGS], "truncated": len(findings) > MAX_FINDINGS}
