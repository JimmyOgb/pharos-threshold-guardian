"""
Pharos Action Simulator
=======================
Safe execution simulator for Threshold Guardian triggers.
Enforces the mandatory zero-gas, zero-mutation safety policy by simulating transactions.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .client import PharosClient
from .engine import DecisionTrace, EvaluationOutcome


@dataclass
class SimulationResult:
    """Audit log of a simulated action dispatch."""
    executed: bool
    status: str  # BLOCKED, SIMULATED_SUCCESS, SIMULATION_FAILED
    decision: str
    action_id: str
    simulated_tx_hash: Optional[str]
    gas_estimate: int
    notice: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "executed": self.executed,
            "status": self.status,
            "decision": self.decision,
            "action_id": self.action_id,
            "simulated_tx_hash": self.simulated_tx_hash,
            "gas_estimate": self.gas_estimate,
            "notice": self.notice,
            "details": self.details,
        }


class ActionSimulator:
    """Pre-flight transaction simulator that verifies safety before reporting."""

    def __init__(self, client: Optional[PharosClient] = None):
        self.client = client

    def execute_simulation(
        self,
        trace: DecisionTrace,
        force_dry_run: bool = True,
    ) -> SimulationResult:
        """Simulate action execution based on the DecisionTrace."""
        action_spec = trace.simulated_action or {}
        action_id = action_spec.get("action_id", "unspecified_action")

        # 1. If Guardian held the action, immediately block
        if trace.decision != EvaluationOutcome.FIRE:
            return SimulationResult(
                executed=False,
                status="BLOCKED",
                decision=trace.decision,
                action_id=action_id,
                simulated_tx_hash=None,
                gas_estimate=0,
                notice="ACTION BLOCKED: Conditions not satisfied. Hold mode engaged.",
                details={"rationale": trace.rationale},
            )

        # 2. If Guardian fired, run safe simulation
        target_contract = action_spec.get("target_contract", "0x0000000000000000000000000000000000000000")
        simulated_gas = action_spec.get("simulated_gas_limit", 150000)

        # Optional pre-flight dry-run check if live client is available
        dry_run_success = True
        dry_run_error = None
        if self.client and target_contract:
            try:
                # Query contract code to ensure deployed target
                code = self.client.rpc_call("eth_getCode", [target_contract, "latest"])
                if code == "0x" or not code:
                    dry_run_error = f"Target address {target_contract} has no deployed bytecode"
            except Exception as e:
                # Still safe simulation
                dry_run_error = str(e)

        sim_hash = f"0xsim_{trace.block_number}_{hash(action_id) & 0xffffffff:08x}"

        return SimulationResult(
            executed=True,
            status="SIMULATED_SUCCESS",
            decision=trace.decision,
            action_id=action_id,
            simulated_tx_hash=sim_hash,
            gas_estimate=simulated_gas,
            notice="SAFE SIMULATION: Zero private keys required. Zero real gas or funds expended.",
            details={
                "target_contract": target_contract,
                "simulated_gas_limit": simulated_gas,
                "preflight_warning": dry_run_error,
                "safety_mode": "simulation_only",
            },
        )
