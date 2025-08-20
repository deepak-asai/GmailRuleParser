import pytest
from src.rules import Condition, Rule, validate_condition, validate_rule, load_rules_from_file
import tempfile
import json
import os


class TestRulesValidation:
    """Test cases for rule validation functionality"""
    
    def test_valid_string_field_condition(self):
        """Test that valid string field conditions pass validation"""
        # Test all valid string predicates
        valid_conditions = [
            Condition("From", "Contains", "example.com"),
            Condition("To", "DoesNotContain", "spam.com"),
            Condition("Subject", "Equals", "Important"),
            Condition("Message", "DoesNotEqual", "test"),
        ]
        
        for condition in valid_conditions:
            validate_condition(condition)  # Should not raise any exception
    
    def test_valid_date_field_condition(self):
        """Test that valid date field conditions pass validation"""
        # Test all valid date predicates
        valid_conditions = [
            Condition("Received", "LessThanDays", "7"),
            Condition("Received", "GreaterThanDays", "30"),
            Condition("Received", "LessThanMonths", "1"),
            Condition("Received", "GreaterThanMonths", "6"),
        ]
        
        for condition in valid_conditions:
            validate_condition(condition)  # Should not raise any exception
    
    def test_invalid_string_field_predicate(self):
        """Test that invalid predicates for string fields raise ValueError"""
        invalid_conditions = [
            Condition("From", "LessThanDays", "7"),
            Condition("Subject", "GreaterThanMonths", "1"),
        ]
        
        for condition in invalid_conditions:
            with pytest.raises(ValueError, match="Invalid predicate.*for string field"):
                validate_condition(condition)
    
    def test_invalid_date_field_predicate(self):
        """Test that invalid predicates for date fields raise ValueError"""
        invalid_conditions = [
            Condition("Received", "Contains", "example.com"),
            Condition("Received", "Equals", "test"),
        ]
        
        for condition in invalid_conditions:
            with pytest.raises(ValueError, match="Invalid predicate.*for date field"):
                validate_condition(condition)
    
    def test_invalid_date_field_value(self):
        """Test that invalid values for date fields raise ValueError"""
        invalid_conditions = [
            Condition("Received", "LessThanDays", "not_a_number"),
            Condition("Received", "GreaterThanMonths", "abc"),
        ]
        
        for condition in invalid_conditions:
            with pytest.raises(ValueError, match="Invalid value.*for date field"):
                validate_condition(condition)
    
    def test_unknown_field(self):
        """Test that unknown fields raise ValueError"""
        invalid_condition = Condition("UnknownField", "Contains", "test")
        
        with pytest.raises(ValueError, match="Unknown field"):
            validate_condition(invalid_condition)
    
    def test_valid_rule(self):
        """Test that valid rules pass validation"""
        valid_rule = Rule(
            predicate="All",
            conditions=[
                Condition("From", "Contains", "example.com"),
                Condition("Subject", "Equals", "Important"),
            ],
            actions={"mark": "read"}
        )
        
        validate_rule(valid_rule)  # Should not raise any exception
    
    def test_invalid_rule_no_conditions(self):
        """Test that rules without conditions raise ValueError"""
        invalid_rule = Rule(
            predicate="All",
            conditions=[],
            actions={"mark": "read"}
        )
        
        with pytest.raises(ValueError, match="Rule must have at least one condition"):
            validate_rule(invalid_rule)
    
    def test_invalid_rule_predicate(self):
        """Test that rules with invalid predicates raise ValueError"""
        invalid_rule = Rule(
            predicate="InvalidPredicate",
            conditions=[Condition("From", "Contains", "example.com")],
            actions={"mark": "read"}
        )
        
        with pytest.raises(ValueError, match="Invalid predicate"):
            validate_rule(invalid_rule)
    
    def test_load_valid_rules_from_file(self):
        """Test loading valid rules from a JSON file"""
        valid_rules_data = [
            {
                "name": "Test Rule 1",
                "predicate": "All",
                "conditions": [
                    {"field": "From", "predicate": "Contains", "value": "example.com"},
                    {"field": "Subject", "predicate": "Equals", "value": "Important"}
                ],
                "actions": {"mark": "read"}
            },
            {
                "name": "Test Rule 2",
                "predicate": "Any",
                "conditions": [
                    {"field": "Received", "predicate": "LessThanDays", "value": "7"}
                ],
                "actions": {"move": "Recent"}
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(valid_rules_data, f)
            temp_file = f.name
        
        try:
            rules = load_rules_from_file(temp_file)
            assert len(rules) == 2
            assert rules[0].name == "Test Rule 1"
            assert rules[1].name == "Test Rule 2"
        finally:
            os.unlink(temp_file)
    
    def test_load_invalid_rules_from_file(self):
        """Test loading invalid rules from a JSON file raises ValueError"""
        invalid_rules_data = [
            {
                "name": "Invalid Rule",
                "predicate": "All",
                "conditions": [
                    {"field": "From", "predicate": "LessThanDays", "value": "7"}  # Invalid predicate for string field
                ],
                "actions": {"mark": "read"}
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_rules_data, f)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Error in Invalid Rule"):
                load_rules_from_file(temp_file)
        finally:
            os.unlink(temp_file)
    
    def test_load_rules_with_invalid_date_value(self):
        """Test loading rules with invalid date values raises ValueError"""
        invalid_rules_data = [
            {
                "name": "Invalid Date Rule",
                "predicate": "All",
                "conditions": [
                    {"field": "Received", "predicate": "LessThanDays", "value": "not_a_number"}
                ],
                "actions": {"mark": "read"}
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(invalid_rules_data, f)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Error in Invalid Date Rule"):
                load_rules_from_file(temp_file)
        finally:
            os.unlink(temp_file)
