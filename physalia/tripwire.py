"""Generate synthetic decoys and an operator-only replenishment watcher."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import secrets
import time
import zipfile

from physalia.archive_metadata import write_archive_member
from physalia.nesting import Artifact
from physalia.validation import integer

LOGGER = logging.getLogger("physalia")


def _tripwire_files(language: str, count: int) -> list[tuple[str, bytes]]:
    japanese = language == "ja"
    batch = secrets.randbelow(900) + 100
    root = secrets.choice(("business", "company", "department", "shared", "workspace"))
    entries = [
        (f"{root}/finance/quarterly_forecast_{batch}.csv",
         "部署,予算コード,計画額,更新区分\n" if japanese else "Department,Budget code,Planned amount,Revision\n",
         "企画,PLAN-041,1280000,仮計画\n運用,PLAN-052,760000,見直し中\n" if japanese else "Planning,PLAN-041,1280000,Draft\nOperations,PLAN-052,760000,Under review\n"),
        (f"{root}/finance/vendor_renewals_{batch}.txt",
         "取引先更新予定（架空データ）\n" if japanese else "Vendor renewal schedule (synthetic data)\n",
         "Example Vendor 17 — 更新確認: 2026-11-18\nExample Vendor 42 — 見積待ち\n" if japanese else "Example Vendor 17 — review: 2026-11-18\nExample Vendor 42 — quote pending\n"),
        (f"{root}/operations/maintenance_windows_{batch}.json", "",
         '{\n  "source": "synthetic",\n  "windows": [{"service": "portal-alpha", "window": "2026-11-21T01:00Z"}, {"service": "batch-07", "window": "2026-11-23T02:30Z"}]\n}\n'),
        (f"{root}/operations/restore_notes_{batch}.txt",
         "復旧作業メモ（架空）\n対象: archive-node-03\n手順書: operations/recovery-index-v4\n確認者: 未割当\n" if japanese else "Recovery work notes (synthetic)\nTarget: archive-node-03\nRunbook: operations/recovery-index-v4\nReviewer: unassigned\n",
         ""),
        (f"{root}/engineering/build_registry_{batch}.csv",
         "成果物,保管先,状態\n" if japanese else "Artifact,Registry path,Status\n",
         "client-shell-2.8,staging/package-14,保留\nworker-core-1.6,archive/build-09,確認待ち\n" if japanese else "client-shell-2.8,staging/package-14,Held\nworker-core-1.6,archive/build-09,Review pending\n"),
        (f"{root}/engineering/deployment_manifest_{batch}.json", "",
         '{\n  "environment": "staging-sample",\n  "release": "r-204",\n  "endpoint": "not-configured",\n  "credentials": "not included"\n}\n'),
        (f"{root}/shared/project_handoff_{batch}.txt",
         "プロジェクト引継ぎ（架空データ）\n作業番号: CASE-731\n納品確認: 未完了\n資料索引: shared/index-12\n" if japanese else "Project handoff (synthetic data)\nWork item: CASE-731\nDelivery review: pending\nDocument index: shared/index-12\n",
         ""),
        (f"{root}/archive/archive_catalog_{batch}.csv",
         "記録ID,保管区分,確認状態\n" if japanese else "Record ID,Retention class,Review status\n",
         "ARC-2041,年度末,未確認\nARC-2098,移行対象,対応中\n" if japanese else "ARC-2041,Fiscal close,Unreviewed\nARC-2098,Migration,In progress\n"),
    ]
    chosen = secrets.SystemRandom().sample(entries, count)
    return [(path, (header + body).encode("utf-8")) for path, header, body in chosen]


def _monitor_script(file_hashes: dict[str, str], language: str) -> bytes:
    baseline = json.dumps(file_hashes, ensure_ascii=True, sort_keys=True)
    ja = language == "ja"
    strings = {
        "start": "監視開始。対象ファイルの変更・削除・差し替えを確認します。読み取りは検知しません。" if ja else "Monitoring started. Watching for changes, deletion and replacement. Reads are not detected.",
        "change": "カナリアファイルの状態変化" if ja else "Tripwire file state changed",
        "error": "監視ログを書き込めません" if ja else "Could not write the monitor log",
        "hint": "Ctrl+Cで停止できます。検知してもプロセス停止や通信遮断は行いません。" if ja else "Press Ctrl+C to stop. Detection does not stop processes or isolate the host.",
    }
    template = r'''#!/usr/bin/env python3
"""Locally replenish changed decoys. No network or process control."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
import time
from datetime import datetime, timezone

BASELINE = __BASELINE__
TEXT = __TEXT__
MAX_LOG_BYTES = 5 * 1024 * 1024
DECOY_NAMES = ("quarterly_report", "vendor_register", "project_handoff", "operations_plan", "invoice_summary")

def replenish(root, relative, generated, total_bytes, max_files, max_bytes):
    # Only create a new file in an existing, non-symlinked decoy directory.
    parent = root
    for part in Path(relative).parts[:-1]:
        parent = parent / part
        info = parent.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise OSError("decoy directory is not a regular directory")
    token = secrets.token_hex(8)
    kind = secrets.choice(("csv", "txt", "json"))
    if kind == "csv":
        content = ("Record,Status,Reference\nPLAN-" + token + ",Review pending,Sample data\n").encode("utf-8")
    elif kind == "txt":
        content = ("Operations handoff\nReference: CASE-" + token + "\nStatus: pending review\n").encode("utf-8")
    else:
        content = (json.dumps({"reference": "PLAN-" + token, "status": "draft", "owner": "team-operations"}) + "\n").encode("utf-8")
    if (max_files and generated >= max_files) or (max_bytes and total_bytes + len(content) > max_bytes):
        return None
    path = parent / (secrets.choice(DECOY_NAMES) + "_" + token + "." + kind)
    with path.open("xb") as output:
        output.write(content)
    return path.relative_to(root).as_posix(), hashlib.sha256(content).hexdigest(), len(content)

def snapshot(root, relative):
    path = root
    parts = Path(relative).parts
    try:
        for part in parts[:-1]:
            path = path / part
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
                return "unsafe-path"
        path = path / parts[-1]
        info = path.lstat()
        if stat.S_ISLNK(info.st_mode):
            return "symlink"
        if not stat.S_ISREG(info.st_mode):
            return "not-regular-file"
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for block in iter(lambda: source.read(65536), b""):
                digest.update(block)
        return digest.hexdigest()
    except FileNotFoundError:
        return "missing"
    except OSError as exc:
        return "unreadable:" + type(exc).__name__

def record(log_path, relative, before, after):
    event = {"time": datetime.now(timezone.utc).isoformat(), "event": TEXT["change"],
             "path": relative, "before": before, "after": after}
    line = json.dumps(event, ensure_ascii=True, sort_keys=True)
    print(line, flush=True)
    try:
        if log_path.exists() and log_path.stat().st_size + len((line + "\n").encode("utf-8")) > MAX_LOG_BYTES:
            os.replace(log_path, log_path.with_name(log_path.name + ".1"))
        with log_path.open("a", encoding="utf-8") as output:
            output.write(line + "\n")
    except OSError as exc:
        print(TEXT["error"] + ": " + str(exc), file=sys.stderr, flush=True)

def main():
    parser = argparse.ArgumentParser(description=TEXT["start"])
    parser.add_argument("root", help="directory where the deployment ZIP was extracted")
    parser.add_argument("--interval", type=float, default=1.0, help="poll interval in seconds (0.25–60)")
    parser.add_argument("--log", help="local JSONL event log (default: beside this script)")
    parser.add_argument("--max-files", type=int, default=0, help="maximum replacements per run; 0 means unlimited")
    parser.add_argument("--max-bytes", type=int, default=0, help="maximum replacement content bytes per run; 0 means unlimited")
    args = parser.parse_args()
    if not 0.25 <= args.interval <= 60:
        parser.error("--interval must be between 0.25 and 60 seconds")
    if args.max_files < 0 or args.max_bytes < 0:
        parser.error("limits must be non-negative")
    root = Path(args.root).expanduser().resolve(strict=True)
    if not root.is_dir():
        parser.error("root must be a directory")
    log_path = Path(args.log).expanduser().resolve() if args.log else Path(__file__).with_name("tripwire-alerts.jsonl")
    previous = dict(BASELINE)
    generated = 0
    total_bytes = 0
    print(TEXT["start"], flush=True)
    print(TEXT["hint"], flush=True)
    try:
        while True:
            for relative, expected in list(previous.items()):
                current = snapshot(root, relative)
                if current != expected:
                    record(log_path, relative, expected, current)
                    del previous[relative]
                    try:
                        replacement = replenish(root, relative, generated, total_bytes, args.max_files, args.max_bytes)
                        if replacement is not None:
                            new_relative, digest, size = replacement
                            previous[new_relative] = digest
                            generated += 1
                            total_bytes += size
                            print("Created: " + new_relative, flush=True)
                        else:
                            print("Replacement limit reached", file=sys.stderr, flush=True)
                    except OSError as exc:
                        print("Could not replenish decoy: " + str(exc), file=sys.stderr, flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Stopped.", flush=True)

if __name__ == "__main__":
    main()
'''
    return template.replace("__BASELINE__", baseline).replace("__TEXT__", repr(strings)).encode("utf-8")


def generate_ransomware_tripwire(settings: dict, language: str = "ja") -> Artifact:
    started = time.monotonic()
    language = language if language in ("ja", "en") else "ja"
    count = integer(settings.get("files", 6), "files", 4, 8, language)
    LOGGER.debug("tripwire_generation_started requested_files=%d language=%s", count, language)
    files = _tripwire_files(language, count)
    output = io.BytesIO()
    hashes = {}
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, content in files:
            hashes[relative] = hashlib.sha256(content).hexdigest()
            write_archive_member(archive, relative, content, language=language)
    deployment_name = "ransomware_tripwire_deployment.zip"
    monitor_name = "ransomware_tripwire_monitor.py"
    summary = {"kind": "ransomware_tripwire", "files": len(files),
               "monitor": monitor_name, "detection": "content_change_delete_replace"}
    monitor = Artifact(monitor_name, "text/x-python; charset=utf-8",
                       _monitor_script(hashes, language), role="operator")
    deployment = output.getvalue()
    LOGGER.info("tripwire_generation_complete files=%d deployment_bytes=%d monitor_bytes=%d elapsed_ms=%d",
                len(files), len(deployment), len(monitor.content),
                max(0, round((time.monotonic() - started) * 1000)))
    return Artifact(deployment_name, "application/zip", deployment, [monitor], summary=summary)
