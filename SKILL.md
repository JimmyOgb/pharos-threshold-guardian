---
name: pharos-threshold-guardian
description: >
  On-chain multi-condition decision engine for the Pharos blockchain. Evaluates independent on-chain conditions (network gas price, vault liquidity reserves, native balance, and custom smart contract view states) against configurable thresholds before approving or holding an automated execution. Implements composite logical gates (ALL, ANY, MAJORITY) and outputs complete, verifiable DecisionTraces with fail-safe zero-gas simulation.
version: 0.1.0
requires:
  anyBins:
  - python3
  - python
---

# Pharos Threshold Guardian

A SkillEngine-compatible decision engine that checks multiple on-chain conditions together before deciding whether to fire an action on the Pharos blockchain.

## Capability Index

| User Need | Capability | Detailed Instructions |
|---|---|---|
| Check multi-condition threshold before transaction | `pharos-guardian evaluate` | → `references/guardian.md#core-capability-decision-evaluation` |
| Run dual-outcome verification (FIRE and HOLD) | `pharos-guardian test-outcomes` | → `references/guardian.md#core-capability-dual-outcome-verification` |
| Monitor conditions continuously on interval | `pharos-guardian watch --interval 5` | → `references/guardian.md#core-capability-decision-evaluation` |
| Evaluate against Pharos Pacific Mainnet | `pharos-guardian evaluate --network mainnet` | → `references/guardian.md#parameters-table` |
| Stream machine-readable decision trace | `pharos-guardian evaluate --json` | → `references/guardian.md#output-parsing-table` |

## Agent Guidelines Block

When an autonomous agent intends to trigger a state-altering transaction (e.g. rebalance, liquidation, arbitrage, or batch swap), the agent MUST follow these safety steps:

1. **Pre-Check On-Chain Conditions**: Run `python scripts/guardian.py evaluate --network <network>` before creating or signing any transaction payload.
2. **Inspect Decision Trace**: Inspect the `.decision` field:
   - If `decision == "FIRE"`: All security conditions are satisfied. Proceed to prepare transaction.
   - If `decision == "HOLD"`: At least one condition failed. Abort immediately. Log the `.rationale` to the user and retry on next interval.
3. **Fail-Safe Principle**: If any network error, timeout, or missing condition occurs, the engine automatically defaults to `HOLD`. Never bypass a `HOLD` decision.
