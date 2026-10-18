"""
Pharos Condition Definitions & Evaluators
=========================================
Implements configurable condition models and evaluation logic for on-chain triggers.
Fail-safe design: Any missing, malformed, or failed read automatically fails the condition.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from .client import PharosClient, PharosClientError


@dataclass
class Condition:
    """Configuration definition for a single on-chain condition."""
    id: str
    name: str
    type: str  # gas_price, token_balance, native_balance, contract_view, block_diff
    operator: str  # <, <=, >, >=, ==, !=, between
    threshold: Union[float, int, List[Union[float, int]]]
    unit: str = ""
    description: str = ""
    contract_address: Optional[str] = None
    holder_address: Optional[str] = None
    decimals: int = 18
    selector: Optional[str] = None
    reference_block: Optional[int] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Condition":
        """Instantiate a Condition from a JSON dictionary."""
        return cls(
            id=data.get("id", "unnamed_condition"),
            name=data.get("name", "Unnamed Condition"),
            type=data.get("type", "gas_price"),
            operator=data.get("operator", "<="),
            threshold=data.get("threshold", 0.0),
            unit=data.get("unit", ""),
            description=data.get("description", ""),
            contract_address=data.get("contract_address"),
            holder_address=data.get("holder_address") or data.get("address"),
            decimals=int(data.get("decimals", 18)),
            selector=data.get("selector"),
            reference_block=data.get("reference_block"),
            extra_params=data.get("extra_params", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Condition to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "operator": self.operator,
            "threshold": self.threshold,
            "unit": self.unit,
            "description": self.description,
            "contract_address": self.contract_address,
            "holder_address": self.holder_address,
            "decimals": self.decimals,
            "selector": self.selector,
            "reference_block": self.reference_block,
        }


@dataclass
class ConditionResult:
    """Detailed evaluation result and audit trace for a condition."""
    condition_id: str
    name: str
    condition_type: str
    operator: str
    threshold: Any
    observed_value: Optional[Union[float, int]]
    observed_display: str
    unit: str
    passed: bool
    status: str  # PASS, FAIL, ERROR
    error_message: Optional[str] = None
    trace_note: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert Result to JSON-serializable dictionary."""
        return {
            "condition_id": self.condition_id,
            "name": self.name,
            "type": self.condition_type,
            "operator": self.operator,
            "threshold": self.threshold,
            "observed_value": self.observed_value,
            "observed_display": self.observed_display,
            "unit": self.unit,
            "passed": self.passed,
            "status": self.status,
            "error_message": self.error_message,
            "trace_note": self.trace_note,
            "timestamp": self.timestamp,
        }


def check_operator(
    observed: float,
    operator: str,
    threshold: Union[float, int, List[Union[float, int]]],
) -> bool:
    """Compare observed value against threshold using standard mathematical operators."""
    op = operator.strip().lower()

    if op in ("<", "lt"):
        return observed < float(threshold)  # type: ignore
    elif op in ("<=", "lte"):
        return observed <= float(threshold)  # type: ignore
    elif op in (">", "gt"):
        return observed > float(threshold)  # type: ignore
    elif op in (">=", "gte"):
        return observed >= float(threshold)  # type: ignore
    elif op in ("==", "eq"):
        return abs(observed - float(threshold)) < 1e-9  # type: ignore
    elif op in ("!=", "neq"):
        return abs(observed - float(threshold)) >= 1e-9  # type: ignore
    elif op in ("between", "range"):
        if isinstance(threshold, (list, tuple)) and len(threshold) == 2:
            low, high = float(threshold[0]), float(threshold[1])
            return low <= observed <= high
        raise ValueError(f"'between' operator requires [min, max] list, got {threshold}")
    else:
        raise ValueError(f"Unsupported comparison operator: {operator}")


def evaluate_condition(
    condition: Condition,
    client: PharosClient,
    transport: Optional[str] = None,
) -> ConditionResult:
    """
    Evaluate a single Condition against the live Pharos network or mock client.
    Guaranteed fail-safe: Any exception causes passed=False and status='ERROR'.
    """
    try:
        c_type = condition.type.lower()
        observed_val: Optional[float] = None
        display_str = ""

        # 1. Network Gas Price
        if c_type == "gas_price":
            gwei = client.get_gas_price_gwei(transport=transport)
            observed_val = gwei
            display_str = f"{gwei:.4f} {condition.unit or 'Gwei'}"

        # 2. Token Balance (ERC-20)
        elif c_type in ("token_balance", "erc20_balance"):
            if not condition.contract_address or not condition.holder_address:
                raise ValueError("token_balance requires both contract_address and holder_address")
            _, scaled = client.get_token_balance(
                condition.contract_address,
                condition.holder_address,
                decimals=condition.decimals,
                transport=transport,
            )
            observed_val = scaled
            display_str = f"{scaled:,.6f} {condition.unit or 'tokens'}"

        # 3. Native Account Balance (PHRS/PROS)
        elif c_type in ("native_balance", "balance"):
            target_addr = condition.holder_address or condition.contract_address
            if not target_addr:
                raise ValueError("native_balance requires holder_address or target address")
            native_val = client.get_native_balance(target_addr, transport=transport)
            observed_val = native_val
            display_str = f"{native_val:.6f} {condition.unit or 'PHRS'}"

        # 4. Arbitrary Contract View Call (uint256)
        elif c_type in ("contract_view", "uint256_view"):
            if not condition.contract_address or not condition.selector:
                raise ValueError("contract_view requires contract_address and selector")
            _, scaled = client.get_contract_uint256(
                condition.contract_address,
                condition.selector,
                decimals=condition.decimals,
                transport=transport,
            )
            observed_val = scaled
            display_str = f"{scaled:,.4f} {condition.unit}"

        # 5. Block Difference / Freshness
        elif c_type in ("block_diff", "block_freshness"):
            cur_block = client.get_block_number(transport=transport)
            ref_block = condition.reference_block if condition.reference_block is not None else cur_block
            diff = float(cur_block - ref_block)
            observed_val = diff
            display_str = f"{int(diff)} blocks (cur: {cur_block}, ref: {ref_block})"

        else:
            raise ValueError(f"Unknown condition type: {condition.type}")

        # Perform the threshold comparison
        passed = check_operator(observed_val, condition.operator, condition.threshold)
        status = "PASS" if passed else "FAIL"

        trace_note = (
            f"Observed {display_str} {condition.operator} {condition.threshold} {condition.unit} -> {status}"
        )

        return ConditionResult(
            condition_id=condition.id,
            name=condition.name,
            condition_type=condition.type,
            operator=condition.operator,
            threshold=condition.threshold,
            observed_value=observed_val,
            observed_display=display_str,
            unit=condition.unit,
            passed=passed,
            status=status,
            error_message=None,
            trace_note=trace_note,
        )

    except Exception as e:
        # Strict fail-safe: any failure prevents passing
        err_msg = str(e)
        return ConditionResult(
            condition_id=condition.id,
            name=condition.name,
            condition_type=condition.type,
            operator=condition.operator,
            threshold=condition.threshold,
            observed_value=None,
            observed_display="N/A",
            unit=condition.unit,
            passed=False,
            status="ERROR",
            error_message=err_msg,
            trace_note=f"Evaluation failed: {err_msg}",
        )
