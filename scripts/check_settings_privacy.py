"""Check canary URL privacy, operator attestations and UI/API URL capacity."""
from html.parser import HTMLParser
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]


class CanaryFieldParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.active_label = None
        self.canary_labels = set()
        self.fields = {}
        self.operator_attestations = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "label":
            self.active_label = attributes.get("for")
            if attributes.get("data-i18n") in ("canary_url", "canary_urls") and self.active_label:
                self.canary_labels.add(self.active_label)
        if attributes.get("data-i18n") in ("canary_url", "canary_urls") and self.active_label:
            self.canary_labels.add(self.active_label)
        field_id = attributes.get("id")
        if field_id and "data-operator-attestation" in attributes:
            self.operator_attestations.add(field_id)
        if field_id and (field_id in self.canary_labels
                         or attributes.get("type") == "url"
                         or "data-secret-url" in attributes):
            self.fields[field_id] = attributes

    def handle_endtag(self, tag):
        if tag == "label":
            self.active_label = None


def main():
    parser = CanaryFieldParser()
    parser.feed((ROOT / "web" / "index.html").read_text(encoding="utf-8"))
    app = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
    match = re.search(r"nonPersistentCanaryUrlControls\s*=\s*new Set\(\[([^]]*)\]\)", app)
    if not match:
        print("Cannot inspect non-persistent canary URL controls", file=sys.stderr)
        return 2
    non_persistent = set(re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)))
    unsafe = []
    for field_id, attrs in parser.fields.items():
        # This project currently uses textareas for the URL fields. If a URL
        # field is changed to an input, the type is captured by the parser too.
        excluded_by_filter = attrs.get("type") == "url" or "data-secret-url" in attrs
        if not excluded_by_filter and field_id not in non_persistent:
            unsafe.append(field_id)
    if unsafe:
        print("Canary URL controls may be exported in settings: " + ", ".join(sorted(unsafe)),
              file=sys.stderr)
        return 1
    required_url_fields = {"nest-url", "maze-url", "encoding-url"}
    if not required_url_fields.issubset(parser.fields):
        print("Cannot inspect every multi-URL generation control", file=sys.stderr)
        return 2
    try:
        validation = (ROOT / "aideceptionguard" / "validation.py").read_text(encoding="utf-8")
        server = (ROOT / "app.py").read_text(encoding="utf-8")
        maximum_urls = int(re.search(r"^MAX_CANARY_URLS\s*=\s*(\d+)\s*$", validation, re.M).group(1))
        maximum_url_length = int(re.search(r"^MAX_CANARY_URL_LENGTH\s*=\s*(\d+)\s*$", validation, re.M).group(1))
        request_match = re.search(r"^MAX_REQUEST\s*=\s*(\d+)\s*\*\s*1024\s*\*\s*1024\s*$", server, re.M)
        request_limit = int(request_match.group(1)) * 1024 * 1024
    except (AttributeError, TypeError, ValueError):
        print("Cannot inspect server and canary URL capacity limits", file=sys.stderr)
        return 2
    required_characters = maximum_urls * maximum_url_length + maximum_urls - 1
    missing_capacity = [field_id for field_id in sorted(required_url_fields)
                        if not parser.fields[field_id].get("maxlength", "").isdecimal()
                        or int(parser.fields[field_id]["maxlength"]) < required_characters]
    if missing_capacity:
        print("Multi-URL controls cannot enter the full backend URL capacity: "
              + ", ".join(missing_capacity), file=sys.stderr)
        return 1
    # Valid URL text can use up to three UTF-8 bytes per BMP character. Leave
    # room for JSON keys, quoting and the surrounding generation settings.
    minimum_request_bytes = required_characters * 3 + 16 * 1024
    if request_limit < minimum_request_bytes:
        print("Generation request limit is too small for the maximum canary URL list",
              file=sys.stderr)
        return 1
    if 'el.type !== "url"' not in app or '!el.hasAttribute("data-secret-url")' not in app:
        print("Settings controls must exclude URL-typed and data-secret-url fields", file=sys.stderr)
        return 1
    if '!el.hasAttribute("data-operator-attestation")' not in app:
        print("Settings controls must exclude every non-portable operator confirmation", file=sys.stderr)
        return 1
    if 'nonPersistentCanaryUrlControls.has(el.id) ? "" : el.value' not in app:
        print("Settings export must blank non-persistent canary URL values", file=sys.stderr)
        return 1
    if not all(f"#{field_id}" in app for field_id in non_persistent):
        print("Settings import must clear non-persistent canary URL controls", file=sys.stderr)
        return 1
    attestation_match = re.search(r"nonPersistentOperatorAttestations\s*=\s*new Set\(\[([^]]*)\]\)", app)
    if not attestation_match:
        print("Cannot inspect non-persistent domain-ownership confirmations", file=sys.stderr)
        return 2
    attestations = set(re.findall(r"['\"]([^'\"]+)['\"]", attestation_match.group(1)))
    required_attestations = {
        "env-dev-url-authorized", "db-email-domain-authorized", "vault-domain-authorized",
    }
    if attestations != required_attestations:
        print("Domain-ownership confirmations must be explicitly excluded from saved settings",
              file=sys.stderr)
        return 1
    if "nonPersistentOperatorAttestations.has(el.id) ? false : el.checked" not in app:
        print("Settings export must store false for non-persistent ownership confirmations", file=sys.stderr)
        return 1
    if not all(f'$("#{field_id}").checked = false' in app for field_id in attestations):
        print("Settings import must require ownership reconfirmation", file=sys.stderr)
        return 1
    required_marked_attestations = {
        "env-dev-url-authorized", "db-email-domain-authorized", "vault-domain-authorized",
    }
    if parser.operator_attestations != required_marked_attestations:
        print("Every operator attestation control must remain explicitly identified", file=sys.stderr)
        return 1
    all_operator_attestations = parser.operator_attestations | attestations
    if all_operator_attestations != {
        "env-dev-url-authorized", "db-email-domain-authorized", "vault-domain-authorized",
    }:
        print("Settings export must account for every operator attestation", file=sys.stderr)
        return 1
    if not all(f'$("#{field_id}").checked = false' in app for field_id in all_operator_attestations):
        print("Settings import must reset every operator attestation", file=sys.stderr)
        return 1
    print(f"All {len(parser.fields)} canary URL controls are omitted or blanked, "
          f"and all {len(all_operator_attestations)} operator attestations are excluded from saved settings "
          f"and reset on import; all multi-URL controls accept {maximum_urls} URLs of up to "
          f"{maximum_url_length} characters within the {request_limit // (1024 * 1024)} MiB request cap.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
