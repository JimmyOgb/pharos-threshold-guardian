"""
Pharos Threshold Guardian — Command-Line Interface
==================================================
Command-line tool for evaluating multi-condition on-chain triggers,
demonstrating decision traces, and safely simulating agent dispatch.
"""

import argparse
import json
import os
import sys
import time
from typing import Optional

from . import __version__
from .client import PharosClient
from .conditions import Condition
from .engine import DecisionEngine, EvaluationOutcome
from .simulator import ActionSimulator


def load_network_config(network_name: str, assets_dir: str) -> dict:
    """Load network parameters from networks.json."""
    net_path = os.path.join(assets_dir, "networks.json")
    if os.path.exists(net_path):
        with open(net_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for n in data.get("networks", []):
                if n["name"].lower() == network_name.lower():
                    return n
    # Built-in fallbacks if assets file not found
    if network_name.lower() in ("mainnet", "pacific"):
        return {
            "name": "mainnet",
            "rpcUrl": "https://rpc.pharos.xyz",
            "mcpUrl": "https://mcp.pharos.xyz/mcp",
            "chainId": 1672,
            "nativeToken": "PROS",
        }
    return {
        "name": "atlantic-testnet",
        "rpcUrl": "https://atlantic.dplabs-internal.com",
        "mcpUrl": "https://mcp.pharos.xyz/mcp",
        "chainId": 688689,
        "nativeToken": "PHRS",
    }


def main():
    parser = argparse.ArgumentParser(
        prog="pharos-guardian",
        description="Pharos Threshold Guardian: On-Chain Multi-Condition Decision Engine",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # -------------------------------------------------------------------------
    # Command: evaluate
    # -------------------------------------------------------------------------
    eval_parser = subparsers.add_parser("evaluate", help="Evaluate conditions against chain state")
    eval_parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to custom rules JSON file (defaults to assets/default_rules.json)",
    )
    eval_parser.add_argument(
        "--network",
        "-n",
        type=str,
        default="atlantic-testnet",
        choices=["atlantic-testnet", "mainnet"],
        help="Target Pharos network (default: atlantic-testnet)",
    )
    eval_parser.add_argument(
        "--transport",
        "-t",
        type=str,
        default="rpc",
        choices=["rpc", "mcp"],
        help="Transport protocol: 'rpc' (JSON-RPC) or 'mcp' (Hosted Chain MCP)",
    )
    eval_parser.add_argument(
        "--operator",
        type=str,
        choices=["ALL", "ANY", "MAJORITY"],
        default=None,
        help="Override composite logical operator",
    )
    eval_parser.add_argument(
        "--max-gas",
        type=float,
        default=None,
        help="Override network gas ceiling threshold (Gwei)",
    )
    eval_parser.add_argument(
        "--min-liquidity",
        type=float,
        default=None,
        help="Override vault liquidity floor threshold (USDC)",
    )
    eval_parser.add_argument(
        "--min-gas-reserve",
        type=float,
        default=None,
        help="Override guardian native gas reserve floor threshold (PHRS/PROS)",
    )
    eval_parser.add_argument(
        "--guardian-address",
        type=str,
        default=None,
        help="Override guardian wallet address for native gas reserve check",
    )
    eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON DecisionTrace instead of formatted table",
    )
    eval_parser.add_argument(
        "--simulate",
        action="store_true",
        default=True,
        help="Simulate execution outcome if decision is FIRE (default: True)",
    )
    eval_parser.add_argument(
        "--offline",
        action="store_true",
        help="Run offline using deterministic synthetic fixtures",
    )

    # -------------------------------------------------------------------------
    # Command: test-outcomes
    # -------------------------------------------------------------------------
    outcomes_parser = subparsers.add_parser(
        "test-outcomes",
        help="Run both deterministic FIRE and HOLD demonstrations with full traces",
    )
    outcomes_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON for both outcomes",
    )

    # -------------------------------------------------------------------------
    # Command: watch
    # -------------------------------------------------------------------------
    watch_parser = subparsers.add_parser(
        "watch",
        help="Continuously monitor and evaluate conditions on an interval",
    )
    watch_parser.add_argument("--interval", "-i", type=int, default=5, help="Polling interval in seconds")
    watch_parser.add_argument(
        "--iterations",
        "-m",
        type=int,
        default=3,
        help="Maximum polling iterations before exit (default: 3)",
    )
    watch_parser.add_argument("--network", "-n", type=str, default="atlantic-testnet")
    watch_parser.add_argument("--transport", "-t", type=str, default="rpc")
    watch_parser.add_argument("--config", "-c", type=str, default=None)
    watch_parser.add_argument("--json", action="store_true", help="Output streaming JSON traces")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Locate assets directory
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assets_dir = os.path.join(base_dir, "assets")

    # -------------------------------------------------------------------------
    # Handle: test-outcomes
    # -------------------------------------------------------------------------
    if args.command == "test-outcomes":
        fire_engine = DecisionEngine.create_deterministic_demo(outcome="FIRE")
        hold_engine = DecisionEngine.create_deterministic_demo(outcome="HOLD")

        fire_trace = fire_engine.evaluate()
        hold_trace = hold_engine.evaluate()

        fire_sim = ActionSimulator().execute_simulation(fire_trace)
        hold_sim = ActionSimulator().execute_simulation(hold_trace)

        if args.json:
            combined = {
                "demo": "Deterministic Demonstration of Dual Outcomes",
                "outcomes": {
                    "fire_scenario": {
                        "trace": fire_trace.to_dict(),
                        "simulation": fire_sim.to_dict(),
                    },
                    "hold_scenario": {
                        "trace": hold_trace.to_dict(),
                        "simulation": hold_sim.to_dict(),
                    },
                },
            }
            print(json.dumps(combined, indent=2))
        else:
            print("\n" + "=" * 78)
            print("  PHAROS THRESHOLD GUARDIAN: DUAL-OUTCOME VERIFICATION SUITE")
            print("=" * 78)
            print("Demonstrating both deterministic execution outcomes against standard rules:\n")

            print("[SCENARIO 1: ALL CONDITIONS MET -> OUTCOME: FIRE]")
            print(fire_trace.format_table())
            print(f"Simulation Dispatch: {fire_sim.status} | Notice: {fire_sim.notice}\n")

            print("[SCENARIO 2: GAS THRESHOLD EXCEEDED -> OUTCOME: HOLD]")
            print(hold_trace.format_table())
            print(f"Simulation Dispatch: {hold_sim.status} | Notice: {hold_sim.notice}\n")
        return

    # -------------------------------------------------------------------------
    # Handle: evaluate & watch
    # -------------------------------------------------------------------------
    config_file = args.config
    if not config_file:
        config_file = os.path.join(assets_dir, "default_rules.json")

    if not os.path.exists(config_file):
        print(f"Error: Rule configuration file not found at: {config_file}", file=sys.stderr)
        sys.exit(1)

    with open(config_file, "r", encoding="utf-8") as f:
        rules_data = json.load(f)

    # Apply overrides if provided
    if getattr(args, "max_gas", None) is not None:
        for c in rules_data.get("conditions", []):
            if c.get("type") == "gas_price":
                c["threshold"] = args.max_gas

    if getattr(args, "min_liquidity", None) is not None:
        for c in rules_data.get("conditions", []):
            if c.get("type") in ("token_balance", "erc20_balance"):
                c["threshold"] = args.min_liquidity

    if getattr(args, "min_gas_reserve", None) is not None:
        for c in rules_data.get("conditions", []):
            if c.get("type") in ("native_balance", "balance"):
                c["threshold"] = args.min_gas_reserve

    if getattr(args, "guardian_address", None):
        for c in rules_data.get("conditions", []):
            if c.get("type") in ("native_balance", "balance"):
                c["address"] = args.guardian_address
                c["holder_address"] = args.guardian_address

    if getattr(args, "operator", None):
        rules_data["operator"] = args.operator

    # Setup client
    if getattr(args, "offline", False):
        engine = DecisionEngine.create_deterministic_demo(outcome="FIRE")
    else:
        net_info = load_network_config(args.network, assets_dir)
        client = PharosClient(
            rpc_url=net_info["rpcUrl"],
            mcp_url=net_info.get("mcpUrl", "https://mcp.pharos.xyz/mcp"),
            chain_id=net_info["chainId"],
            prefer_transport=args.transport,
        )
        engine = DecisionEngine(
            rules=rules_data,
            client=client,
            network_name=net_info["name"],
            chain_id=net_info["chainId"],
        )

    if args.command == "evaluate":
        trace = engine.evaluate(transport=args.transport)
        sim_res = ActionSimulator(client=engine.client).execute_simulation(trace)

        if args.json:
            out = trace.to_dict()
            out["simulation_dispatch"] = sim_res.to_dict()
            print(json.dumps(out, indent=2))
        else:
            print(trace.format_table())
            print(f"Simulation: {sim_res.status} | Notice: {sim_res.notice}")

    elif args.command == "watch":
        max_iters = args.iterations
        interval = args.interval
        print(f"Starting Threshold Guardian Watch mode (Network: {args.network}, Polling every {interval}s, Max {max_iters} checks)...")

        for iteration in range(1, max_iters + 1):
            trace = engine.evaluate(transport=args.transport)
            if args.json:
                print(json.dumps(trace.to_dict()))
            else:
                print(f"\n[Check #{iteration} at {trace.timestamp}] Outcome: {trace.decision} (Passed {trace.passed_count}/{trace.total_count})")
                for c in trace.condition_results:
                    print(f"  • {c.name:<24}: {c.observed_display:<18} [{c.status}]")
                print(f"  Rationale: {trace.rationale}")

            if iteration < max_iters:
                time.sleep(interval)


if __name__ == "__main__":
    main()
