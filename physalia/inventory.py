"""Private lifecycle inventory for every generated deployment artifact."""
from datetime import datetime, timedelta, timezone
import hashlib
import json

from physalia.nesting import Artifact
from physalia.i18n import translate
from physalia.validation import is_reserved_example_url


def _physalia_download_name(name):
    if name.startswith("Physalia_"):
        return name
    if name == ".env":
        return "Physalia_environment.env"
    if name.startswith(".env."):
        suffix = name[len(".env."):].replace(".", "_")
        return f"Physalia_environment_{suffix}.env"
    return "Physalia_" + name


def attach_inventory(asset, kind, settings, language):
    # Make generated downloads easy to find while retaining plausible names
    # inside the decoy content and deployment archives.
    renamed = {asset.name: _physalia_download_name(asset.name)}
    asset.name = renamed[asset.name]
    for companion in asset.companions:
        renamed[companion.name] = _physalia_download_name(companion.name)
        companion.name = renamed[companion.name]
    for location in asset.summary.get("canary_locations", []):
        artifact_name = location.get("artifact")
        for old_name, new_name in renamed.items():
            if artifact_name == old_name or (isinstance(artifact_name, str)
                                              and artifact_name.startswith(old_name + "!/")):
                location["artifact"] = new_name + artifact_name[len(old_name):]
                break

    if kind == "nest":
        # The sample needs only a private password list for authorized testing.
        # Do not emit the opaque lifecycle inventory used by other generators.
        asset.summary.update({"kind": kind, "has_monitoring_url": False,
                              "canary_url_configured": False, "canary_placements": 0,
                              "canary_urls_supplied": 0, "canary_urls_used": 0,
                              "canary_urls_unused": 0, "reserved_canary_host": False})
        return asset

    raw_urls = settings.get("canary_urls")
    if kind in ("nest", "directory_maze", "encoding_maze") and raw_urls is not None:
        active_urls = [url for url in raw_urls if isinstance(url, str) and url.strip()] if isinstance(raw_urls, list) else []
    else:
        # Single-URL generators consume canary_url even if an API caller also
        # supplies the multi-URL field. Inventory must describe the URL the
        # artifact actually embeds, not an ignored setting.
        active_urls = ([settings["canary_url"]] if isinstance(settings.get("canary_url"), str)
                       and settings["canary_url"].strip() else [])
    if kind == "stream":
        active_urls = []
    configured = bool(active_urls)
    if kind == "nest":
        placements = asset.summary.get("canaries", 0)
    elif kind in ("directory_maze", "encoding_maze"):
        placements = asset.summary.get("canary_placements", 0)
    else:
        placements = int(configured)
    distinct_used = min(len(active_urls), placements)
    unused_urls = max(0, len(active_urls) - distinct_used)
    now = datetime.now(timezone.utc)
    inventory_name = asset.name + ".inventory.json"
    generation_details = {}
    if kind == "nest":
        generation_details = {
            "primary_document_format": asset.summary.get("primary_document_format"),
            "varied_formats": asset.summary.get("varied_formats"),
            "format_counts": asset.summary.get("format_counts", {}),
            "documents": asset.summary.get("documents", 0),
        }
    inventory = {
        "schema": "adg-deployment-v1", "method": kind, "created_at": now.isoformat(),
        "review_after": (now + timedelta(days=30)).isoformat(),
        # The inventory cannot contain its own digest without a self-reference.
        # Name it explicitly so operators know to retain this file as well.
        "inventory_file": inventory_name,
        "artifact": {"name": asset.name, "bytes": len(asset.content), "sha256": hashlib.sha256(asset.content).hexdigest()},
        **generation_details,
        **({"resolved_canary_context": asset.summary["resolved_canary_context"]}
           if "resolved_canary_context" in asset.summary else {}),
        "operator_files": [item.name for item in asset.companions if item.role == "operator"],
        "operator_artifacts": [{"name": item.name, "bytes": len(item.content),
                                "sha256": hashlib.sha256(item.content).hexdigest()}
                               for item in asset.companions if item.role == "operator"],
        "deployment_packages": [{"name": item.name, "bytes": len(item.content),
                                 "sha256": hashlib.sha256(item.content).hexdigest()}
                                for item in asset.companions if item.role == "deployment"],
        "canary_summary": {"configured": configured, "placements": placements,
                           "distinct_urls_supplied": len(active_urls),
                           "distinct_urls_used": distinct_used, "unused_urls": unused_urls,
                           "locations": asset.summary.get("canary_locations", [])},
        "settings": settings, "owner": "", "deployed_at": "", "deployment_location": "",
        "notification_tested_at": "", "retired_at": "",
        "warning": translate("operator_warning", language),
    }
    asset.companions.append(Artifact(inventory_name, "application/json",
                           json.dumps(inventory, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")))
    asset.summary["canary_url_configured"] = configured
    asset.summary["canary_placements"] = placements
    asset.summary["canary_urls_supplied"] = len(active_urls)
    asset.summary["canary_urls_used"] = distinct_used
    asset.summary["canary_urls_unused"] = unused_urls
    asset.summary["has_monitoring_url"] = placements > 0
    asset.summary["reserved_canary_host"] = any(is_reserved_example_url(value) for value in active_urls)
    return asset
