from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional
from src.config import get_logger
from src.constants import (
    RULE_PREDICATE_ALL, RULE_PREDICATE_ANY,
    STRING_FIELDS, DATE_FIELDS, STRING_PREDICATES, DATE_PREDICATES
)

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

def validate_condition(condition: Condition) -> None:
    """
    Validate that a condition follows the correct field-predicate pattern.
    
    Args:
        condition: The condition to validate
        
    Raises:
        ValueError: If the condition is invalid
    """
    field = condition.field
    predicate = condition.predicate
    
    # Validate string fields
    if field in STRING_FIELDS:
        if predicate not in STRING_PREDICATES:
            raise ValueError(
                f"Invalid predicate '{predicate}' for string field '{field}'. "
                f"Valid predicates for string fields are: {', '.join(STRING_PREDICATES)}"
            )
    
    # Validate date fields
    elif field in DATE_FIELDS:
        if predicate not in DATE_PREDICATES:
            raise ValueError(
                f"Invalid predicate '{predicate}' for date field '{field}'. "
                f"Valid predicates for date fields are: {', '.join(DATE_PREDICATES)}"
            )
        
        # Validate that the value is a valid number for date comparisons
        try:
            float(condition.value)
        except ValueError:
            raise ValueError(
                f"Invalid value '{condition.value}' for date field '{field}'. "
                f"Value must be a valid number (days/months)."
            )
    
    else:
        raise ValueError(f"Unknown field '{field}'. Valid fields are: {', '.join(STRING_FIELDS | DATE_FIELDS)}")

def validate_rule(rule: Rule) -> None:
    """
    Validate that a rule follows the correct pattern.
    
    Args:
        rule: The rule to validate
        
    Raises:
        ValueError: If the rule is invalid
    """
    if not rule.conditions:
        raise ValueError("Rule must have at least one condition")
    
    if rule.predicate not in {RULE_PREDICATE_ALL, RULE_PREDICATE_ANY}:
        raise ValueError(f"Invalid predicate '{rule.predicate}'. Must be '{RULE_PREDICATE_ALL}' or '{RULE_PREDICATE_ANY}'")
    
    # Validate each condition
    for condition in rule.conditions:
        validate_condition(condition)

def load_rules_from_file(path: str) -> List[Rule]:
    with open(path, "r") as f:
        data = json.load(f)

    # Expect an array of rule objects
    if not isinstance(data, list):
        raise ValueError("Rules file must contain an array of rule objects")
    
    rules = []
    for i, rule_data in enumerate(data):
        try:
            conds = [
                Condition(field=c["field"], predicate=c["predicate"], value=str(c["value"]))
                for c in rule_data.get("conditions", [])
            ]
            actions = rule_data.get("actions", {})
            rule = Rule(
                conditions=conds,
                predicate=rule_data.get("predicate", RULE_PREDICATE_ALL),
                actions=actions,
                name=rule_data.get("name"),
            )
            
            # Validate the rule
            validate_rule(rule)
            rules.append(rule)
            
        except Exception as e:
            rule_name = rule_data.get("name", f"Rule {i+1}")
            raise ValueError(f"Error in {rule_name}: {str(e)}")
    
    return rules
