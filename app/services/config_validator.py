"""
Configuration Validator for Validation Rules.

Validates configuration parameters for each validation rule.
"""

from typing import Dict, List, Tuple, Any, Optional, Union
import logging

logger = logging.getLogger(__name__)


# Validation schema for each rule's parameters
VALIDATION_RULES = {
    # E1: Structural Rules
    "E1-S1": {
        "rule_name": "Required Fields Validation",
        "parameters": {}  # No configurable parameters
    },
    "E1-S2": {
        "rule_name": "Data Type Validation",
        "parameters": {}
    },
    "E1-S3": {
        "rule_name": "Format Validation",
        "parameters": {}
    },
    "E1-S4": {
        "rule_name": "Value Range Validation",
        "parameters": {}
    },
    # E2: Financial Rules
    "E2-F1": {
        "rule_name": "Amount Tolerance",
        "parameters": {
            "tolerance_amount_cents": {
                "type": int,
                "min": 0,
                "max": 100000,
                "description": "Tolerance in cents"
            },
            "tolerance_percentage": {
                "type": float,
                "min": 0.0,
                "max": 5.0,
                "description": "Tolerance as percentage"
            },
            "warning_threshold_percentage": {
                "type": float,
                "min": 0.0,
                "max": 10.0,
                "description": "Threshold for SOFT vs HARD severity"
            }
        }
    },
    "E2-F2": {
        "rule_name": "Line Total Match",
        "parameters": {
            "tolerance_percentage": {
                "type": float,
                "min": 0.0,
                "max": 5.0,
                "description": "Line total tolerance percentage"
            }
        }
    },
    "E2-F3": {
        "rule_name": "High Amount Validation",
        "parameters": {
            "high_amount_threshold": {
                "type": int,
                "min": 100000,
                "max": 10000000,
                "description": "High amount threshold in cents"
            }
        }
    },
    "E2-F4": {
        "rule_name": "Total Amount Validation",
        "parameters": {}
    },
    # E3: Policy Rules
    "E3-P1": {
        "rule_name": "Currency Validation",
        "parameters": {
            "allowed_currencies": {
                "type": list,
                "items": str,
                "min_items": 1,
                "max_items": 50,
                "description": "List of allowed ISO-4217 currency codes"
            }
        }
    },
    "E3-P2": {
        "rule_name": "Vendor Validation",
        "parameters": {}
    },
    "E3-P3": {
        "rule_name": "Date Validation",
        "parameters": {
            "date_validation_window_days": {
                "type": int,
                "min": 1,
                "max": 365,
                "description": "Days to allow between invoice and invoice date"
            }
        }
    },
    "E3-P4": {
        "rule_name": "Vendor Country Validation",
        "parameters": {
            "required_countries": {
                "type": list,
                "items": str,
                "min_items": 1,
                "max_items": 50,
                "description": "List of allowed country codes"
            }
        }
    },
    # E4: Duplicate Rules
    "E4-D1": {
        "rule_name": "Exact Duplicate Invoice",
        "parameters": {}  # No configurable parameters
    },
    "E4-D2": {
        "rule_name": "Time-Window Duplicate",
        "parameters": {
            "time_window_days": {
                "type": int,
                "min": 1,
                "max": 365,
                "description": "Days to check for duplicates"
            }
        }
    },
    "E4-D3": {
        "rule_name": "Similar Amount Heuristic",
        "parameters": {
            "similar_amount_tolerance_pct": {
                "type": float,
                "min": 0.1,
                "max": 10.0,
                "description": "Percentage tolerance for similar amounts"
            },
            "time_window_days": {
                "type": int,
                "min": 1,
                "max": 365,
                "description": "Days to check for similar amounts"
            }
        }
    }
}


def validate_parameters(
    rule_id: str,
    parameters: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate configuration parameters for a rule.
    
    Args:
        rule_id: Rule ID (e.g., "E2-F1")
        parameters: Parameters to validate
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    if rule_id not in VALIDATION_RULES:
        return False, [f"Unknown rule ID: {rule_id}"]
    
    errors = []
    rule_schema = VALIDATION_RULES[rule_id]
    param_schema = rule_schema.get("parameters", {})
    
    # If rule has no configurable parameters, accept empty dict
    if not param_schema:
        if parameters and isinstance(parameters, dict) and parameters:
            return False, [f"Rule {rule_id} does not accept parameters, got: {list(parameters.keys())}"]
        return True, []
    
    # Validate each parameter
    for param_name, param_def in param_schema.items():
        if param_name not in parameters:
            # Parameter not provided - skip validation (optional)
            continue
        
        param_value = parameters[param_name]
        
        # Type validation
        expected_type = param_def.get("type")
        if expected_type == int and not isinstance(param_value, int):
            errors.append(f"Parameter '{param_name}': expected int, got {type(param_value).__name__}")
            continue
        
        if expected_type == float and not isinstance(param_value, (int, float)):
            errors.append(f"Parameter '{param_name}': expected float, got {type(param_value).__name__}")
            continue
        
        if expected_type == list and not isinstance(param_value, list):
            errors.append(f"Parameter '{param_name}': expected list, got {type(param_value).__name__}")
            continue
        
        # Numeric range validation
        if expected_type in (int, float):
            min_val = param_def.get("min")
            max_val = param_def.get("max")
            
            if min_val is not None and param_value < min_val:
                errors.append(f"Parameter '{param_name}': value {param_value} is below minimum {min_val}")
            
            if max_val is not None and param_value > max_val:
                errors.append(f"Parameter '{param_name}': value {param_value} is above maximum {max_val}")
        
        # List validation
        if expected_type == list:
            items_type = param_def.get("items")
            min_items = param_def.get("min_items")
            max_items = param_def.get("max_items")
            
            # Check item types
            if items_type == str:
                for idx, item in enumerate(param_value):
                    if not isinstance(item, str):
                        errors.append(f"Parameter '{param_name}[{idx}]': expected str, got {type(item).__name__}")
            
            # Check list length
            if min_items is not None and len(param_value) < min_items:
                errors.append(f"Parameter '{param_name}': list has {len(param_value)} items, minimum is {min_items}")
            
            if max_items is not None and len(param_value) > max_items:
                errors.append(f"Parameter '{param_name}': list has {len(param_value)} items, maximum is {max_items}")
    
    # Cross-parameter validation
    cross_errors = _validate_cross_parameters(rule_id, parameters)
    errors.extend(cross_errors)
    
    return len(errors) == 0, errors


def _validate_cross_parameters(
    rule_id: str,
    parameters: Dict[str, Any]
) -> List[str]:
    """
    Validate relationships between multiple parameters.
    
    Args:
        rule_id: Rule ID
        parameters: Parameters to validate
    
    Returns:
        List of error messages
    """
    errors = []
    
    # E2-F1: tolerance_percentage should be <= warning_threshold_percentage
    if rule_id == "E2-F1":
        if "tolerance_percentage" in parameters and "warning_threshold_percentage" in parameters:
            if parameters["tolerance_percentage"] > parameters["warning_threshold_percentage"]:
                errors.append(
                    f"tolerance_percentage ({parameters['tolerance_percentage']}) "
                    f"should be <= warning_threshold_percentage ({parameters['warning_threshold_percentage']})"
                )
    
    # E3-P1: Validate currency codes (basic ISO-4217 validation)
    if rule_id == "E3-P1":
        if "allowed_currencies" in parameters:
            valid_currencies = {
                "USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "INR",
                "CNY", "MXN", "BRL", "SGD", "HKD", "NOK", "SEK", "DKK",
                "PLN", "CZK", "HUF", "RON", "BGN", "HRK", "NZD", "AED"
            }
            for currency in parameters["allowed_currencies"]:
                if currency not in valid_currencies:
                    errors.append(f"Currency code '{currency}' is not a valid ISO-4217 code")
    
    # E3-P4: Validate country codes
    if rule_id == "E3-P4":
        if "required_countries" in parameters:
            valid_countries = {
                "US", "EU", "UK", "CA", "AU", "JP", "IN", "CN", "MX", "BR",
                "SG", "HK", "NO", "SE", "DK", "PL", "CZ", "HU", "RO", "BG",
                "HR", "NZ", "AE", "CH", "DE", "FR", "IT", "ES", "NL", "BE"
            }
            for country in parameters["required_countries"]:
                if country not in valid_countries:
                    errors.append(f"Country code '{country}' is not recognized")
    
    return errors


def get_rule_schema(rule_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the validation schema for a rule.
    
    Args:
        rule_id: Rule ID
    
    Returns:
        Schema dictionary or None if rule not found
    """
    return VALIDATION_RULES.get(rule_id)


def get_all_rules_schema() -> Dict[str, Dict[str, Any]]:
    """
    Get all validation rule schemas.
    
    Returns:
        Dictionary mapping rule_id to schema
    """
    return VALIDATION_RULES.copy()
