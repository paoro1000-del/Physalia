"""Password policies for decoy archives, not for production credentials."""
import secrets
import string
import re

from aideceptionguard.i18n import translate
from aideceptionguard.validation import integer

WORDS = (
    "Atlas", "Cedar", "Delta", "Maple", "North", "River", "Stone", "Cloud", "Orbit", "Field",
    "Coral", "Green", "Amber", "Ocean", "Vista", "Prime", "Birch", "Meadow", "Copper", "Harbor",
    "Willow", "Aspen", "Summit", "Silver", "Canyon", "Prairie", "Lantern", "Beacon", "Clover", "Ember",
    "Frost", "Indigo", "Juniper", "Marble", "Nectar", "Rowan", "Solace", "Timber", "Umber", "Valley",
    "Winter", "Zephyr", "Acorn", "Brisk", "Cobalt", "Dune", "Echo", "Fable", "Grove", "Hazel",
)
SYMBOLS = "!@#_$%+-"


def validate_policy(raw, language="ja"):
    if not isinstance(raw, dict):
        raise ValueError(translate("policy_error", language))
    allowed = {
        "mode", "min_length", "max_length", "lowercase", "uppercase", "digits",
        "symbols", "progressive", "hints", "hint_characters", "words",
    }
    if set(raw) - allowed:
        raise ValueError(translate("policy_error", language))
    mode = raw.get("mode", "memorable")
    minimum = integer(raw.get("min_length", 9), "min_length", 4, 64, language)
    maximum = integer(raw.get("max_length", 13), "max_length", 4, 64, language)
    groups = {key: raw.get(key, True) for key in ("lowercase", "uppercase", "digits", "symbols")}
    progressive = raw.get("progressive", True)
    hints = raw.get("hints", "early")
    hint_characters = integer(raw.get("hint_characters", 2), "hint_characters", 2, 6, language)
    words = raw.get("words", list(WORDS))
    if (not isinstance(words, list) or not 1 <= len(words) <= 50
            or any(not isinstance(word, str) or not re.fullmatch(r"[A-Za-z]{3,20}", word) for word in words)
            or len({word.casefold() for word in words if isinstance(word, str)}) != len(words)):
        raise ValueError(translate("words_error", language))
    if (mode not in ("random", "memorable") or minimum > maximum or not any(groups.values())
            or any(not isinstance(v, bool) for v in (*groups.values(), progressive))
            or hints not in ("none", "early", "all")
            or (mode == "memorable" and not (groups["lowercase"] or groups["uppercase"]))):
        raise ValueError(translate("policy_error", language))
    return dict(mode=mode, min_length=minimum, max_length=maximum, progressive=progressive, hints=hints,
                hint_characters=hint_characters, words=words, **groups)


def make_password(policy, depth, layers):
    rng = secrets.SystemRandom()
    minimum, maximum = policy["min_length"], policy["max_length"]
    length = (minimum + round((maximum - minimum) * (depth - 1) / max(1, layers - 1))
              if policy["progressive"] else rng.randint(minimum, maximum))
    groups = [alphabet for key, alphabet in (("lowercase", string.ascii_lowercase), ("uppercase", string.ascii_uppercase),
              ("digits", string.digits), ("symbols", SYMBOLS)) if policy[key]]
    if policy["mode"] == "random":
        chars = [rng.choice(group) for group in groups]
        chars += [rng.choice("".join(groups)) for _ in range(length - len(chars))]
        rng.shuffle(chars)
        password = "".join(chars)
    else:
        # Keep a recognizable word as a base, but make its layout less
        # predictable than a fixed year + digit + symbol suffix.
        word = rng.choice(policy["words"]).capitalize()
        if not policy["uppercase"]: word = word.lower()
        elif not policy["lowercase"]: word = word.upper()
        reserve = int(policy["digits"]) + int(policy["symbols"])
        target = length - reserve
        stem = list(word[:target])
        letters = ((string.ascii_lowercase if policy["lowercase"] else "")
                   + (string.ascii_uppercase if policy["uppercase"] else ""))
        while len(stem) < target:
            stem.insert(rng.randrange(len(stem) + 1), rng.choice(letters))
        extras = ([rng.choice(string.digits)] if policy["digits"] else [])
        extras += ([rng.choice(SYMBOLS)] if policy["symbols"] else [])
        for character in extras:
            stem.insert(rng.randrange(len(stem) + 1), character)
        password = "".join(stem)
    hinted = policy["hints"] == "all" or (policy["hints"] == "early" and depth <= 2)
    # Keep actual password characters in the operator manifest only. The
    # deployable note may claim characters are held elsewhere, but reveals none.
    masked = min(policy["hint_characters"], len(password) - 1)
    hint = masked if hinted else None
    return password, hint
