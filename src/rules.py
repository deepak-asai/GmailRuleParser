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

def _normalize_field(message: Dict[str, object], field: FieldName) -> str | datetime | None:
    if field == "From":
        return str(message.get("from", ""))
    if field == "Subject":
        return str(message.get("subject", ""))
    if field == "Message":
        return str(message.get("snippet", ""))
    if field == "Received":
        return message.get("received_at")  # datetime or None
    return ""


def _match_condition(condition: Condition, message: Dict[str, object]) -> bool:
    # breakpoint()
    value = _normalize_field(message, condition.field)
    pred = condition.predicate
    expected = condition.value

    if isinstance(value, str):
        left = value.lower()
        right = expected.lower()
        if pred == "Contains":
            return right in left
        if pred == "DoesNotContain":
            return right not in left
        if pred == "Equals":
            return left == right
        if pred == "DoesNotEqual":
            return left != right

    # Date-based
    if isinstance(value, datetime):
        now = datetime.now(timezone.utc)
        try:
            num = float(expected)
        except Exception:
            return False
        if pred == "LessThanDays":
            return (now - value) < timedelta(days=num)
        if pred == "GreaterThanDays":
            return (now - value) > timedelta(days=num)
        if pred == "LessThanMonths":
            return (now - value) < timedelta(days=num * 30)
        if pred == "GreaterThanMonths":
            return (now - value) > timedelta(days=num * 30)

    return False


def message_matches_rule(rule: Rule, message: Dict[str, object]) -> bool:
    results = [
        _match_condition(cond, message)
        for cond in rule.conditions
    ]
    if rule.predicate == "All":
        return all(results)
    return any(results)
