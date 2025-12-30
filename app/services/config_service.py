"""
Configuration Service for Validation Rules.

Manages loading, caching, and resolving validation rule configuration
from MongoDB with fallback to hardcoded defaults.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
import pymongo.database

logger = logging.getLogger(__name__)


# Default hardcoded configuration values (from E1-E4)
DEFAULT_CONFIG = {
    # E2: Financial Rules
    "E2-F1": {
        "rule_name": "Amount Tolerance",
        "rule_category": "FINANCIAL",
        "severity": "SOFT",
        "parameters": {
            "tolerance_amount_cents": 100,
            "tolerance_percentage": 0.5,
            "warning_threshold_percentage": 2.0
        }
    },
    "E2-F2": {
        "rule_name": "Line Total Match",
        "rule_category": "FINANCIAL",
        "severity": "SOFT",
        "parameters": {
            "tolerance_percentage": 0.5
        }
    },
    "E2-F3": {
        "rule_name": "High Amount Validation",
        "rule_category": "FINANCIAL",
        "severity": "HARD",
        "parameters": {
            "high_amount_threshold": 1000000
        }
    },
    "E2-F4": {
        "rule_name": "Total Amount Validation",
        "rule_category": "FINANCIAL",
        "severity": "HARD",
        "parameters": {}
    },
    # E3: Policy Rules
    "E3-P1": {
        "rule_name": "Currency Validation",
        "rule_category": "POLICY",
        "severity": "HARD",
        "parameters": {
            "allowed_currencies": ["USD", "EUR", "GBP", "CHF", "CAD", "AUD", "JPY", "INR"]
        }
    },
    "E3-P2": {
        "rule_name": "Vendor Validation",
        "rule_category": "POLICY",
        "severity": "HARD",
        "parameters": {}
    },
    "E3-P3": {
        "rule_name": "Date Validation",
        "rule_category": "POLICY",
        "severity": "HARD",
        "parameters": {
            "date_validation_window_days": 180
        }
    },
    "E3-P4": {
        "rule_name": "Vendor Country Validation",
        "rule_category": "POLICY",
        "severity": "HARD",
        "parameters": {
            "required_countries": ["US", "EU"]
        }
    },
    # E4: Duplicate Rules
    "E4-D1": {
        "rule_name": "Exact Duplicate Invoice",
        "rule_category": "DUPLICATE",
        "severity": "HARD",
        "parameters": {}
    },
    "E4-D2": {
        "rule_name": "Time-Window Duplicate",
        "rule_category": "DUPLICATE",
        "severity": "SOFT",
        "parameters": {
            "time_window_days": 30
        }
    },
    "E4-D3": {
        "rule_name": "Similar Amount Heuristic",
        "rule_category": "DUPLICATE",
        "severity": "SOFT",
        "parameters": {
            "time_window_days": 60,
            "similar_amount_tolerance_pct": 2.0
        }
    },
    # E1: Structural Rules (minimal config)
    "E1-S1": {
        "rule_name": "Required Fields Validation",
        "rule_category": "STRUCTURAL",
        "severity": "HARD",
        "parameters": {}
    },
    "E1-S2": {
        "rule_name": "Data Type Validation",
        "rule_category": "STRUCTURAL",
        "severity": "HARD",
        "parameters": {}
    },
    "E1-S3": {
        "rule_name": "Format Validation",
        "rule_category": "STRUCTURAL",
        "severity": "HARD",
        "parameters": {}
    },
    "E1-S4": {
        "rule_name": "Value Range Validation",
        "rule_category": "STRUCTURAL",
        "severity": "HARD",
        "parameters": {}
    }
}


class ConfigurationService:
    """
    Manages validation rule configuration with caching and fallback to defaults.
    
    Resolution order for configuration:
    1. Organization + Region specific
    2. Organization + "ALL" region (global)
    3. Hardcoded defaults
    """

    def __init__(self, db: pymongo.database.Database, cache_ttl_seconds: int = 300):
        """
        Initialize configuration service.
        
        Args:
            db: MongoDB database instance
            cache_ttl_seconds: Cache time-to-live in seconds (default 5 minutes)
        """
        self.db = db
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
        self._lock = asyncio.Lock()

    async def get_rule_config(
        self,
        org_id: str,
        rule_id: str,
        region: str = "US"
    ) -> Dict[str, Any]:
        """
        Get configuration for a specific validation rule.
        
        Resolution order:
        1. Organization + Region specific (e.g., ORG-001 + US + E2-F1)
        2. Organization + "ALL" region (e.g., ORG-001 + ALL + E2-F1)
        3. Hardcoded defaults
        
        Results are cached with configurable TTL.
        
        Args:
            org_id: Organization ID
            rule_id: Rule ID (e.g., "E2-F1")
            region: Region code (default "US")
        
        Returns:
            Configuration dictionary with rule_name, rule_category, parameters, etc.
        """
        # Build cache key
        cache_key = f"{org_id}:{region}:{rule_id}"
        
        # Check cache
        if cache_key in self._cache:
            cached_time, cached_value = self._cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(seconds=self.cache_ttl_seconds):
                logger.debug(f"[cache_hit] {cache_key}")
                return cached_value
        
        # Cache miss or expired - load from database
        try:
            # Try organization + region specific
            config = await self._load_from_db(org_id, rule_id, region)
            
            # If not found, try organization + "ALL" region
            if not config:
                config = await self._load_from_db(org_id, rule_id, "ALL")
            
            # If still not found, use hardcoded default
            if not config:
                config = self._get_hardcoded_default(rule_id)
                logger.debug(f"[fallback_hardcoded] {rule_id}")
            else:
                logger.debug(f"[loaded_from_db] {cache_key}")
            
            # Cache the result
            self._cache[cache_key] = (datetime.utcnow(), config)
            return config
        
        except Exception as e:
            logger.error(f"Error loading config for {cache_key}: {e}")
            # Fallback to hardcoded defaults on error
            config = self._get_hardcoded_default(rule_id)
            self._cache[cache_key] = (datetime.utcnow(), config)
            return config

    async def get_all_active_rules(
        self,
        org_id: str,
        region: str = "US"
    ) -> List[Dict[str, Any]]:
        """
        Get all enabled validation rules for an organization/region.
        
        Returns cached list (5-minute TTL).
        
        Args:
            org_id: Organization ID
            region: Region code (default "US")
        
        Returns:
            List of configuration dictionaries for all enabled rules
        """
        cache_key = f"all:{org_id}:{region}"
        
        # Check cache
        if cache_key in self._cache:
            cached_time, cached_value = self._cache[cache_key]
            if datetime.utcnow() - cached_time < timedelta(seconds=self.cache_ttl_seconds):
                logger.debug(f"[cache_hit] {cache_key}")
                return cached_value
        
        try:
            # Query all enabled rules for org + region
            rules = list(self.db.validation_config.find({
                "organization_id": org_id,
                "region": {"$in": [region, "ALL"]},
                "enabled": True
            }).sort([("region", -1), ("rule_id", 1)]))
            
            # If no region-specific rules, use ALL region
            if not rules:
                rules = list(self.db.validation_config.find({
                    "organization_id": org_id,
                    "region": "ALL",
                    "enabled": True
                }))
            
            # Add hardcoded defaults for any missing rules
            configured_rule_ids = {r["rule_id"] for r in rules}
            for rule_id, default_config in DEFAULT_CONFIG.items():
                if rule_id not in configured_rule_ids:
                    rules.append({
                        "rule_id": rule_id,
                        "rule_name": default_config["rule_name"],
                        "rule_category": default_config["rule_category"],
                        "severity": default_config["severity"],
                        "parameters": default_config["parameters"],
                        "enabled": True,
                        "_source": "hardcoded_default"
                    })
            
            logger.debug(f"[loaded_all_rules] {cache_key}: {len(rules)} rules")
            
            # Cache result
            self._cache[cache_key] = (datetime.utcnow(), rules)
            return rules
        
        except Exception as e:
            logger.error(f"Error loading all rules for {cache_key}: {e}")
            # Return all hardcoded defaults on error
            rules = [
                {
                    "rule_id": rule_id,
                    "rule_name": default_config["rule_name"],
                    "rule_category": default_config["rule_category"],
                    "severity": default_config["severity"],
                    "parameters": default_config["parameters"],
                    "enabled": True,
                    "_source": "hardcoded_default"
                }
                for rule_id, default_config in DEFAULT_CONFIG.items()
            ]
            self._cache[cache_key] = (datetime.utcnow(), rules)
            return rules

    async def reload_config(
        self,
        org_id: Optional[str] = None,
        region: Optional[str] = None,
        rule_id: Optional[str] = None
    ) -> None:
        """
        Invalidate cache for specific org/region/rule.
        Called after configuration updates.
        
        Args:
            org_id: Organization ID (optional, if None clears entire cache)
            region: Region code (optional)
            rule_id: Rule ID (optional)
        """
        if org_id is None:
            # Clear entire cache
            self._cache.clear()
            logger.info("[cache_cleared] entire cache")
            return
        
        # Build cache key pattern and clear matching entries
        keys_to_delete = []
        for cache_key in self._cache.keys():
            if org_id in cache_key:
                if region and region not in cache_key:
                    continue
                if rule_id and rule_id not in cache_key:
                    continue
                keys_to_delete.append(cache_key)
        
        for key in keys_to_delete:
            del self._cache[key]
        
        logger.info(f"[cache_invalidated] {len(keys_to_delete)} entries for {org_id}:{region}:{rule_id}")

    async def validate_config_params(
        self,
        rule_id: str,
        parameters: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that parameters are valid for a rule.
        
        Args:
            rule_id: Rule ID
            parameters: Parameters to validate
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Import validator here to avoid circular imports
        from app.services.config_validator import validate_parameters
        
        is_valid, errors = validate_parameters(rule_id, parameters)
        error_message = "; ".join(errors) if errors else None
        return is_valid, error_message

    async def _load_from_db(
        self,
        org_id: str,
        rule_id: str,
        region: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load configuration from database.
        
        Args:
            org_id: Organization ID
            rule_id: Rule ID
            region: Region code
        
        Returns:
            Configuration dictionary or None if not found
        """
        try:
            config = self.db.validation_config.find_one({
                "organization_id": org_id,
                "region": region,
                "rule_id": rule_id,
                "enabled": True
            })
            return config
        except Exception as e:
            logger.error(f"Database error loading config {org_id}:{region}:{rule_id}: {e}")
            return None

    def _get_hardcoded_default(self, rule_id: str) -> Dict[str, Any]:
        """
        Get hardcoded default configuration for a rule.
        
        Args:
            rule_id: Rule ID
        
        Returns:
            Configuration dictionary with defaults
        """
        if rule_id in DEFAULT_CONFIG:
            return {
                "rule_id": rule_id,
                **DEFAULT_CONFIG[rule_id],
                "enabled": True,
                "_source": "hardcoded_default"
            }
        
        # Unknown rule - return minimal config
        logger.warning(f"Unknown rule ID: {rule_id}")
        return {
            "rule_id": rule_id,
            "rule_name": "Unknown Rule",
            "rule_category": "UNKNOWN",
            "severity": "HARD",
            "parameters": {},
            "enabled": True,
            "_source": "hardcoded_default"
        }

    def get_all_default_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all hardcoded default configurations.
        
        Returns:
            Dictionary mapping rule_id to configuration
        """
        return {
            rule_id: {
                "rule_id": rule_id,
                **config,
                "enabled": True,
                "_source": "hardcoded_default"
            }
            for rule_id, config in DEFAULT_CONFIG.items()
        }


# Singleton instance
_config_service: Optional[ConfigurationService] = None


async def get_config_service(db: pymongo.database.Database) -> ConfigurationService:
    """
    Get or create the configuration service instance.
    
    Args:
        db: MongoDB database instance
    
    Returns:
        ConfigurationService instance
    """
    global _config_service
    if _config_service is None:
        _config_service = ConfigurationService(db)
    return _config_service


def reset_config_service() -> None:
    """Reset the configuration service instance (for testing)."""
    global _config_service
    _config_service = None
