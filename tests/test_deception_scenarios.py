import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pyzipper

from examples.evaluate_deception import MAX_BYTES, evaluate, main
from physalia.generators import generate

URL = "https://canary.example.invalid/token"


class ScenarioTests(unittest.TestCase):
    def test_nest_uses_matching_scenario_without_canaries(self):
        asset = generate(
            "nest", {"scenario": "migration", "layers": 2, "branches": 2, "decoys": 3}
        )
        passwords = {
            path: password
            for path, password in (
                line.split("\t", 1)
                for line in asset.companions[0].content.decode("utf-8").splitlines()[3:]
            )
        }
        self.assertEqual(len(passwords), 3)
        archive_names = []

        def visit(data, location):
            with pyzipper.AESZipFile(io.BytesIO(data)) as archive:
                password = passwords[location].encode()
                self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))
                for name in archive.namelist():
                    if name.endswith(".zip"):
                        archive_names.append(name)
                        visit(archive.read(name, pwd=password), location + "!/" + name)
                    else:
                        self.assertNotIn(URL.encode(), archive.read(name, pwd=password))

        visit(asset.content, asset.name)
        self.assertTrue(
            all(
                any(
                    stem in name
                    for stem in (
                        "migration_export",
                        "import_archive",
                        "legacy_accounts",
                        "migration_batch",
                        "source_backup",
                        "import_manifest",
                        "account_mapping",
                        "customer_delta",
                    )
                )
                for name in archive_names
            )
        )

    def test_maze_scenario_has_unique_environment_files(self):
        asset = generate(
            "directory_maze",
            {
                "scenario": "archive",
                "depth": 1,
                "branches": 5,
                "format": "env",
                "files_per_directory": 3,
                "canary_url": URL,
            },
        )
        with zipfile.ZipFile(io.BytesIO(asset.content)) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), len(set(names)))
            envs = [name for name in names if ".env.development" in name]
            self.assertEqual(len(envs), 18)
            for name in envs:
                self.assertIn(
                    '# ARCHIVE_API_URL="' + URL + '"', archive.read(name).decode()
                )
        with self.assertRaises(ValueError):
            generate("directory_maze", {"scenario": "unknown"})


class EvaluationTests(unittest.TestCase):
    def test_cli_rejects_large_file_after_bounded_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.json"
            path.write_bytes(b" " * (MAX_BYTES + 1))
            error = io.StringIO()
            with (
                patch.object(sys, "argv", ["evaluate_deception.py", str(path)]),
                patch("sys.stderr", error),
            ):
                self.assertEqual(main(), 2)
            self.assertIn("input exceeds 2 MiB", error.getvalue())

    def test_comparison_reports_descriptive_deltas_only_for_same_single_budget(self):
        result = evaluate(
            {
                "runs": [
                    {
                        "actor": "attacker",
                        "arm": "control",
                        "budget_seconds": 100,
                        "secret_time": 20,
                    },
                    {
                        "actor": "attacker",
                        "arm": "control",
                        "budget_seconds": 100,
                        "secret_time": 40,
                    },
                    {
                        "actor": "attacker",
                        "arm": "decoy",
                        "budget_seconds": 100,
                        "secret_time": 80,
                    },
                    {
                        "actor": "attacker",
                        "arm": "decoy",
                        "budget_seconds": 100,
                        "secret_time": None,
                    },
                ]
            }
        )
        comparison = result["attacker_comparison"]
        self.assertTrue(comparison["comparable_single_budget"])
        self.assertEqual(
            comparison["mock_secret_rate_difference_decoy_minus_control"], -0.5
        )
        self.assertEqual(
            comparison["median_reached_time_difference_seconds_decoy_minus_control"], 50
        )
        self.assertIn("selection bias", comparison["interpretation"])

        unmatched = evaluate(
            {
                "runs": [
                    {
                        "actor": "attacker",
                        "arm": "control",
                        "budget_seconds": 100,
                        "secret_time": 20,
                    },
                    {
                        "actor": "attacker",
                        "arm": "decoy",
                        "budget_seconds": 120,
                        "secret_time": 80,
                    },
                ]
            }
        )["attacker_comparison"]
        self.assertFalse(unmatched["comparable_single_budget"])
        self.assertIsNone(unmatched["mock_secret_rate_difference_decoy_minus_control"])

    def test_success_rate_and_censored_median(self):
        result = evaluate(
            {
                "runs": [
                    {
                        "actor": "attacker",
                        "arm": "decoy",
                        "budget_seconds": 100,
                        "secret_time": 80,
                    },
                    {
                        "actor": "attacker",
                        "arm": "decoy",
                        "budget_seconds": 100,
                        "secret_time": None,
                        "response_time": 90,
                    },
                ]
            }
        )
        report = result["groups"]["attacker_decoy"]
        self.assertEqual(report["mock_secret_rate"], 0.5)
        self.assertEqual(report["median_seconds_when_reached"], 80)
        self.assertEqual(report["response_before_secret_or_cutoff"], 1)
        self.assertTrue(any("control" in warning for warning in result["warnings"]))

    def test_rejects_out_of_budget_times(self):
        with self.assertRaises(ValueError):
            evaluate(
                {
                    "runs": [
                        {
                            "actor": "attacker",
                            "arm": "control",
                            "budget_seconds": 10,
                            "secret_time": 11,
                        }
                    ]
                }
            )


if __name__ == "__main__":
    unittest.main()
