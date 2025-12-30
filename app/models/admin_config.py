"""
Schemas for admin configuration API endpoints.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List, Any
from datetime import datetime


class ChangeHistoryEntry(BaseModel):
    """Single change history entry."""
    timestamp: datetime
    changed_by: str
    field_changed: str
    old_value: Any
    new_value: Any
    reason: Optional[str] = None


class ConfigurationParametersUpdate(BaseModel):
    """Update to configuration parameters."""
    org_id: str
    region: str = "US"
    enabled: Optional[bool] = None
    parameters: Optional[Dict[str, Any]] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    reason: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        valid_regions = {"US", "EU", "APAC", "ALL"}
        if v not in valid_regions:
            raise ValueError(f"Region must be one of: {valid_regions}")
        return v

    @field_validator("effective_to")
    @classmethod
    def validate_effective_dates(cls, v: Optional[datetime], info) -> Optional[datetime]:
        if v is None:
            return v
        effective_from = info.data.get("effective_from")
        if effective_from and v <= effective_from:
            raise ValueError("effective_to must be after effective_from")
        return v


class ConfigurationResponse(BaseModel):
    """Response with configuration details."""
    rule_id: str
    rule_name: str
    rule_category: str
    enabled: bool
    severity: Optional[str] = None
    parameters: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    change_count: Optional[int] = None


class ConfigurationListResponse(BaseModel):
    """Response containing list of configurations."""
    data: List[ConfigurationResponse]
    total: int
    org_id: str
    region: str


class ConfigurationHistoryResponse(BaseModel):
    """Single change history entry for API response."""
    timestamp: datetime
    changed_by: str
    rule_id: str
    field: str
    old_value: Any
    new_value: Any
    reason: Optional[str] = None
    effective_period: Optional[str] = None


class ConfigurationHistoryListResponse(BaseModel):
    """Response containing change history."""
    data: List[ConfigurationHistoryResponse]
    total: int
    org_id: str
    rule_id: Optional[str] = None
    days: int


class ConfigurationValidationRequest(BaseModel):
    """Request to validate configuration parameters."""
    rule_id: str
    parameters: Dict[str, Any]


class ConfigurationValidationResponse(BaseModel):
    """Response from parameter validation."""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ConfigurationUpdateResponse(BaseModel):
    """Response after updating configuration."""
    success: bool
    rule_id: str
    org_id: str
    region: str
    updated_at: datetime
    message: Optional[str] = None


class ConfigurationDisableResponse(BaseModel):
    """Response after disabling configuration."""
    success: bool
    rule_id: str
    org_id: str
    region: str
    enabled: bool
    disabled_at: datetime


class DefaultConfigurationResponse(BaseModel):
    """Response containing default configuration."""
    rule_id: str
    rule_name: str
    rule_category: str
    severity: str
    parameters: Dict[str, Any]


class DefaultConfigurationListResponse(BaseModel):
    """Response containing list of default configurations."""
    data: List[DefaultConfigurationResponse]
    total: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    status_code: int
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AdminConfigDisableRequest(BaseModel):
    """Request to disable a configuration."""
    org_id: str
    reason: Optional[str] = None
