"""Decrypt ADG1 nesting for local testing; never overwrites an output file."""
import argparse
import getpass
import json
import os
from pathlib import Path
import stat
import sys

from cryptography.exceptions import InvalidTag
from physalia.generators import MAGIC, MAX_LAYERS, decrypt_layer
from physalia.i18n import translate

MAX_INPUT_BYTES = 64 * 1024 * 1024


def safe_display(value):
    """Escape terminal controls and bidi formatting in user-supplied paths."""
    printable = "".join(
        character if character.isprintable() else
        (f"\\u{ord(character):04x}" if ord(character) <= 0xFFFF else f"\\U{ord(character):08x}")
        for character in str(value))
    return json.dumps(printable, ensure_ascii=False)[1:-1]


def read_input(path: Path, language: str) -> bytes:
    """Read only a regular file, without blocking on a FIFO or device."""
    before = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or path.is_symlink():
        raise OSError(translate("invalid_input", language))
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_size,
                                 item.st_mtime_ns, item.st_ctime_ns)
        current = path.stat(follow_symlinks=False)
        if (not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened)
                or identity(opened) != identity(current)):
            raise OSError(translate("invalid_input", language))
        if opened.st_size > MAX_INPUT_BYTES:
            raise OSError(translate("decrypt_input_limit", language))
        with os.fdopen(descriptor, "rb") as source:
            descriptor = -1
            data = source.read(MAX_INPUT_BYTES + 1)
            finished = os.fstat(source.fileno())
            after = path.stat(follow_symlinks=False)
            if identity(opened) != identity(finished) or identity(finished) != identity(after):
                raise OSError(translate("invalid_input", language))
            return data
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def main():
    language_parser = argparse.ArgumentParser(add_help=False)
    language_parser.add_argument("--lang", choices=("ja", "en"), default="ja")
    language = language_parser.parse_known_args()[0].lang
    parser = argparse.ArgumentParser(description=translate("decrypt_description", language), parents=[language_parser])
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if os.name == "nt":
        print(translate("decrypt_windows_permissions", language), file=sys.stderr)
    try:
        data = read_input(args.input, language)
    except OSError as exc:
        parser.error(safe_display(exc))
    if len(data) > MAX_INPUT_BYTES:
        parser.error(translate("decrypt_input_limit", language))
    # Avoid asking for a password when the selected file cannot be this
    # legacy format at all. The minimum header length is checked by
    # decrypt_layer too, but doing it here keeps the CLI interaction clear.
    if not data.startswith(MAGIC) or len(data) < 48:
        parser.exit(1, translate("invalid_format", language) + "\n")
    password = getpass.getpass(translate("password_prompt", language))
    count = 0
    try:
        while data.startswith(MAGIC) and count < MAX_LAYERS:
            data = decrypt_layer(data, password, language)
            count += 1
        if not count or data.startswith(MAGIC):
            raise ValueError(translate("invalid_format", language))
        output_flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL
                        | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        output_descriptor = os.open(args.output, output_flags, 0o600)
        with os.fdopen(output_descriptor, "wb") as output:
            output.write(data)
    except (ValueError, InvalidTag):
        parser.exit(1, translate("decrypt_failed", language) + "\n")
    except FileExistsError:
        parser.error(translate("decrypt_output_exists", language))
    except OSError as exc:
        parser.error(safe_display(exc))
    print(translate("decrypt_done", language, count=count, output=safe_display(args.output)))


if __name__ == "__main__":
    main()
