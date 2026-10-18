"""
Pharos Threshold Guardian
=========================
A SkillEngine-compatible on-chain multi-condition decision engine for guarded execution on Pharos.
"""

__version__ = "0.1.0"
__author__ = "JimmyOgb"

from .client import PharosClient
from .conditions import Condition, ConditionResult, evaluate_condition
from .engine import DecisionEngine, DecisionTrace, EvaluationOutcome
from .simulator import ActionSimulator

__all__ = [
    "PharosClient",
    "Condition",
    "ConditionResult",
    "evaluate_condition",
    "DecisionEngine",
    "DecisionTrace",
    "EvaluationOutcome",
    "ActionSimulator",
]
