"""
Tests for asset models.
"""

import pytest
from shapely.geometry import Point as ShapelyPoint

from entmoot.models.assets import (
    Asset,
    AssetType,
    BuildingAsset,
    EquipmentYardAsset,
    ParkingLotAsset,
    StorageTankAsset,
    RotationAngle,
    create_asset_from_dict,
)


class TestAssetBase:
    """Tests for base Asset class."""

    def test_building_asset_creation(self):
        """Test creating a building asset."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office Building",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
            position=(100.0, 100.0),
            rotation=0.0,
        )

        assert asset.id == "bldg_001"
        assert asset.name == "Office Building"
        assert asset.asset_type == AssetType.BUILDING
        assert asset.dimensions == (30.0, 50.0)
        assert asset.area_sqm == 1500.0
        assert asset.position == (100.0, 100.0)
        assert asset.rotation == 0.0

    def test_asset_geometry(self):
        """Test asset geometry generation."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(0.0, 0.0),
            rotation=0.0,
        )

        geom = asset.get_geometry()
        assert geom.is_valid
        assert abs(geom.area - 600.0) < 0.1

    def test_asset_rotation(self):
        """Test asset rotation."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(0.0, 0.0),
            rotation=0.0,
        )

        # Rotate 90 degrees
        asset.set_rotation(90)
        assert asset.rotation == 90

        # Test wrap-around
        asset.set_rotation(370)
        assert asset.rotation == 10

    def test_asset_position_update(self):
        """Test updating asset position."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(0.0, 0.0),
        )

        asset.set_position(100.0, 200.0)
        assert asset.position == (100.0, 200.0)

    def test_asset_setback_geometry(self):
        """Test setback geometry generation."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(0.0, 0.0),
            min_setback_m=5.0,
        )

        setback_geom = asset.get_setback_geometry()
        base_geom = asset.get_geometry()

        assert setback_geom.area > base_geom.area
        assert setback_geom.contains(base_geom)

    def test_asset_intersection(self):
        """Test intersection detection."""
        asset1 = BuildingAsset(
            id="bldg_001",
            name="Office 1",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(0.0, 0.0),
        )

        asset2 = BuildingAsset(
            id="bldg_002",
            name="Office 2",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(10.0, 10.0),
        )

        # Should intersect
        assert asset1.intersects(asset2.get_geometry())

    def test_asset_contains_point(self):
        """Test point containment."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(20.0, 30.0),
            area_sqm=600.0,
            position=(0.0, 0.0),
        )

        # Point inside
        assert asset.contains_point(ShapelyPoint(0.0, 0.0))

        # Point outside
        assert not asset.contains_point(ShapelyPoint(100.0, 100.0))

    def test_dimension_validation(self):
        """Test dimension validation."""
        with pytest.raises(ValueError, match="Dimensions must be positive"):
            BuildingAsset(
                id="bldg_001",
                name="Office",
                dimensions=(-20.0, 30.0),
                area_sqm=600.0,
            )

    def test_area_dimension_mismatch(self):
        """Test area validation against dimensions."""
        with pytest.raises(ValueError, match="Area.*does not match dimensions"):
            BuildingAsset(
                id="bldg_001",
                name="Office",
                dimensions=(20.0, 30.0),
                area_sqm=1000.0,  # Wrong area
            )


class TestBuildingAsset:
    """Tests for BuildingAsset."""

    def test_building_defaults(self):
        """Test building asset defaults."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
        )

        assert asset.asset_type == AssetType.BUILDING
        assert asset.max_slope_percent == 5.0  # Buildings need flat ground
        assert asset.num_stories == 1
        assert asset.foundation_type == "slab"

    def test_building_constraint_validation(self):
        """Test building constraint validation."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
            num_stories=2,
            building_height_m=7.0,
        )

        is_valid, errors = asset.validate_constraints()
        assert is_valid
        assert len(errors) == 0

    def test_building_height_validation(self):
        """Test building height vs stories validation."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
            num_stories=3,
            building_height_m=5.0,  # Too short for 3 stories
        )

        is_valid, errors = asset.validate_constraints()
        assert not is_valid
        assert any("height" in err.lower() for err in errors)

    def test_building_to_geojson(self):
        """Test building GeoJSON export."""
        asset = BuildingAsset(
            id="bldg_001",
            name="Office Building",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
            position=(100.0, 100.0),
        )

        geojson = asset.to_geojson()
        assert geojson["type"] == "Feature"
        assert geojson["geometry"]["type"] == "Polygon"
        assert geojson["properties"]["id"] == "bldg_001"
        assert geojson["properties"]["asset_type"] == "building"


class TestEquipmentYardAsset:
    """Tests for EquipmentYardAsset."""

    def test_equipment_yard_defaults(self):
        """Test equipment yard defaults."""
        asset = EquipmentYardAsset(
            id="yard_001",
            name="Storage Yard",
            dimensions=(40.0, 60.0),
            area_sqm=2400.0,
        )

        assert asset.asset_type == AssetType.EQUIPMENT_YARD
        assert asset.max_slope_percent == 10.0  # More tolerant than buildings
        assert asset.surface_type == "gravel"
        assert asset.fenced is True

    def test_equipment_yard_validation(self):
        """Test equipment yard validation."""
        asset = EquipmentYardAsset(
            id="yard_001",
            name="Storage Yard",
            dimensions=(40.0, 60.0),
            area_sqm=2400.0,
        )

        is_valid, errors = asset.validate_constraints()
        assert is_valid

    def test_equipment_yard_small_area(self):
        """Test validation of small equipment yard."""
        asset = EquipmentYardAsset(
            id="yard_001",
            name="Storage Yard",
            dimensions=(5.0, 10.0),
            area_sqm=50.0,  # Too small
        )

        is_valid, errors = asset.validate_constraints()
        assert not is_valid
        assert any("too small" in err.lower() for err in errors)


class TestParkingLotAsset:
    """Tests for ParkingLotAsset."""

    def test_parking_lot_defaults(self):
        """Test parking lot defaults."""
        asset = ParkingLotAsset(
            id="parking_001",
            name="Main Parking",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
            num_spaces=60,
        )

        assert asset.asset_type == AssetType.PARKING_LOT
        assert asset.max_slope_percent == 5.0  # Parking needs flat ground
        assert asset.surface_type == "asphalt"
        assert asset.ada_compliant is True

    def test_parking_lot_validation(self):
        """Test parking lot validation."""
        asset = ParkingLotAsset(
            id="parking_001",
            name="Main Parking",
            dimensions=(30.0, 50.0),
            area_sqm=1500.0,
            num_spaces=60,
            metadata={"accessible_spaces": 3},  # ADA compliant
        )

        is_valid, errors = asset.validate_constraints()
        assert is_valid

    def test_parking_lot_insufficient_area(self):
        """Test validation of parking lot with insufficient area."""
        asset = ParkingLotAsset(
            id="parking_001",
            name="Main Parking",
            dimensions=(10.0, 10.0),
            area_sqm=100.0,
            num_spaces=100,  # Too many spaces for area
        )

        is_valid, errors = asset.validate_constraints()
        assert not is_valid
        assert any("insufficient" in err.lower() for err in errors)


class TestStorageTankAsset:
    """Tests for StorageTankAsset."""

    def test_storage_tank_defaults(self):
        """Test storage tank defaults."""
        asset = StorageTankAsset(
            id="tank_001",
            name="Fuel Tank",
            dimensions=(10.0, 10.0),
            area_sqm=100.0,
            capacity_liters=50000,
            tank_height_m=5.0,
        )

        assert asset.asset_type == AssetType.STORAGE_TANK
        assert asset.max_slope_percent == 5.0  # Tanks need flat ground
        assert asset.min_setback_m == 15.0  # Larger setback for safety
        assert asset.tank_type == "fuel"
        assert asset.containment_required is True

    def test_storage_tank_validation(self):
        """Test storage tank validation."""
        asset = StorageTankAsset(
            id="tank_001",
            name="Fuel Tank",
            dimensions=(10.0, 10.0),
            area_sqm=100.0,
            capacity_liters=50000,
            tank_height_m=5.0,
            containment_required=True,
        )

        is_valid, errors = asset.validate_constraints()
        # Will have error about missing containment area
        assert not is_valid
        assert any("containment" in err.lower() for err in errors)

    def test_storage_tank_with_containment(self):
        """Test storage tank with containment metadata."""
        asset = StorageTankAsset(
            id="tank_001",
            name="Fuel Tank",
            dimensions=(10.0, 10.0),
            area_sqm=100.0,
            capacity_liters=50000,
            tank_height_m=5.0,
            containment_required=True,
            metadata={"containment_area_sqm": 110.0},
        )

        is_valid, errors = asset.validate_constraints()
        assert is_valid


class TestAssetFactory:
    """Tests for asset factory function."""

    def test_create_building_from_dict(self):
        """Test creating building from dictionary."""
        asset_data = {
            "id": "bldg_001",
            "name": "Office",
            "asset_type": "building",
            "dimensions": (30.0, 50.0),
            "area_sqm": 1500.0,
        }

        asset = create_asset_from_dict(asset_data)
        assert isinstance(asset, BuildingAsset)
        assert asset.id == "bldg_001"

    def test_create_equipment_yard_from_dict(self):
        """Test creating equipment yard from dictionary."""
        asset_data = {
            "id": "yard_001",
            "name": "Storage",
            "asset_type": "equipment_yard",
            "dimensions": (40.0, 60.0),
            "area_sqm": 2400.0,
        }

        asset = create_asset_from_dict(asset_data)
        assert isinstance(asset, EquipmentYardAsset)

    def test_create_parking_lot_from_dict(self):
        """Test creating parking lot from dictionary."""
        asset_data = {
            "id": "parking_001",
            "name": "Main Parking",
            "asset_type": "parking_lot",
            "dimensions": (30.0, 50.0),
            "area_sqm": 1500.0,
            "num_spaces": 60,
        }

        asset = create_asset_from_dict(asset_data)
        assert isinstance(asset, ParkingLotAsset)

    def test_create_storage_tank_from_dict(self):
        """Test creating storage tank from dictionary."""
        asset_data = {
            "id": "tank_001",
            "name": "Fuel Tank",
            "asset_type": "storage_tank",
            "dimensions": (10.0, 10.0),
            "area_sqm": 100.0,
            "capacity_liters": 50000,
            "tank_height_m": 5.0,
        }

        asset = create_asset_from_dict(asset_data)
        assert isinstance(asset, StorageTankAsset)

    def test_create_asset_invalid_type(self):
        """Test creating asset with invalid type."""
        asset_data = {
            "id": "asset_001",
            "name": "Unknown",
            "asset_type": "invalid_type",
            "dimensions": (10.0, 10.0),
            "area_sqm": 100.0,
        }

        with pytest.raises(ValueError, match="Unknown asset type"):
            create_asset_from_dict(asset_data)


class TestRotationAngle:
    """Tests for rotation angle enum."""

    def test_rotation_angles(self):
        """Test standard rotation angles."""
        assert RotationAngle.NORTH == 0.0
        assert RotationAngle.EAST == 90.0
        assert RotationAngle.SOUTH == 180.0
        assert RotationAngle.WEST == 270.0
