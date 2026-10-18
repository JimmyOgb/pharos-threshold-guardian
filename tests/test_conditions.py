"""
Unit Tests for Pharos Condition Definitions & Evaluators
========================================================
Tests operator comparisons, boundary values, condition types, and fail-safe error handling.
"""

import unittest
from unittest.mock import MagicMock, patch

from guardian.client import PharosClient, PharosClientError
from guardian.conditions import (
    Condition,
    ConditionResult,
    check_operator,
    evaluate_condition,
)


class TestConditionsOperators(unittest.TestCase):
    """Tests comparison operators and boundary conditions."""

    def test_less_than_operator(self):
        self.assertTrue(check_operator(1.5, "<", 2.0))
        self.assertFalse(check_operator(2.0, "<", 2.0))
        self.assertFalse(check_operator(2.5, "<", 2.0))

    def test_less_than_or_equal_operator(self):
        self.assertTrue(check_operator(1.99, "<=", 2.0))
        self.assertTrue(check_operator(2.0, "<=", 2.0))
        self.assertFalse(check_operator(2.01, "<=", 2.0))

    def test_greater_than_operator(self):
        self.assertTrue(check_operator(5.1, ">", 5.0))
        self.assertFalse(check_operator(5.0, ">", 5.0))
        self.assertFalse(check_operator(4.9, ">", 5.0))

    def test_greater_than_or_equal_operator(self):
        self.assertTrue(check_operator(10.0, ">=", 10.0))
        self.assertTrue(check_operator(10.5, ">=", 10.0))
        self.assertFalse(check_operator(9.99, ">=", 10.0))

    def test_equal_operator(self):
        self.assertTrue(check_operator(42.0, "==", 42.0))
        self.assertTrue(check_operator(42.0000000001, "==", 42.0))
        self.assertFalse(check_operator(42.1, "==", 42.0))

    def test_not_equal_operator(self):
        self.assertTrue(check_operator(42.1, "!=", 42.0))
        self.assertFalse(check_operator(42.0, "!=", 42.0))

    def test_between_operator(self):
        self.assertTrue(check_operator(15.0, "between", [10.0, 20.0]))
        self.assertTrue(check_operator(10.0, "between", [10.0, 20.0]))
        self.assertTrue(check_operator(20.0, "between", [10.0, 20.0]))
        self.assertFalse(check_operator(9.9, "between", [10.0, 20.0]))
        self.assertFalse(check_operator(20.1, "between", [10.0, 20.0]))

    def test_between_operator_invalid_threshold_raises(self):
        with self.assertRaises(ValueError):
            check_operator(15.0, "between", 10.0)  # Needs list of 2

    def test_unsupported_operator_raises(self):
        with self.assertRaises(ValueError):
            check_operator(10.0, "approx", 10.0)


class TestConditionEvaluationTypes(unittest.TestCase):
    """Tests evaluation dispatch across different on-chain condition types with mocked client."""

    def setUp(self):
        self.mock_client = MagicMock(spec=PharosClient)

    def test_evaluate_gas_price_success(self):
        self.mock_client.get_gas_price_gwei.return_value = 1.45
        cond = Condition(
            id="test_gas",
            name="Test Gas Price",
            type="gas_price",
            operator="<=",
            threshold=2.0,
            unit="Gwei",
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, "PASS")
        self.assertAlmostEqual(res.observed_value, 1.45)
        self.assertIn("1.4500 Gwei", res.observed_display)

    def test_evaluate_gas_price_failure(self):
        self.mock_client.get_gas_price_gwei.return_value = 3.80
        cond = Condition(
            id="test_gas",
            name="Test Gas Price",
            type="gas_price",
            operator="<=",
            threshold=2.0,
            unit="Gwei",
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "FAIL")
        self.assertAlmostEqual(res.observed_value, 3.80)

    def test_evaluate_token_balance_success(self):
        self.mock_client.get_token_balance.return_value = (100000000, 100.0)
        cond = Condition(
            id="vault_usdc",
            name="Vault USDC",
            type="token_balance",
            contract_address="0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8",
            holder_address="0x000000000000000000000000000000000000dEaD",
            decimals=6,
            operator=">=",
            threshold=50.0,
            unit="USDC",
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.observed_value, 100.0)

    def test_evaluate_native_balance_success(self):
        self.mock_client.get_native_balance.return_value = 4.25
        cond = Condition(
            id="guardian_phrs",
            name="Guardian PHRS",
            type="native_balance",
            holder_address="0x71C80F57f9A3AcB0111aD9207E2F899DFF9C168e",
            operator=">=",
            threshold=1.0,
            unit="PHRS",
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.observed_value, 4.25)

    def test_evaluate_contract_view_uint256(self):
        self.mock_client.get_contract_uint256.return_value = (1000000000000000000, 1.0)
        cond = Condition(
            id="view_counter",
            name="Contract State View",
            type="contract_view",
            contract_address="0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8",
            selector="0x18160ddd",
            decimals=18,
            operator=">=",
            threshold=0.5,
            unit="tokens",
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertTrue(res.passed)
        self.assertEqual(res.status, "PASS")
        self.assertEqual(res.observed_value, 1.0)

    def test_evaluate_block_diff_freshness(self):
        self.mock_client.get_block_number.return_value = 31405900
        cond = Condition(
            id="block_freshness",
            name="Block Freshness",
            type="block_diff",
            reference_block=31405890,
            operator="<=",
            threshold=20,
            unit="blocks",
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertTrue(res.passed)
        self.assertEqual(res.observed_value, 10)


class TestConditionFailSafeBehavior(unittest.TestCase):
    """Verifies that missing parameters, timeouts, and network errors safely FAIL."""

    def setUp(self):
        self.mock_client = MagicMock(spec=PharosClient)

    def test_rpc_exception_triggers_safe_error_status(self):
        self.mock_client.get_gas_price_gwei.side_effect = PharosClientError("Connection timed out to RPC")
        cond = Condition(
            id="gas_error_test",
            name="Gas Price Error Test",
            type="gas_price",
            operator="<=",
            threshold=5.0,
            unit="Gwei",
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("Connection timed out", res.error_message)
        self.assertIsNone(res.observed_value)

    def test_missing_contract_address_in_token_balance_safely_errors(self):
        cond = Condition(
            id="missing_contract",
            name="Missing Contract Address",
            type="token_balance",
            contract_address=None,
            holder_address="0x000000000000000000000000000000000000dEaD",
            operator=">=",
            threshold=10.0,
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("requires both contract_address and holder_address", res.error_message)

    def test_unknown_condition_type_safely_errors(self):
        cond = Condition(
            id="invalid_type",
            name="Unknown Type",
            type="non_existent_type",
            operator="<=",
            threshold=10.0,
        )
        res = evaluate_condition(cond, self.mock_client)
        self.assertFalse(res.passed)
        self.assertEqual(res.status, "ERROR")
        self.assertIn("Unknown condition type", res.error_message)


if __name__ == "__main__":
    unittest.main()
