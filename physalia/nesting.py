"""Bounded trees of AES-encrypted ZIPs with varied synthetic documents."""
from dataclasses import dataclass, field
import io
import json
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
from physalia.validation import CanaryURLCycle, canary_url_list, filename, integer
from physalia.scenarios import place_canary, scenario_for

MAX_LAYERS = 8
MAX_NODES = 40
MAX_CONTENT_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
PRIMARY_FORMAT_PERCENT = 75
ALTERNATE_FORMAT_WEIGHTS = {
    "xlsx": 20, "sqlite": 20, "env": 15, "csv": 15,
    "pdf": 10, "json": 10, "txt": 5, "html": 3, "pptx": 2,
}
DEFAULT_DIRECTORIES = ["finance", "operations", "exports", "backups", "archive", "config", "reports"]
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
    chance = integer(settings.get("canary_percent", 25), "canary_percent", 0, 100, language)
    count = sum(branches ** n for n in range(layers))
    if count > MAX_NODES:
        raise ValueError(translate("node_limit", language, count=count, maximum=MAX_NODES))
    fmt = settings.get("format", "txt")
    if not isinstance(fmt, str) or fmt not in FORMATS:
        raise ValueError(translate("invalid_format", language))
    varied_formats = settings.get("varied_formats", True)
    if not isinstance(varied_formats, bool):
        raise ValueError(translate("invalid_format", language))
    directories = settings.get("directories", DEFAULT_DIRECTORIES)
    if not isinstance(directories, list) or not 1 <= len(directories) <= 20:
        raise ValueError(translate("directories_error", language))
    directories = [filename(v, language) for v in directories]
    if len({directory.casefold() for directory in directories}) != len(directories):
        raise ValueError(translate("directories_error", language))
    policy = validate_policy(settings.get("password_policy", {}), language)
    url_cycle = CanaryURLCycle(canary_url_list(settings, language))
    scenario_name, scenario = scenario_for(settings, language)
    context = resolve_context({"canary_context": scenario["context"]}, language)
    period = datetime.now(timezone.utc).strftime("%Y%m")
    basename = filename(settings["filename"], language) if settings.get("filename") else plausible_filename("nest")
    rng = secrets.SystemRandom()
    inventory, documents, consumed, archived = [], [], 0, 0
    format_counts = {name: 0 for name in FORMATS}
    passwords = set()

    def path():
        parts, used = [], set()
        for _ in range(rng.randint(1, directory_depth)):
            candidates = [name for name in directories if name.casefold() not in used]
            if not candidates:
                candidates = [name for name in directories if not parts or name.casefold() != parts[-1].casefold()]
            if not candidates:
                candidates = directories
            selected = rng.choice(candidates)
            parts.append(selected)
            used.add(selected.casefold())
        return "/".join(parts)

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

        for _ in range(decoys):
            token_url = url_cycle.next() if rng.randrange(100) < chance else ""
            document_fmt = fmt
            if varied_formats and rng.randrange(100) >= PRIMARY_FORMAT_PERCENT:
                alternatives = [(name, weight) for name, weight in ALTERNATE_FORMAT_WEIGHTS.items() if name != fmt]
                ticket = rng.randrange(sum(weight for _, weight in alternatives))
                for name, weight in alternatives:
                    if ticket < weight:
                        document_fmt = name
                        break
                    ticket -= weight
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
                if document_fmt != "env" and scenario.get("canary_field") and canary_cell is not None:
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
                write_archive_member(archive, member, content, info_type=pyzipper.ZipInfo, language=language)
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
    manifest = {
        "format": "Physalia operator inventory v3", "warning": translate("operator_warning", language),
        "deployment": outer_name, "policy": policy, "layers": layers, "branches": branches,
        "scenario": scenario_name, "schema": scenario["schema"],
        "primary_document_format": fmt, "varied_formats": varied_formats,
        "format_counts": {name: amount for name, amount in format_counts.items() if amount},
        "archives": inventory, "documents": documents,
        "summary": {"archives": count, "documents": len(documents), "canaries": sum(d["canary"] for d in documents),
                    "primary_document_format": fmt, "varied_formats": varied_formats,
                    "format_counts": {name: amount for name, amount in format_counts.items() if amount}},
    }
    companion = Artifact(f"{basename}.operator.json", "application/json",
                         json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8"))
    deployment = output.getvalue()
    if len(deployment) > MAX_ARCHIVE_BYTES:
        raise ValueError(translate("archive_size_limit", language))
    return Artifact(f"{basename}_deployment.zip", "application/zip", deployment, [companion], manifest["summary"])
