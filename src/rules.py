from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Literal, Optional
from src.config import get_logger

# Set up logger for this module
logger = get_logger(__name__)


FieldName = Literal["From", "To", "Subject", "Message", "Received"]
Predicate = Literal[
    "Contains",
    "DoesNotContain",
    "Equals",
    "DoesNotEqual",
    # Date comparisons (days/months ago)
    "LessThanDays",
    "GreaterThanDays",
    "LessThanMonths",
    "GreaterThanMonths",
]

@dataclass(frozen=True)
class Condition:
    field: FieldName
    predicate: Predicate
    value: str


@dataclass(frozen=True)
class Rule:
    predicate: Literal["All", "Any"]
    conditions: List[Condition]
    actions: Dict[str, Optional[str]]
    name: Optional[str] = None

def load_rules_from_file(path: str) -> List[Rule]:
    with open(path, "r") as f:
        data = json.load(f)

    # Expect an array of rule objects
    if not isinstance(data, list):
        raise ValueError("Rules file must contain an array of rule objects")
    
    rules = []
    for rule_data in data:
        conds = [
            Condition(field=c["field"], predicate=c["predicate"], value=str(c["value"]))
            for c in rule_data.get("conditions", [])
        ]
        actions = rule_data.get("actions", {})
        rule = Rule(
            conditions=conds,
            predicate=rule_data.get("predicate", "All"),
            actions=actions,
            name=rule_data.get("name"),
        )
        rules.append(rule)
    
    return rules
