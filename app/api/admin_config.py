"""
Admin API endpoints for validation configuration management.

Provides endpoints to:
- View configuration for organizations/regions
- Update configuration parameters
- View change history
- Validate parameters
- Access default configurations
"""

from fastapi import APIRouter, Depends, Query, HTTPException, status
from typing import Optional, List
from datetime import datetime, timedelta
import logging

from app.storage.mongo_client import get_db
from app.services.config_service import get_config_service, ConfigurationService
from app.services.config_validator import validate_parameters, get_rule_schema, get_all_rules_schema
from app.models.admin_config import (
    ConfigurationResponse,
    ConfigurationListResponse,
    ConfigurationHistoryResponse,
    ConfigurationHistoryListResponse,
    ConfigurationValidationRequest,
    ConfigurationValidationResponse,
    ConfigurationUpdateResponse,
    ConfigurationDisableResponse,
    DefaultConfigurationResponse,
    DefaultConfigurationListResponse,
    ConfigurationParametersUpdate,
    AdminConfigDisableRequest,
    ErrorResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/validation-config", tags=["admin-config"])


# Dependency to get config service
async def get_config_svc(db=Depends(get_db)) -> ConfigurationService:
    """Get configuration service instance."""
    return await get_config_service(db)


@router.get(
    "",
    response_model=ConfigurationListResponse,
    summary="Get all configurations for organization",
    description="Retrieve all validation rule configurations for an organization and region"
)
async def get_configurations(
    org_id: str = Query(..., description="Organization ID"),
    region: str = Query("US", description="Region (US, EU, APAC, ALL)"),
    config_svc: ConfigurationService = Depends(get_config_svc),
    db=Depends(get_db)
) -> ConfigurationListResponse:
    """
    Get all active validation rule configurations for an organization/region.
    
    Returns configurations from database if available, otherwise returns hardcoded defaults.
    """
    try:
        rules = await config_svc.get_all_active_rules(org_id, region)
        
        # Remove internal fields
        data = []
        for rule in rules:
            resp = ConfigurationResponse(
                rule_id=rule.get("rule_id"),
                rule_name=rule.get("rule_name"),
                rule_category=rule.get("rule_category"),
                enabled=rule.get("enabled", True),
                severity=rule.get("severity"),
                parameters=rule.get("parameters", {}),
                created_at=rule.get("created_at"),
                updated_at=rule.get("updated_at"),
                created_by=rule.get("created_by"),
                updated_by=rule.get("updated_by"),
                effective_from=rule.get("effective_from"),
                effective_to=rule.get("effective_to"),
                tags=rule.get("tags"),
                notes=rule.get("notes"),
                change_count=len(rule.get("change_history", []))
            )
            data.append(resp)
        
        return ConfigurationListResponse(
            data=data,
            total=len(data),
            org_id=org_id,
            region=region
        )
    except Exception as e:
        logger.error(f"Error retrieving configurations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving configurations"
        )


@router.get(
    "/{rule_id}",
    response_model=ConfigurationResponse,
    summary="Get specific rule configuration",
    description="Retrieve configuration for a specific validation rule"
)
async def get_rule_configuration(
    rule_id: str = Query(..., description="Rule ID (e.g., E2-F1)"),
    org_id: str = Query(..., description="Organization ID"),
    region: str = Query("US", description="Region (US, EU, APAC, ALL)"),
    config_svc: ConfigurationService = Depends(get_config_svc),
    db=Depends(get_db)
) -> ConfigurationResponse:
    """
    Get configuration for a specific validation rule.
    """
    try:
        rule_config = await config_svc.get_rule_config(org_id, rule_id, region)
        
        return ConfigurationResponse(
            rule_id=rule_config.get("rule_id"),
            rule_name=rule_config.get("rule_name"),
            rule_category=rule_config.get("rule_category"),
            enabled=rule_config.get("enabled", True),
            severity=rule_config.get("severity"),
            parameters=rule_config.get("parameters", {}),
            created_at=rule_config.get("created_at"),
            updated_at=rule_config.get("updated_at"),
            created_by=rule_config.get("created_by"),
            updated_by=rule_config.get("updated_by"),
            effective_from=rule_config.get("effective_from"),
            effective_to=rule_config.get("effective_to"),
            tags=rule_config.get("tags"),
            notes=rule_config.get("notes"),
            change_count=len(rule_config.get("change_history", []))
        )
    except Exception as e:
        logger.error(f"Error retrieving rule configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving rule configuration"
        )


@router.put(
    "/{rule_id}",
    response_model=ConfigurationUpdateResponse,
    summary="Update rule configuration",
    description="Update configuration parameters for a validation rule"
)
async def update_rule_configuration(
    rule_id: str,
    request: ConfigurationParametersUpdate,
    config_svc: ConfigurationService = Depends(get_config_svc),
    db=Depends(get_db)
) -> ConfigurationUpdateResponse:
    """
    Update configuration for a validation rule.
    
    Validates parameters before updating, records change history.
    """
    try:
        # Validate parameters if provided
        if request.parameters:
            is_valid, error_msg = await config_svc.validate_config_params(rule_id, request.parameters)
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid parameters: {error_msg}"
                )
        
        # Get current config for change history
        current = await config_svc.get_rule_config(request.org_id, rule_id, request.region)
        current_params = current.get("parameters", {})
        
        # Prepare update data
        update_data = {
            "organization_id": request.org_id,
            "region": request.region,
            "rule_id": rule_id,
            "updated_at": datetime.utcnow(),
            "updated_by": "admin_api"  # TODO: Get from auth context
        }
        
        if request.enabled is not None:
            update_data["enabled"] = request.enabled
        
        if request.parameters is not None:
            update_data["parameters"] = request.parameters
        
        if request.effective_from:
            update_data["effective_from"] = request.effective_from
        
        if request.effective_to:
            update_data["effective_to"] = request.effective_to
        
        if request.tags:
            update_data["tags"] = request.tags
        
        if request.notes:
            update_data["notes"] = request.notes
        
        # Build change history entry
        change_entry = {
            "timestamp": datetime.utcnow(),
            "changed_by": "admin_api",  # TODO: Get from auth context
            "field_changed": "parameters" if request.parameters else "enabled",
            "old_value": current_params if request.parameters else current.get("enabled"),
            "new_value": request.parameters if request.parameters else request.enabled,
            "reason": request.reason
        }
        
        # Update in database
        result = db.validation_config.update_one(
            {
                "organization_id": request.org_id,
                "region": request.region,
                "rule_id": rule_id
            },
            {
                "$set": update_data,
                "$push": {"change_history": change_entry}
            },
            upsert=True
        )
        
        if not result.matched_count:
            # Insert new document
            insert_data = {
                "organization_id": request.org_id,
                "region": request.region,
                "rule_id": rule_id,
                "rule_name": current.get("rule_name", "Unknown"),
                "rule_category": current.get("rule_category", "UNKNOWN"),
                "severity": current.get("severity", "HARD"),
                "enabled": request.enabled if request.enabled is not None else True,
                "parameters": request.parameters or {},
                "created_at": datetime.utcnow(),
                "created_by": "admin_api",
                "updated_at": datetime.utcnow(),
                "updated_by": "admin_api",
                "change_history": [change_entry]
            }
            db.validation_config.insert_one(insert_data)
        
        # Invalidate cache
        await config_svc.reload_config(request.org_id, request.region, rule_id)
        
        logger.info(f"Updated config: {request.org_id}:{request.region}:{rule_id}")
        
        return ConfigurationUpdateResponse(
            success=True,
            rule_id=rule_id,
            org_id=request.org_id,
            region=request.region,
            updated_at=datetime.utcnow(),
            message="Configuration updated successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error updating configuration"
        )


@router.put(
    "/{rule_id}/disable",
    response_model=ConfigurationDisableResponse,
    summary="Disable rule configuration",
    description="Disable a validation rule for an organization"
)
async def disable_rule(
    rule_id: str,
    request: AdminConfigDisableRequest,
    config_svc: ConfigurationService = Depends(get_config_svc),
    db=Depends(get_db)
) -> ConfigurationDisableResponse:
    """
    Disable a validation rule for an organization.
    """
    try:
        current = await config_svc.get_rule_config(request.org_id, rule_id, "US")
        
        change_entry = {
            "timestamp": datetime.utcnow(),
            "changed_by": "admin_api",
            "field_changed": "enabled",
            "old_value": current.get("enabled", True),
            "new_value": False,
            "reason": request.reason
        }
        
        result = db.validation_config.update_one(
            {
                "organization_id": request.org_id,
                "region": "ALL",
                "rule_id": rule_id
            },
            {
                "$set": {
                    "enabled": False,
                    "updated_at": datetime.utcnow(),
                    "updated_by": "admin_api"
                },
                "$push": {"change_history": change_entry}
            },
            upsert=True
        )
        
        # Invalidate cache
        await config_svc.reload_config(request.org_id, None, rule_id)
        
        logger.info(f"Disabled rule: {request.org_id}:{rule_id}")
        
        return ConfigurationDisableResponse(
            success=True,
            rule_id=rule_id,
            org_id=request.org_id,
            region="ALL",
            enabled=False,
            disabled_at=datetime.utcnow()
        )
    
    except Exception as e:
        logger.error(f"Error disabling rule: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error disabling rule"
        )


@router.get(
    "/history",
    response_model=ConfigurationHistoryListResponse,
    summary="Get configuration change history",
    description="Retrieve change history for configurations"
)
async def get_configuration_history(
    org_id: str = Query(..., description="Organization ID"),
    rule_id: Optional[str] = Query(None, description="Optional rule ID filter"),
    days: int = Query(30, ge=1, le=365, description="Number of days to retrieve"),
    db=Depends(get_db)
) -> ConfigurationHistoryListResponse:
    """
    Get configuration change history for an organization.
    """
    try:
        # Build query
        query = {"organization_id": org_id}
        if rule_id:
            query["rule_id"] = rule_id
        
        # Calculate date range
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Find configurations with change history
        configs = list(db.validation_config.find(query))
        
        # Extract and filter change history entries
        history_entries = []
        for config in configs:
            for entry in config.get("change_history", []):
                entry_time = entry.get("timestamp")
                if isinstance(entry_time, str):
                    entry_time = datetime.fromisoformat(entry_time)
                
                if entry_time >= start_date:
                    history_entries.append(ConfigurationHistoryResponse(
                        timestamp=entry_time,
                        changed_by=entry.get("changed_by", "unknown"),
                        rule_id=config.get("rule_id"),
                        field=entry.get("field_changed", "unknown"),
                        old_value=entry.get("old_value"),
                        new_value=entry.get("new_value"),
                        reason=entry.get("reason"),
                        effective_period=(
                            f"{config.get('effective_from', '').split('T')[0]} to "
                            f"{config.get('effective_to', '').split('T')[0]}"
                            if config.get("effective_from") or config.get("effective_to")
                            else None
                        )
                    ))
        
        # Sort by timestamp descending
        history_entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        return ConfigurationHistoryListResponse(
            data=history_entries,
            total=len(history_entries),
            org_id=org_id,
            rule_id=rule_id,
            days=days
        )
    
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving history"
        )


@router.post(
    "/validate",
    response_model=ConfigurationValidationResponse,
    summary="Validate configuration parameters",
    description="Validate that parameters are correct for a rule"
)
async def validate_config(
    request: ConfigurationValidationRequest,
    config_svc: ConfigurationService = Depends(get_config_svc)
) -> ConfigurationValidationResponse:
    """
    Validate configuration parameters for a rule.
    """
    try:
        is_valid, error_msg = await config_svc.validate_config_params(request.rule_id, request.parameters)
        
        return ConfigurationValidationResponse(
            valid=is_valid,
            errors=[error_msg] if error_msg else [],
            warnings=[]
        )
    
    except Exception as e:
        logger.error(f"Error validating parameters: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating parameters"
        )


@router.get(
    "/defaults",
    response_model=DefaultConfigurationListResponse,
    summary="Get default configurations",
    description="Retrieve hardcoded default configurations"
)
async def get_defaults(
    rule_id: Optional[str] = Query(None, description="Optional rule ID filter"),
    config_svc: ConfigurationService = Depends(get_config_svc)
) -> DefaultConfigurationListResponse:
    """
    Get hardcoded default configurations.
    """
    try:
        all_defaults = config_svc.get_all_default_configs()
        
        data = []
        for rid, config in all_defaults.items():
            if rule_id and rid != rule_id:
                continue
            
            data.append(DefaultConfigurationResponse(
                rule_id=config.get("rule_id"),
                rule_name=config.get("rule_name"),
                rule_category=config.get("rule_category"),
                severity=config.get("severity"),
                parameters=config.get("parameters", {})
            ))
        
        return DefaultConfigurationListResponse(
            data=data,
            total=len(data)
        )
    
    except Exception as e:
        logger.error(f"Error retrieving defaults: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error retrieving defaults"
        )
