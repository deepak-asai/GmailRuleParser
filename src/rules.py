from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Literal, Optional


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

def load_single_rule_from_file(path: str) -> Rule:
    """Load a single rule from file (for backward compatibility)"""
    rules = load_rules_from_file(path)
    if len(rules) == 0:
        raise ValueError("No rules found in file")
    if len(rules) > 1:
        print(f"Warning: Multiple rules found in file, using first rule: {rules[0].name}")
    return rules[0]