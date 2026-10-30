"""Validate study metadata or check the blank starter template using stdlib only."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "examples" / "deception-study-metadata-template.schema.json"
TEMPLATE_PATH = ROOT / "examples" / "deception-study-metadata-template.json"
SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SUPPORTED_KEYWORDS = {
    "$schema", "title", "description", "type", "additionalProperties",
    "required", "properties", "items", "const", "enum", "minimum",
    "minLength", "maxLength", "minItems", "maxItems", "uniqueItems",
}
MAX_METADATA_BYTES = 2 * 1024 * 1024


def safe_display(value):
    """Escape terminal controls and bidi formatting in input-derived errors."""
    return "".join(
        character if character.isprintable() else
        (f"\\u{ord(character):04x}" if ord(character) <= 0xFFFF else f"\\U{ord(character):08x}")
        for character in str(value))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError(f"Non-standard JSON constant: {value}")


def _load_json(path: Path):
    path = Path(path)
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode):
        raise OSError(f"{path} must be a regular file")
    if before.st_size > MAX_METADATA_BYTES:
        raise ValueError(f"{path} exceeds 2 MiB")
    identity = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                              info.st_mtime_ns, info.st_ctime_ns)
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
             | getattr(os, "O_NONBLOCK", 0))
    descriptor = os.open(path, flags)
    try:
        with os.fdopen(descriptor, "rb") as source:
            descriptor = -1
            opened = os.fstat(source.fileno())
            if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
                raise OSError(f"{path} changed while opening")
            raw = source.read(MAX_METADATA_BYTES + 1)
            finished = os.fstat(source.fileno())
            after = path.stat(follow_symlinks=False)
        if len(raw) > MAX_METADATA_BYTES:
            raise ValueError(f"{path} exceeds 2 MiB")
        if identity(opened) != identity(finished) or identity(finished) != identity(after):
            raise OSError(f"{path} changed while reading")
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _matches_type(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValueError(f"Unsupported JSON Schema type: {expected}")


def _check_schema_node(schema, path="$schema"):
    if not isinstance(schema, dict):
        raise ValueError(f"{path} must be an object")
    unsupported = set(schema) - SUPPORTED_KEYWORDS
    if unsupported:
        raise ValueError(f"{path} uses unsupported schema keywords: {sorted(unsupported)}")
    if "type" in schema:
        types = schema["type"]
        if isinstance(types, str):
            types = [types]
        if not isinstance(types, list) or not types or any(not isinstance(item, str) for item in types):
            raise ValueError(f"{path}.type must be a type name or a non-empty type-name array")
        for item in types:
            if item not in {"object", "array", "string", "integer", "number", "boolean", "null"}:
                raise ValueError(f"{path}.type has an unsupported value: {item}")
    if "required" in schema:
        required = schema["required"]
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise ValueError(f"{path}.required must be an array of strings")
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            raise ValueError(f"{path}.properties must be an object")
        for name, child in schema["properties"].items():
            _check_schema_node(child, f"{path}.properties.{name}")
    if "items" in schema:
        _check_schema_node(schema["items"], f"{path}.items")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise ValueError(f"{path}.enum must be a non-empty array")
    if "minimum" in schema and (isinstance(schema["minimum"], bool)
                                 or not isinstance(schema["minimum"], (int, float))):
        raise ValueError(f"{path}.minimum must be a number")
    for keyword in ("minLength", "maxLength", "minItems", "maxItems"):
        value = schema.get(keyword)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError(f"{path}.{keyword} must be a non-negative integer")
    if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
        raise ValueError(f"{path}.uniqueItems must be a boolean")
    if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], bool):
        raise ValueError(f"{path}.additionalProperties must be a boolean")


def _validate(value, schema, path="$", allow_incomplete=False):
    if "const" in schema and value != schema["const"]:
        raise ValueError(f"{path} does not match its required constant")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path} is not one of its allowed values")

    expected = schema.get("type")
    if expected is not None:
        types = expected if isinstance(expected, list) else [expected]
        if not any(_matches_type(value, item) for item in types):
            raise ValueError(f"{path} has type {type(value).__name__}; expected {types}")

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        missing = set(schema.get("required", [])) - set(value)
        if missing:
            raise ValueError(f"{path} is missing required properties: {sorted(missing)}")
        extras = set(value) - set(properties)
        if schema.get("additionalProperties") is False and extras:
            raise ValueError(f"{path} has unexpected properties: {sorted(extras)}")
        for name, item in value.items():
            if name in properties:
                _validate(item, properties[name], f"{path}.{name}", allow_incomplete)
    elif isinstance(value, list) and "items" in schema:
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if minimum is not None and len(value) < minimum and not (allow_incomplete and not value):
            raise ValueError(f"{path} has fewer than {minimum} items")
        if maximum is not None and len(value) > maximum:
            raise ValueError(f"{path} has more than {maximum} items")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                raise ValueError(f"{path} contains duplicate items")
        for index, item in enumerate(value):
            _validate(item, schema["items"], f"{path}[{index}]", allow_incomplete)
    elif isinstance(value, str):
        minimum = schema.get("minLength")
        maximum = schema.get("maxLength")
        if (minimum is not None and (len(value) < minimum or (minimum > 0 and not value.strip()))
                and not (allow_incomplete and not value)):
            raise ValueError(f"{path} is shorter than {minimum} characters")
        if maximum is not None and len(value) > maximum:
            raise ValueError(f"{path} is longer than {maximum} characters")
    elif (isinstance(value, (int, float)) and not isinstance(value, bool)
          and "minimum" in schema and value < schema["minimum"]):
        raise ValueError(f"{path} is below its minimum")


def main():
    parser = argparse.ArgumentParser(description="Validate study metadata against the bundled schema.")
    parser.add_argument("metadata", nargs="?", type=Path,
                        help="completed UTF-8 metadata JSON (omit to check the blank starter template shape)")
    args = parser.parse_args()
    try:
        schema = _load_json(SCHEMA_PATH)
        template_mode = args.metadata is None
        if (not template_mode
                and os.path.normcase(os.path.abspath(args.metadata))
                == os.path.normcase(os.path.abspath(TEMPLATE_PATH))):
            raise ValueError(
                "The starter template is intentionally incomplete. Omit the metadata argument to check its shape, "
                "or copy it, fill the required fields and validate the completed file."
            )
        metadata = _load_json(TEMPLATE_PATH if template_mode else args.metadata)
        if schema.get("$schema") != SCHEMA_DRAFT:
            raise ValueError(f"Schema must declare {SCHEMA_DRAFT}")
        _check_schema_node(schema)
        _validate(metadata, schema, allow_incomplete=template_mode)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        parser.error(safe_display(exc))
    if template_mode:
        print("Study metadata schema is valid for the supported keywords; starter template shape conforms.")
    else:
        print("Study metadata conforms to the bundled schema.")


if __name__ == "__main__":
    main()
