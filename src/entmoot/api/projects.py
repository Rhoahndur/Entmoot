"""
Project API endpoints for layout generation.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from entmoot.models.errors import ErrorResponse
from entmoot.models.project import (
    Bounds,
    BuildableArea,
    Coordinate,
    CostBreakdown,
    EarthworkVolumes,
    LayoutAlternative,
    LayoutMetrics,
    LayoutResults,
    OptimizationResults,
    ProjectConfig,
    ProjectResponse,
    ProjectStatus,
    ProjectStatusResponse,
    RoadNetwork,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", tags=["projects"])

# In-memory storage for projects (in production, use a database)
projects_db: Dict[str, Dict] = {}
layout_results_db: Dict[str, LayoutResults] = {}


@router.get(
    "",
    response_model=list,
    summary="Get all projects",
    description="Retrieve a list of all projects",
)
async def get_all_projects():
    """
    Get a list of all projects.

    Returns:
        List of projects with basic information
    """
    projects = []
    for project_id, project_data in projects_db.items():
        projects.append({
            "id": project_id,
            "name": project_data.get("project_name", "Unnamed Project"),
            "status": project_data.get("status", "unknown"),
            "created_at": project_data.get("created_at"),
            "progress": project_data.get("progress", 0),
        })

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
        # Generate unique project ID
        project_id = str(uuid.uuid4())

        # Validate weights sum to 100
        weights = config.optimization_weights
        total_weight = (
            weights.cost
            + weights.buildable_area
            + weights.accessibility
            + weights.environmental_impact
            + weights.aesthetics
        )

        if abs(total_weight - 100) > 0.01:  # Allow small floating point errors
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code="INVALID_WEIGHTS",
                    message=f"Optimization weights must sum to 100%, got {total_weight}%",
                ).model_dump(mode="json"),
            )

        # Store project configuration
        created_at_iso = datetime.utcnow().isoformat()
        projects_db[project_id] = {
            "config": config.model_dump(),
            "project_name": config.project_name,
            "status": ProjectStatus.CREATED,
            "created_at": created_at_iso,
            "updated_at": created_at_iso,
            "progress": 0,
            "error": None,
        }

        logger.info(f"Created project {project_id}: {config.project_name}")

        # Start layout generation in background
        asyncio.create_task(generate_layout_async(project_id, config))

        return ProjectResponse(
            project_id=project_id,
            project_name=config.project_name,
            status=ProjectStatus.PROCESSING,
            created_at=datetime.fromisoformat(projects_db[project_id]["created_at"]),
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
    if project_id not in projects_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
            ).model_dump(mode="json"),
        )

    project = projects_db[project_id]

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
        # Check if project exists
        if project_id not in projects_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error_code="PROJECT_NOT_FOUND",
                    message=f"Project {project_id} not found",
                ).model_dump(mode="json"),
            )

        # Get existing project configuration
        project = projects_db[project_id]
        existing_config = ProjectConfig(**project["config"])

        # Merge updates into existing config
        if config_updates:
            config_dict = existing_config.model_dump()

            # Deep merge for nested objects
            for key, value in config_updates.items():
                if key in config_dict and isinstance(config_dict[key], dict) and isinstance(value, dict):
                    # Merge nested dictionaries
                    config_dict[key].update(value)
                else:
                    config_dict[key] = value

            # Create new config from merged data
            updated_config = ProjectConfig(**config_dict)
        else:
            # Use existing config as-is
            updated_config = existing_config

        # Validate weights sum to 100
        weights = updated_config.optimization_weights
        total_weight = (
            weights.cost
            + weights.buildable_area
            + weights.accessibility
            + weights.environmental_impact
            + weights.aesthetics
        )

        if abs(total_weight - 100) > 0.01:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=ErrorResponse(
                    error_code="INVALID_WEIGHTS",
                    message=f"Optimization weights must sum to 100%, got {total_weight}%",
                ).model_dump(mode="json"),
            )

        # Update project configuration and reset status
        updated_at_iso = datetime.utcnow().isoformat()
        projects_db[project_id].update({
            "config": updated_config.model_dump(),
            "status": ProjectStatus.PROCESSING,
            "updated_at": updated_at_iso,
            "progress": 0,
            "error": None,
        })

        logger.info(f"Re-optimizing project {project_id}: {updated_config.project_name}")

        # Get current assets if available (to use as starting point for optimization)
        current_assets = None
        if project.get("results") and project["results"].get("alternatives"):
            # Use the first (best) alternative's assets
            current_alternative = project["results"]["alternatives"][0]
            if current_alternative.get("assets"):
                current_assets = current_alternative["assets"]
                logger.info(f"Re-optimization will start from current asset positions")

        # Start layout generation in background
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
        # Check if project exists
        if project_id not in projects_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error_code="PROJECT_NOT_FOUND",
                    message=f"Project {project_id} not found",
                ).model_dump(mode="json"),
            )

        # Check if results exist
        if project_id not in layout_results_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorResponse(
                    error_code="RESULTS_NOT_FOUND",
                    message=f"Results for project {project_id} not found",
                ).model_dump(mode="json"),
            )

        # Update the assets in the layout results
        if 'assets' in update_data:
            from entmoot.models.project import PlacedAsset

            # Validate and convert assets
            updated_assets = [PlacedAsset(**asset) for asset in update_data['assets']]

            # Update the stored results
            layout_results_db[project_id].placed_assets = updated_assets

            # Update timestamp
            projects_db[project_id]["updated_at"] = datetime.utcnow().isoformat()

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
    if project_id not in projects_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorResponse(
                error_code="PROJECT_NOT_FOUND",
                message=f"Project {project_id} not found",
            ).model_dump(mode="json"),
        )

    project = projects_db[project_id]

    if project["status"] != ProjectStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(
                error_code="RESULTS_NOT_READY",
                message=f"Layout results not ready. Current status: {project['status']}",
                details={"progress": project["progress"]},
            ).model_dump(mode="json"),
        )

    if project_id not in layout_results_db:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorResponse(
                error_code="RESULTS_MISSING",
                message="Layout results are missing",
            ).model_dump(mode="json"),
        )

    layout_results = layout_results_db[project_id]

    # Get property boundary and bounds from project metadata
    property_boundary_coords = project.get("property_boundary", [])
    bounds_data = project.get("bounds", {})

    # Convert LayoutResults to LayoutAlternative
    # Calculate total road length
    total_road_length = sum(segment.length for segment in layout_results.road_network)

    # Create road network structure
    road_network = RoadNetwork(
        segments=layout_results.road_network,
        total_length=total_road_length,
        intersections=[],  # TODO: Calculate intersections
    )

    # Detect constraint violations
    from entmoot.models.project import ConstraintViolation
    from shapely.geometry import Polygon as ShapelyPolygon, Point

    violations = []

    # Check each asset for violations
    for i, asset in enumerate(layout_results.placed_assets):
        asset_id = asset.id

        # Create polygon for this asset (using simple rectangle approximation)
        # Convert feet to degrees (approximate)
        lat_per_foot = 1 / 364000
        lng_per_foot = 1 / 288200

        half_width = (asset.width / 2) * lng_per_foot
        half_length = (asset.length / 2) * lat_per_foot

        # Rotate corners based on asset rotation
        import math
        rot_rad = (asset.rotation * math.pi) / 180
        cos_r = math.cos(rot_rad)
        sin_r = math.sin(rot_rad)

        corners = [
            (-half_width, -half_length),
            (half_width, -half_length),
            (half_width, half_length),
            (-half_width, half_length),
        ]

        rotated_corners = []
        for x, y in corners:
            rot_x = x * cos_r - y * sin_r
            rot_y = x * sin_r + y * cos_r
            rotated_corners.append((
                asset.position.longitude + rot_x,
                asset.position.latitude + rot_y
            ))

        asset_poly = ShapelyPolygon(rotated_corners)

        # Check overlap with other assets
        for j, other_asset in enumerate(layout_results.placed_assets):
            if i >= j:  # Skip self and already checked pairs
                continue

            # Create polygon for other asset
            other_half_width = (other_asset.width / 2) * lng_per_foot
            other_half_length = (other_asset.length / 2) * lat_per_foot

            other_rot_rad = (other_asset.rotation * math.pi) / 180
            other_cos = math.cos(other_rot_rad)
            other_sin = math.sin(other_rot_rad)

            other_corners = []
            for x, y in [(-other_half_width, -other_half_length),
                         (other_half_width, -other_half_length),
                         (other_half_width, other_half_length),
                         (-other_half_width, other_half_length)]:
                rot_x = x * other_cos - y * other_sin
                rot_y = x * other_sin + y * other_cos
                other_corners.append((
                    other_asset.position.longitude + rot_x,
                    other_asset.position.latitude + rot_y
                ))

            other_poly = ShapelyPolygon(other_corners)

            # Check for intersection
            if asset_poly.intersects(other_poly):
                overlap_area = asset_poly.intersection(other_poly).area
                # Convert area to square feet (approximate)
                overlap_sqft = overlap_area / (lat_per_foot * lng_per_foot)

                violations.append(ConstraintViolation(
                    asset_id=asset_id,
                    constraint_type="setback",
                    severity="error",
                    message=f"Asset overlaps with another asset (overlap: {overlap_sqft:.0f} sq ft)"
                ))

        # Check if asset is within site boundary
        if property_boundary_coords:
            try:
                boundary_poly = ShapelyPolygon([(p["longitude"], p["latitude"]) for p in property_boundary_coords])
                if not boundary_poly.contains(asset_poly):
                    # Check how much is outside
                    if asset_poly.intersects(boundary_poly):
                        outside_area = asset_poly.difference(boundary_poly).area
                        outside_sqft = outside_area / (lat_per_foot * lng_per_foot)
                        violations.append(ConstraintViolation(
                            asset_id=asset_id,
                            constraint_type="property_line",
                            severity="error",
                            message=f"Asset extends {outside_sqft:.0f} sq ft beyond property boundary"
                        ))
                    else:
                        violations.append(ConstraintViolation(
                            asset_id=asset_id,
                            constraint_type="property_line",
                            severity="error",
                            message="Asset is completely outside property boundary"
                        ))
            except Exception as e:
                logger.warning(f"Could not check boundary violation: {e}")

    logger.info(f"Detected {len(violations)} constraint violations")

    # Create metrics
    # Calculate cost breakdown components
    earthwork_cost = layout_results.earthwork.estimated_cost
    road_cost = total_road_length * 100  # Rough estimate: $100/ft

    # Calculate asset construction cost by subtracting known costs from total
    # Total cost = earthwork + roads + assets + contingency (10%)
    # So: assets = (total / 1.1) - earthwork - roads
    base_cost = layout_results.total_cost / 1.1  # Remove contingency to get base
    asset_cost = max(0.0, base_cost - earthwork_cost - road_cost)
    contingency_cost = layout_results.total_cost * 0.1

    metrics = LayoutMetrics(
        property_area=project.get("property_area", 0.0),
        buildable_area=project.get("buildable_area", 0.0),
        buildable_percentage=layout_results.buildable_area_used,
        assets_placed=len(layout_results.placed_assets),
        total_road_length=total_road_length,
        earthwork_volumes=EarthworkVolumes(
            cut=layout_results.earthwork.total_cut_volume,
            fill=layout_results.earthwork.total_fill_volume,
            net=layout_results.earthwork.net_volume,
            balance_ratio=(
                layout_results.earthwork.total_cut_volume / layout_results.earthwork.total_fill_volume
                if layout_results.earthwork.total_fill_volume > 0
                else 0.0
            ),
        ),
        estimated_cost=CostBreakdown(
            earthwork=earthwork_cost,
            roads=road_cost,
            utilities=asset_cost,  # Use utilities field for asset construction cost
            drainage=0.0,
            landscaping=0.0,
            contingency=contingency_cost,
            total=layout_results.total_cost,
        ),
        constraint_violations=0 if layout_results.constraints_satisfied else 1,
        optimization_score=layout_results.fitness_score * 100,  # Convert 0-1 to 0-100
    )

    # Create the alternative
    alternative = LayoutAlternative(
        id="alt-1",
        name="Optimized Layout",
        description="AI-generated optimized site layout",
        metrics=metrics,
        assets=layout_results.placed_assets,
        road_network=road_network,
        constraint_zones=[],  # TODO: Extract from optimization
        buildable_areas=[],  # TODO: Extract from terrain analysis
        earthwork_zones=[],
        violations=violations,
        created_at=project.get("created_at", datetime.utcnow().isoformat()),
    )

    # Create complete results
    return OptimizationResults(
        project_id=project_id,
        project_name=project.get("project_name", "Unnamed Project"),
        property_boundary=property_boundary_coords,
        bounds=Bounds(**bounds_data) if bounds_data else Bounds(north=0, south=0, east=0, west=0),
        alternatives=[alternative],
        selected_alternative_id="alt-1",
        created_at=project.get("created_at", datetime.utcnow().isoformat()),
        updated_at=project.get("updated_at", datetime.utcnow().isoformat()),
    )


async def generate_layout_async(
    project_id: str,
    config: ProjectConfig,
    current_assets: Optional[List[Dict]] = None
) -> None:
    """
    Background task to generate site layout using the optimization engine.

    Args:
        project_id: Project identifier
        current_assets: Optional list of current asset placements to use as seed
        config: Project configuration
    """
    try:
        logger.info(f"Starting layout generation for project {project_id}")

        # Update status to processing
        projects_db[project_id]["status"] = ProjectStatus.PROCESSING
        projects_db[project_id]["progress"] = 0

        # Run the actual optimization in a thread pool to avoid blocking
        # (CPU-intensive work should not run in the async event loop)
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_optimization_sync, project_id, config, current_assets)
            results = await asyncio.get_event_loop().run_in_executor(None, future.result)

        # Store results
        layout_results_db[project_id] = results

        # Update status to completed
        projects_db[project_id]["status"] = ProjectStatus.COMPLETED
        projects_db[project_id]["progress"] = 100
        projects_db[project_id]["updated_at"] = datetime.utcnow().isoformat()

        logger.info(f"Layout generation completed for project {project_id}")

    except Exception as e:
        logger.error(f"Error generating layout for project {project_id}: {e}", exc_info=True)
        projects_db[project_id]["status"] = ProjectStatus.FAILED
        projects_db[project_id]["error"] = str(e)


def run_optimization_sync(
    project_id: str, config: ProjectConfig, current_assets: Optional[List[Dict]] = None
) -> LayoutResults:
    """
    Run the actual optimization engine synchronously.

    This function integrates all components from Waves 2-5:
    - KML parsing (Wave 1)
    - Terrain analysis (Wave 2)
    - Asset placement optimization (Wave 3)
    - Road network generation (Wave 4)
    - Earthwork calculation (Wave 5)

    Args:
        project_id: Project identifier
        config: Project configuration

    Returns:
        LayoutResults with optimized placement

    Raises:
        Exception: If optimization fails
    """
    from uuid import UUID
    import numpy as np
    from shapely.geometry import Polygon as ShapelyPolygon, box

    # Import optimization components
    from entmoot.core.storage import storage_service
    from entmoot.core.parsers.kml_parser import KMLParser
    from entmoot.models.assets import (
        BuildingAsset,
        EquipmentYardAsset,
        ParkingLotAsset,
        StorageTankAsset,
    )
    from entmoot.core.optimization.genetic_algorithm import (
        GeneticOptimizer,
        GeneticAlgorithmConfig,
        InitializationStrategy,
    )
    from entmoot.core.optimization.problem import (
        OptimizationObjective,
        OptimizationConstraints,
        ObjectiveWeights,
    )

    logger.info(f"Running optimization for project {project_id}")

    # Step 1: Load KML file from storage
    logger.info(f"Loading KML file for upload_id: {config.upload_id}")
    upload_id = UUID(config.upload_id)

    # This needs to be called in async context, but we're in sync function
    # For now, use a synchronous approach by directly accessing the file path
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    kml_file_path = loop.run_until_complete(storage_service.get_file_path(upload_id))
    loop.close()

    if not kml_file_path or not kml_file_path.exists():
        raise ValueError(f"KML file not found for upload_id: {config.upload_id}")

    # Step 2: Parse KML file
    logger.info(f"Parsing KML file: {kml_file_path}")
    parser = KMLParser(validate=False)  # Skip validation for speed
    parsed_kml = parser.parse(kml_file_path)

    # Initialize inverse transformer at function scope (will be set if we need CRS transformation)
    inverse_transformer = None

    # Extract property boundary (first polygon)
    property_boundaries = parsed_kml.get_property_boundaries()
    if not property_boundaries or not property_boundaries[0].geometry:
        # Fallback: create a default boundary
        logger.warning("No property boundary found in KML, using default 500x500 ft boundary")
        site_boundary = box(0, 0, 500 * 0.3048, 500 * 0.3048)  # 500x500 feet converted to meters
    else:
        from entmoot.core.crs.detector import detect_crs_from_kml
        from entmoot.core.crs.transformer import CRSTransformer
        from entmoot.core.crs.utm import get_utm_crs_info
        from entmoot.models.crs import CRSInfo
        from shapely.ops import transform as shapely_transform

        raw_boundary = property_boundaries[0].geometry
        logger.info(
            f"Found property boundary with area in source CRS: {raw_boundary.area:.6f} sq degrees"
        )

        # Detect CRS from KML (usually WGS84 EPSG:4326)
        source_crs = detect_crs_from_kml(kml_file_path)
        logger.info(f"Detected CRS: {source_crs.name} (EPSG:{source_crs.epsg})")

        # Extract and store property boundary coordinates (lat/lon)
        # Assuming WGS84 where x=longitude, y=latitude
        property_boundary_latlon = []
        for x, y in raw_boundary.exterior.coords[:-1]:  # Skip last point (duplicate of first)
            property_boundary_latlon.append({"latitude": y, "longitude": x})

        # Calculate bounds from property boundary
        coords_x = [coord["longitude"] for coord in property_boundary_latlon]
        coords_y = [coord["latitude"] for coord in property_boundary_latlon]
        bounds = {
            "north": max(coords_y),
            "south": min(coords_y),
            "east": max(coords_x),
            "west": min(coords_x),
        }

        # Store property boundary and bounds in projects_db
        projects_db[project_id]["property_boundary"] = property_boundary_latlon
        projects_db[project_id]["bounds"] = bounds
        projects_db[project_id]["property_area"] = 0.0  # Will be updated after transformation
        projects_db[project_id]["buildable_area"] = 0.0  # Will be updated after transformation
        logger.info(f"Stored property boundary with {len(property_boundary_latlon)} points and bounds: {bounds}")

        # If it's geographic (lat/lon), transform to UTM for accurate meter-based measurements
        if source_crs.is_geographic:
            # Get center point of boundary
            center_lon, center_lat = raw_boundary.centroid.x, raw_boundary.centroid.y
            logger.info(f"Boundary center: lon={center_lon:.6f}, lat={center_lat:.6f}")

            # Detect appropriate UTM zone
            target_crs = get_utm_crs_info(center_lon, center_lat)
            logger.info(f"Transforming to {target_crs.name} for accurate measurements")

            # Create transformer (forward: WGS84 -> UTM)
            transformer = CRSTransformer(source_crs, target_crs)

            # Create inverse transformer (backward: UTM -> WGS84)
            inverse_transformer = CRSTransformer(target_crs, source_crs)

            # Transform the geometry
            def transform_coords(x, y, z=None):
                """Transform individual coordinates."""
                tx, ty = transformer.transform(x, y)
                return tx, ty

            site_boundary = shapely_transform(transform_coords, raw_boundary)
            boundary_area_sqft = site_boundary.area * 10.7639
            logger.info(
                f"Transformed boundary area: {site_boundary.area:.2f} square meters "
                f"({boundary_area_sqft:.2f} square feet)"
            )

            # Update the property area with accurate measurement
            projects_db[project_id]["property_area"] = boundary_area_sqft
            projects_db[project_id]["buildable_area"] = boundary_area_sqft * 0.75  # Rough estimate: 75% buildable
        else:
            # Already in projected coordinates
            site_boundary = raw_boundary
            logger.info(f"Using boundary as-is (already in projected CRS)")

        # Additional validation: check if area is reasonable
        # Typical site should be at least 10,000 sq ft (929 sq m)
        min_area_sqm = 929  # 10,000 sq ft
        if site_boundary.area < min_area_sqm:
            logger.warning(
                f"Property boundary area ({site_boundary.area:.2f} sqm) is suspiciously small. "
                f"Using default 500x500 ft boundary instead."
            )
            site_boundary = box(0, 0, 500 * 0.3048, 500 * 0.3048)

    # Update progress
    projects_db[project_id]["progress"] = 10

    # Step 3: Create Asset instances from config
    logger.info(f"Creating {len(config.assets)} asset instances")
    assets = []
    for i, asset_config in enumerate(config.assets):
        # Convert dimensions from feet to meters (if needed)
        width_m = asset_config.width * 0.3048  # feet to meters
        length_m = asset_config.length * 0.3048

        # Create multiple instances based on quantity
        for j in range(asset_config.quantity):
            asset_id = f"{asset_config.type.value}_{i}_{j}"

            # Create appropriate asset type
            asset_data = {
                "id": asset_id,
                "name": f"{asset_config.type.value.replace('_', ' ').title()} {j+1}",
                "dimensions": (width_m, length_m),
                "area_sqm": width_m * length_m,
                "position": (0.0, 0.0),  # Will be set by optimizer
                "rotation": 0.0,
            }

            # Add height if provided
            if asset_config.height:
                asset_data["building_height_m"] = asset_config.height * 0.3048

            # Create asset based on type
            if asset_config.type.value == "buildings":
                asset = BuildingAsset(**asset_data)
            elif asset_config.type.value == "equipment_yard":
                asset = EquipmentYardAsset(**asset_data)
            elif asset_config.type.value == "parking_lot":
                # Estimate number of spaces (25 sqm per space)
                num_spaces = max(1, int(asset_data["area_sqm"] / 25))
                asset_data["num_spaces"] = num_spaces
                asset = ParkingLotAsset(**asset_data)
            elif asset_config.type.value == "storage_tanks":
                # Default tank properties
                asset_data["capacity_liters"] = 50000
                asset_data["tank_height_m"] = 5.0
                asset = StorageTankAsset(**asset_data)
            else:
                # Default to building
                asset = BuildingAsset(**asset_data)

            assets.append(asset)

    logger.info(f"Created {len(assets)} total asset instances")

    # Update progress
    projects_db[project_id]["progress"] = 20

    # Step 4: Set up constraints
    logger.info("Setting up optimization constraints")
    constraints = OptimizationConstraints(
        site_boundary=site_boundary,
        buildable_zones=[],  # Will use full site for now
        exclusion_zones=[],
        regulatory_constraints=[],
        min_setback_m=config.constraints.setback_distance * 0.3048,  # feet to meters
        min_asset_spacing_m=config.constraints.min_distance_between_assets * 0.3048,
        max_site_coverage_percent=40.0,  # Default 40%
        require_road_access=True,
        max_total_road_length_m=1000.0,
    )

    # Step 5: Set up optimization objectives
    logger.info("Setting up optimization objectives")
    # Map frontend weights (0-100) to backend weights (0-1, must sum to 1)
    total_weight = (
        config.optimization_weights.cost
        + config.optimization_weights.buildable_area
        + config.optimization_weights.accessibility
        + config.optimization_weights.environmental_impact
        + config.optimization_weights.aesthetics
    )

    objective_weights = ObjectiveWeights(
        cut_fill_weight=config.optimization_weights.cost / 100.0,
        accessibility_weight=config.optimization_weights.accessibility / 100.0,
        road_length_weight=config.optimization_weights.buildable_area / 100.0,
        compactness_weight=config.optimization_weights.aesthetics / 100.0,
        slope_variance_weight=config.optimization_weights.environmental_impact / 100.0,
    )

    objective = OptimizationObjective(
        constraints=constraints,
        weights=objective_weights,
        elevation_data=None,  # Would load DEM data here
        slope_data=None,
        transform=None,
        road_entry_point=(site_boundary.centroid.x, site_boundary.centroid.y),
    )

    # Update progress
    projects_db[project_id]["progress"] = 30

    # Step 6: Run genetic algorithm optimization
    logger.info("Running genetic algorithm optimization")
    ga_config = GeneticAlgorithmConfig(
        population_size=50,  # Larger population for better diversity
        num_generations=150,  # More generations to find valid solutions
        mutation_rate=0.4,  # Higher mutation rate to escape local optima
        crossover_rate=0.7,
        elitism_rate=0.15,  # Keep more elite solutions
        tournament_size=3,
        convergence_threshold=0.001,
        convergence_patience=20,  # More patience before early stopping
        diversity_weight=0.2,
        num_alternatives=3,
        time_limit_seconds=120.0,  # 2 minutes max
    )

    optimizer = GeneticOptimizer(
        objective=objective, constraints=constraints, config=ga_config, random_seed=42
    )

    # Run optimization with progress updates
    def update_progress(generation: int, max_generations: int):
        progress = 30 + int((generation / max_generations) * 50)
        projects_db[project_id]["progress"] = progress

    # If current assets provided, create seed solution from them
    seed_solution = None
    if current_assets:
        try:
            from entmoot.core.optimization.solution import PlacementSolution

            # Create asset objects with current positions/rotations
            seed_assets = []
            for asset_data, asset in zip(current_assets, assets):
                # Clone asset and set position/rotation from current data
                asset_copy = asset.model_copy(deep=True)
                asset_copy.set_position(
                    asset_data.get("position", {}).get("longitude", asset.position[0]),
                    asset_data.get("position", {}).get("latitude", asset.position[1])
                )
                asset_copy.set_rotation(asset_data.get("rotation", 0))
                seed_assets.append(asset_copy)

            seed_solution = PlacementSolution(assets=seed_assets)
            logger.info(f"Using current asset positions as seed solution for optimization")
        except Exception as e:
            logger.warning(f"Failed to create seed solution from current assets: {e}")
            seed_solution = None

    result = optimizer.optimize(
        assets,
        initialization_strategy=InitializationStrategy.RANDOM,
        seed_solution=seed_solution
    )

    logger.info(
        f"Optimization completed: {result.generations_run} generations, "
        f"best fitness: {result.best_solution.fitness:.2f}"
    )

    # Update progress
    projects_db[project_id]["progress"] = 80

    # Step 7: Extract placed assets from best solution
    # Import models for results
    from entmoot.models.project import PlacedAsset, RoadSegment, EarthworkSummary, AssetType, Coordinate
    from entmoot.models.asset import AssetType as OptimizationAssetType

    # Map optimization AssetType to project AssetType
    asset_type_mapping = {
        OptimizationAssetType.BUILDING: AssetType.BUILDINGS,
        OptimizationAssetType.EQUIPMENT_YARD: AssetType.EQUIPMENT_YARD,
        OptimizationAssetType.PARKING: AssetType.PARKING_LOT,
        OptimizationAssetType.UTILITY: AssetType.STORAGE_TANKS,
        # Map other types to BUILDINGS as fallback
        OptimizationAssetType.STRUCTURE: AssetType.BUILDINGS,
        OptimizationAssetType.ROAD: AssetType.BUILDINGS,
        OptimizationAssetType.LANDSCAPE: AssetType.BUILDINGS,
        OptimizationAssetType.CUSTOM: AssetType.BUILDINGS,
    }

    placed_assets = []
    for asset in result.best_solution.assets:
        # Map the asset type from optimization to project enum
        project_asset_type = asset_type_mapping.get(asset.asset_type, AssetType.BUILDINGS)

        # Transform UTM coordinates back to WGS84 lat/lon
        if inverse_transformer:
            lon, lat = inverse_transformer.transform(asset.position[0], asset.position[1])
            logger.debug(f"Transformed asset position: UTM({asset.position[0]:.2f}, {asset.position[1]:.2f}) -> WGS84({lon:.6f}, {lat:.6f})")
        else:
            # No transformation needed (already in geographic coordinates)
            lon, lat = asset.position[0], asset.position[1]
            logger.warning(f"No inverse transformer available! Using coordinates as-is: ({lon}, {lat})")

        placed_asset = PlacedAsset(
            id=asset.id,
            type=project_asset_type,
            position=Coordinate(latitude=lat, longitude=lon),
            rotation=asset.rotation,
            width=asset.dimensions[0] * 3.28084,  # Convert back to feet
            length=asset.dimensions[1] * 3.28084,
            height=getattr(asset, "building_height_m", None) * 3.28084
            if hasattr(asset, "building_height_m")
            else None,
            polygon=[],  # TODO: Calculate actual footprint corners
        )
        placed_assets.append(placed_asset)

    # Update progress
    projects_db[project_id]["progress"] = 90

    # Step 8: Generate road network (simplified for now)
    logger.info("Generating road network")
    # For now, create a simple road network connecting assets to site entrance
    road_segments = []
    entrance_pos = (site_boundary.centroid.x, site_boundary.centroid.y)

    for i, asset in enumerate(result.best_solution.assets):
        # Transform entrance position to lat/lon
        if inverse_transformer:
            entrance_lon, entrance_lat = inverse_transformer.transform(entrance_pos[0], entrance_pos[1])
            asset_lon, asset_lat = inverse_transformer.transform(asset.position[0], asset.position[1])
        else:
            entrance_lon, entrance_lat = entrance_pos[0], entrance_pos[1]
            asset_lon, asset_lat = asset.position[0], asset.position[1]

        # Calculate road length (approximate, in feet)
        import math
        dx_m = asset.position[0] - entrance_pos[0]
        dy_m = asset.position[1] - entrance_pos[1]
        length_m = math.sqrt(dx_m**2 + dy_m**2)
        length_ft = length_m * 3.28084

        segment = RoadSegment(
            id=f"road_{i}",
            points=[
                Coordinate(latitude=entrance_lat, longitude=entrance_lon),
                Coordinate(latitude=asset_lat, longitude=asset_lon),
            ],
            width=config.road_design.min_width,
            grade=0.0,  # Would calculate from DEM
            surface_type=config.road_design.surface_type,
            length=length_ft,
        )
        road_segments.append(segment)

    # Step 9: Calculate earthwork (simplified)
    logger.info("Calculating earthwork")
    # For now, use simplified estimates
    total_cut = sum(a.area_sqm * 0.5 for a in result.best_solution.assets)  # 0.5m avg cut
    total_fill = sum(a.area_sqm * 0.3 for a in result.best_solution.assets)  # 0.3m avg fill

    # Convert to cubic yards
    total_cut_cy = total_cut * 1.30795  # m³ to cy
    total_fill_cy = total_fill * 1.30795

    earthwork = EarthworkSummary(
        total_cut_volume=total_cut_cy,
        total_fill_volume=total_fill_cy,
        net_volume=total_cut_cy - total_fill_cy,
        estimated_cost=total_cut_cy * 15.0 + total_fill_cy * 12.0,  # $15/cy cut, $12/cy fill
    )

    # Step 10: Calculate total cost
    logger.info("Calculating total project cost")
    # Simplified cost calculation
    road_cost = len(road_segments) * 100 * 50  # $50/linear foot
    asset_cost = sum(a.area_sqm * 500 for a in result.best_solution.assets)  # $500/sqm
    total_cost = earthwork.estimated_cost + road_cost + asset_cost

    # Step 11: Calculate buildable area usage
    total_asset_area = sum(a.area_sqm for a in result.best_solution.assets)
    buildable_area_used = (total_asset_area / (site_boundary.area * 0.092903)) * 100  # % used

    # Step 12: Create final results
    results = LayoutResults(
        project_id=project_id,
        placed_assets=placed_assets,
        road_network=road_segments,
        earthwork=earthwork,
        total_cost=total_cost,
        buildable_area_used=buildable_area_used,
        constraints_satisfied=result.best_solution.is_valid,
        fitness_score=result.best_solution.fitness / 100.0,  # Normalize to 0-1
        alternatives=[],  # Could include alternative solutions
    )

    logger.info(
        f"Optimization complete: {len(placed_assets)} assets placed, "
        f"fitness: {results.fitness_score:.2f}, cost: ${total_cost:,.2f}"
    )

    return results
