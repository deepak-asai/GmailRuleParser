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


@dataclass(frozen=True)
class Ruleset:
    rules: List[Rule]


def load_rules_from_file(path: str) -> Ruleset:
    with open(path, "r") as f:
        data = json.load(f)

    # Expect a single rule object with conditions and actions
    conds = [
        Condition(field=c["field"], predicate=c["predicate"], value=str(c["value"]))
        for c in data.get("conditions", [])
    ]
    actions = data.get("actions", {})
    return Rule(
        conditions=conds,
        predicate=data.get("predicate", "All"),
        actions=actions,
        name=data.get("name"),
    )