"""
Optimization service — layout generation and genetic algorithm orchestration.

Extracted from api/projects.py to keep route handlers thin.
"""

import asyncio
import concurrent.futures
import json
import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import numpy as np
from shapely.geometry import box, shape

from entmoot.core.redis_storage import get_storage
from entmoot.models.project import (
    AssetType,
    Coordinate,
    EarthworkSummary,
    LayoutResults,
    PlacedAsset,
    ProjectConfig,
    ProjectStatus,
    RoadSegment,
)

logger = logging.getLogger(__name__)

storage = get_storage()


async def generate_layout_async(
    project_id: str,
    config: ProjectConfig,
    current_assets: Optional[List[Dict]] = None,
) -> None:
    """
    Background task to generate site layout using the optimization engine.

    Args:
        project_id: Project identifier
        config: Project configuration
        current_assets: Optional list of current asset placements to use as seed
    """
    try:
        logger.info(f"Starting layout generation for project {project_id}")

        project = storage.get_project(project_id)
        if project:
            project["status"] = ProjectStatus.PROCESSING
            project["progress"] = 0
            storage.set_project(project_id, project)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_optimization_sync, project_id, config, current_assets)
            results = await asyncio.get_event_loop().run_in_executor(None, future.result)

        storage.set_results(project_id, results.model_dump())

        project = storage.get_project(project_id)
        if project:
            project["status"] = ProjectStatus.COMPLETED
            project["progress"] = 100
            project["updated_at"] = datetime.utcnow().isoformat()
            storage.set_project(project_id, project)

        logger.info(f"Layout generation completed for project {project_id}")

    except Exception as e:
        logger.error(f"Error generating layout for project {project_id}: {e}", exc_info=True)
        project = storage.get_project(project_id)
        if project:
            project["status"] = ProjectStatus.FAILED
            project["error"] = str(e)
            storage.set_project(project_id, project)


def run_optimization_sync(  # noqa: C901
    project_id: str,
    config: ProjectConfig,
    current_assets: Optional[List[Dict]] = None,
) -> LayoutResults:
    """
    Run the actual optimization engine synchronously.

    Integrates all components:
    - KML / KMZ / GeoJSON parsing
    - CRS transformation
    - Asset placement optimization (genetic algorithm)
    - Road network generation
    - Earthwork calculation

    Args:
        project_id: Project identifier
        config: Project configuration
        current_assets: Optional current asset positions as seed

    Returns:
        LayoutResults with optimized placement

    Raises:
        Exception: If optimization fails
    """
    from entmoot.core.optimization.genetic_algorithm import (
        GeneticAlgorithmConfig,
        GeneticOptimizer,
        InitializationStrategy,
    )
    from entmoot.core.optimization.problem import (
        ObjectiveWeights,
        OptimizationConstraints,
        OptimizationObjective,
    )
    from entmoot.core.parsers.kml_parser import KMLParser
    from entmoot.core.storage import storage_service
    from entmoot.models.assets import (
        Asset,
        BuildingAsset,
        EquipmentYardAsset,
        ParkingLotAsset,
        StorageTankAsset,
    )

    logger.info(f"Running optimization for project {project_id}")

    # ------------------------------------------------------------------
    # Step 1: Load file from storage
    # ------------------------------------------------------------------
    logger.info(f"Loading file for upload_id: {config.upload_id}")
    upload_id = UUID(config.upload_id)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    kml_file_path = loop.run_until_complete(storage_service.get_file_path(upload_id))
    loop.close()

    if not kml_file_path or not kml_file_path.exists():
        raise ValueError(f"File not found for upload_id: {config.upload_id}")

    # ------------------------------------------------------------------
    # Step 2: Parse uploaded file (KML, KMZ, or GeoJSON)
    # ------------------------------------------------------------------
    file_extension = kml_file_path.suffix.lower()
    logger.info(f"Parsing file: {kml_file_path} (extension: {file_extension})")

    site_boundary = None
    raw_boundary = None

    if file_extension in [".geojson", ".json"]:
        logger.info("Using GeoJSON parser")
        with open(kml_file_path, "r") as f:
            geojson_data = json.load(f)

        polygons: List[Any] = []
        if geojson_data.get("type") == "FeatureCollection":
            for feature in geojson_data.get("features", []):
                geom = feature.get("geometry", {})
                if geom.get("type") == "Polygon":
                    polygons.append(shape(geom))
                elif geom.get("type") == "MultiPolygon":
                    multi = shape(geom)
                    polygons.extend(list(multi.geoms))
        elif geojson_data.get("type") == "Feature":
            geom = geojson_data.get("geometry", {})
            if geom.get("type") == "Polygon":
                polygons.append(shape(geom))
        elif geojson_data.get("type") == "Polygon":
            polygons.append(shape(geojson_data))

        if polygons:
            raw_boundary = polygons[0]
            logger.info(f"Found {len(polygons)} polygon(s) in GeoJSON, using first as boundary")
        else:
            logger.warning("No polygons found in GeoJSON")
    else:
        is_kmz = file_extension == ".kmz"

        if not is_kmz:
            try:
                with open(kml_file_path, "rb") as fb:
                    header = fb.read(2)
                    if header == b"PK":
                        logger.info("File has ZIP signature (PK), treating as KMZ")
                        is_kmz = True
            except Exception as e:
                logger.warning(f"Could not check file signature: {e}")

        if is_kmz:
            from entmoot.core.parsers.kmz_parser import KMZParser

            logger.info("Using KMZParser for KMZ file")
            kmz_parser = KMZParser(validate=False)
            parsed_kml = kmz_parser.parse(kml_file_path)
        else:
            logger.info("Using KMLParser for KML file")
            kml_parser = KMLParser(validate=False)
            parsed_kml = kml_parser.parse(kml_file_path)
        property_boundaries = parsed_kml.get_property_boundaries()
        if property_boundaries and property_boundaries[0].geometry:
            raw_boundary = property_boundaries[0].geometry

    # ------------------------------------------------------------------
    # Step 2b: CRS transformation
    # ------------------------------------------------------------------
    inverse_transformer = None

    if not raw_boundary:
        logger.warning("No property boundary found in file, using default 500x500 ft boundary")
        site_boundary = box(0, 0, 500 * 0.3048, 500 * 0.3048)
    else:
        from shapely.ops import transform as shapely_transform

        from entmoot.core.crs.detector import detect_crs_from_geojson, detect_crs_from_kml
        from entmoot.core.crs.transformer import CRSTransformer
        from entmoot.core.crs.utm import get_utm_crs_info

        logger.info(
            f"Found property boundary with area in source CRS: "
            f"{raw_boundary.area:.6f} sq degrees"
        )

        if file_extension in [".geojson", ".json"]:
            source_crs = detect_crs_from_geojson(kml_file_path)
        else:
            source_crs = detect_crs_from_kml(kml_file_path)
        logger.info(f"Detected CRS: {source_crs.name} (EPSG:{source_crs.epsg})")

        # Store boundary coordinates (lat/lon)
        property_boundary_latlon = []
        for x, y in raw_boundary.exterior.coords[:-1]:
            property_boundary_latlon.append({"latitude": y, "longitude": x})

        coords_x = [c["longitude"] for c in property_boundary_latlon]
        coords_y = [c["latitude"] for c in property_boundary_latlon]
        bounds = {
            "north": max(coords_y),
            "south": min(coords_y),
            "east": max(coords_x),
            "west": min(coords_x),
        }

        project = storage.get_project(project_id)
        if project:
            project["property_boundary"] = property_boundary_latlon
            project["bounds"] = bounds
            project["property_area"] = 0.0
            project["buildable_area"] = 0.0
            storage.set_project(project_id, project)
        logger.info(
            f"Stored property boundary with {len(property_boundary_latlon)} points "
            f"and bounds: {bounds}"
        )

        if source_crs.is_geographic:
            center_lon, center_lat = (
                raw_boundary.centroid.x,
                raw_boundary.centroid.y,
            )
            logger.info(f"Boundary center: lon={center_lon:.6f}, lat={center_lat:.6f}")

            target_crs = get_utm_crs_info(center_lon, center_lat)
            logger.info(f"Transforming to {target_crs.name} for accurate measurements")

            transformer = CRSTransformer(source_crs, target_crs)
            inverse_transformer = CRSTransformer(target_crs, source_crs)

            def transform_coords(x: Any, y: Any, z: Any = None) -> tuple:
                tx, ty = transformer.transform(x, y)
                return tx, ty

            site_boundary = shapely_transform(transform_coords, raw_boundary)
            boundary_area_sqft = site_boundary.area * 10.7639
            logger.info(
                f"Transformed boundary area: {site_boundary.area:.2f} square meters "
                f"({boundary_area_sqft:.2f} square feet)"
            )

            project = storage.get_project(project_id)
            if project:
                project["property_area"] = boundary_area_sqft
                project["buildable_area"] = boundary_area_sqft * 0.75
                storage.set_project(project_id, project)
        else:
            site_boundary = raw_boundary
            logger.info("Using boundary as-is (already in projected CRS)")

        min_area_sqm = 929  # ~10,000 sq ft
        if site_boundary.area < min_area_sqm:
            logger.warning(
                f"Property boundary area ({site_boundary.area:.2f} sqm) is "
                f"suspiciously small. Using default 500x500 ft boundary instead."
            )
            site_boundary = box(0, 0, 500 * 0.3048, 500 * 0.3048)

    # ------------------------------------------------------------------
    # Step 2c: Load DEM if provided
    # ------------------------------------------------------------------
    terrain_data = None
    target_crs_epsg = None

    if hasattr(config, "dem_upload_id") and config.dem_upload_id:
        try:
            from entmoot.services.terrain_service import prepare_terrain_data

            logger.info(f"Loading DEM for dem_upload_id: {config.dem_upload_id}")
            dem_upload_id = UUID(config.dem_upload_id)

            dem_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(dem_loop)
            dem_file_path = dem_loop.run_until_complete(
                storage_service.get_file_path(dem_upload_id)
            )
            dem_loop.close()

            if dem_file_path and dem_file_path.exists():
                # Determine target CRS EPSG
                if "target_crs" in dir() and hasattr(target_crs, "to_epsg"):
                    target_crs_epsg = target_crs.to_epsg()
                else:
                    # Fallback: derive from boundary centroid in lon/lat
                    from entmoot.core.crs.utm import get_utm_crs_info

                    if raw_boundary:
                        # raw_boundary is in geographic (lon/lat) coordinates
                        cx, cy = raw_boundary.centroid.x, raw_boundary.centroid.y
                    else:
                        # site_boundary may be in projected coords; not suitable
                        # for get_utm_crs_info which expects lon/lat
                        cx, cy = site_boundary.centroid.x, site_boundary.centroid.y
                    tc = get_utm_crs_info(cx, cy)
                    target_crs_epsg = tc.epsg

                if target_crs_epsg is not None:
                    terrain_data = prepare_terrain_data(
                        dem_file_path, site_boundary, target_crs_epsg
                    )
                    logger.info("Terrain data loaded successfully")
                else:
                    logger.warning("Could not determine target CRS EPSG, skipping DEM")
            else:
                logger.warning(f"DEM file not found for dem_upload_id: {config.dem_upload_id}")
        except Exception as e:
            logger.warning(f"Failed to load DEM, continuing without terrain data: {e}")
            terrain_data = None

    # ------------------------------------------------------------------
    # Step 2d: Fetch existing conditions from OpenStreetMap
    # ------------------------------------------------------------------
    existing_conditions_zones: list = []
    existing_conditions_display: list = []
    road_entry_override = None

    if (
        config.constraints.use_existing_conditions
        and raw_boundary is not None
        and inverse_transformer is not None
    ):
        try:
            from entmoot.services.existing_conditions_service import ExistingConditionsService

            logger.info("Fetching existing conditions from OpenStreetMap")
            ec_service = ExistingConditionsService()

            ec_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(ec_loop)
            ec_result = ec_loop.run_until_complete(
                ec_service.fetch_and_process(
                    site_boundary_wgs84=raw_boundary,
                    transformer=transformer,
                    inverse_transformer=inverse_transformer,
                    site_boundary_utm=site_boundary,
                )
            )
            ec_loop.close()

            existing_conditions_zones = ec_result.exclusion_zones
            existing_conditions_display = ec_result.display_features
            road_entry_override = ec_result.road_entry_point

            logger.info(
                f"Existing conditions: {ec_result.feature_count} features -> "
                f"{len(existing_conditions_zones)} exclusion zones"
            )

            # Store display features for the API response
            project = storage.get_project(project_id)
            if project:
                project["existing_conditions"] = [
                    z.model_dump() for z in existing_conditions_display
                ]
                storage.set_project(project_id, project)

        except Exception as e:
            logger.warning(f"Failed to fetch existing conditions, continuing without: {e}")

    # Update progress
    _update_progress(project_id, 10)

    # ------------------------------------------------------------------
    # Step 3: Create Asset instances from config
    # ------------------------------------------------------------------
    logger.info(f"Creating {len(config.assets)} asset instances")
    assets: List[Asset] = []
    for i, asset_config in enumerate(config.assets):
        width_m = asset_config.width * 0.3048
        length_m = asset_config.length * 0.3048

        for j in range(asset_config.quantity):
            asset_id = f"{asset_config.type.value}_{i}_{j}"
            asset_data: Dict[str, Any] = {
                "id": asset_id,
                "name": f"{asset_config.type.value.replace('_', ' ').title()} {j + 1}",
                "dimensions": (width_m, length_m),
                "area_sqm": width_m * length_m,
                "position": (0.0, 0.0),
                "rotation": 0.0,
            }

            if asset_config.height:
                asset_data["building_height_m"] = asset_config.height * 0.3048

            created_asset: Asset
            if asset_config.type.value == "buildings":
                created_asset = BuildingAsset(**asset_data)
            elif asset_config.type.value == "equipment_yard":
                created_asset = EquipmentYardAsset(**asset_data)
            elif asset_config.type.value == "parking_lot":
                num_spaces = max(1, int(asset_data["area_sqm"] / 25))
                asset_data["num_spaces"] = num_spaces
                created_asset = ParkingLotAsset(**asset_data)
            elif asset_config.type.value == "storage_tanks":
                asset_data["capacity_liters"] = 50000
                asset_data["tank_height_m"] = 5.0
                created_asset = StorageTankAsset(**asset_data)
            else:
                created_asset = BuildingAsset(**asset_data)

            assets.append(created_asset)

    logger.info(f"Created {len(assets)} total asset instances")

    _update_progress(project_id, 20)

    # ------------------------------------------------------------------
    # Step 4: Set up constraints
    # ------------------------------------------------------------------
    logger.info("Setting up optimization constraints")
    constraints = OptimizationConstraints(
        site_boundary=site_boundary,
        buildable_zones=[],
        exclusion_zones=list(existing_conditions_zones),
        regulatory_constraints=[],
        min_setback_m=config.constraints.setback_distance * 0.3048,
        min_asset_spacing_m=config.constraints.min_distance_between_assets * 0.3048,
        max_site_coverage_percent=40.0,
        require_road_access=True,
        max_total_road_length_m=1000.0,
    )

    # ------------------------------------------------------------------
    # Step 4b: Generate slope exclusion zones from terrain data
    # ------------------------------------------------------------------
    if terrain_data is not None:
        try:
            import rasterio.features
            from shapely.geometry import shape as shapely_shape

            slope_limit = config.constraints.slope_limit
            steep_mask = (terrain_data.slope_percent > slope_limit).astype(np.uint8)

            if np.any(steep_mask):
                shapes_gen = rasterio.features.shapes(
                    steep_mask, mask=steep_mask == 1, transform=terrain_data.transform
                )
                for geom, _value in shapes_gen:
                    exclusion_poly = shapely_shape(geom)
                    clipped = exclusion_poly.intersection(site_boundary)
                    if not clipped.is_empty and clipped.area > 1.0:
                        if clipped.geom_type == "Polygon":
                            constraints.exclusion_zones.append(clipped)
                        elif clipped.geom_type == "MultiPolygon":
                            for part in clipped.geoms:
                                if part.area > 1.0:
                                    constraints.exclusion_zones.append(part)

                logger.info(
                    f"Added {len(constraints.exclusion_zones)} slope exclusion zones "
                    f"(slope > {slope_limit}%)"
                )
        except Exception as e:
            logger.warning(f"Failed to generate slope exclusion zones: {e}")

    # ------------------------------------------------------------------
    # Step 5: Set up optimization objectives
    # ------------------------------------------------------------------
    logger.info("Setting up optimization objectives")

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
        elevation_data=terrain_data.elevation if terrain_data else None,
        slope_data=terrain_data.slope_percent if terrain_data else None,
        transform=terrain_data.transform if terrain_data else None,
        road_entry_point=(
            road_entry_override
            if road_entry_override is not None
            else (site_boundary.centroid.x, site_boundary.centroid.y)
        ),
        terrain_data=terrain_data,
    )

    _update_progress(project_id, 30)

    # ------------------------------------------------------------------
    # Step 6: Run genetic algorithm
    # ------------------------------------------------------------------
    logger.info("Running genetic algorithm optimization")
    ga_config = GeneticAlgorithmConfig(
        population_size=50,
        num_generations=150,
        mutation_rate=0.4,
        crossover_rate=0.7,
        elitism_rate=0.15,
        tournament_size=3,
        convergence_threshold=0.001,
        convergence_patience=20,
        diversity_weight=0.2,
        num_alternatives=3,
        time_limit_seconds=120.0,
    )

    optimizer = GeneticOptimizer(
        objective=objective,
        constraints=constraints,
        config=ga_config,
        random_seed=42,
    )

    # Build seed solution from current_assets if provided
    seed_solution = None
    if current_assets:
        try:
            from entmoot.core.optimization.solution import PlacementSolution

            seed_assets = []
            for asset_data_item, asset in zip(current_assets, assets):
                asset_copy = asset.model_copy(deep=True)
                asset_copy.set_position(
                    asset_data_item.get("position", {}).get("longitude", asset.position[0]),
                    asset_data_item.get("position", {}).get("latitude", asset.position[1]),
                )
                asset_copy.set_rotation(asset_data_item.get("rotation", 0))
                seed_assets.append(asset_copy)

            seed_solution = PlacementSolution(assets=seed_assets)
            logger.info("Using current asset positions as seed solution for optimization")
        except Exception as e:
            logger.warning(f"Failed to create seed solution from current assets: {e}")
            seed_solution = None

    result = optimizer.optimize(
        assets,
        initialization_strategy=InitializationStrategy.RANDOM,
        seed_solution=seed_solution,
    )

    logger.info(
        f"Optimization completed: {result.generations_run} generations, "
        f"best fitness: {result.best_solution.fitness:.2f}"
    )

    _update_progress(project_id, 80)

    # ------------------------------------------------------------------
    # Step 7: Extract placed assets and resolve polygon TODO
    # ------------------------------------------------------------------
    from entmoot.models.asset import AssetType as OptimizationAssetType

    asset_type_mapping = {
        OptimizationAssetType.BUILDING: AssetType.BUILDINGS,
        OptimizationAssetType.EQUIPMENT_YARD: AssetType.EQUIPMENT_YARD,
        OptimizationAssetType.PARKING: AssetType.PARKING_LOT,
        OptimizationAssetType.UTILITY: AssetType.STORAGE_TANKS,
        OptimizationAssetType.STRUCTURE: AssetType.BUILDINGS,
        OptimizationAssetType.ROAD: AssetType.BUILDINGS,
        OptimizationAssetType.LANDSCAPE: AssetType.BUILDINGS,
        OptimizationAssetType.CUSTOM: AssetType.BUILDINGS,
    }

    placed_assets = []
    for asset in result.best_solution.assets:
        project_asset_type = asset_type_mapping.get(
            asset.asset_type, AssetType.BUILDINGS  # type: ignore[call-overload]
        )

        if inverse_transformer:
            lon, lat = inverse_transformer.transform(asset.position[0], asset.position[1])
            logger.debug(
                f"Transformed asset position: "
                f"UTM({asset.position[0]:.2f}, {asset.position[1]:.2f}) -> "
                f"WGS84({lon:.6f}, {lat:.6f})"
            )
        else:
            lon, lat = asset.position[0], asset.position[1]
            logger.warning(
                f"No inverse transformer available! " f"Using coordinates as-is: ({lon}, {lat})"
            )

        # Compute footprint polygon (resolves TODO: polygon=[])
        footprint_coords = _compute_asset_footprint(asset, lon, lat, inverse_transformer)

        placed_asset = PlacedAsset(
            id=asset.id,
            type=project_asset_type,
            position=Coordinate(latitude=lat, longitude=lon),
            rotation=asset.rotation,
            width=asset.dimensions[0] * 3.28084,
            length=asset.dimensions[1] * 3.28084,
            height=(
                float(getattr(asset, "building_height_m")) * 3.28084
                if getattr(asset, "building_height_m", None) is not None
                else None
            ),
            polygon=footprint_coords,
        )
        placed_assets.append(placed_asset)

    _update_progress(project_id, 90)

    # ------------------------------------------------------------------
    # Step 8: Generate road network
    # ------------------------------------------------------------------
    logger.info("Generating road network")
    road_segments = []
    entrance_pos = (site_boundary.centroid.x, site_boundary.centroid.y)

    for i, asset in enumerate(result.best_solution.assets):
        if inverse_transformer:
            entrance_lon, entrance_lat = inverse_transformer.transform(
                entrance_pos[0], entrance_pos[1]
            )
            asset_lon, asset_lat = inverse_transformer.transform(
                asset.position[0], asset.position[1]
            )
        else:
            entrance_lon, entrance_lat = entrance_pos[0], entrance_pos[1]
            asset_lon, asset_lat = asset.position[0], asset.position[1]

        dx_m = asset.position[0] - entrance_pos[0]
        dy_m = asset.position[1] - entrance_pos[1]
        length_m = math.sqrt(dx_m**2 + dy_m**2)
        length_ft = length_m * 3.28084

        # Compute road grade from real elevation if terrain data is available
        road_grade = 0.0
        if terrain_data and length_m > 0:
            elev_start = terrain_data.sample_elevation(entrance_pos[0], entrance_pos[1])
            elev_end = terrain_data.sample_elevation(asset.position[0], asset.position[1])
            if elev_start is not None and elev_end is not None:
                road_grade = abs(elev_end - elev_start) / length_m * 100.0

        segment = RoadSegment(
            id=f"road_{i}",
            points=[
                Coordinate(latitude=entrance_lat, longitude=entrance_lon),
                Coordinate(latitude=asset_lat, longitude=asset_lon),
            ],
            width=config.road_design.min_width,
            grade=round(road_grade, 2),
            surface_type=config.road_design.surface_type,
            length=length_ft,
        )
        road_segments.append(segment)

    # ------------------------------------------------------------------
    # Step 9: Calculate earthwork
    # ------------------------------------------------------------------
    logger.info("Calculating earthwork")

    if terrain_data:
        # Real earthwork: sample elevation under each asset footprint, compute cut/fill
        # against median target elevation
        total_cut_m3 = 0.0
        total_fill_m3 = 0.0
        for asset in result.best_solution.assets:
            footprint = asset.get_geometry()
            elevations = terrain_data.get_elevation_under_footprint(footprint)
            if len(elevations) > 0:
                target_elev = float(np.median(elevations))
                cuts = elevations[elevations > target_elev] - target_elev
                fills = target_elev - elevations[elevations < target_elev]
                pixel_area = terrain_data.cell_size**2
                total_cut_m3 += float(np.sum(cuts)) * pixel_area
                total_fill_m3 += float(np.sum(fills)) * pixel_area
            else:
                # Fallback for assets outside DEM extent
                total_cut_m3 += asset.area_sqm * 0.5
                total_fill_m3 += asset.area_sqm * 0.3
    else:
        total_cut_m3 = sum(a.area_sqm * 0.5 for a in result.best_solution.assets)
        total_fill_m3 = sum(a.area_sqm * 0.3 for a in result.best_solution.assets)

    total_cut_cy = total_cut_m3 * 1.30795
    total_fill_cy = total_fill_m3 * 1.30795

    earthwork = EarthworkSummary(
        total_cut_volume=total_cut_cy,
        total_fill_volume=total_fill_cy,
        net_volume=total_cut_cy - total_fill_cy,
        estimated_cost=total_cut_cy * 15.0 + total_fill_cy * 12.0,
    )

    # ------------------------------------------------------------------
    # Step 10-12: Cost, buildable area, final results
    # ------------------------------------------------------------------
    logger.info("Calculating total project cost")
    road_cost = len(road_segments) * 100 * 50
    asset_cost = sum(a.area_sqm * 500 for a in result.best_solution.assets)
    total_cost = earthwork.estimated_cost + road_cost + asset_cost

    total_asset_area = sum(a.area_sqm for a in result.best_solution.assets)
    buildable_area_used = (total_asset_area / (site_boundary.area * 0.092903)) * 100

    results = LayoutResults(
        project_id=project_id,
        placed_assets=placed_assets,
        road_network=road_segments,
        earthwork=earthwork,
        total_cost=total_cost,
        buildable_area_used=buildable_area_used,
        constraints_satisfied=result.best_solution.is_valid,
        fitness_score=result.best_solution.fitness / 100.0,
        alternatives=[],
    )

    logger.info(
        f"Optimization complete: {len(placed_assets)} assets placed, "
        f"fitness: {results.fitness_score:.2f}, cost: ${total_cost:,.2f}"
    )

    return results


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _update_progress(project_id: str, progress: int) -> None:
    """Persist progress update for a project."""
    project = storage.get_project(project_id)
    if project:
        project["progress"] = progress
        storage.set_project(project_id, project)


def _compute_asset_footprint(
    asset: Any,
    center_lon: float,
    center_lat: float,
    inverse_transformer: Any,
) -> List[Coordinate]:
    """Compute the WGS84 footprint polygon for an asset.

    Uses the asset's geometry (width/height in meters) and rotation,
    inverse-transforming the corners back to WGS84.
    """
    half_w = asset.dimensions[0] / 2
    half_l = asset.dimensions[1] / 2

    rot_rad = math.radians(asset.rotation)
    cos_r = math.cos(rot_rad)
    sin_r = math.sin(rot_rad)

    local_corners = [
        (-half_w, -half_l),
        (half_w, -half_l),
        (half_w, half_l),
        (-half_w, half_l),
    ]

    coords: List[Coordinate] = []
    for dx, dy in local_corners:
        rx = dx * cos_r - dy * sin_r + asset.position[0]
        ry = dx * sin_r + dy * cos_r + asset.position[1]

        if inverse_transformer:
            clon, clat = inverse_transformer.transform(rx, ry)
        else:
            clon, clat = rx, ry

        coords.append(Coordinate(latitude=clat, longitude=clon))

    return coords
