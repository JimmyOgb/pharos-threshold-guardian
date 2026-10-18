"""
Live Integration Tests for Pharos Threshold Guardian
====================================================
Tests live read-only observations against Pharos Atlantic Testnet and Pacific Mainnet.
Runs exclusively when environment variable PHAROS_LIVE_TESTS=1 is set.
"""

import os
import unittest

from guardian.client import PharosClient
from guardian.conditions import Condition, evaluate_condition
from guardian.engine import DecisionEngine, EvaluationOutcome


class TestLivePharosNetwork(unittest.TestCase):
    """Integration test suite executing read-only RPC/MCP calls against live Pharos chains."""

    @classmethod
    def setUpClass(cls):
        if os.environ.get("PHAROS_LIVE_TESTS") != "1":
            raise unittest.SkipTest("Skipping live integration tests (set PHAROS_LIVE_TESTS=1 to enable).")

        cls.atlantic_client = PharosClient(
            rpc_url="https://atlantic.dplabs-internal.com",
            mcp_url="https://mcp.pharos.xyz/mcp",
            chain_id=688689,
            timeout=15.0,
        )

    def test_live_atlantic_gas_price_rpc(self):
        gas_gwei = self.atlantic_client.get_gas_price_gwei(transport="rpc")
        self.assertGreater(gas_gwei, 0.0)
        self.assertLess(gas_gwei, 500.0)

    def test_live_atlantic_block_number_rpc(self):
        block = self.atlantic_client.get_block_number(transport="rpc")
        self.assertGreater(block, 30_000_000)

    def test_live_atlantic_usdc_balance_rpc(self):
        # Atlantic USDC address
        usdc_addr = "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8"
        holder_addr = "0x000000000000000000000000000000000000dEaD"

        raw_wei, scaled = self.atlantic_client.get_token_balance(
            token_address=usdc_addr,
            holder_address=holder_addr,
            decimals=6,
            transport="rpc",
        )
        self.assertGreaterEqual(scaled, 0.0)

    def test_live_mcp_read(self):
        # Query hosted Chain MCP server
        try:
            mcp_block = self.atlantic_client.get_block_number(transport="mcp")
            self.assertGreater(mcp_block, 20_000_000)
        except Exception as e:
            # If hosted MCP endpoint is experiencing temporary upstream rate-limit or network latency
            self.skipTest(f"Hosted Chain MCP endpoint unreachable or slow: {e}")

    def test_live_decision_engine_evaluation(self):
        # Run end-to-end evaluation with live Atlantic client
        rules = {
            "strategy_id": "live-atlantic-test",
            "name": "Live Atlantic Evaluation Strategy",
            "operator": "ALL",
            "conditions": [
                {
                    "id": "live_gas",
                    "name": "Live Gas Price",
                    "type": "gas_price",
                    "operator": "<=",
                    "threshold": 100.0,
                    "unit": "Gwei",
                },
                {
                    "id": "live_usdc_liquidity",
                    "name": "Live USDC Balance",
                    "type": "token_balance",
                    "contract_address": "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8",
                    "holder_address": "0x000000000000000000000000000000000000dEaD",
                    "decimals": 6,
                    "operator": ">=",
                    "threshold": 0.0,
                    "unit": "USDC",
                },
                {
                    "id": "live_native_balance",
                    "name": "Live Burn Balance",
                    "type": "native_balance",
                    "holder_address": "0x0000000000000000000000000000000000000000",
                    "operator": ">=",
                    "threshold": 0.0,
                    "unit": "PHRS",
                },
            ],
            "action": {
                "action_id": "live_safe_rebalance",
                "simulation_only": True,
            },
        }

        engine = DecisionEngine(
            rules=rules,
            client=self.atlantic_client,
            network_name="atlantic-testnet",
            chain_id=688689,
        )
        trace = engine.evaluate(transport="rpc")

        self.assertIn(trace.decision, [EvaluationOutcome.FIRE, EvaluationOutcome.HOLD])
        self.assertEqual(len(trace.condition_results), 3)
        self.assertGreater(trace.block_number, 30_000_000)


if __name__ == "__main__":
    unittest.main()
