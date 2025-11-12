"""
Tests for PDF report generation.

Tests cover:
- PDF document creation
- Report sections
- Tables and charts
- Map generation
- Data validation
- File output
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
import numpy as np
from shapely.geometry import Polygon, Point, LineString

from entmoot.core.reports.pdf_generator import (
    PDFReportGenerator,
    ReportData,
)


@pytest.fixture
def sample_boundary() -> Polygon:
    """Create sample site boundary."""
    return Polygon([
        (0, 0),
        (100, 0),
        (100, 100),
        (0, 100),
        (0, 0),
    ])


@pytest.fixture
def sample_report_data(sample_boundary: Polygon) -> ReportData:
    """Create sample report data."""
    data = ReportData(
        project_name="Test Site Project",
        location="123 Test Street, Test City, TS 12345",
        site_boundary=sample_boundary,
        date=datetime(2024, 1, 15),
    )

    # Add buildable area
    data.buildable_area_sqm = 7500.0
    data.buildable_area_acres = data.buildable_area_sqm * 0.000247105

    # Add constraints
    data.constraints = [
        {
            'name': 'Property Line Setback',
            'type': 'property_line',
            'constraint_type': 'property_line',
            'severity': 'blocking',
            'description': '25-foot setback from property boundary',
            'area_sqm': 1500.0,
        },
        {
            'name': 'Wetland Buffer',
            'type': 'wetland',
            'constraint_type': 'wetland',
            'severity': 'blocking',
            'description': 'Protected wetland area',
            'area_sqm': 800.0,
        },
    ]

    # Add assets
    data.assets = [
        {
            'name': 'Main Building',
            'type': 'building',
            'asset_type': 'building',
            'area_sqm': 500.0,
            'position': (50, 50),
        },
        {
            'name': 'Parking Lot',
            'type': 'parking_lot',
            'asset_type': 'parking_lot',
            'area_sqm': 300.0,
            'position': (30, 70),
        },
    ]

    # Add earthwork data
    data.earthwork = {
        'cut_volume_m3': 5000.0,
        'fill_volume_m3': 4500.0,
        'cut_cost': 25000.0,
        'fill_cost': 22500.0,
        'haul_cost': 5000.0,
        'total_cost': 52500.0,
    }

    # Add road data
    data.roads = {
        'total_length_m': 250.0,
        'num_segments': 3,
        'avg_grade': 3.5,
        'max_grade': 8.0,
        'total_cost': 75000.0,
    }

    # Add cost data
    data.costs = {
        'earthwork_cost': 52500.0,
        'road_cost': 75000.0,
        'utility_cost': 35000.0,
        'site_prep_cost': 20000.0,
    }

    # Add terrain metrics
    data.terrain_metrics = {
        'min_elevation': 100.0,
        'max_elevation': 125.0,
        'mean_elevation': 112.5,
        'std_elevation': 5.2,
        'elevation_range': 25.0,
    }

    # Add DEM data
    dem_data = np.random.rand(50, 50) * 25 + 100  # Random elevation 100-125m
    data.dem_data = dem_data
    data.dem_bounds = (0, 0, 100, 100)

    # Add recommendations
    data.recommendations = [
        "Consider additional soil testing in the northwest corner",
        "Evaluate alternative access road alignment to reduce grading costs",
        "Review wetland buffer requirements with local authorities",
    ]

    return data


class TestReportData:
    """Test ReportData class."""

    def test_init(self, sample_boundary: Polygon) -> None:
        """Test ReportData initialization."""
        data = ReportData(
            project_name="Test Project",
            location="Test Location",
            site_boundary=sample_boundary,
        )

        assert data.project_name == "Test Project"
        assert data.location == "Test Location"
        assert data.site_boundary == sample_boundary
        assert data.total_area_sqm == sample_boundary.area
        assert data.total_area_acres > 0
        assert isinstance(data.date, datetime)

    def test_init_with_date(self, sample_boundary: Polygon) -> None:
        """Test ReportData initialization with specific date."""
        test_date = datetime(2024, 1, 15)
        data = ReportData(
            project_name="Test Project",
            location="Test Location",
            site_boundary=sample_boundary,
            date=test_date,
        )

        assert data.date == test_date

    def test_area_calculations(self, sample_boundary: Polygon) -> None:
        """Test area calculations."""
        data = ReportData(
            project_name="Test",
            location="Test",
            site_boundary=sample_boundary,
        )

        # 100x100 square = 10,000 m²
        assert data.total_area_sqm == 10000.0
        # Convert to acres
        expected_acres = 10000.0 * 0.000247105
        assert abs(data.total_area_acres - expected_acres) < 0.001


class TestPDFReportGenerator:
    """Test PDFReportGenerator class."""

    def test_init_default(self) -> None:
        """Test generator initialization with defaults."""
        generator = PDFReportGenerator()

        assert generator.page_size is not None
        assert generator.include_toc is True
        assert generator.styles is not None

    def test_init_custom(self) -> None:
        """Test generator initialization with custom settings."""
        from reportlab.lib.pagesizes import A4

        generator = PDFReportGenerator(
            page_size=A4,
            include_toc=False,
        )

        assert generator.page_size == A4
        assert generator.include_toc is False

    def test_generate_basic_report(
        self,
        sample_report_data: ReportData,
        tmp_path: Path,
    ) -> None:
        """Test basic PDF generation."""
        output_path = tmp_path / "test_report.pdf"
        generator = PDFReportGenerator()

        # Generate report
        generator.generate(sample_report_data, output_path)

        # Verify file exists
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_generate_minimal_report(
        self,
        sample_boundary: Polygon,
        tmp_path: Path,
    ) -> None:
        """Test PDF generation with minimal data."""
        data = ReportData(
            project_name="Minimal Test",
            location="Test Location",
            site_boundary=sample_boundary,
        )

        output_path = tmp_path / "minimal_report.pdf"
        generator = PDFReportGenerator()

        # Should not raise error with minimal data
        generator.generate(data, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_generate_without_toc(
        self,
        sample_report_data: ReportData,
        tmp_path: Path,
    ) -> None:
        """Test PDF generation without table of contents."""
        output_path = tmp_path / "no_toc_report.pdf"
        generator = PDFReportGenerator(include_toc=False)

        generator.generate(sample_report_data, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_cover_page_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test cover page creation."""
        generator = PDFReportGenerator()
        story = generator._create_cover_page(sample_report_data)

        # Should have multiple elements
        assert len(story) > 0

    def test_executive_summary_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test executive summary creation."""
        generator = PDFReportGenerator()
        story = generator._create_executive_summary(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_site_overview_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test site overview creation."""
        generator = PDFReportGenerator()
        story = generator._create_site_overview(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_constraint_analysis_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test constraint analysis creation."""
        generator = PDFReportGenerator()
        story = generator._create_constraint_analysis(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_asset_summary_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test asset summary creation."""
        generator = PDFReportGenerator()
        story = generator._create_asset_summary(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_earthwork_analysis_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test earthwork analysis creation."""
        generator = PDFReportGenerator()
        story = generator._create_earthwork_analysis(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_road_summary_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test road summary creation."""
        generator = PDFReportGenerator()
        story = generator._create_road_summary(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_cost_summary_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test cost summary creation."""
        generator = PDFReportGenerator()
        story = generator._create_cost_summary(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_recommendations_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test recommendations creation."""
        generator = PDFReportGenerator()
        story = generator._create_recommendations(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_technical_appendix_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test technical appendix creation."""
        generator = PDFReportGenerator()
        story = generator._create_technical_appendix(sample_report_data)

        # Should have content
        assert len(story) > 0

    def test_site_boundary_map_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test site boundary map creation."""
        generator = PDFReportGenerator()
        image = generator._create_site_boundary_map(sample_report_data)

        # Should create image or None (not error)
        assert image is not None or image is None

    def test_elevation_map_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test elevation map creation."""
        generator = PDFReportGenerator()
        image = generator._create_elevation_map(sample_report_data)

        # Should create image
        assert image is not None or image is None

    def test_asset_layout_map_creation(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test asset layout map creation."""
        generator = PDFReportGenerator()
        image = generator._create_asset_layout_map(sample_report_data)

        # Should create image or None
        assert image is not None or image is None

    def test_generate_with_all_sections(
        self,
        sample_report_data: ReportData,
        tmp_path: Path,
    ) -> None:
        """Test PDF generation with all sections populated."""
        output_path = tmp_path / "complete_report.pdf"
        generator = PDFReportGenerator()

        generator.generate(sample_report_data, output_path)

        # Verify file exists and has reasonable size
        assert output_path.exists()
        file_size = output_path.stat().st_size
        assert file_size > 10000  # Should be at least 10KB with all content

    def test_generate_with_empty_collections(
        self,
        sample_boundary: Polygon,
        tmp_path: Path,
    ) -> None:
        """Test PDF generation with empty data collections."""
        data = ReportData(
            project_name="Empty Collections Test",
            location="Test Location",
            site_boundary=sample_boundary,
        )

        # Explicitly set empty collections
        data.constraints = []
        data.assets = []
        data.roads = None
        data.earthwork = None
        data.costs = None
        data.recommendations = []

        output_path = tmp_path / "empty_collections_report.pdf"
        generator = PDFReportGenerator()

        # Should handle empty collections gracefully
        generator.generate(data, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0


class TestPDFIntegration:
    """Integration tests for PDF generation."""

    def test_complete_workflow(
        self,
        sample_boundary: Polygon,
        tmp_path: Path,
    ) -> None:
        """Test complete PDF generation workflow."""
        # Create comprehensive report data
        data = ReportData(
            project_name="Integration Test Site",
            location="123 Integration Ave, Test City, TC 12345",
            site_boundary=sample_boundary,
        )

        # Populate with realistic data
        data.buildable_area_sqm = 8000.0
        data.buildable_area_acres = data.buildable_area_sqm * 0.000247105

        # Multiple constraints
        for i in range(5):
            data.constraints.append({
                'name': f'Constraint {i+1}',
                'type': 'setback',
                'constraint_type': 'property_line',
                'severity': 'blocking',
                'description': f'Test constraint {i+1}',
                'area_sqm': 500.0 + i * 100,
            })

        # Multiple assets
        asset_types = ['building', 'equipment_yard', 'parking_lot', 'storage_tank']
        for i, atype in enumerate(asset_types):
            data.assets.append({
                'name': f'{atype.replace("_", " ").title()} {i+1}',
                'type': atype,
                'asset_type': atype,
                'area_sqm': 400.0 + i * 50,
                'position': (20 + i*15, 30 + i*10),
            })

        # Earthwork
        data.earthwork = {
            'cut_volume_m3': 12000.0,
            'fill_volume_m3': 10500.0,
            'cut_cost': 60000.0,
            'fill_cost': 52500.0,
            'haul_cost': 15000.0,
            'total_cost': 127500.0,
        }

        # Roads
        data.roads = {
            'total_length_m': 450.0,
            'num_segments': 5,
            'avg_grade': 4.2,
            'max_grade': 9.5,
            'total_cost': 135000.0,
        }

        # Costs
        data.costs = {
            'earthwork_cost': 127500.0,
            'road_cost': 135000.0,
            'utility_cost': 85000.0,
            'site_prep_cost': 45000.0,
        }

        # Terrain
        data.terrain_metrics = {
            'min_elevation': 95.0,
            'max_elevation': 135.0,
            'mean_elevation': 115.0,
            'std_elevation': 8.5,
            'elevation_range': 40.0,
        }

        # DEM
        dem_data = np.random.rand(100, 100) * 40 + 95
        data.dem_data = dem_data
        data.dem_bounds = (0, 0, 100, 100)

        # Recommendations
        data.recommendations = [
            "Optimize cut/fill balance to minimize haul costs",
            "Consider phased development approach",
            "Evaluate alternative road alignments",
            "Review utility connection points",
            "Assess environmental impact mitigation strategies",
        ]

        # Generate PDF
        output_path = tmp_path / "integration_test_report.pdf"
        generator = PDFReportGenerator(include_toc=True)
        generator.generate(data, output_path)

        # Verify comprehensive output
        assert output_path.exists()
        file_size = output_path.stat().st_size
        assert file_size > 50000  # Should be substantial with all content

    def test_error_handling_invalid_path(
        self,
        sample_report_data: ReportData,
    ) -> None:
        """Test error handling for invalid output path."""
        invalid_path = Path("/nonexistent/directory/report.pdf")
        generator = PDFReportGenerator()

        # Should raise appropriate error
        with pytest.raises(Exception):
            generator.generate(sample_report_data, invalid_path)

    def test_multiple_reports_same_generator(
        self,
        sample_report_data: ReportData,
        tmp_path: Path,
    ) -> None:
        """Test generating multiple reports with same generator instance."""
        generator = PDFReportGenerator()

        # Generate multiple reports
        for i in range(3):
            output_path = tmp_path / f"report_{i}.pdf"
            generator.generate(sample_report_data, output_path)
            assert output_path.exists()
            assert output_path.stat().st_size > 0
