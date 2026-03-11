"""
Project API endpoints for layout generation.

Thin route handlers that delegate to the service layer.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from entmoot.core.redis_storage import get_storage
from entmoot.models.errors import ErrorResponse
from entmoot.models.project import (
    ConstraintViolation,
    LayoutResults,
    OptimizationResults,
    PlacedAsset,
    ProjectConfig,
    ProjectResponse,
    ProjectStatus,
    ProjectStatusResponse,
)
from entmoot.services.optimization_service import generate_layout_async
from entmoot.services.project_service import ProjectService


class LatLng(BaseModel):
    """Geographic coordinate pair."""

    lat: float
    lng: float


class ValidatePlacementRequest(BaseModel):
    """Request body for single-asset placement validation."""

    asset_id: str
    position: LatLng
    rotation: float = 0.0
    width: float = Field(..., description="Width in feet")
    length: float = Field(..., description="Length in feet")


class ValidatePlacementResponse(BaseModel):
    """Response for placement validation."""

    violations: list[ConstraintViolation]
    is_valid: bool


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])

# Redis storage for projects (persists across container restarts)
storage = get_storage()


@router.get(
    "",
    response_model=list[dict[str, Any]],
    summary="Get all projects",
    description="Retrieve a list of all projects",
)
async def get_all_projects() -> list[dict[str, Any]]:
    """
    Get a list of all projects.

    Returns:
        List of projects with basic information
    """
    projects = []
    all_project_data = storage.get_all_projects()

    for project_data in all_project_data:
        projects.append(
            {
                "id": project_data.get("project_id"),
                "name": project_data.get("project_name", "Unnamed Project"),
                "status": project_data.get("status", "unknown"),
                "created_at": project_data.get("created_at"),
                "progress": project_data.get("progress", 0),
            }
        )

    # Sort by created_at descending (newest first)
    projects.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return projects


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid configuration"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Create a new project",
    description="Create a new project with configuration and start layout generation",
)
async def create_project(config: ProjectConfig) -> ProjectResponse:
    """
    Create a new project and initiate layout generation.

    Args:
        config: Project configuration including assets, constraints, and optimization weights

    Returns:
        ProjectResponse with project ID and initial status
    """
    try:
        project_id = str(uuid.uuid4())

        # Validate weights
        weights = config.optimization_weights
        error = ProjectService.validate_weights(
            weights.cost,
            weights.buildable_area,
            weights.accessibility,
            weights.environmental_impact,
            weights.aesthetics,
        )
        if error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code="INVALID_WEIGHTS",
                    message=error,
                ).model_dump(mode="json"),
            )

        # Store project configuration
        created_at_iso = datetime.utcnow().isoformat()
        project_data = {
            "project_id": project_id,
            "config": config.model_dump(),
            "project_name": config.project_name,
            "status": ProjectStatus.CREATED,
            "created_at": created_at_iso,
            "updated_at": created_at_iso,
            "progress": 0,
            "error": None,
        }
        storage.set_project(project_id, project_data)

        logger.info(f"Created project {project_id}: {config.project_name}")

        # Start layout generation in background
        asyncio.create_task(generate_layout_async(project_id, config))

        return ProjectResponse(
            project_id=project_id,
            project_name=config.project_name,
            status=ProjectStatus.PROCESSING,
            created_at=datetime.fromisoformat(created_at_iso),
            message="Project created successfully. Layout generation started.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating project: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="PROJECT_CREATION_ERROR",
                message="Failed to create project",
                details={"error": str(e)},
            ).model_dump(mode="json"),
        )


@router.get(
    "/{project_id}/status",
    response_model=ProjectStatusResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
    summary="Get project status",
    description="Check the status and progress of a layout generation project",
)
async def get_project_status(project_id: str) -> ProjectStatusResponse:
    """
    Get the current status of a project.

    Args:
        project_id: Project identifier

    Returns:
        ProjectStatusResponse with current status and progress
    """
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
            ).model_dump(mode="json"),
        )

    status_messages = {
        ProjectStatus.CREATED: "Project created, initializing...",
        ProjectStatus.PROCESSING: f"Generating layout... {project['progress']:.0f}% complete",
        ProjectStatus.COMPLETED: "Layout generation completed successfully",
        ProjectStatus.FAILED: "Layout generation failed",
    }

    return ProjectStatusResponse(
        project_id=project_id,
        status=project["status"],
        progress=project["progress"],
        message=status_messages.get(project["status"], "Unknown status"),
        error=project.get("error"),
    )


@router.post(
    "/{project_id}/reoptimize",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
        400: {"model": ErrorResponse, "description": "Invalid configuration"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Re-optimize a project",
    description="Re-run optimization with updated configuration parameters",
)
async def reoptimize_project(
    project_id: str,
    config_updates: Optional[Dict] = None,
) -> ProjectResponse:
    """
    Re-optimize an existing project with optional configuration updates.

    Args:
        project_id: Project identifier
        config_updates: Optional partial configuration updates (weights, constraints, etc.)

    Returns:
        ProjectResponse with updated status
    """
    try:
        project = storage.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error_code="PROJECT_NOT_FOUND",
                    message=f"Project {project_id} not found",
                ).model_dump(mode="json"),
            )

        existing_config = ProjectConfig(**project["config"])

        if config_updates:
            config_dict = existing_config.model_dump()
            for key, value in config_updates.items():
                if (
                    key in config_dict
                    and isinstance(config_dict[key], dict)
                    and isinstance(value, dict)
                ):
                    config_dict[key].update(value)
                else:
                    config_dict[key] = value
            updated_config = ProjectConfig(**config_dict)
        else:
            updated_config = existing_config

        # Validate weights
        weights = updated_config.optimization_weights
        error = ProjectService.validate_weights(
            weights.cost,
            weights.buildable_area,
            weights.accessibility,
            weights.environmental_impact,
            weights.aesthetics,
        )
        if error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code="INVALID_WEIGHTS",
                    message=error,
                ).model_dump(mode="json"),
            )

        updated_at_iso = datetime.utcnow().isoformat()
        project.update(
            {
                "config": updated_config.model_dump(),
                "status": ProjectStatus.PROCESSING,
                "updated_at": updated_at_iso,
                "progress": 0,
                "error": None,
            }
        )
        storage.set_project(project_id, project)

        logger.info(f"Re-optimizing project {project_id}: {updated_config.project_name}")

        current_assets = None
        results_data = storage.get_results(project_id)
        if results_data and results_data.get("placed_assets"):
            current_assets = results_data["placed_assets"]
            logger.info(
                f"Re-optimization will start from {len(current_assets)} current asset positions"
            )

        asyncio.create_task(generate_layout_async(project_id, updated_config, current_assets))

        return ProjectResponse(
            project_id=project_id,
            project_name=updated_config.project_name,
            status=ProjectStatus.PROCESSING,
            created_at=datetime.fromisoformat(project["created_at"]),
            message="Re-optimization started. Layout generation in progress.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error re-optimizing project: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="REOPTIMIZATION_ERROR",
                message="Failed to re-optimize project",
                details={"error": str(e)},
            ).model_dump(mode="json"),
        )


@router.put(
    "/{project_id}/alternatives/{alternative_id}",
    response_model=Dict,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
        400: {"model": ErrorResponse, "description": "Invalid data"},
    },
    summary="Update alternative layout",
    description="Update the assets in an alternative layout",
)
async def update_alternative(
    project_id: str,
    alternative_id: str,
    update_data: Dict,
) -> Dict:
    """
    Update an alternative's assets.

    Args:
        project_id: Project identifier
        alternative_id: Alternative identifier
        update_data: Dictionary containing 'assets' array

    Returns:
        Success response
    """
    try:
        project = storage.get_project(project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error_code="PROJECT_NOT_FOUND",
                    message=f"Project {project_id} not found",
                ).model_dump(mode="json"),
            )

        results_data = storage.get_results(project_id)
        if not results_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error_code="RESULTS_NOT_FOUND",
                    message=f"Results for project {project_id} not found",
                ).model_dump(mode="json"),
            )

        if "assets" in update_data:
            from entmoot.models.project import PlacedAsset

            updated_assets = [PlacedAsset(**asset) for asset in update_data["assets"]]
            results_data["placed_assets"] = [asset.model_dump() for asset in updated_assets]
            storage.set_results(project_id, results_data)

            project["updated_at"] = datetime.utcnow().isoformat()
            storage.set_project(project_id, project)

            logger.info(f"Updated {len(updated_assets)} assets for project {project_id}")

        return {"success": True, "message": "Alternative updated successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alternative: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="UPDATE_ERROR",
                message="Failed to update alternative",
                details={"error": str(e)},
            ).model_dump(mode="json"),
        )


@router.get(
    "/{project_id}/results",
    response_model=OptimizationResults,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
        400: {"model": ErrorResponse, "description": "Results not ready"},
    },
    summary="Get layout results",
    description="Retrieve the generated layout results for a completed project",
)
async def get_layout_results(project_id: str) -> OptimizationResults:
    """
    Get the layout generation results.

    Args:
        project_id: Project identifier

    Returns:
        OptimizationResults with placed assets, roads, cost estimates, and metadata
    """
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
            ).model_dump(mode="json"),
        )

    if project["status"] != ProjectStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_code="RESULTS_NOT_READY",
                message=f"Layout results not ready. Current status: {project['status']}",
                details={"progress": project["progress"]},
            ).model_dump(mode="json"),
        )

    results_data = storage.get_results(project_id)
    if not results_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="RESULTS_MISSING",
                message="Layout results are missing",
            ).model_dump(mode="json"),
        )

    layout_results = LayoutResults(**results_data)

    return ProjectService.build_optimization_results(project, layout_results, project_id)


@router.post(
    "/{project_id}/validate-placement",
    response_model=ValidatePlacementResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
    summary="Validate single asset placement",
    description="Check a single asset position against constraints (for drag-and-drop)",
)
async def validate_placement(
    project_id: str,
    req: ValidatePlacementRequest,
) -> ValidatePlacementResponse:
    """Validate a single asset placement against project constraints."""
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
            ).model_dump(mode="json"),
        )

    results_data = storage.get_results(project_id)
    other_assets = []
    if results_data and results_data.get("placed_assets"):
        other_assets = [PlacedAsset(**a) for a in results_data["placed_assets"]]

    violations = ProjectService.validate_single_asset_placement(
        asset_id=req.asset_id,
        lat=req.position.lat,
        lng=req.position.lng,
        rotation=req.rotation,
        width_ft=req.width,
        length_ft=req.length,
        other_assets=other_assets,
        utm_data=project.get("utm_data"),
    )

    has_errors = any(v.severity == "error" for v in violations)
    return ValidatePlacementResponse(
        violations=violations,
        is_valid=not has_errors,
    )


@router.get(
    "/{project_id}/alternatives/{alternative_id}/export/{export_format}",
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
        400: {"model": ErrorResponse, "description": "Invalid format"},
    },
    summary="Export layout",
    description="Export a layout alternative in the specified format",
)
async def export_layout(
    project_id: str,
    alternative_id: str,
    export_format: str,
) -> Any:
    """
    Export layout in specified format.

    Args:
        project_id: Project identifier
        alternative_id: Alternative identifier
        export_format: Export format (pdf, dxf, kmz, geojson)

    Returns:
        Export file as response
    """
    import tempfile
    from pathlib import Path

    from shapely.geometry import LineString as ShapelyLineString
    from shapely.geometry import Polygon as ShapelyPolygon

    valid_formats = {"kmz", "geojson", "dxf", "pdf"}
    if export_format.lower() not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_code="INVALID_FORMAT",
                message=f"Invalid export format '{export_format}'. Must be one of: {', '.join(sorted(valid_formats))}",
            ).model_dump(mode="json"),
        )

    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
            ).model_dump(mode="json"),
        )

    results_data = storage.get_results(project_id)
    if not results_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="RESULTS_NOT_FOUND",
                message=f"No results found for project {project_id}",
            ).model_dump(mode="json"),
        )

    project_name = project.get("name", "Untitled")
    boundary_coords = project.get("property_boundary", [])
    site_boundary = None
    if boundary_coords:
        site_boundary = ShapelyPolygon([(p["longitude"], p["latitude"]) for p in boundary_coords])

    placed_assets = results_data.get("placed_assets", [])
    road_network = results_data.get("road_network", [])
    fmt = export_format.lower()

    if fmt in ("kmz", "geojson", "dxf"):
        from entmoot.core.export import DXFExporter, ExportData, GeoJSONExporter, KMZExporter

        export_data = ExportData(
            project_name=project_name,
            crs_epsg=4326,
            site_boundary=site_boundary,
        )

        for asset in placed_assets:
            polygon_coords = asset.get("polygon", [])
            if polygon_coords:
                footprint = ShapelyPolygon(
                    [(c["longitude"], c["latitude"]) for c in polygon_coords]
                )
                export_data.add_asset(
                    geometry=footprint,
                    name=asset.get("id", "asset"),
                    asset_type=asset.get("type", "unknown"),
                )

        for seg in road_network:
            points = seg.get("points", [])
            if len(points) >= 2:
                line = ShapelyLineString([(p["longitude"], p["latitude"]) for p in points])
                export_data.add_road(
                    geometry=line,
                    name=seg.get("id", "road"),
                )

        suffix_map = {"kmz": ".kmz", "geojson": ".geojson", "dxf": ".dxf"}
        media_map = {
            "kmz": "application/vnd.google-earth.kmz",
            "geojson": "application/geo+json",
            "dxf": "application/dxf",
        }
        exporter_map = {
            "kmz": KMZExporter(),
            "geojson": GeoJSONExporter(),
            "dxf": DXFExporter(),
        }

        with tempfile.NamedTemporaryFile(suffix=suffix_map[fmt], delete=False) as tmp:
            output_path = Path(tmp.name)

        exporter_map[fmt].export(export_data, output_path)

        return FileResponse(
            path=str(output_path),
            media_type=media_map[fmt],
            filename=f"{project_name}{suffix_map[fmt]}",
        )

    else:  # pdf
        from entmoot.core.reports import PDFReportGenerator, ReportData

        location = project.get("location", "Unknown")
        if site_boundary is None:
            site_boundary = ShapelyPolygon([(0, 0), (1, 0), (1, 1), (0, 1)])

        report_data = ReportData(
            project_name=project_name,
            location=location,
            site_boundary=site_boundary,
        )

        report_data.assets = [
            {
                "id": a.get("id", ""),
                "type": a.get("type", ""),
                "width": a.get("width", 0),
                "length": a.get("length", 0),
                "position": a.get("position", {}),
            }
            for a in placed_assets
        ]

        total_road_length = sum(s.get("length", 0) for s in road_network)
        report_data.roads = {
            "total_length_m": total_road_length * 0.3048,  # feet to meters
            "segments": [
                {
                    "id": s.get("id", ""),
                    "length": s.get("length", 0),
                    "width": s.get("width", 0),
                    "grade": s.get("grade", 0),
                }
                for s in road_network
            ],
        }

        earthwork = results_data.get("earthwork", {})
        report_data.earthwork = earthwork

        report_data.costs = {
            "total": results_data.get("total_cost", 0),
            "earthwork": earthwork.get("estimated_cost", 0),
        }

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            output_path = Path(tmp.name)

        PDFReportGenerator().generate(report_data, output_path)

        return FileResponse(
            path=str(output_path),
            media_type="application/pdf",
            filename=f"{project_name}_report.pdf",
        )


@router.delete(
    "/{project_id}",
    responses={
        404: {"model": ErrorResponse, "description": "Project not found"},
    },
    summary="Delete a project",
    description="Delete a project and its associated data",
)
async def delete_project(project_id: str) -> Dict:
    """
    Delete a project.

    Args:
        project_id: Project identifier

    Returns:
        Success response
    """
    project = storage.get_project(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
            ).model_dump(mode="json"),
        )

    storage.delete_project(project_id)
    logger.info(f"Deleted project {project_id}")

    return {"success": True, "message": f"Project {project_id} deleted"}
