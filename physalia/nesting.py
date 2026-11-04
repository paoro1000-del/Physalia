"""Bounded trees of AES-encrypted ZIPs with varied synthetic documents."""
from dataclasses import dataclass, field
import io
import posixpath
import secrets
import zipfile
from datetime import datetime, timezone

import pyzipper

from physalia.archive_metadata import write_archive_member
from physalia.database import records
from physalia.formats import FORMATS, render, render_switchable_env, resolve_context
from physalia.i18n import translate
from physalia.naming import plausible_filename
from physalia.passwords import make_password, validate_policy
from physalia.validation import filename, integer
from physalia.scenarios import place_canary, scenario_for

MAX_LAYERS = 8
MAX_NODES = 40
MAX_CONTENT_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
DIRECTORY_DIMENSIONS = {
    "crm": (("customer_1048", "customer_2176", "customer_3891", "account_west", "account_enterprise"),
            ("day_03", "day_08", "day_14", "day_21", "day_27"),
            ("owner_team_a", "owner_team_b", "review_queue", "regional_review")),
    "migration": (("batch_014", "batch_027", "source_legacy", "target_import", "delta_review"),
                  ("customer_1048", "customer_2176", "account_west", "account_enterprise"),
                  ("day_03", "day_08", "day_14", "day_21", "day_27")),
    "archive": (("customer_1048", "customer_2176", "account_west", "account_enterprise", "retention_hold"),
                ("snapshot_01", "snapshot_15", "day_08", "day_21"),
                ("owner_team_a", "owner_team_b", "restore_review", "retention_check")),
    "cards": (("cardholder_1048", "cardholder_2176", "renewal_batch", "billing_west"),
              ("day_03", "day_08", "day_14", "day_21", "day_27"),
              ("review_team_a", "review_team_b", "reconciliation", "expiry_review")),
    "companies": (("company_1048", "company_2176", "company_west", "enterprise_accounts"),
                  ("contact_updates", "ownership_review", "day_08", "day_21"),
                  ("owner_team_a", "owner_team_b", "industry_review")),
    "passwords": (("service_billing", "service_support", "service_archive", "service_portal"),
                  ("account_1048", "account_2176", "account_admin", "recovery_queue"),
                  ("rotation_review", "owner_team_a", "owner_team_b", "access_review")),
    "api_credentials": (("integration_billing", "integration_support", "client_1048", "client_2176"),
                        ("rotation_01", "rotation_15", "scope_review", "day_21"),
                        ("owner_team_a", "owner_team_b", "access_review", "release_check")),
    "invoices": (("customer_1048", "customer_2176", "region_west", "enterprise_accounts"),
                 ("day_03", "day_08", "day_14", "day_21", "day_27"),
                 ("collector_team_a", "collector_team_b", "overdue_review", "reconciliation")),
    "employees": (("department_finance", "department_ops", "department_support", "region_west"),
                  ("employee_1048", "employee_2176", "employee_3891", "payroll_review"),
                  ("manager_team_a", "manager_team_b", "onboarding", "role_review")),
    "vendors": (("vendor_1048", "vendor_2176", "supplier_west", "service_partner"),
                ("contract_014", "contract_027", "renewal_review", "day_21"),
                ("owner_team_a", "owner_team_b", "due_diligence", "finance_review")),
    "orders": (("customer_1048", "customer_2176", "region_west", "enterprise_accounts"),
               ("day_03", "day_08", "day_14", "day_21", "day_27"),
               ("fulfillment_team_a", "fulfillment_team_b", "returns_review", "billing_check")),
    "tickets": (("customer_1048", "customer_2176", "region_west", "priority_queue"),
                ("case_014", "case_027", "day_08", "day_21"),
                ("agent_team_a", "agent_team_b", "escalation_review", "resolution_check")),
    "assets": (("region_west", "region_east", "office_014", "datacenter_02"),
               ("device_1048", "device_2176", "endpoint_3891", "license_review"),
               ("assigned_team_a", "assigned_team_b", "lifecycle_review")),
    "cloud": (("subscription_014", "subscription_027", "tenant_west", "platform_shared"),
              ("region_east", "region_west", "resource_group_1048", "resource_group_2176"),
              ("deployment_014", "deployment_027", "owner_team_a", "recovery_review")),
}
HINT_NOTE_PRESETS = {
    "ja": (
        "データ移行 引継ぎメモ\n展開キー控えは月次の鍵管理票を参照。\n末尾{hint}文字は別管理。\n",
        "保管データ復元メモ\n復号キーは更新済みの保管ノートを確認。\n末尾{hint}文字はこの資料に記載なし。\n",
        "アーカイブ整理記録\n鍵の先頭部分は引継ぎ資料に記録。\n末尾{hint}文字は別管理。\n",
        "共有フォルダー移行\nZIPキーは月次パスワード台帳を参照。\n末尾{hint}文字はこの資料に記載なし。\n",
    ),
    "en": (
        "Export handover\nSee the monthly key register for the archive key.\nThe final {hint} characters are stored separately.\n",
        "Restore notes\nThe updated storage note has the decryption key.\nThe final {hint} characters are not listed here.\n",
        "Archive closeout\nThe handover record has the key prefix.\nThe final {hint} characters are stored separately.\n",
        "Shared folder migration\nSee the monthly password register for the ZIP key.\nThe final {hint} characters are not listed here.\n",
    ),
}


@dataclass
class Artifact:
    name: str
    mime: str
    content: bytes
    companions: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    role: str = "operator"

    def __iter__(self):
        # Retain three-value unpacking for the original generator API.
        return iter((self.name, self.mime, self.content))


def generate_nest(settings, language="ja"):
    layers = integer(settings.get("layers", 3), "layers", 1, MAX_LAYERS, language)
    branches = integer(settings.get("branches", 2), "branches", 1, 3, language)
    decoys = integer(settings.get("decoys", 4), "decoys", 0, 10, language)
    directory_depth = integer(settings.get("directory_depth", 2), "directory_depth", 1, 5, language)
    rows = integer(settings.get("rows", 20), "rows", 1, 100, language)
    count = sum(branches ** n for n in range(layers))
    if count > MAX_NODES:
        raise ValueError(translate("node_limit", language, count=count, maximum=MAX_NODES))
    rng = secrets.SystemRandom()
    scenario_name, scenario = scenario_for(settings, language)
    directories = settings.get("directories", DIRECTORY_DIMENSIONS.get(scenario_name, DIRECTORY_DIMENSIONS["crm"])[0])
    if not isinstance(directories, list) or not 1 <= len(directories) <= 20:
        raise ValueError(translate("directories_error", language))
    directories = [filename(v, language) for v in directories]
    if len({directory.casefold() for directory in directories}) != len(directories):
        raise ValueError(translate("directories_error", language))
    policy = validate_policy(settings.get("password_policy", {}), language)
    # Encrypted Deep Nest is a decoy-only sample; it never places canary files.
    context = resolve_context({"canary_context": scenario["context"]}, language)
    directory_dimensions = DIRECTORY_DIMENSIONS.get(scenario_name, DIRECTORY_DIMENSIONS["crm"])
    current_year = datetime.now(timezone.utc).year
    year_names = [str(year) for year in range(current_year - 3, current_year + 1)]
    month_names = [f"{month:02d}_{name}" for month, name in enumerate(
        ("january", "february", "march", "april", "may", "june", "july", "august",
         "september", "october", "november", "december"), 1)]
    directory_levels = (year_names, month_names,
                        list(dict.fromkeys((*directory_dimensions[0], *directories))),
                        list(directory_dimensions[1]), list(directory_dimensions[2]))
    period = datetime.now(timezone.utc).strftime("%Y%m")
    basename = plausible_filename("nest")
    inventory, documents, consumed, archived = [], [], 0, 0
    format_counts = {name: 0 for name in FORMATS}
    passwords = set()

    def path():
        depth = rng.randint(1, directory_depth)
        return "/".join(rng.choice(directory_levels[level]) for level in range(depth))

    def budget(content):
        nonlocal consumed
        consumed += len(content)
        if consumed > MAX_CONTENT_BYTES:
            raise ValueError(translate("content_limit", language))

    def archive_budget(content):
        nonlocal archived
        archived += len(content)
        if archived > MAX_ARCHIVE_BYTES:
            raise ValueError(translate("archive_size_limit", language))

    def node(depth, location):
        password, hint = make_password(policy, depth, layers)
        password_mode = policy["mode"]
        if password in passwords:
            # Memorable policies can collapse to the same candidate (for
            # example, one word with no digits or symbols). Keep each archive
            # independently protected by switching collisions to the same
            # length/character policy in random mode.
            unique_policy = {**policy, "mode": "random"}
            if policy["mode"] == "memorable":
                password_mode = "random_fallback"
            for _ in range(128):
                password, hint = make_password(unique_policy, depth, layers)
                if password not in passwords:
                    break
            else:
                raise ValueError(translate("password_uniqueness_error", language))
        passwords.add(password)
        entry = {"path": location, "depth": depth, "password": password, "password_mode": password_mode,
                 "hint": hint, "hint_file": None, "files": []}
        inventory.append(entry)
        contents = []
        title = scenario["title"]
        env_count = 0
        used_members = set()

        def reserve_member(candidate):
            """Reserve a path case-insensitively for portable ZIP extraction."""
            key = candidate.casefold()
            if any(key == used or key.startswith(used + "/") or used.startswith(key + "/")
                   for used in used_members):
                return False
            used_members.add(key)
            return True

        archive_formats = rng.sample(tuple(FORMATS), len(FORMATS))
        for decoy_index in range(decoys):
            token_url = ""
            document_fmt = archive_formats[decoy_index % len(archive_formats)]
            format_counts[document_fmt] += 1
            if document_fmt == "env":
                content = render_switchable_env({"env_variable": scenario["env_key"]}, title, token_url, language)
                leaf = (".env.development", ".env.development_backup", ".env.development_previous")[env_count] if env_count < 3 else f".env.development_backup_{env_count + 1:02d}"
                env_count += 1
                for _ in range(64):
                    member = f"{path()}/{leaf}"
                    if reserve_member(member):
                        break
                else:
                    raise ValueError(translate("unique_path_error", language))
            else:
                # Generate synthetic records independently per document.
                data = list(records(scenario["columns"], rows, language))
                canary_cell = place_canary(scenario, data, token_url)
                reference = secrets.token_hex(6).upper()
                content = render(document_fmt, title, token_url, data, language, reference=reference, context=context,
                                 columns=scenario["columns"], table=scenario["table"], canary_cell=canary_cell)
                extension = FORMATS[document_fmt][0]
                suffixes = ("", "_current", "_previous", "_review", "_archive", "_backup", "_regional", "_reconciled")
                for _ in range(64):
                    leaf = f"{rng.choice(scenario['file_stems'])}{rng.choice(suffixes)}.{extension}"
                    member = f"{path()}/{leaf}"
                    if reserve_member(member):
                        break
                else:
                    raise ValueError(translate("unique_path_error", language))
            contents.append((member, content))
            detail = {"path": location + "!/" + member, "format": document_fmt, "canary": bool(token_url)}
            if token_url:
                detail["canary_url"] = token_url
                if document_fmt == "env":
                    detail["canary_field"] = scenario["env_key"]
                    detail["canary_location"] = "commented production setting"
                elif scenario.get("canary_field") and canary_cell is not None:
                    detail["canary_field"] = scenario["columns"][canary_cell[1]]["name"]
                    detail["canary_record"] = canary_cell[0] + 1
            entry["files"].append(detail)
            documents.append(detail)
            budget(content)
        if depth < layers:
            for _ in range(branches):
                archive_suffixes = ("", "_current", "_previous", "_regional", f"_{period}", "_review", "_backup", "_reconciled")
                for _ in range(64):
                    archive_name = f"{rng.choice(scenario['archive_stems'])}{rng.choice(archive_suffixes)}.zip"
                    member = f"{path()}/{archive_name}"
                    if reserve_member(member):
                        break
                else:
                    raise ValueError(translate("unique_path_error", language))
                child, child_hint = node(depth + 1, location + "!/" + member)
                contents.append((member, child))
                if child_hint:
                    note_path = hint_path(member, used_members)
                    contents.append((note_path, hint_text(child_hint)))
                    child_location = location + "!/" + member
                    child_entry = next(item for item in inventory if item["path"] == child_location)
                    child_entry["hint_file"] = location + "!/" + note_path
        elif not decoys:
            contents.append((f"{path()}/index.txt", b"Archive index\nNo pending exports.\n"))
        rng.shuffle(contents)
        if archived + sum(len(content) for _, content in contents) > MAX_ARCHIVE_BYTES:
            raise ValueError(translate("archive_size_limit", language))
        output = io.BytesIO()
        with pyzipper.AESZipFile(output, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as archive:
            archive.setpassword(password.encode("utf-8"))
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            for member, content in contents:
                write_archive_member(archive, member, content, info_type=archive.zipinfo_cls, language=language)
        encrypted_archive = output.getvalue()
        archive_budget(encrypted_archive)
        return encrypted_archive, hint

    def hint_text(hint):
        template = secrets.choice(HINT_NOTE_PRESETS.get(language, HINT_NOTE_PRESETS["ja"]))
        return template.format(hint=hint).encode("utf-8")

    def hint_path(archive_path, used_members=None):
        parent, leaf = posixpath.split(archive_path)
        stem, _ = posixpath.splitext(leaf)
        suffixes = ("handover", "restore_notes", "export_checklist", "key_register")
        for _ in range(64):
            suffix = rng.choice(suffixes)
            name = f"{stem}_{suffix}.txt"
            candidate = posixpath.join(parent, name) if parent else name
            key = candidate.casefold()
            conflict = used_members is not None and any(
                key == used or key.startswith(used + "/") or used.startswith(key + "/")
                for used in used_members
            )
            if not conflict:
                if used_members is not None:
                    used_members.add(key)
                return candidate
        raise ValueError(translate("unique_path_error", language))

    outer_name = f"{basename}.zip"
    outer, hint = node(1, outer_name)
    # A separate unencrypted delivery ZIP contains the outer archive and optional recovery-note decoy.
    # It never contains passwords or the operator inventory.
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as delivery:
        write_archive_member(delivery, outer_name, outer, language=language)
        if hint:
            note_path = hint_path(outer_name)
            write_archive_member(delivery, note_path, hint_text(hint), language=language)
            inventory[0]["hint_file"] = note_path
    summary = {"archives": count, "documents": len(documents), "canaries": 0,
               "format_counts": {name: amount for name, amount in format_counts.items() if amount}}
    password_lines = [
        "Physalia Encrypted Deep Nest verification passwords",
        "For authorized sample verification only. Contains passwords; keep private and do not deploy.",
        "",
    ]
    password_lines.extend(f"{item['path']}\t{item['password']}" for item in inventory)
    companion = Artifact(f"{basename}_zip_passwords.txt", "text/plain; charset=utf-8",
                         "\n".join(password_lines).encode("utf-8"), role="verification")
    deployment = output.getvalue()
    if len(deployment) > MAX_ARCHIVE_BYTES:
        raise ValueError(translate("archive_size_limit", language))
    return Artifact(f"{basename}_deployment.zip", "application/zip", deployment, [companion], summary)
