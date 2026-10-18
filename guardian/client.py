"""
Pharos On-Chain Transport Client
================================
Dual-engine transport client supporting direct JSON-RPC and Pharos Hosted Chain MCP.
Designed exclusively for read-only observations with zero state-altering capabilities.
"""

import json
import re
import socket
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple, Union

# Address validation regex (EVM standard: 0x followed by 40 hex chars)
ADDRESS_REGEX = re.compile(r"^0x[a-fA-F0-9]{40}$")


class PharosClientError(Exception):
    """Custom exception raised for Pharos transport and communication errors."""
    pass


class PharosClient:
    """
    Read-only transport client supporting both direct JSON-RPC endpoints and
    the official Pharos Hosted Chain MCP (Model Context Protocol).
    """

    def __init__(
        self,
        rpc_url: str = "https://atlantic.dplabs-internal.com",
        mcp_url: str = "https://mcp.pharos.xyz/mcp",
        chain_id: int = 688689,
        timeout: float = 12.0,
        prefer_transport: str = "rpc",
    ):
        self.rpc_url = rpc_url.rstrip("/")
        self.mcp_url = mcp_url.rstrip("/")
        self.chain_id = chain_id
        self.timeout = timeout
        self.prefer_transport = prefer_transport.lower()
        self._mcp_session_id: Optional[str] = None

    # -------------------------------------------------------------------------
    # Core JSON-RPC Transport
    # -------------------------------------------------------------------------

    def rpc_call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """Execute a raw JSON-RPC call against the configured RPC endpoint."""
        if params is None:
            params = []

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.rpc_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "PharosThresholdGuardian/0.1.0",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_text = resp.read().decode("utf-8")
                res = json.loads(resp_text)
                if "error" in res:
                    err_msg = res["error"].get("message", str(res["error"]))
                    raise PharosClientError(f"RPC Error [{method}]: {err_msg}")
                if "result" not in res:
                    raise PharosClientError(f"Malformed RPC response: missing 'result' in {res}")
                return res["result"]
        except (urllib.error.URLError, socket.timeout, ConnectionResetError) as e:
            raise PharosClientError(f"Failed RPC connection to {self.rpc_url}: {e}") from e
        except json.JSONDecodeError as e:
            raise PharosClientError(f"Invalid JSON returned by RPC endpoint: {e}") from e

    # -------------------------------------------------------------------------
    # Hosted Chain MCP Transport
    # -------------------------------------------------------------------------

    def mcp_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Execute an MCP tool call against the official Pharos hosted MCP endpoint.
        Implements Model Context Protocol HTTP POST with initialization handshake.
        """
        # Step 1: Initialize session if not already active
        if not self._mcp_session_id:
            init_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "pharos-guardian-client", "version": "0.1.0"},
                },
            }
            init_req = urllib.request.Request(
                self.mcp_url,
                data=json.dumps(init_payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                    "User-Agent": "PharosThresholdGuardian/0.1.0",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(init_req, timeout=self.timeout) as resp:
                    session_id = resp.headers.get("mcp-session-id")
                    self._mcp_session_id = session_id
                    cookie = resp.headers.get("Set-Cookie")
                    self._mcp_cookie = cookie.split(";")[0] if cookie else None
            except Exception as e:
                raise PharosClientError(f"Failed to initialize session with Hosted MCP ({self.mcp_url}): {e}") from e

        # Step 2: Call tool
        common_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "PharosThresholdGuardian/0.1.0",
            "mcp-session-id": self._mcp_session_id or "",
        }
        if getattr(self, "_mcp_cookie", None):
            common_headers["Cookie"] = self._mcp_cookie

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        req = urllib.request.Request(
            self.mcp_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=common_headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw_body = resp.read().decode("utf-8")

            # Parse SSE stream if returned as SSE
            parsed = None
            for line in raw_body.splitlines():
                if line.startswith("data: "):
                    parsed = json.loads(line[6:])
                    break
                elif line.startswith("data:"):
                    parsed = json.loads(line[5:])
                    break

            if parsed is None:
                try:
                    parsed = json.loads(raw_body)
                except json.JSONDecodeError:
                    raise PharosClientError(f"Failed to parse Hosted MCP payload: {raw_body[:200]}")

            if "error" in parsed:
                raise PharosClientError(f"MCP tool error [{tool_name}]: {parsed['error']}")

            result_obj = parsed.get("result", {})
            content = result_obj.get("content", [])
            if content and isinstance(content, list):
                text_out = content[0].get("text", "")
                try:
                    return json.loads(text_out)
                except (json.JSONDecodeError, TypeError):
                    return text_out
            return result_obj
        except (urllib.error.URLError, socket.timeout) as e:
            raise PharosClientError(f"Failed MCP call to {self.mcp_url}: {e}") from e

    # -------------------------------------------------------------------------
    # High-Level Read Observers
    # -------------------------------------------------------------------------

    def get_block_number(self, transport: Optional[str] = None) -> int:
        """Fetch current chain block number."""
        trans = (transport or self.prefer_transport).lower()
        if trans == "mcp":
            res = self.mcp_call_tool("get_block_number", {})
            if isinstance(res, dict):
                for k in ("blockNumber", "block_number", "blockNumberHex"):
                    if k in res:
                        val = res[k]
                        return int(val, 16) if str(val).startswith("0x") else int(val)
            if isinstance(res, (int, str)):
                return int(res, 16) if str(res).startswith("0x") else int(res)
            return int(res)
        else:
            hex_str = self.rpc_call("eth_blockNumber", [])
            return int(hex_str, 16)

    def get_gas_price_wei(self, transport: Optional[str] = None) -> int:
        """Fetch current gas price in Wei."""
        trans = (transport or self.prefer_transport).lower()
        if trans == "mcp":
            res = self.mcp_call_tool("get_gas_price", {})
            if isinstance(res, dict):
                for k in ("gasPriceWei", "gas_price", "gasPriceHex", "gasPrice"):
                    if k in res:
                        val = res[k]
                        return int(val, 16) if str(val).startswith("0x") else int(val)
                if "gasPriceGwei" in res:
                    return int(float(res["gasPriceGwei"]) * 1e9)
            if isinstance(res, (int, str)):
                return int(res, 16) if str(res).startswith("0x") else int(res)
            return int(res)
        else:
            hex_str = self.rpc_call("eth_gasPrice", [])
            return int(hex_str, 16)

    def get_gas_price_gwei(self, transport: Optional[str] = None) -> float:
        """Fetch current gas price formatted in Gwei."""
        wei = self.get_gas_price_wei(transport=transport)
        return wei / 1e9

    def get_native_balance_wei(self, address: str, transport: Optional[str] = None) -> int:
        """Fetch native account balance in Wei (PHRS on Atlantic, PROS on Mainnet)."""
        if not ADDRESS_REGEX.match(address):
            raise PharosClientError(f"Invalid Ethereum address format: {address}")

        trans = (transport or self.prefer_transport).lower()
        if trans == "mcp":
            res = self.mcp_call_tool("get_balance", {"address": address, "block": "latest"})
            if isinstance(res, dict):
                for k in ("balanceWei", "balance", "balanceHex"):
                    if k in res:
                        val = res[k]
                        return int(val, 16) if str(val).startswith("0x") else int(val)
                if "balanceEther" in res:
                    return int(float(res["balanceEther"]) * 1e18)
            if isinstance(res, (int, str)):
                return int(res, 16) if str(res).startswith("0x") else int(res)
            return int(res)
        else:
            hex_str = self.rpc_call("eth_getBalance", [address, "latest"])
            return int(hex_str, 16)

    def get_native_balance(self, address: str, transport: Optional[str] = None) -> float:
        """Fetch native account balance formatted in ether units (18 decimals)."""
        wei = self.get_native_balance_wei(address, transport=transport)
        return wei / 1e18

    def eth_call(self, to_address: str, data: str, transport: Optional[str] = None) -> str:
        """Execute a read-only EVM call (eth_call) against a contract."""
        if not ADDRESS_REGEX.match(to_address):
            raise PharosClientError(f"Invalid contract address format: {to_address}")
        if not data.startswith("0x"):
            data = "0x" + data

        trans = (transport or self.prefer_transport).lower()
        if trans == "mcp":
            res = self.mcp_call_tool("eth_call", {"to": to_address, "data": data, "block": "latest"})
            if isinstance(res, dict) and "result" in res:
                return str(res["result"])
            return str(res)
        else:
            res = self.rpc_call("eth_call", [{"to": to_address, "data": data}, "latest"])
            return str(res)

    def get_token_balance(
        self,
        token_address: str,
        holder_address: str,
        decimals: int = 18,
        transport: Optional[str] = None,
    ) -> Tuple[int, float]:
        """
        Query an ERC-20 token balance for holder_address via standard balanceOf(address).
        Selector for balanceOf(address) is 0x70a08231.
        Returns: (raw_wei_units, human_scaled_float)
        """
        clean_holder = holder_address.lower().replace("0x", "")
        padded_holder = clean_holder.rjust(64, "0")
        calldata = "0x70a08231" + padded_holder

        raw_hex = self.eth_call(token_address, calldata, transport=transport)
        clean_hex = raw_hex.replace("0x", "")
        if not clean_hex:
            return (0, 0.0)

        raw_units = int(clean_hex, 16)
        scaled = raw_units / (10 ** decimals)
        return (raw_units, scaled)

    def get_contract_uint256(
        self,
        contract_address: str,
        selector_or_data: str,
        decimals: int = 0,
        transport: Optional[str] = None,
    ) -> Tuple[int, float]:
        """
        Query any view method on contract returning uint256.
        Returns: (raw_int, human_scaled_float)
        """
        raw_hex = self.eth_call(contract_address, selector_or_data, transport=transport)
        clean_hex = raw_hex.replace("0x", "")
        if not clean_hex:
            return (0, 0.0)
        raw_val = int(clean_hex, 16)
        scaled = raw_val / (10 ** decimals) if decimals > 0 else float(raw_val)
        return (raw_val, scaled)
