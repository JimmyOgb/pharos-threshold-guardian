# Pharos Threshold Guardian — Reference Guide

This reference document defines the technical capabilities, parameters, output formats, and error handling for the **Pharos Threshold Guardian** (`pharos-guardian`).

---

## 1. Core Capability: Decision Evaluation

### Command Template
```bash
python scripts/guardian.py evaluate [OPTIONS]
```

### Parameters Table

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `--config`, `-c` | `string` | No | `assets/default_rules.json` | Path to custom strategy and threshold rule JSON file. |
| `--network`, `-n` | `string` | No | `atlantic-testnet` | Target Pharos network (`atlantic-testnet` or `mainnet`). |
| `--transport`, `-t` | `string` | No | `rpc` | On-chain observer transport: `rpc` (JSON-RPC) or `mcp` (Hosted Chain MCP). |
| `--operator` | `string` | No | Strategy default | Composite decision gate: `ALL`, `ANY`, or `MAJORITY`. |
| `--max-gas` | `float` | No | Strategy default | Override ceiling threshold for network gas price (in Gwei). |
| `--min-liquidity` | `float` | No | Strategy default | Override floor threshold for target token/vault liquidity. |
| `--json` | `flag` | No | `false` | Output machine-readable JSON `DecisionTrace`. |
| `--offline` | `flag` | No | `false` | Execute using deterministic offline simulation fixtures. |

### Output Parsing Table

| Field | JSON Path | Type | Description |
|---|---|---|---|
| Strategy ID | `.strategy_id` | `string` | Unique identifier for evaluated rule set. |
| Decision | `.decision` | `string` | Composite outcome: `FIRE` or `HOLD`. |
| Passed Count | `.passed_count` | `int` | Number of individual conditions that satisfied their threshold. |
| Total Conditions | `.total_count` | `int` | Total number of evaluated conditions. |
| Block Number | `.block_number` | `int` | Verified on-chain block height at evaluation time. |
| Rationale | `.rationale` | `string` | Human-readable explanation of why the action was fired or held. |
| Conditions Array | `.conditions[]` | `array` | Detailed list of observed values, targets, and PASS/FAIL/ERROR statuses. |
| Simulation Status | `.simulation_dispatch.status` | `string` | `SIMULATED_SUCCESS` or `BLOCKED`. |

### Error Handling Table

| Error Signature | Root Cause | Safe Fallback Action |
|---|---|---|
| `Failed RPC connection` | Upstream RPC network timeout or DNS failure | Condition status marks `ERROR`. Safe `HOLD` is enforced. |
| `Failed to initialize session with Hosted MCP` | MCP endpoint rate limit or unavailable | Falls back to offline error status; enforces safe `HOLD`. |
| `Invalid Ethereum address format` | Checksum or regex validation mismatch | Validation fails early before network dispatch; enforces `HOLD`. |
| `Missing contract_address` | Malformed condition specification in JSON | Fails condition with explicit error message; enforces `HOLD`. |

---

## 2. Core Capability: Dual-Outcome Verification

### Command Template
```bash
python scripts/guardian.py test-outcomes [--json]
```

Demonstrates both possible execution paths deterministically without spending funds:
1. **Scenario 1 (FIRE)**: All conditions satisfy thresholds (low gas, ample vault liquidity, positive gas reserve) -> Evaluates to `FIRE` and triggers simulated action.
2. **Scenario 2 (HOLD)**: Gas ceiling exceeded (observed 8.5 Gwei > 3.0 Gwei limit) -> Evaluates to `HOLD` and blocks simulated action.
