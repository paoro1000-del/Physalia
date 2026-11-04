"""Summarize recorded, authorized control/decoy exercises without reading real secrets."""
import argparse
import json
import math
import os
from pathlib import Path
import stat
import sys

MAX_BYTES = 2 * 1024 * 1024
MAX_RUNS = 10000
TIME_FIELDS = ("secret_time", "decoy_time", "alert_time", "response_time")
WILSON_Z_95 = 1.959963984540054


def safe_display(value):
    """Escape terminal controls and bidi formatting in OS error text."""
    printable = "".join(
        character if character.isprintable() else
        (f"\\u{ord(character):04x}" if ord(character) <= 0xFFFF else f"\\U{ord(character):08x}")
        for character in str(value))
    return json.dumps(printable, ensure_ascii=False)[1:-1]


def read_input(path):
    """Read a stable, bounded regular file without following links or blocking."""
    path = Path(path)
    before = path.stat(follow_symlinks=False)
    if path.is_symlink() or not stat.S_ISREG(before.st_mode):
        raise OSError("input must be a regular file")
    if before.st_size > MAX_BYTES:
        raise ValueError("input exceeds 2 MiB")
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_NOFOLLOW", 0))
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        identity = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_size,
                                 item.st_mtime_ns, item.st_ctime_ns)
        current = path.stat(follow_symlinks=False)
        if (path.is_symlink() or not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened)
                or identity(opened) != identity(current)):
            raise OSError("input changed or is not a regular file")
        with os.fdopen(descriptor, "rb") as source:
            descriptor = -1
            raw = source.read(MAX_BYTES + 1)
            finished = os.fstat(source.fileno())
            after = path.stat(follow_symlinks=False)
            if (identity(opened) != identity(finished) or identity(finished) != identity(after)):
                raise OSError("input changed while being read")
            return raw
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def finite_number(value):
    """Validate JSON numbers without letting oversized integers crash math.isfinite."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def median(values):
    """Compute a median without summing two potentially huge finite values."""
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    lower, upper = ordered[middle - 1], ordered[middle]
    # All time measurements are nonnegative, so this avoids overflow while
    # keeping the result between the two middle observations.
    return lower + (upper - lower) / 2


def unique_json_object(pairs):
    """Reject ambiguous duplicate keys at every level of an input document."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def wilson_bounds(successes, total):
    """Return unrounded two-sided 95% Wilson bounds for a binomial rate."""
    if total <= 0:
        return None
    rate = successes / total
    z2 = WILSON_Z_95 ** 2
    denominator = 1 + z2 / total
    center = (rate + z2 / (2 * total)) / denominator
    margin = WILSON_Z_95 * math.sqrt(rate * (1 - rate) / total + z2 / (4 * total ** 2)) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


def wilson_interval(successes, total):
    """Return display-ready two-sided 95% Wilson bounds."""
    bounds = wilson_bounds(successes, total)
    return [round(bound, 4) for bound in bounds] if bounds is not None else None


def difference_interval(rate_a, interval_a, rate_b, interval_b):
    """Newcombe interval for the difference of two independent proportions."""
    difference = rate_a - rate_b
    lower = difference - math.sqrt((rate_a - interval_a[0]) ** 2 + (interval_b[1] - rate_b) ** 2)
    upper = difference + math.sqrt((interval_a[1] - rate_a) ** 2 + (rate_b - interval_b[0]) ** 2)
    return [round(max(-1.0, lower), 4), round(min(1.0, upper), 4)]


def survival_summary(runs, horizon):
    """Estimate target-free time with Kaplan-Meier and restricted mean survival time."""
    observations = []
    for row in runs:
        event_time = row.get("secret_time")
        if event_time is not None and event_time <= horizon:
            observations.append((event_time, True))
        else:
            observations.append((horizon, False))

    observations.sort(key=lambda observation: observation[0])
    survival = 1.0
    area = 0.0
    previous = 0.0
    median = None
    at_risk = len(observations)
    index = 0
    while index < len(observations):
        time_point = observations[index][0]
        group_end = index
        events = 0
        while group_end < len(observations) and observations[group_end][0] == time_point:
            events += observations[group_end][1]
            group_end += 1
        area += survival * (time_point - previous)
        if at_risk:
            survival *= 1 - events / at_risk
        if median is None and survival <= 0.5:
            median = time_point
        previous = time_point
        # Events are applied before censoring at a tied time. All observations
        # in this time group leave the risk set after the KM step.
        at_risk -= group_end - index
        index = group_end
    area += survival * (horizon - previous)
    return {"horizon_seconds": horizon,
            "kaplan_meier_median_seconds_to_mock_secret": round(median, 3) if median is not None else None,
            "restricted_mean_seconds_without_mock_secret": round(area, 3)}


def evaluate(payload):
    if not isinstance(payload, dict) or set(payload) != {"runs"}:
        raise ValueError("top-level JSON object must contain only the runs field")
    if not isinstance(payload["runs"], list) or not 1 <= len(payload["runs"]) <= MAX_RUNS:
        raise ValueError("runs must contain 1–10,000 records")
    groups = {(actor, arm): [] for actor in ("attacker", "authorized") for arm in ("control", "decoy")}
    for run in payload["runs"]:
        if not isinstance(run, dict) or run.get("actor") not in ("attacker", "authorized") or run.get("arm") not in ("control", "decoy"):
            raise ValueError("each run needs actor=attacker/authorized and arm=control/decoy")
        allowed_fields = {"actor", "arm", "budget_seconds", *TIME_FIELDS}
        if set(run) - allowed_fields:
            # Do not silently turn a misspelled event field into an apparent
            # censored observation, which can bias results toward the decoy.
            raise ValueError("each run contains an unsupported field; check field names against the documented schema")
        budget = run.get("budget_seconds")
        if not finite_number(budget) or budget <= 0:
            raise ValueError("budget_seconds must be a positive number")
        for name in TIME_FIELDS:
            value = run.get(name)
            if value is not None and (not finite_number(value) or not 0 <= value <= budget):
                raise ValueError(f"{name} must be null or between zero and budget_seconds")
        if run["actor"] == "authorized" and run.get("secret_time") is not None:
            raise ValueError("authorized runs cannot have secret_time")
        if run["arm"] == "control" and run.get("decoy_time") is not None:
            raise ValueError("control-arm runs cannot have decoy_time")
        groups[(run["actor"], run["arm"])].append(run)

    def count(runs, name):
        return sum(row.get(name) is not None for row in runs)

    result = {"schema": "adg-evaluation-v10", "groups": {}, "warnings": []}
    for (actor, arm), runs in groups.items():
        if not runs:
            continue
        budgets = sorted({row["budget_seconds"] for row in runs})
        alert_runs = count(runs, "alert_time")
        alert_rate = alert_runs / len(runs)
        omitted_event_fields = {name: sum(name not in row for row in runs) for name in TIME_FIELDS}
        decoy_alert_pairs = [row["alert_time"] - row["decoy_time"] for row in runs
                             if row.get("decoy_time") is not None and row.get("alert_time") is not None]
        alert_response_pairs = [row["response_time"] - row["alert_time"] for row in runs
                                if row.get("alert_time") is not None and row.get("response_time") is not None]
        decoy_alert_latencies = [latency for latency in decoy_alert_pairs if latency > 0]
        alert_response_latencies = [latency for latency in alert_response_pairs if latency > 0]
        report = {"runs": len(runs), "budgets_seconds": budgets, "decoy_contacts": count(runs, "decoy_time"),
                  "alerts": alert_runs, "alert_run_rate": round(alert_rate, 4),
                  "alert_run_rate_95ci": wilson_interval(alert_runs, len(runs)),
                  "alert_rate_comparable_within_group": len(budgets) == 1,
                  "responses": count(runs, "response_time"),
                  "event_time_medians_seconds_when_observed": {
                      name: median([row[name] for row in runs if row.get(name) is not None])
                      if count(runs, name) else None
                      for name in ("decoy_time", "alert_time", "response_time")},
                  "ordered_latency_pairs": {"decoy_to_alert": len(decoy_alert_latencies),
                                            "alert_to_response": len(alert_response_latencies)},
                  "nonpositive_latency_pairs": {
                      "decoy_to_alert": sum(latency <= 0 for latency in decoy_alert_pairs),
                      "alert_to_response": sum(latency <= 0 for latency in alert_response_pairs)},
                  "ordered_latency_medians_seconds": {
                      "decoy_to_alert": median(decoy_alert_latencies) if decoy_alert_latencies else None,
                      "alert_to_response": median(alert_response_latencies) if alert_response_latencies else None},
                  "omitted_event_fields": omitted_event_fields}
        if actor == "attacker":
            survival = survival_summary(runs, min(budgets))
            reached = [row["secret_time"] for row in runs if row.get("secret_time") is not None]
            rate = len(reached) / len(runs)
            interval = wilson_interval(len(reached), len(runs))
            decoy_delays = [row["secret_time"] - row["decoy_time"] for row in runs
                            if row.get("decoy_time") is not None and row.get("secret_time") is not None
                            and row["decoy_time"] < row["secret_time"]]
            censored_after_decoy = [row["budget_seconds"] - row["decoy_time"] for row in runs
                                    if row.get("decoy_time") is not None and row.get("secret_time") is None]
            simultaneous = sum(row.get("decoy_time") is not None and row.get("secret_time") is not None
                               and row["decoy_time"] == row["secret_time"] for row in runs)
            reached_before_decoy = sum(row.get("secret_time") is not None and
                                       (row.get("decoy_time") is None or row["secret_time"] < row["decoy_time"])
                                       for row in runs)
            report.update(mock_secret_reached=len(reached), mock_secret_rate=round(rate, 4),
                          mock_secret_rate_95ci=[round(bound, 4) for bound in interval],
                          median_seconds_when_reached=median(reached) if reached else None,
                          **survival,
                          decoy_contact_before_secret_or_cutoff=len(decoy_delays) + len(censored_after_decoy),
                          secret_reached_before_decoy_or_without_decoy=reached_before_decoy,
                          secret_reached_after_decoy=len(decoy_delays),
                          simultaneous_decoy_contact_and_secret=simultaneous,
                          median_seconds_from_decoy_to_secret_when_reached=median(decoy_delays) if decoy_delays else None,
                          decoy_contacts_without_secret_by_cutoff=len(censored_after_decoy),
                          median_seconds_after_decoy_without_secret_by_cutoff=median(censored_after_decoy) if censored_after_decoy else None,
                          response_before_secret_or_cutoff=sum(row.get("response_time") is not None and
                              (row.get("secret_time") is None or row["response_time"] < row["secret_time"]) for row in runs))
        result["groups"][actor + "_" + arm] = report
    control = result["groups"].get("attacker_control")
    decoy = result["groups"].get("attacker_decoy")
    result["attacker_comparison"] = None
    if control and decoy:
        same_single_budget = (len(control["budgets_seconds"]) == len(decoy["budgets_seconds"]) == 1
                              and control["budgets_seconds"] == decoy["budgets_seconds"])
        comparison = {
            "comparable_single_budget": same_single_budget,
            "control_runs": control["runs"], "decoy_runs": decoy["runs"],
            "mock_secret_rate_difference_decoy_minus_control": None,
            "mock_secret_rate_difference_95ci": None,
            "median_reached_time_difference_seconds_decoy_minus_control": None,
            "restricted_mean_seconds_without_mock_secret_difference_decoy_minus_control": None,
            "interpretation": "Descriptive, unpaired comparison. A negative rate difference means fewer decoy-arm runs reached the mock secret; a positive restricted-mean difference means the decoy group spent longer without reaching it within the common horizon. The 95% rate intervals quantify sampling uncertainty under a binomial model; neither metric establishes causation or effectiveness. The reached-only median is subject to selection bias.",
        }
        if same_single_budget:
            decoy_rate = decoy["mock_secret_reached"] / decoy["runs"]
            control_rate = control["mock_secret_reached"] / control["runs"]
            rate_difference = decoy_rate - control_rate
            comparison["mock_secret_rate_difference_decoy_minus_control"] = round(rate_difference, 4)
            comparison["mock_secret_rate_difference_95ci"] = difference_interval(
                decoy_rate, wilson_bounds(decoy["mock_secret_reached"], decoy["runs"]),
                control_rate, wilson_bounds(control["mock_secret_reached"], control["runs"]))
            comparison["restricted_mean_seconds_without_mock_secret_difference_decoy_minus_control"] = round(
                decoy["restricted_mean_seconds_without_mock_secret"]
                - control["restricted_mean_seconds_without_mock_secret"], 3)
            if (decoy["median_seconds_when_reached"] is not None
                    and control["median_seconds_when_reached"] is not None):
                comparison["median_reached_time_difference_seconds_decoy_minus_control"] = round(
                    decoy["median_seconds_when_reached"] - control["median_seconds_when_reached"], 3)
        result["attacker_comparison"] = comparison
    if not groups[("attacker", "control")] or not groups[("attacker", "decoy")]:
        result["warnings"].append("Both attacker control and decoy runs are required for comparison.")
    if not groups[("authorized", "control")]:
        result["warnings"].append("No authorized-user control runs are present; baseline alerts and decoy contacts during normal use cannot be compared.")
    if not groups[("authorized", "decoy")]:
        result["warnings"].append("No authorized-user decoy runs are present; potential false alerts and normal-user contact with decoys cannot be assessed.")
    if len({row["budget_seconds"] for row in payload["runs"] if row["actor"] == "attacker"}) > 1:
        result["warnings"].append("Attacker budgets differ; success rates and times are not directly comparable.")
    if any(len({row["budget_seconds"] for row in runs}) > 1 for runs in groups.values() if runs):
        result["warnings"].append("Alert rates within groups with mixed budgets are descriptive only; unequal observation time can change the chance of recording an alert.")
    result["warnings"].append("Median time covers only runs that reached the mock secret; null is right-censored at the budget. Correlation and human-reviewed response are not proof of causation or prevention.")
    result["warnings"].append("The input schema does not record scenario equivalence, assignment method, AI model, scripts, concurrency, or starting information. Verify and retain these as non-sensitive study metadata; the summaries cannot correct for differences between control and decoy runs.")
    result["warnings"].append("Wilson and Newcombe intervals treat run outcomes as independent binomial observations. Repeated runs sharing an attacker, AI agent/session, operator, or scenario may be correlated and make these intervals too narrow; use cluster-aware analysis for such designs.")
    result["warnings"].append("Kaplan-Meier and restricted-mean estimates treat budget cutoffs as right-censoring and assume censoring is independent of target-reaching time. Progress-triggered early stops can violate that assumption.")
    result["warnings"].append("For runs without secret_time, budget_seconds must be the actual observed follow-up duration; record the planned maximum separately in study metadata. Using the planned maximum after an early stop overstates observed target-free time.")
    result["warnings"].append("Decoy-to-secret medians cover only runs where decoy contact preceded secret access. Runs with no secret access are reported separately as right-censored time from decoy contact to budget; neither value alone proves causal delay.")
    result["warnings"].append("Alert rates are the share of runs with an alert timestamp. In authorized-user groups, treat these as potential false-positive rates only after confirming the alert was caused by normal authorized activity; they do not include repeated alert counts within a run.")
    if any(name not in row for row in payload["runs"] for name in TIME_FIELDS):
        result["warnings"].append("Omitted event-time fields are treated as null in calculations. Check omitted_event_fields: omission means not recorded, not proof that the event did not occur; use explicit null only when the event was observed not to occur within the run.")
    return result


def main():
    parser = argparse.ArgumentParser(description="Compare recorded deception exercise outcomes; use synthetic secrets only.")
    parser.add_argument("input", type=Path, help="UTF-8 JSON containing a runs array")
    args = parser.parse_args()
    try:
        raw = read_input(args.input)
        if len(raw) > MAX_BYTES:
            raise ValueError("input exceeds 2 MiB")
        print(json.dumps(evaluate(json.loads(raw, object_pairs_hook=unique_json_object)),
                         indent=2, allow_nan=False))
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(f"Cannot evaluate: {safe_display(exc)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
