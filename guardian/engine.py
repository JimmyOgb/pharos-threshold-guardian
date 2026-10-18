"""
Pharos Decision Engine
======================
Core aggregation engine that reads multiple on-chain conditions, evaluates composite
logical gates (ALL / ANY / MAJORITY), and outputs an exhaustive DecisionTrace.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from .client import PharosClient
from .conditions import Condition, ConditionResult, evaluate_condition


class EvaluationOutcome:
    FIRE = "FIRE"
    HOLD = "HOLD"


@dataclass
class DecisionTrace:
    """Complete, verifiable audit trace of a single guardian evaluation cycle."""
    strategy_id: str
    strategy_name: str
    timestamp: str
    network: str
    chain_id: int
    block_number: int
    operator: str
    condition_results: List[ConditionResult]
    passed_count: int
    total_count: int
    decision: str  # FIRE or HOLD
    rationale: str
    simulated_action: Optional[Dict[str, Any]] = None
    execution_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to JSON-serializable dictionary."""
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "timestamp": self.timestamp,
            "network": self.network,
            "chain_id": self.chain_id,
            "block_number": self.block_number,
            "operator": self.operator,
            "passed_count": self.passed_count,
            "total_count": self.total_count,
            "decision": self.decision,
            "rationale": self.rationale,
            "execution_duration_ms": round(self.execution_duration_ms, 2),
            "simulated_action": self.simulated_action,
            "conditions": [c.to_dict() for c in self.condition_results],
        }

    def format_table(self) -> str:
        """Render a clean, human-readable terminal table for developer review."""
        lines = []
        lines.append("=" * 78)
        lines.append(f"  PHAROS THRESHOLD GUARDIAN :: DECISION TRACE")
        lines.append("=" * 78)
        lines.append(f"Strategy   : {self.strategy_name} ({self.strategy_id})")
        lines.append(f"Network    : {self.network} (Chain ID: {self.chain_id}) | Block: #{self.block_number}")
        lines.append(f"Timestamp  : {self.timestamp} ({self.execution_duration_ms:.1f} ms)")
        lines.append(f"Gate Rule  : {self.operator} (Requires {self.operator} conditions to pass)")
        lines.append("-" * 78)
        lines.append(f"{'Condition':<24} | {'Target':<14} | {'Observed':<18} | {'Status':<6}")
        lines.append("-" * 78)

        for c in self.condition_results:
            op_display = f"{c.operator} {c.threshold} {c.unit}".strip()
            obs_display = f"{c.observed_display}".strip()
            stat_icon = "[PASS]" if c.status == "PASS" else f"[{c.status}]"
            lines.append(f"{c.name[:24]:<24} | {op_display[:14]:<14} | {obs_display[:18]:<18} | {stat_icon:<6}")

        lines.append("-" * 78)
        dec_color = ">>> DECISION: FIRE <<<" if self.decision == EvaluationOutcome.FIRE else "--- DECISION: HOLD ---"
        lines.append(f"Score      : {self.passed_count} / {self.total_count} conditions passed")
        lines.append(f"Outcome    : {dec_color}")
        lines.append(f"Rationale  : {self.rationale}")

        if self.simulated_action:
            lines.append("-" * 78)
            action_desc = self.simulated_action.get('description', 'Simulated execution')
            lines.append(f"Action     : {action_desc}")
            lines.append(f"Safe Mode  : Simulation only (Zero gas spent / Zero state mutation)")

        lines.append("=" * 78)
        return "\n".join(lines)


class DecisionEngine:
    """
    Evaluates configured conditions against Pharos on-chain state and
    applies composite decision logic (ALL, ANY, MAJORITY).
    """

    def __init__(
        self,
        rules: Optional[Dict[str, Any]] = None,
        client: Optional[PharosClient] = None,
        network_name: str = "atlantic-testnet",
        chain_id: int = 688689,
    ):
        self.rules = rules or {}
        self.client = client or PharosClient(chain_id=chain_id)
        self.network_name = network_name
        self.chain_id = chain_id

    @classmethod
    def from_file(
        cls,
        rules_path: str,
        client: Optional[PharosClient] = None,
        network_name: str = "atlantic-testnet",
        chain_id: int = 688689,
    ) -> "DecisionEngine":
        """Load engine configuration from a JSON file."""
        with open(rules_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(rules=data, client=client, network_name=network_name, chain_id=chain_id)

    def evaluate(
        self,
        transport: Optional[str] = None,
        custom_conditions: Optional[List[Condition]] = None,
        operator_override: Optional[str] = None,
    ) -> DecisionTrace:
        """
        Execute full evaluation cycle against chain.
        Returns exhaustive DecisionTrace.
        """
        start_time = time.perf_counter()
        timestamp = datetime.now(timezone.utc).isoformat()

        strategy_id = self.rules.get("strategy_id", "custom-strategy")
        strategy_name = self.rules.get("name", "Custom Threshold Strategy")
        operator = (operator_override or self.rules.get("operator", "ALL")).upper().strip()
        action_spec = self.rules.get("action", {})

        # Parse conditions
        conditions_to_run: List[Condition] = []
        if custom_conditions:
            conditions_to_run = custom_conditions
        else:
            raw_conds = self.rules.get("conditions", [])
            for rc in raw_conds:
                conditions_to_run.append(Condition.from_dict(rc))

        if not conditions_to_run:
            raise ValueError("No conditions configured for decision engine.")

        # Read current block for metadata
        try:
            block_number = self.client.get_block_number(transport=transport)
        except Exception:
            block_number = 0

        # Evaluate all conditions
        results: List[ConditionResult] = []
        passed_count = 0
        total_count = len(conditions_to_run)

        for cond in conditions_to_run:
            res = evaluate_condition(cond, self.client, transport=transport)
            results.append(res)
            if res.passed:
                passed_count += 1

        # Apply aggregation logic
        decision = EvaluationOutcome.HOLD
        rationale = ""

        if operator == "ALL":
            if passed_count == total_count:
                decision = EvaluationOutcome.FIRE
                rationale = f"All {total_count} conditions met. Trigger approved."
            else:
                decision = EvaluationOutcome.HOLD
                failed_names = [r.name for r in results if not r.passed]
                rationale = f"Condition gate failed ({passed_count}/{total_count} passed). Blocked by: {', '.join(failed_names)}."

        elif operator == "ANY":
            if passed_count >= 1:
                decision = EvaluationOutcome.FIRE
                passed_names = [r.name for r in results if r.passed]
                rationale = f"ANY condition satisfied ({passed_count}/{total_count}). Passed: {', '.join(passed_names)}."
            else:
                decision = EvaluationOutcome.HOLD
                rationale = f"Zero of {total_count} conditions satisfied."

        elif operator == "MAJORITY":
            needed = (total_count // 2) + 1
            if passed_count >= needed:
                decision = EvaluationOutcome.FIRE
                rationale = f"Majority requirement met ({passed_count}/{total_count} passed, needed {needed})."
            else:
                decision = EvaluationOutcome.HOLD
                rationale = f"Majority not reached ({passed_count}/{total_count} passed, needed {needed})."

        else:
            decision = EvaluationOutcome.HOLD
            rationale = f"Unrecognized aggregation operator '{operator}'. Safe HOLD enforced."

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return DecisionTrace(
            strategy_id=strategy_id,
            strategy_name=strategy_name,
            timestamp=timestamp,
            network=self.network_name,
            chain_id=self.chain_id,
            block_number=block_number,
            operator=operator,
            condition_results=results,
            passed_count=passed_count,
            total_count=total_count,
            decision=decision,
            rationale=rationale,
            simulated_action=action_spec,
            execution_duration_ms=elapsed_ms,
        )

    # -------------------------------------------------------------------------
    # Deterministic Offline Demonstration Fixtures
    # -------------------------------------------------------------------------

    @classmethod
    def create_deterministic_demo(cls, outcome: str) -> "DecisionEngine":
        """
        Creates a self-contained mock engine demonstrating deterministic
        FIRE and HOLD outcomes without requiring live internet connectivity.
        """
        target_outcome = outcome.upper().strip()

        # Offline Mock Client that returns synthetic on-chain data
        class MockDeterministicClient(PharosClient):
            def __init__(self, mode: str):
                super().__init__(rpc_url="http://mock.internal", chain_id=688689)
                self.mode = mode

            def get_block_number(self, transport: Optional[str] = None) -> int:
                return 31406000

            def get_gas_price_gwei(self, transport: Optional[str] = None) -> float:
                # In FIRE mode gas is low (1.20 Gwei); in HOLD mode gas spikes (8.50 Gwei)
                return 1.20 if self.mode == EvaluationOutcome.FIRE else 8.50

            def get_token_balance(
                self, token_address: str, holder_address: str, decimals: int = 18, transport: Optional[str] = None
            ) -> Tuple[int, float]:
                # In FIRE mode vault has 1,500 USDC; in HOLD mode vault only has 10 USDC
                scaled = 1500.0 if self.mode == EvaluationOutcome.FIRE else 10.0
                raw = int(scaled * (10 ** decimals))
                return (raw, scaled)

            def get_native_balance(self, address: str, transport: Optional[str] = None) -> float:
                # Both maintain 2.5 PHRS gas reserve
                return 2.50

            def eth_call(self, to_address: str, data: str, transport: Optional[str] = None) -> str:
                return "0x0000000000000000000000000000000000000000000000000000000000000001"

        mock_client = MockDeterministicClient(mode=target_outcome)

        rules = {
            "strategy_id": f"demo-{target_outcome.lower()}-fixture",
            "name": f"Deterministic Demonstration ({target_outcome} Scenario)",
            "operator": "ALL",
            "conditions": [
                {
                    "id": "demo_gas_price",
                    "name": "Gas Price Ceiling",
                    "type": "gas_price",
                    "operator": "<=",
                    "threshold": 3.0,
                    "unit": "Gwei",
                    "description": "Network gas must be <= 3.0 Gwei",
                },
                {
                    "id": "demo_vault_reserve",
                    "name": "Vault Reserve Floor",
                    "type": "token_balance",
                    "contract_address": "0xE0BE08c77f415F577A1B3A9aD7a1Df1479564ec8",
                    "holder_address": "0x000000000000000000000000000000000000dEaD",
                    "decimals": 6,
                    "operator": ">=",
                    "threshold": 500.0,
                    "unit": "USDC",
                    "description": "Target vault must hold at least 500.0 USDC",
                },
                {
                    "id": "demo_native_balance",
                    "name": "Guardian Gas Reserve",
                    "type": "native_balance",
                    "holder_address": "0x71C80F57f9A3AcB0111aD9207E2F899DFF9C168e",
                    "operator": ">=",
                    "threshold": 1.0,
                    "unit": "PHRS",
                    "description": "Guardian must hold at least 1.0 PHRS for execution gas",
                },
            ],
            "action": {
                "action_id": "trigger_rebalance_demo",
                "description": f"Demonstration payload for {target_outcome}",
                "simulation_only": True,
            },
        }

        return cls(
            rules=rules,
            client=mock_client,
            network_name="offline-deterministic-sim",
            chain_id=688689,
        )
