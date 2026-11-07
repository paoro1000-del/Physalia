"""Bounded trees of AES-encrypted ZIPs with varied synthetic documents."""

import io
import logging
import posixpath
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pyzipper

from physalia.archive_metadata import write_archive_member
from physalia.database import records
from physalia.formats import FORMATS, render, render_switchable_env, resolve_context
from physalia.i18n import translate
from physalia.naming import plausible_filename
from physalia.passwords import make_password, validate_policy
from physalia.scenarios import place_canary, scenario_for
from physalia.validation import filename, integer

MAX_LAYERS = 8
MAX_NODES = 40
MAX_CONTENT_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
LOGGER = logging.getLogger("physalia")
DIRECTORY_DIMENSIONS = {
    "crm": (
        (
            "1048_customer",
            "2176_customer",
            "3891_customer",
            "west_01_account",
            "enterprise_02_account",
        ),
        (
            "03_day_close",
            "08_day_close",
            "14_day_close",
            "21_day_close",
            "27_day_close",
        ),
        ("a_owner_team", "b_owner_team", "01_review_queue", "02_regional_review"),
    ),
    "migration": (
        (
            "014_migration_batch",
            "027_migration_batch",
            "01_legacy_source",
            "02_import_target",
            "03_delta_review",
        ),
        ("1048_customer", "2176_customer", "west_01_account", "enterprise_02_account"),
        (
            "03_day_close",
            "08_day_close",
            "14_day_close",
            "21_day_close",
            "27_day_close",
        ),
    ),
    "archive": (
        (
            "1048_customer",
            "2176_customer",
            "west_01_account",
            "enterprise_02_account",
            "01_retention_hold",
        ),
        ("01_snapshot", "15_snapshot", "08_day_close", "21_day_close"),
        ("a_owner_team", "b_owner_team", "01_restore_review", "02_retention_check"),
    ),
    "cards": (
        ("1048_cardholder", "2176_cardholder", "01_renewal_batch", "west_billing"),
        (
            "03_day_close",
            "08_day_close",
            "14_day_close",
            "21_day_close",
            "27_day_close",
        ),
        ("a_review_team", "b_review_team", "01_reconciliation", "02_expiry_review"),
    ),
    "companies": (
        ("1048_company", "2176_company", "west_company", "enterprise_01_account"),
        ("01_contact_updates", "02_ownership_review", "08_day_close", "21_day_close"),
        ("a_owner_team", "b_owner_team", "01_industry_review"),
    ),
    "passwords": (
        (
            "01_billing_service",
            "02_support_service",
            "03_archive_service",
            "04_service_portal",
        ),
        ("1048_account", "2176_account", "03_admin_account", "04_recovery_queue"),
        ("01_rotation_review", "a_owner_team", "b_owner_team", "02_access_review"),
    ),
    "api_credentials": (
        (
            "01_billing_integration",
            "02_support_integration",
            "1048_client",
            "2176_client",
        ),
        ("01_rotation", "15_rotation", "01_scope_review", "21_day_close"),
        ("a_owner_team", "b_owner_team", "01_access_review", "01_release_check"),
    ),
    "invoices": (
        ("1048_customer", "2176_customer", "west_region", "enterprise_01_account"),
        (
            "03_day_close",
            "08_day_close",
            "14_day_close",
            "21_day_close",
            "27_day_close",
        ),
        (
            "a_collector_team",
            "b_collector_team",
            "01_overdue_review",
            "02_reconciliation",
        ),
    ),
    "employees": (
        (
            "01_finance_department",
            "02_ops_department",
            "03_support_department",
            "west_region",
        ),
        ("1048_employee", "2176_employee", "3891_employee", "01_payroll_review"),
        ("a_manager_team", "b_manager_team", "01_onboarding", "02_role_review"),
    ),
    "vendors": (
        ("1048_vendor", "2176_vendor", "west_supplier", "01_service_partner"),
        ("014_contract", "027_contract", "01_renewal_review", "21_day_close"),
        ("a_owner_team", "b_owner_team", "01_due_diligence", "02_finance_review"),
    ),
    "orders": (
        ("1048_customer", "2176_customer", "west_region", "enterprise_01_account"),
        (
            "03_day_close",
            "08_day_close",
            "14_day_close",
            "21_day_close",
            "27_day_close",
        ),
        (
            "a_fulfillment_team",
            "b_fulfillment_team",
            "01_returns_review",
            "02_billing_check",
        ),
    ),
    "tickets": (
        ("1048_customer", "2176_customer", "west_region", "01_priority_queue"),
        ("014_case", "027_case", "08_day_close", "21_day_close"),
        ("a_agent_team", "b_agent_team", "01_escalation_review", "02_resolution_check"),
    ),
    "assets": (
        ("west_region", "east_region", "014_office", "02_datacenter"),
        ("1048_device", "2176_device", "3891_endpoint", "01_license_review"),
        ("a_assigned_team", "b_assigned_team", "01_lifecycle_review"),
    ),
    "cloud": (
        ("014_subscription", "027_subscription", "west_tenant", "01_shared_platform"),
        ("east_region", "west_region", "1048_resource_group", "2176_resource_group"),
        ("014_deployment", "027_deployment", "a_owner_team", "01_recovery_review"),
    ),
}
HINT_NOTE_PRESETS = {
    "ja": (
        "データ移行 引継ぎメモ\n展開キー控えは月次の鍵管理票を参照。\n",
        "保管データ復元メモ\n復号キーは更新済みの保管ノートを確認。\n",
        "アーカイブ整理記録\n鍵管理票は引継ぎ資料と合わせて保管。\n",
        "共有フォルダー移行\nZIPキーは月次パスワード台帳を参照。\n",
    ),
    "en": (
        "Export handover\nSee the monthly key register for the archive key.\n",
        "Restore notes\nSee the updated storage note for the decryption key.\n",
        "Archive closeout\nThe key register is stored with the handover records.\n",
        "Shared folder migration\nSee the monthly password register for the ZIP key.\n",
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
    started = time.monotonic()
    LOGGER.debug("deep_nest_started setting_keys=%s",
                 ",".join(sorted(key for key in settings if isinstance(key, str))))
    layers = integer(settings.get("layers", 3), "layers", 1, MAX_LAYERS, language)
    branches = integer(settings.get("branches", 3), "branches", 1, 4, language)
    decoys = integer(settings.get("decoys", 4), "decoys", 0, 10, language)
    directory_depth = integer(
        settings.get("directory_depth", 6), "directory_depth", 1, 8, language
    )
    rows = integer(settings.get("rows", 1100), "rows", 1, 10000, language)
    count = sum(branches**n for n in range(layers))
    if count > MAX_NODES:
        raise ValueError(
            translate("node_limit", language, count=count, maximum=MAX_NODES)
        )
    rng = secrets.SystemRandom()
    scenario_name, scenario = scenario_for(settings, language)
    directories = settings.get(
        "directories",
        list(DIRECTORY_DIMENSIONS.get(scenario_name, DIRECTORY_DIMENSIONS["crm"])[0]),
    )
    if not isinstance(directories, list) or not 1 <= len(directories) <= 20:
        raise ValueError(translate("directories_error", language))
    directories = [filename(v, language) for v in directories]
    if len({directory.casefold() for directory in directories}) != len(directories):
        raise ValueError(translate("directories_error", language))
    policy = validate_policy(settings.get("password_policy", {}), language)
    # Encrypted Deep Nest is a decoy-only sample; it never places canary files.
    context = resolve_context({"canary_context": scenario["context"]}, language)
    directory_dimensions = DIRECTORY_DIMENSIONS.get(
        scenario_name, DIRECTORY_DIMENSIONS["crm"]
    )
    current_year = datetime.now(UTC).year
    year_names = [str(year) for year in range(current_year - 3, current_year + 1)]
    month_names = [
        f"{month:02d}_{name}"
        for month, name in enumerate(
            (
                "january",
                "february",
                "march",
                "april",
                "may",
                "june",
                "july",
                "august",
                "september",
                "october",
                "november",
                "december",
            ),
            1,
        )
    ]
    directory_levels = (
        year_names,
        month_names,
        list(dict.fromkeys((*directory_dimensions[0], *directories))),
        list(directory_dimensions[1]),
        list(directory_dimensions[2]),
        ["active", "pending", "review", "closed", "retained", "restricted"],
        ["current", "previous", "approved", "archived", "reconciled"],
        ["east_region", "west_region", "central_region", "north_region"],
    )
    period = datetime.now(UTC).strftime("%Y%m")
    basename = plausible_filename("nest")
    inventory, documents, consumed, archived = [], [], 0, 0
    nodes_started = 0
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
        nonlocal nodes_started
        nodes_started += 1
        LOGGER.debug("deep_nest_node_started node=%d depth=%d", nodes_started, depth)
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
        entry = {
            "path": location,
            "depth": depth,
            "password": password,
            "password_mode": password_mode,
            "hint": hint,
            "hint_file": None,
            "files": [],
        }
        inventory.append(entry)
        contents = []
        title = scenario["title"]
        env_count = 0
        used_members = set()

        def reserve_member(candidate):
            """Reserve a path case-insensitively for portable ZIP extraction."""
            key = candidate.casefold()
            if any(
                key == used or key.startswith(used + "/") or used.startswith(key + "/")
                for used in used_members
            ):
                return False
            used_members.add(key)
            return True

        archive_formats = rng.sample(tuple(FORMATS), len(FORMATS))
        for decoy_index in range(decoys):
            token_url = ""
            document_fmt = archive_formats[decoy_index % len(archive_formats)]
            format_counts[document_fmt] += 1
            if document_fmt == "env":
                content = render_switchable_env(
                    {"env_variable": scenario["env_key"]}, title, token_url, language
                )
                leaf = (
                    (
                        ".env.development",
                        ".env.development_backup",
                        ".env.development_previous",
                    )[env_count]
                    if env_count < 3
                    else f".env.development_backup_{env_count + 1:02d}"
                )
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
                content = render(
                    document_fmt,
                    title,
                    token_url,
                    data,
                    language,
                    reference=reference,
                    context=context,
                    columns=scenario["columns"],
                    table=scenario["table"],
                    canary_cell=canary_cell,
                )
                extension = FORMATS[document_fmt][0]
                suffixes = (
                    "",
                    "_current",
                    "_previous",
                    "_review",
                    "_archive",
                    "_backup",
                    "_regional",
                    "_reconciled",
                )
                for _ in range(64):
                    leaf = f"{rng.choice(scenario['file_stems'])}{rng.choice(suffixes)}.{extension}"
                    member = f"{path()}/{leaf}"
                    if reserve_member(member):
                        break
                else:
                    raise ValueError(translate("unique_path_error", language))
            contents.append((member, content))
            detail = {
                "path": location + "!/" + member,
                "format": document_fmt,
                "canary": bool(token_url),
            }
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
                archive_suffixes = (
                    "",
                    "_current",
                    "_previous",
                    "_regional",
                    f"_{period}",
                    "_review",
                    "_backup",
                    "_reconciled",
                )
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
                    contents.append((note_path, hint_text()))
                    child_location = location + "!/" + member
                    child_entry = next(
                        item for item in inventory if item["path"] == child_location
                    )
                    child_entry["hint_file"] = location + "!/" + note_path
        elif not decoys:
            contents.append(
                (f"{path()}/index.txt", b"Archive index\nNo pending exports.\n")
            )
        rng.shuffle(contents)
        if archived + sum(len(content) for _, content in contents) > MAX_ARCHIVE_BYTES:
            raise ValueError(translate("archive_size_limit", language))
        output = io.BytesIO()
        with pyzipper.AESZipFile(
            output, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
        ) as archive:
            archive.setpassword(password.encode("utf-8"))
            archive.setencryption(pyzipper.WZ_AES, nbits=256)
            for member, content in contents:
                write_archive_member(
                    archive,
                    member,
                    content,
                    info_type=archive.zipinfo_cls,
                    language=language,
                )
        encrypted_archive = output.getvalue()
        archive_budget(encrypted_archive)
        return encrypted_archive, hint

    def hint_text():
        return secrets.choice(
            HINT_NOTE_PRESETS.get(language, HINT_NOTE_PRESETS["ja"])
        ).encode("utf-8")

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
    outer, _root_hint = node(1, outer_name)
    summary = {
        "archives": count,
        "documents": len(documents),
        "canaries": 0,
        "format_counts": {
            name: amount for name, amount in format_counts.items() if amount
        },
    }
    password_lines = [
        "Physalia Encrypted Deep Nest verification passwords",
        "For authorized sample verification only. Contains passwords; keep private and do not deploy.",
        "",
    ]
    password_lines.extend(f"{item['path']}\t{item['password']}" for item in inventory)
    companion = Artifact(
        f"{basename}_zip_passwords.txt",
        "text/plain; charset=utf-8",
        "\n".join(password_lines).encode("utf-8"),
        role="verification",
    )
    # Deliver the first AES-encrypted archive itself, without a plaintext ZIP wrapper.
    LOGGER.info("deep_nest_complete nodes=%d documents=%d archives=%d plaintext_bytes=%d encrypted_bytes=%d elapsed_ms=%d",
                count, len(documents), archived, consumed, len(outer),
                max(0, round((time.monotonic() - started) * 1000)))
    return Artifact(outer_name, "application/zip", outer, [companion], summary)
