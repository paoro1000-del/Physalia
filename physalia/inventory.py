"""Private lifecycle inventory for every generated deployment artifact."""
from datetime import datetime, timedelta, timezone
import hashlib
import json

from physalia.nesting import Artifact
from physalia.i18n import translate
from physalia.validation import is_reserved_example_url


def attach_inventory(asset, kind, settings, language):
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
        "inventory_file": asset.name + ".inventory.json",
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
    asset.companions.append(Artifact(asset.name + ".inventory.json", "application/json",
                           json.dumps(inventory, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")))
    asset.summary["canary_url_configured"] = configured
    asset.summary["canary_placements"] = placements
    asset.summary["canary_urls_supplied"] = len(active_urls)
    asset.summary["canary_urls_used"] = distinct_used
    asset.summary["canary_urls_unused"] = unused_urls
    asset.summary["has_monitoring_url"] = placements > 0
    asset.summary["reserved_canary_host"] = any(is_reserved_example_url(value) for value in active_urls)
    return asset
