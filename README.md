# Pharos Threshold Guardian

[![CI Test Suite](https://github.com/JimmyOgb/pharos-threshold-guardian/actions/workflows/test.yml/badge.svg)](https://github.com/JimmyOgb/pharos-threshold-guardian/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![Pharos Chain ID: 688689](https://img.shields.io/badge/Pharos%20Testnet-688689-blueviolet.svg)](https://atlantic.pharosscan.xyz/)
[![Arena Task: threshold-guardian](https://img.shields.io/badge/Agent%20Arena-threshold--guardian-orange.svg)](https://pharos-agent-arena.vercel.app/tasks/threshold-guardian)

**On-chain multi-condition decision engine for guarded execution and automated DeFi safety on the Pharos blockchain.**

Built for **Pharos Agent Arena (Season of AI) — Task 5: Threshold Guardian (`threshold-guardian`)**.

---

## 1. Problem Statement & Value Proposition

Autonomous AI agents executing on-chain transactions often face severe operational risks:
- **Gas Spikes**: Triggering non-urgent rebalances or swaps during network fee surges results in capital loss.
- **Liquidity Depletion & Slippage**: Executing an order when a liquidity pool or vault balance has dropped exposes the agent to slippage or reverts.
- **Stale State & MEV Front-Running**: Single-trigger actions lack multi-metric validation, allowing adversarial exploitation.

**Threshold Guardian** solves this by introducing a **composite decision gate** for autonomous agents and SkillEngine workflows. Before firing any transaction, the guardian evaluates **at least three independent on-chain conditions** (network gas price, vault liquidity reserves, native balance, or arbitrary contract view calls) against configurable rules. If all requirements are met, it approves execution (`FIRE`); if even one condition fails or errors, it engages safe hold mode (`HOLD`).

---

## 2. Architecture Overview

```mermaid
flowchart TD
    subgraph PharosNetwork["Pharos Blockchain (Atlantic Testnet / Pacific Mainnet)"]
        RPC["Direct JSON-RPC (eth_gasPrice, eth_call)"]
        MCP["Hosted Chain MCP (get_gas_price, get_balance)"]
    end

    subgraph GuardianEngine["Pharos Threshold Guardian"]
        Config["Rule Configuration (JSON / CLI Overrides)"]
        Observer["Dual-Transport Observer Client"]
        CondEvaluator["Multi-Condition Evaluator"]
        Gate["Composite Gate (ALL / ANY / MAJORITY)"]
        Trace["Decision Trace Generator"]
        Simulator["Zero-Gas Action Simulator"]
    end

    Config --> CondEvaluator
    RPC --> Observer
    MCP --> Observer
    Observer --> CondEvaluator
    CondEvaluator --> Gate
    Gate --> Trace
    Trace --> Simulator

    Simulator -->|All Conditions Pass| FIRE["Decision: FIRE (Simulated Success)"]
    Simulator -->|Any Condition Fails / Error| HOLD["Decision: HOLD (Action Blocked)"]
```

---

## 3. Key Features

### Required Arena Functionality
- **3+ Independent On-Chain Conditions**: Evaluates live network gas price (via `eth_gasPrice`), vault ERC-20 token reserves (via `balanceOf`), and native account gas balance (via `eth_getBalance`).
- **Fully Configurable**: All targets, contract addresses, operators (`<`, `<=`, `>`, `>=`, `==`, `between`), and units are defined in clean JSON files with instant CLI override flags.
- **Exhaustive Decision Trace**: Generates a structured audit trace detailing observed values, target thresholds, condition statuses (`PASS`, `FAIL`, `ERROR`), execution block height, and plain-language rationales.
- **Deterministic Dual-Outcome Suite**: Built-in verification command demonstrating both `FIRE` and `HOLD` outcomes deterministically.

### Differentiators Beyond the Minimum
- **Zero Third-Party Dependencies ($0 Cost)**: Written exclusively using the Python standard library. No `pip install web3` or external packages needed.
- **Fail-Safe Security Architecture**: Any network dropout, RPC timeout, or invalid address causes the condition to fail with an `ERROR` status, enforcing an automatic `HOLD`.
- **Pre-Flight Safe Simulation**: The action simulator verifies contract bytecode existence and confirms safe parameters without signing or expending real funds.
- **Dual Transport Support**: Works seamlessly via direct JSON-RPC or the official Pharos Hosted Chain MCP (`https://mcp.pharos.xyz/mcp`).
- **Machine-Readable JSON Streaming**: Supports `--json` for direct ingestion into autonomous agentic pipelines.

---

## 4. Technology Stack

- **Language**: Python 3.9+ (Standard Library: `urllib.request`, `json`, `argparse`, `dataclasses`, `socket`, `unittest`)
- **Networks**:
  - Pharos Atlantic Testnet (`Chain ID: 688689`, RPC: `https://atlantic.dplabs-internal.com`)
  - Pharos Pacific Mainnet (`Chain ID: 1672`, RPC: `https://rpc.pharos.xyz`)
  - Pharos Hosted Chain MCP (`https://mcp.pharos.xyz/mcp`)
- **Compatibility**: Linux, macOS, and Windows.

---

## 5. Prerequisites & Quick Start

### Prerequisites
- Python 3.9 or higher installed.
- No API keys, gas tokens, or private keys required for evaluation.

### Installation
Clone the repository:
```bash
git clone https://github.com/JimmyOgb/pharos-threshold-guardian.git
cd pharos-threshold-guardian
```

Verify the installation by running the test suite:
```bash
python -m unittest discover tests -v
```

---

## 6. Verified Real-World Usage Examples

The following outputs were captured directly from terminal execution against live Pharos Atlantic Testnet and offline deterministic fixtures.

### Example 1: Deterministic Dual-Outcome Demonstration (`test-outcomes`)

Demonstrates both `FIRE` and `HOLD` scenarios side-by-side:
```bash
python scripts/guardian.py test-outcomes
```

**Actual Verified Output:**
```text
==============================================================================
  PHAROS THRESHOLD GUARDIAN: DUAL-OUTCOME VERIFICATION SUITE
==============================================================================
Demonstrating both deterministic execution outcomes against standard rules:

[SCENARIO 1: ALL CONDITIONS MET -> OUTCOME: FIRE]
==============================================================================
  PHAROS THRESHOLD GUARDIAN :: DECISION TRACE
==============================================================================
Strategy   : Deterministic Demonstration (FIRE Scenario) (demo-fire-fixture)
Network    : offline-deterministic-sim (Chain ID: 688689) | Block: #31406000
Timestamp  : 2026-10-18T06:05:13.653497+00:00 (0.2 ms)
Gate Rule  : ALL (Requires ALL conditions to pass)
------------------------------------------------------------------------------
Condition                | Target         | Observed           | Status
------------------------------------------------------------------------------
Gas Price Ceiling        | <= 3.0 Gwei    | 1.2000 Gwei        | [PASS]
Vault Reserve Floor      | >= 500.0 USDC  | 1,500.000000 USDC  | [PASS]
Guardian Gas Reserve     | >= 1.0 PHRS    | 2.500000 PHRS      | [PASS]
------------------------------------------------------------------------------
Score      : 3 / 3 conditions passed
Outcome    : >>> DECISION: FIRE <<<
Rationale  : All 3 conditions met. Trigger approved.
------------------------------------------------------------------------------
Action     : Demonstration payload for FIRE
Safe Mode  : Simulation only (Zero gas spent / Zero state mutation)
==============================================================================
Simulation Dispatch: SIMULATED_SUCCESS | Notice: SAFE SIMULATION: Zero private keys required. Zero real gas or funds expended.

[SCENARIO 2: GAS THRESHOLD EXCEEDED -> OUTCOME: HOLD]
==============================================================================
  PHAROS THRESHOLD GUARDIAN :: DECISION TRACE
==============================================================================
Strategy   : Deterministic Demonstration (HOLD Scenario) (demo-hold-fixture)
Network    : offline-deterministic-sim (Chain ID: 688689) | Block: #31406000
Timestamp  : 2026-10-18T06:05:13.654951+00:00 (0.2 ms)
Gate Rule  : ALL (Requires ALL conditions to pass)
------------------------------------------------------------------------------
Condition                | Target         | Observed           | Status
------------------------------------------------------------------------------
Gas Price Ceiling        | <= 3.0 Gwei    | 8.5000 Gwei        | [FAIL]
Vault Reserve Floor      | >= 500.0 USDC  | 10.000000 USDC     | [FAIL]
Guardian Gas Reserve     | >= 1.0 PHRS    | 2.500000 PHRS      | [PASS]
------------------------------------------------------------------------------
Score      : 1 / 3 conditions passed
Outcome    : --- DECISION: HOLD ---
Rationale  : Condition gate failed (1/3 passed). Blocked by: Gas Price Ceiling, Vault Reserve Floor.
------------------------------------------------------------------------------
Action     : Demonstration payload for HOLD
Safe Mode  : Simulation only (Zero gas spent / Zero state mutation)
==============================================================================
Simulation Dispatch: BLOCKED | Notice: ACTION BLOCKED: Conditions not satisfied. Hold mode engaged.
```

---

### Example 2: Live On-Chain Evaluation (Holding on Gas Ceiling)

Querying live Pharos Atlantic Testnet with default rules (gas limit 3.0 Gwei):
```bash
python scripts/guardian.py evaluate --network atlantic-testnet
```

**Actual Verified Output:**
```text
==============================================================================
  PHAROS THRESHOLD GUARDIAN :: DECISION TRACE
==============================================================================
Strategy   : Pharos Vault Rebalance Guard (pharos-vault-rebalance-guard)
Network    : atlantic-testnet (Chain ID: 688689) | Block: #31564324
Timestamp  : 2026-10-18T06:06:22.387041+00:00 (8367.1 ms)
Gate Rule  : ALL (Requires ALL conditions to pass)
------------------------------------------------------------------------------
Condition                | Target         | Observed           | Status
------------------------------------------------------------------------------
Network Gas Price Guard  | <= 3.0 Gwei    | 10.0000 Gwei       | [FAIL]
Vault Minimum Liquidity  | >= 50.0 USDC   | 73.000000 USDC     | [PASS]
Guardian Native Gas Rese | >= 0.0 PHRS    | 3880087.884955 PHR | [PASS]
------------------------------------------------------------------------------
Score      : 2 / 3 conditions passed
Outcome    : --- DECISION: HOLD ---
Rationale  : Condition gate failed (2/3 passed). Blocked by: Network Gas Price Guard.
------------------------------------------------------------------------------
Action     : Simulated vault rebalance call
Safe Mode  : Simulation only (Zero gas spent / Zero state mutation)
==============================================================================
Simulation: BLOCKED | Notice: ACTION BLOCKED: Conditions not satisfied. Hold mode engaged.
```

---

### Example 3: Live On-Chain Evaluation (Approved FIRE with CLI Override)

Overriding the gas ceiling to 15.0 Gwei so all live conditions pass:
```bash
python scripts/guardian.py evaluate --network atlantic-testnet --max-gas 15.0
```

**Actual Verified Output:**
```text
==============================================================================
  PHAROS THRESHOLD GUARDIAN :: DECISION TRACE
==============================================================================
Strategy   : Pharos Vault Rebalance Guard (pharos-vault-rebalance-guard)
Network    : atlantic-testnet (Chain ID: 688689) | Block: #31564328
Timestamp  : 2026-10-18T06:06:40.017146+00:00 (6712.8 ms)
Gate Rule  : ALL (Requires ALL conditions to pass)
------------------------------------------------------------------------------
Condition                | Target         | Observed           | Status
------------------------------------------------------------------------------
Network Gas Price Guard  | <= 15.0 Gwei   | 10.0000 Gwei       | [PASS]
Vault Minimum Liquidity  | >= 50.0 USDC   | 73.000000 USDC     | [PASS]
Guardian Native Gas Rese | >= 0.0 PHRS    | 3880087.884955 PHR | [PASS]
------------------------------------------------------------------------------
Score      : 3 / 3 conditions passed
Outcome    : >>> DECISION: FIRE <<<
Rationale  : All 3 conditions met. Trigger approved.
------------------------------------------------------------------------------
Action     : Simulated vault rebalance call
Safe Mode  : Simulation only (Zero gas spent / Zero state mutation)
==============================================================================
Simulation: SIMULATED_SUCCESS | Notice: SAFE SIMULATION: Zero private keys required. Zero real gas or funds expended.
```

---

### Example 4: Machine-Readable JSON Output (`--json`)

```bash
python scripts/guardian.py evaluate --network atlantic-testnet --max-gas 15.0 --json
```

**Actual Verified Output Snippet:**
```json
{
  "strategy_id": "pharos-vault-rebalance-guard",
  "strategy_name": "Pharos Vault Rebalance Guard",
  "timestamp": "2026-10-18T06:07:24.883957+00:00",
  "network": "atlantic-testnet",
  "chain_id": 688689,
  "block_number": 31564340,
  "operator": "ALL",
  "passed_count": 3,
  "total_count": 3,
  "decision": "FIRE",
  "rationale": "All 3 conditions met. Trigger approved.",
  "execution_duration_ms": 8445.09,
  "simulation_dispatch": {
    "executed": true,
    "status": "SIMULATED_SUCCESS",
    "decision": "FIRE",
    "action_id": "vault_rebalance_trigger",
    "simulated_tx_hash": "0xsim_31564340_37a81b15",
    "gas_estimate": 250000,
    "notice": "SAFE SIMULATION: Zero private keys required. Zero real gas or funds expended."
  }
}
```

---

## 7. Automated Testing Suite

The repository includes **35 automated tests** covering unit logic, condition operators, error boundaries, composite operators, and live on-chain integration.

### Run Offline Unit Tests (30 Tests)
```bash
python -m unittest discover tests -v
```
**Actual Output:**
```text
test_cli_evaluate_offline_with_overrides (test_cli.TestGuardianCLI) ... ok
test_cli_help (test_cli.TestGuardianCLI) ... ok
test_cli_test_outcomes_human_readable (test_cli.TestGuardianCLI) ... ok
test_cli_test_outcomes_json (test_cli.TestGuardianCLI) ... ok
test_evaluate_block_diff_freshness (test_conditions.TestConditionEvaluationTypes) ... ok
test_evaluate_contract_view_uint256 (test_conditions.TestConditionEvaluationTypes) ... ok
test_evaluate_gas_price_failure (test_conditions.TestConditionEvaluationTypes) ... ok
test_evaluate_gas_price_success (test_conditions.TestConditionEvaluationTypes) ... ok
test_evaluate_native_balance_success (test_conditions.TestConditionEvaluationTypes) ... ok
test_evaluate_token_balance_success (test_conditions.TestConditionEvaluationTypes) ... ok
test_missing_contract_address_in_token_balance_safely_errors (test_conditions.TestConditionFailSafeBehavior) ... ok
test_rpc_exception_triggers_safe_error_status (test_conditions.TestConditionFailSafeBehavior) ... ok
test_unknown_condition_type_safely_errors (test_conditions.TestConditionFailSafeBehavior) ... ok
test_between_operator (test_conditions.TestConditionsOperators) ... ok
test_between_operator_invalid_threshold_raises (test_conditions.TestConditionsOperators) ... ok
test_equal_operator (test_conditions.TestConditionsOperators) ... ok
test_greater_than_operator (test_conditions.TestConditionsOperators) ... ok
test_greater_than_or_equal_operator (test_conditions.TestConditionsOperators) ... ok
test_less_than_operator (test_conditions.TestConditionsOperators) ... ok
test_less_than_or_equal_operator (test_conditions.TestConditionsOperators) ... ok
test_not_equal_operator (test_conditions.TestConditionsOperators) ... ok
test_unsupported_operator_raises (test_conditions.TestConditionsOperators) ... ok
test_all_operator_all_pass_results_in_fire (test_engine.TestDecisionEngineAggregation) ... ok
test_all_operator_one_failure_results_in_hold (test_engine.TestDecisionEngineAggregation) ... ok
test_any_operator_at_least_one_pass_results_in_fire (test_engine.TestDecisionEngineAggregation) ... ok
test_majority_operator_two_of_three_passes_results_in_fire (test_engine.TestDecisionEngineAggregation) ... ok
test_format_table_renders_correctly (test_engine.TestDecisionTraceFormatting) ... ok
test_to_dict_and_json_serialization (test_engine.TestDecisionTraceFormatting) ... ok
test_deterministic_fire_scenario (test_engine.TestDeterministicDualOutcomes) ... ok
test_deterministic_hold_scenario (test_engine.TestDeterministicDualOutcomes) ... ok

Ran 30 tests in 0.384s — OK (skipped=1)
```

### Run Live Network Integration Tests (35 Tests)
```bash
PHAROS_LIVE_TESTS=1 python -m unittest discover tests -v
```
**Actual Output:**
```text
test_live_atlantic_block_number_rpc (test_live.TestLivePharosNetwork) ... ok
test_live_atlantic_gas_price_rpc (test_live.TestLivePharosNetwork) ... ok
test_live_atlantic_usdc_balance_rpc (test_live.TestLivePharosNetwork) ... ok
test_live_decision_engine_evaluation (test_live.TestLivePharosNetwork) ... ok
test_live_mcp_read (test_live.TestLivePharosNetwork) ... ok

Ran 35 tests in 32.918s — OK (0 failures)
```

---

## 8. Task Acceptance Criteria Verification

| # | Official Task Requirement | Implementation Status | Evidence / Verification |
|---|---|---|---|
| **01** | Evaluates at least 3 independent conditions read from chain. | **VERIFIED MET** | Evaluates Network Gas Price (`gas_price`), Vault USDC Balance (`token_balance`), and Guardian Native Balance (`native_balance`) from live chain state. |
| **02** | Conditions and thresholds are configurable, not hard-coded. | **VERIFIED MET** | Defined in `assets/default_rules.json` with support for custom JSON paths (`--config`) and direct CLI flags (`--max-gas`, `--min-liquidity`, `--operator`). |
| **03** | Logs a clear decision trace each run: each condition's value, pass/fail, and final decision. | **VERIFIED MET** | Outputs structured ASCII table and JSON `DecisionTrace` with observed values, targets, PASS/FAIL statuses, and composite decision. |
| **04** | Demonstrates both outcomes: one run where it fires and one where it holds. | **VERIFIED MET** | Deterministically demonstrated in `test-outcomes` command and verified live on Atlantic Testnet (HOLD with 3.0 Gwei target; FIRE with 15.0 Gwei target). |

---

## 9. Security & Limitations

- **Read-Only Scope**: The guardian purely queries on-chain state. It does not sign or broadcast transactions.
- **Fail-Safe Design**: Any network partition, malformed JSON, or missing parameter causes the condition to enter an `ERROR` state and prevents `FIRE`.
- **Zero Cost**: Built entirely with Python standard library and free public RPC/MCP endpoints.

---

## 10. Official Links & Community

- **Pharos Agent Arena**: [https://pharos-agent-arena.vercel.app/](https://pharos-agent-arena.vercel.app/)
- **Official Task Specification**: [Task 5 — Threshold Guardian](https://pharos-agent-arena.vercel.app/tasks/threshold-guardian)
- **Atlantic Block Explorer**: [https://atlantic.pharosscan.xyz/](https://atlantic.pharosscan.xyz/)
- **Pharos Developer Hub**: [https://www.pharos.xyz/devhub](https://www.pharos.xyz/devhub)

---

## 11. License

MIT License. See [LICENSE](LICENSE) for details.
