"""
Unit Tests for Pharos Threshold Guardian CLI
============================================
Tests command-line argument handling, overrides, JSON formatting, and outcome testing.
"""

import io
import json
import os
import sys
import unittest
from unittest.mock import patch

from guardian.cli import main


class TestGuardianCLI(unittest.TestCase):
    """Tests CLI entrypoint and subcommand executions."""

    def test_cli_help(self):
        with patch("sys.argv", ["pharos-guardian", "--help"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            with self.assertRaises(SystemExit) as cm:
                main()
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("Pharos Threshold Guardian", out.getvalue())

    def test_cli_test_outcomes_human_readable(self):
        with patch("sys.argv", ["pharos-guardian", "test-outcomes"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            main()
            output = out.getvalue()
            self.assertIn("DUAL-OUTCOME VERIFICATION SUITE", output)
            self.assertIn("OUTCOME: FIRE", output)
            self.assertIn("OUTCOME: HOLD", output)
            self.assertIn("SIMULATED_SUCCESS", output)
            self.assertIn("ACTION BLOCKED", output)

    def test_cli_test_outcomes_json(self):
        with patch("sys.argv", ["pharos-guardian", "test-outcomes", "--json"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            main()
            output = out.getvalue()
            data = json.loads(output)
            self.assertIn("outcomes", data)
            self.assertIn("fire_scenario", data["outcomes"])
            self.assertIn("hold_scenario", data["outcomes"])
            self.assertEqual(data["outcomes"]["fire_scenario"]["trace"]["decision"], "FIRE")
            self.assertEqual(data["outcomes"]["hold_scenario"]["trace"]["decision"], "HOLD")

    def test_cli_evaluate_offline_with_overrides(self):
        with patch("sys.argv", ["pharos-guardian", "evaluate", "--offline", "--operator", "ALL", "--json"]), patch("sys.stdout", new_callable=io.StringIO) as out:
            main()
            output = out.getvalue()
            data = json.loads(output)
            self.assertIn("decision", data)
            self.assertIn("conditions", data)
            self.assertIn("simulation_dispatch", data)


if __name__ == "__main__":
    unittest.main()
