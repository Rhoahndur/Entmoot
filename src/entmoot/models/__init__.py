"""
Data models and schemas.
"""

from .boundary import (
    BoundaryExtractionResult,
    BoundaryMetadata,
    BoundaryMetrics,
    BoundarySource,
    GeometryIssue,
    PropertyBoundary,
    SubParcel,
)
from .constraints import (
    Constraint,
    ConstraintType,
    ConstraintSeverity,
    ConstraintPriority,
    SetbackConstraint,
    ExclusionZoneConstraint,
    RegulatoryConstraint as RegulatoryConstraintV2,
    UserDefinedConstraint,
    STANDARD_SETBACKS,
    create_standard_setback,
)
from .regulatory import (
    FloodplainData,
    FloodZone,
    FloodZoneType,
    RegulatoryConstraint,
    RegulatoryDataSource,
)
from .elevation import (
    DEMTileMetadata,
    DEMTileRequest,
    ElevationBatchResponse,
    ElevationDataSource,
    ElevationDatum,
    ElevationPoint,
    ElevationQuery,
    ElevationQueryStatus,
    USRegion,
)
from .terrain import (
    DEMData,
    DEMMetadata,
    DEMValidationResult,
    ElevationUnit,
    InterpolationMethod,
    ResamplingMethod,
    TerrainMetrics,
)
from .upload import ErrorResponse, FileType, UploadMetadata, UploadResponse, UploadStatus
from .asset import (
    AssetType,
    PlacedAsset,
    SpacingRule,
    DEFAULT_SPACING_RULES,
    get_required_spacing,
)
from .assets import (
    Asset,
    BuildingAsset,
    EquipmentYardAsset,
    ParkingLotAsset,
    StorageTankAsset,
    RotationAngle,
    create_asset_from_dict,
)

__all__ = [
    # Boundary models
    "PropertyBoundary",
    "BoundaryMetrics",
    "BoundaryMetadata",
    "SubParcel",
    "BoundaryExtractionResult",
    "BoundarySource",
    "GeometryIssue",
    # Constraint models (Story 2.4)
    "Constraint",
    "ConstraintType",
    "ConstraintSeverity",
    "ConstraintPriority",
    "SetbackConstraint",
    "ExclusionZoneConstraint",
    "RegulatoryConstraintV2",
    "UserDefinedConstraint",
    "STANDARD_SETBACKS",
    "create_standard_setback",
    # Terrain models (Story 2.1)
    "DEMData",
    "DEMMetadata",
    "DEMValidationResult",
    "ElevationUnit",
    "InterpolationMethod",
    "ResamplingMethod",
    "TerrainMetrics",
    # Elevation models (Story 2.7)
    "ElevationPoint",
    "ElevationQuery",
    "ElevationQueryStatus",
    "ElevationBatchResponse",
    "ElevationDataSource",
    "ElevationDatum",
    "DEMTileMetadata",
    "DEMTileRequest",
    "USRegion",
    # Upload models
    "UploadMetadata",
    "UploadResponse",
    "ErrorResponse",
    "FileType",
    "UploadStatus",
    # Regulatory models
    "FloodZone",
    "FloodZoneType",
    "FloodplainData",
    "RegulatoryConstraint",
    "RegulatoryDataSource",
    # Asset models (Story 3.4)
    "AssetType",
    "PlacedAsset",
    "SpacingRule",
    "DEFAULT_SPACING_RULES",
    "get_required_spacing",
    # Optimization asset models (Story 3.1)
    "Asset",
    "BuildingAsset",
    "EquipmentYardAsset",
    "ParkingLotAsset",
    "StorageTankAsset",
    "RotationAngle",
    "create_asset_from_dict",
]
