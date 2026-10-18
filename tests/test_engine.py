"""
Unit Tests for Pharos Decision Engine & Aggregation Logic
=========================================================
Tests composite logical operators (ALL, ANY, MAJORITY), fail-safe holding,
DecisionTrace table formatting, JSON serialization, and deterministic dual-outcomes.
"""

import json
import unittest
from unittest.mock import MagicMock

from guardian.client import PharosClient
from guardian.conditions import Condition, ConditionResult
from guardian.engine import DecisionEngine, DecisionTrace, EvaluationOutcome
from guardian.simulator import ActionSimulator


class TestDecisionEngineAggregation(unittest.TestCase):
    """Tests the aggregation logic across composite operators."""

    def setUp(self):
        self.mock_client = MagicMock(spec=PharosClient)
        self.mock_client.get_block_number.return_value = 31405000

    def test_all_operator_all_pass_results_in_fire(self):
        # 3 conditions: all return values that satisfy the condition
        self.mock_client.get_gas_price_gwei.return_value = 1.50   # <= 2.0 (PASS)
        self.mock_client.get_token_balance.return_value = (100, 100.0) # >= 50.0 (PASS)
        self.mock_client.get_native_balance.return_value = 2.0     # >= 1.0 (PASS)

        rules = {
            "strategy_id": "test_strat",
            "name": "Test Strategy",
            "operator": "ALL",
            "conditions": [
                {"id": "c1", "name": "Gas", "type": "gas_price", "operator": "<=", "threshold": 2.0, "unit": "Gwei"},
                {"id": "c2", "name": "USDC", "type": "token_balance", "contract_address": "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8", "holder_address": "0x000000000000000000000000000000000000dEaD", "operator": ">=", "threshold": 50.0, "unit": "USDC"},
                {"id": "c3", "name": "Native", "type": "native_balance", "holder_address": "0x71C80F57f9A3AcB0111aD9207E2F899DFF9C168e", "operator": ">=", "threshold": 1.0, "unit": "PHRS"},
            ],
            "action": {"action_id": "trigger_call", "simulation_only": True},
        }

        engine = DecisionEngine(rules=rules, client=self.mock_client)
        trace = engine.evaluate()

        self.assertEqual(trace.decision, EvaluationOutcome.FIRE)
        self.assertEqual(trace.passed_count, 3)
        self.assertEqual(trace.total_count, 3)
        self.assertIn("All 3 conditions met", trace.rationale)

    def test_all_operator_one_failure_results_in_hold(self):
        # Condition 1 fails (gas price high: 4.5 Gwei > 2.0 Gwei limit)
        self.mock_client.get_gas_price_gwei.return_value = 4.50
        self.mock_client.get_token_balance.return_value = (100, 100.0)
        self.mock_client.get_native_balance.return_value = 2.0

        rules = {
            "strategy_id": "test_strat",
            "name": "Test Strategy",
            "operator": "ALL",
            "conditions": [
                {"id": "c1", "name": "Gas", "type": "gas_price", "operator": "<=", "threshold": 2.0, "unit": "Gwei"},
                {"id": "c2", "name": "USDC", "type": "token_balance", "contract_address": "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8", "holder_address": "0x000000000000000000000000000000000000dEaD", "operator": ">=", "threshold": 50.0, "unit": "USDC"},
                {"id": "c3", "name": "Native", "type": "native_balance", "holder_address": "0x71C80F57f9A3AcB0111aD9207E2F899DFF9C168e", "operator": ">=", "threshold": 1.0, "unit": "PHRS"},
            ],
        }

        engine = DecisionEngine(rules=rules, client=self.mock_client)
        trace = engine.evaluate()

        self.assertEqual(trace.decision, EvaluationOutcome.HOLD)
        self.assertEqual(trace.passed_count, 2)
        self.assertEqual(trace.total_count, 3)
        self.assertIn("Blocked by: Gas", trace.rationale)

    def test_any_operator_at_least_one_pass_results_in_fire(self):
        # 2 fail, 1 passes
        self.mock_client.get_gas_price_gwei.return_value = 5.0   # FAIL (>2.0)
        self.mock_client.get_token_balance.return_value = (10, 10.0) # FAIL (<50.0)
        self.mock_client.get_native_balance.return_value = 3.5  # PASS (>=1.0)

        rules = {
            "operator": "ANY",
            "conditions": [
                {"id": "c1", "name": "Gas", "type": "gas_price", "operator": "<=", "threshold": 2.0},
                {"id": "c2", "name": "USDC", "type": "token_balance", "contract_address": "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8", "holder_address": "0x000000000000000000000000000000000000dEaD", "operator": ">=", "threshold": 50.0},
                {"id": "c3", "name": "Native", "type": "native_balance", "holder_address": "0x71C80F57f9A3AcB0111aD9207E2F899DFF9C168e", "operator": ">=", "threshold": 1.0},
            ],
        }

        engine = DecisionEngine(rules=rules, client=self.mock_client)
        trace = engine.evaluate()

        self.assertEqual(trace.decision, EvaluationOutcome.FIRE)
        self.assertEqual(trace.passed_count, 1)

    def test_majority_operator_two_of_three_passes_results_in_fire(self):
        # 2 pass, 1 fails
        self.mock_client.get_gas_price_gwei.return_value = 1.5   # PASS (<=2.0)
        self.mock_client.get_token_balance.return_value = (60, 60.0) # PASS (>=50.0)
        self.mock_client.get_native_balance.return_value = 0.5  # FAIL (<1.0)

        rules = {
            "operator": "MAJORITY",
            "conditions": [
                {"id": "c1", "name": "Gas", "type": "gas_price", "operator": "<=", "threshold": 2.0},
                {"id": "c2", "name": "USDC", "type": "token_balance", "contract_address": "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8", "holder_address": "0x000000000000000000000000000000000000dEaD", "operator": ">=", "threshold": 50.0},
                {"id": "c3", "name": "Native", "type": "native_balance", "holder_address": "0x71C80F57f9A3AcB0111aD9207E2F899DFF9C168e", "operator": ">=", "threshold": 1.0},
            ],
        }

        engine = DecisionEngine(rules=rules, client=self.mock_client)
        trace = engine.evaluate()

        self.assertEqual(trace.decision, EvaluationOutcome.FIRE)
        self.assertEqual(trace.passed_count, 2)
        self.assertIn("Majority requirement met", trace.rationale)


class TestDeterministicDualOutcomes(unittest.TestCase):
    """Tests the built-in deterministic fixtures that demonstrate both FIRE and HOLD outcomes."""

    def test_deterministic_fire_scenario(self):
        engine = DecisionEngine.create_deterministic_demo(outcome="FIRE")
        trace = engine.evaluate()

        self.assertEqual(trace.decision, EvaluationOutcome.FIRE)
        self.assertEqual(trace.passed_count, 3)
        self.assertEqual(trace.total_count, 3)

        # Simulator verifies action executes safely
        sim = ActionSimulator().execute_simulation(trace)
        self.assertTrue(sim.executed)
        self.assertEqual(sim.status, "SIMULATED_SUCCESS")
        self.assertIsNotNone(sim.simulated_tx_hash)

    def test_deterministic_hold_scenario(self):
        engine = DecisionEngine.create_deterministic_demo(outcome="HOLD")
        trace = engine.evaluate()

        self.assertEqual(trace.decision, EvaluationOutcome.HOLD)
        self.assertLess(trace.passed_count, trace.total_count)

        # Simulator verifies action is strictly blocked
        sim = ActionSimulator().execute_simulation(trace)
        self.assertFalse(sim.executed)
        self.assertEqual(sim.status, "BLOCKED")
        self.assertIsNone(sim.simulated_tx_hash)


class TestDecisionTraceFormatting(unittest.TestCase):
    """Verifies that DecisionTrace generates valid tables and JSON payloads."""

    def test_format_table_renders_correctly(self):
        engine = DecisionEngine.create_deterministic_demo(outcome="FIRE")
        trace = engine.evaluate()
        table_str = trace.format_table()

        self.assertIn("PHAROS THRESHOLD GUARDIAN", table_str)
        self.assertIn(">>> DECISION: FIRE <<<", table_str)
        self.assertIn("[PASS]", table_str)

    def test_to_dict_and_json_serialization(self):
        engine = DecisionEngine.create_deterministic_demo(outcome="HOLD")
        trace = engine.evaluate()
        d = trace.to_dict()

        json_str = json.dumps(d)
        self.assertIsInstance(json_str, str)
        self.assertEqual(d["decision"], EvaluationOutcome.HOLD)
        self.assertEqual(len(d["conditions"]), 3)


if __name__ == "__main__":
    unittest.main()
