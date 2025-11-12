"""
PDF report generator for site layout analysis.

Generates comprehensive, publication-ready PDF reports with:
- Cover page
- Executive summary
- Site maps
- Constraint analysis
- Asset placement summaries
- Earthwork analysis
- Road network details
- Cost summaries
- Recommendations
- Technical appendix
"""

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
from numpy.typing import NDArray
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Image as RLImage,
    KeepTogether,
)
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from shapely.geometry import Polygon as ShapelyPolygon, Point as ShapelyPoint, LineString
from shapely.geometry.base import BaseGeometry

logger = logging.getLogger(__name__)


class ReportData:
    """
    Container for all data needed to generate a PDF report.

    Attributes:
        project_name: Name of the project
        date: Report generation date
        location: Project location
        site_boundary: Site boundary polygon
        buildable_area_sqm: Buildable area in square meters
        total_area_sqm: Total site area in square meters
        constraints: List of constraint dictionaries
        assets: List of asset dictionaries
        earthwork: Earthwork analysis data
        roads: Road network data
        costs: Cost summary data
        terrain_metrics: Terrain statistics
        dem_data: DEM elevation data for visualization
        recommendations: List of recommendation strings
    """

    def __init__(
        self,
        project_name: str,
        location: str,
        site_boundary: ShapelyPolygon,
        date: Optional[datetime] = None,
    ) -> None:
        """
        Initialize report data.

        Args:
            project_name: Name of the project
            location: Project location
            site_boundary: Site boundary polygon
            date: Report date (defaults to now)
        """
        self.project_name = project_name
        self.location = location
        self.date = date or datetime.now()
        self.site_boundary = site_boundary

        # Calculate basic metrics
        self.total_area_sqm = site_boundary.area
        self.total_area_acres = self.total_area_sqm * 0.000247105

        # Optional data
        self.buildable_area_sqm: Optional[float] = None
        self.buildable_area_acres: Optional[float] = None
        self.constraints: List[Dict[str, Any]] = []
        self.assets: List[Dict[str, Any]] = []
        self.earthwork: Optional[Dict[str, Any]] = None
        self.roads: Optional[Dict[str, Any]] = None
        self.costs: Optional[Dict[str, Any]] = None
        self.terrain_metrics: Optional[Dict[str, Any]] = None
        self.dem_data: Optional[NDArray[np.floating[Any]]] = None
        self.dem_bounds: Optional[Tuple[float, float, float, float]] = None
        self.recommendations: List[str] = []
        self.metadata: Dict[str, Any] = {}


class PDFReportGenerator:
    """
    Generate comprehensive PDF reports for site analysis.

    Creates publication-ready reports with professional formatting,
    charts, maps, and tables.
    """

    def __init__(
        self,
        page_size: Tuple[float, float] = letter,
        include_toc: bool = True,
    ) -> None:
        """
        Initialize PDF report generator.

        Args:
            page_size: Page size (default: letter)
            include_toc: Include table of contents
        """
        self.page_size = page_size
        self.include_toc = include_toc
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self) -> None:
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(
            ParagraphStyle(
                name='CustomTitle',
                parent=self.styles['Title'],
                fontSize=24,
                textColor=colors.HexColor('#1f4788'),
                spaceAfter=30,
                alignment=TA_CENTER,
            )
        )

        # Heading styles
        self.styles.add(
            ParagraphStyle(
                name='Heading1',
                parent=self.styles['Heading1'],
                fontSize=16,
                textColor=colors.HexColor('#1f4788'),
                spaceAfter=12,
                spaceBefore=12,
            )
        )

        self.styles.add(
            ParagraphStyle(
                name='Heading2',
                parent=self.styles['Heading2'],
                fontSize=14,
                textColor=colors.HexColor('#2563eb'),
                spaceAfter=10,
                spaceBefore=10,
            )
        )

        # Body text
        self.styles.add(
            ParagraphStyle(
                name='CustomBody',
                parent=self.styles['BodyText'],
                fontSize=11,
                alignment=TA_JUSTIFY,
                spaceAfter=12,
            )
        )

        # Caption style
        self.styles.add(
            ParagraphStyle(
                name='Caption',
                parent=self.styles['BodyText'],
                fontSize=9,
                textColor=colors.grey,
                alignment=TA_CENTER,
                spaceAfter=12,
            )
        )

    def generate(
        self,
        data: ReportData,
        output_path: Path,
    ) -> None:
        """
        Generate PDF report.

        Args:
            data: Report data
            output_path: Path to save PDF
        """
        logger.info(f"Generating PDF report: {output_path}")

        # Create document
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=self.page_size,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch,
        )

        # Build content
        story = []

        # Cover page
        story.extend(self._create_cover_page(data))
        story.append(PageBreak())

        # Table of contents (if enabled)
        if self.include_toc:
            story.extend(self._create_toc())
            story.append(PageBreak())

        # Executive summary
        story.extend(self._create_executive_summary(data))
        story.append(PageBreak())

        # Site overview
        story.extend(self._create_site_overview(data))
        story.append(PageBreak())

        # Constraint analysis
        if data.constraints:
            story.extend(self._create_constraint_analysis(data))
            story.append(PageBreak())

        # Asset placement summary
        if data.assets:
            story.extend(self._create_asset_summary(data))
            story.append(PageBreak())

        # Earthwork analysis
        if data.earthwork:
            story.extend(self._create_earthwork_analysis(data))
            story.append(PageBreak())

        # Road network summary
        if data.roads:
            story.extend(self._create_road_summary(data))
            story.append(PageBreak())

        # Cost summary
        if data.costs:
            story.extend(self._create_cost_summary(data))
            story.append(PageBreak())

        # Recommendations
        if data.recommendations:
            story.extend(self._create_recommendations(data))
            story.append(PageBreak())

        # Technical appendix
        story.extend(self._create_technical_appendix(data))

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

        logger.info(f"PDF report generated successfully: {output_path}")

    def _add_page_number(self, canvas_obj: canvas.Canvas, doc: SimpleDocTemplate) -> None:
        """Add page number to footer."""
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica', 9)
        canvas_obj.drawRightString(
            doc.pagesize[0] - 0.75*inch,
            0.5*inch,
            text
        )
        canvas_obj.restoreState()

    def _create_cover_page(self, data: ReportData) -> List[Any]:
        """Create cover page."""
        story = []

        # Add some space from top
        story.append(Spacer(1, 2*inch))

        # Title
        story.append(Paragraph(data.project_name, self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5*inch))

        # Subtitle
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=self.styles['Normal'],
            fontSize=18,
            textColor=colors.HexColor('#4b5563'),
            alignment=TA_CENTER,
        )
        story.append(Paragraph("Site Layout Analysis Report", subtitle_style))
        story.append(Spacer(1, 1*inch))

        # Location and date
        info_style = ParagraphStyle(
            'Info',
            parent=self.styles['Normal'],
            fontSize=14,
            alignment=TA_CENTER,
            spaceAfter=12,
        )
        story.append(Paragraph(f"<b>Location:</b> {data.location}", info_style))
        story.append(Paragraph(
            f"<b>Report Date:</b> {data.date.strftime('%B %d, %Y')}",
            info_style
        ))

        # Site area
        story.append(Spacer(1, 0.5*inch))
        story.append(Paragraph(
            f"<b>Total Site Area:</b> {data.total_area_acres:.2f} acres "
            f"({data.total_area_sqm:.0f} m²)",
            info_style
        ))

        return story

    def _create_toc(self) -> List[Any]:
        """Create table of contents."""
        story = []
        story.append(Paragraph("Table of Contents", self.styles['Heading1']))
        story.append(Spacer(1, 0.3*inch))

        # Note: Full TOC implementation would require custom bookmark handling
        # This is a simplified version
        toc_items = [
            "1. Executive Summary",
            "2. Site Overview",
            "3. Constraint Analysis",
            "4. Asset Placement Summary",
            "5. Earthwork Analysis",
            "6. Road Network Summary",
            "7. Cost Summary",
            "8. Recommendations",
            "9. Technical Appendix",
        ]

        for item in toc_items:
            story.append(Paragraph(item, self.styles['Normal']))
            story.append(Spacer(1, 0.1*inch))

        return story

    def _create_executive_summary(self, data: ReportData) -> List[Any]:
        """Create executive summary section."""
        story = []
        story.append(Paragraph("1. Executive Summary", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        # Key metrics table
        story.append(Paragraph("Key Metrics", self.styles['Heading2']))

        metrics_data = [
            ["Metric", "Value"],
            ["Total Site Area", f"{data.total_area_acres:.2f} acres ({data.total_area_sqm:.0f} m²)"],
        ]

        if data.buildable_area_sqm:
            buildable_pct = (data.buildable_area_sqm / data.total_area_sqm) * 100
            metrics_data.append([
                "Buildable Area",
                f"{data.buildable_area_acres:.2f} acres ({buildable_pct:.1f}% of total)"
            ])

        if data.constraints:
            metrics_data.append(["Total Constraints", str(len(data.constraints))])

        if data.assets:
            metrics_data.append(["Proposed Assets", str(len(data.assets))])
            total_asset_area = sum(a.get('area_sqm', 0) for a in data.assets)
            metrics_data.append([
                "Total Asset Footprint",
                f"{total_asset_area * 0.000247105:.2f} acres"
            ])

        if data.earthwork:
            cut_vol = data.earthwork.get('cut_volume_m3', 0)
            fill_vol = data.earthwork.get('fill_volume_m3', 0)
            metrics_data.append(["Cut Volume", f"{cut_vol:,.0f} m³"])
            metrics_data.append(["Fill Volume", f"{fill_vol:,.0f} m³"])
            metrics_data.append(["Net Volume", f"{abs(cut_vol - fill_vol):,.0f} m³"])

        if data.roads:
            total_length = data.roads.get('total_length_m', 0)
            metrics_data.append(["Road Network Length", f"{total_length:.0f} m"])

        table = Table(metrics_data, colWidths=[3*inch, 3.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3*inch))

        # Summary text
        story.append(Paragraph("Summary", self.styles['Heading2']))
        summary_text = f"""
        This report presents a comprehensive analysis of the site layout for {data.project_name}
        located at {data.location}. The analysis encompasses site constraints, proposed asset
        placement, earthwork requirements, road network design, and cost estimates.
        """
        story.append(Paragraph(summary_text, self.styles['CustomBody']))

        # Recommendations preview
        if data.recommendations:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph("Key Recommendations", self.styles['Heading2']))
            for i, rec in enumerate(data.recommendations[:3], 1):  # Show top 3
                story.append(Paragraph(f"{i}. {rec}", self.styles['CustomBody']))

        return story

    def _create_site_overview(self, data: ReportData) -> List[Any]:
        """Create site overview section with map."""
        story = []
        story.append(Paragraph("2. Site Overview", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        # Site description
        story.append(Paragraph("Site Description", self.styles['Heading2']))
        description = f"""
        The site is located at {data.location} and encompasses approximately
        {data.total_area_acres:.2f} acres ({data.total_area_sqm:.0f} square meters).
        """

        if data.terrain_metrics:
            min_elev = data.terrain_metrics.get('min_elevation', 0)
            max_elev = data.terrain_metrics.get('max_elevation', 0)
            mean_elev = data.terrain_metrics.get('mean_elevation', 0)
            description += f"""
            The terrain elevation ranges from {min_elev:.1f}m to {max_elev:.1f}m,
            with a mean elevation of {mean_elev:.1f}m.
            """

        story.append(Paragraph(description, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))

        # Site boundary map
        story.append(Paragraph("Site Boundary Map", self.styles['Heading2']))
        site_map = self._create_site_boundary_map(data)
        if site_map:
            story.append(site_map)
            story.append(Paragraph(
                "Figure 1: Site boundary and location",
                self.styles['Caption']
            ))

        # Elevation map if available
        if data.dem_data is not None and data.dem_bounds is not None:
            story.append(Spacer(1, 0.3*inch))
            story.append(Paragraph("Terrain Elevation Map", self.styles['Heading2']))
            elev_map = self._create_elevation_map(data)
            if elev_map:
                story.append(elev_map)
                story.append(Paragraph(
                    "Figure 2: Site elevation heatmap",
                    self.styles['Caption']
                ))

        return story

    def _create_constraint_analysis(self, data: ReportData) -> List[Any]:
        """Create constraint analysis section."""
        story = []
        story.append(Paragraph("3. Constraint Analysis", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        # Summary
        story.append(Paragraph(
            f"A total of {len(data.constraints)} constraints have been identified "
            f"that affect development potential on this site.",
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.2*inch))

        # Constraints by type
        constraint_types: Dict[str, int] = {}
        for c in data.constraints:
            ctype = c.get('constraint_type', 'unknown')
            constraint_types[ctype] = constraint_types.get(ctype, 0) + 1

        # Constraint summary table
        story.append(Paragraph("Constraints by Type", self.styles['Heading2']))

        table_data = [["Constraint Type", "Count", "Severity"]]
        for ctype, count in sorted(constraint_types.items()):
            # Get severity from first constraint of this type
            severity = next(
                (c.get('severity', 'unknown') for c in data.constraints
                 if c.get('constraint_type') == ctype),
                'unknown'
            )
            table_data.append([ctype.replace('_', ' ').title(), str(count), severity])

        table = Table(table_data, colWidths=[2.5*inch, 1.5*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3*inch))

        # Detailed constraint list
        story.append(Paragraph("Detailed Constraint List", self.styles['Heading2']))

        for i, constraint in enumerate(data.constraints[:10], 1):  # Limit to 10
            name = constraint.get('name', f'Constraint {i}')
            desc = constraint.get('description', 'No description')
            area = constraint.get('area_sqm', 0) * 0.000247105  # to acres

            story.append(Paragraph(
                f"<b>{i}. {name}</b> ({area:.2f} acres)",
                self.styles['Normal']
            ))
            story.append(Paragraph(desc, self.styles['CustomBody']))
            story.append(Spacer(1, 0.1*inch))

        if len(data.constraints) > 10:
            story.append(Paragraph(
                f"... and {len(data.constraints) - 10} more constraints (see appendix)",
                self.styles['Caption']
            ))

        return story

    def _create_asset_summary(self, data: ReportData) -> List[Any]:
        """Create asset placement summary section."""
        story = []
        story.append(Paragraph("4. Asset Placement Summary", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        # Summary
        total_asset_area = sum(a.get('area_sqm', 0) for a in data.assets)
        story.append(Paragraph(
            f"The proposed layout includes {len(data.assets)} assets with a total "
            f"footprint of {total_asset_area * 0.000247105:.2f} acres.",
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.2*inch))

        # Asset table
        story.append(Paragraph("Asset Inventory", self.styles['Heading2']))

        table_data = [["Asset Name", "Type", "Area (acres)", "Position (X, Y)"]]
        for asset in data.assets:
            name = asset.get('name', 'Unnamed')
            atype = asset.get('asset_type', 'unknown').replace('_', ' ').title()
            area = asset.get('area_sqm', 0) * 0.000247105
            pos = asset.get('position', (0, 0))
            position_str = f"({pos[0]:.1f}, {pos[1]:.1f})"

            table_data.append([name, atype, f"{area:.3f}", position_str])

        table = Table(table_data, colWidths=[2*inch, 1.5*inch, 1.2*inch, 1.8*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.2*inch))

        # Asset layout map
        story.append(Paragraph("Asset Layout Map", self.styles['Heading2']))
        layout_map = self._create_asset_layout_map(data)
        if layout_map:
            story.append(layout_map)
            story.append(Paragraph(
                "Figure 3: Proposed asset placement",
                self.styles['Caption']
            ))

        return story

    def _create_earthwork_analysis(self, data: ReportData) -> List[Any]:
        """Create earthwork analysis section."""
        story = []
        story.append(Paragraph("5. Earthwork Analysis", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        earthwork = data.earthwork
        if not earthwork:
            story.append(Paragraph("No earthwork data available.", self.styles['CustomBody']))
            return story

        # Summary
        cut_vol = earthwork.get('cut_volume_m3', 0)
        fill_vol = earthwork.get('fill_volume_m3', 0)
        net_vol = cut_vol - fill_vol

        summary = f"""
        The proposed grading plan requires {cut_vol:,.0f} m³ of cut and {fill_vol:,.0f} m³
        of fill, resulting in a net {"export" if net_vol > 0 else "import"} of
        {abs(net_vol):,.0f} m³.
        """
        story.append(Paragraph(summary, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))

        # Volume table
        story.append(Paragraph("Volume Summary", self.styles['Heading2']))

        table_data = [
            ["Category", "Volume (m³)", "Volume (yd³)"],
            ["Cut Volume", f"{cut_vol:,.0f}", f"{cut_vol * 1.30795:,.0f}"],
            ["Fill Volume", f"{fill_vol:,.0f}", f"{fill_vol * 1.30795:,.0f}"],
            ["Net Volume", f"{abs(net_vol):,.0f}", f"{abs(net_vol) * 1.30795:,.0f}"],
        ]

        table = Table(table_data, colWidths=[2*inch, 2*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.3*inch))

        # Cost breakdown if available
        if 'total_cost' in earthwork:
            story.append(Paragraph("Earthwork Costs", self.styles['Heading2']))

            cost_data = [
                ["Cost Item", "Amount"],
                ["Cut Cost", f"${earthwork.get('cut_cost', 0):,.2f}"],
                ["Fill Cost", f"${earthwork.get('fill_cost', 0):,.2f}"],
                ["Haul Cost", f"${earthwork.get('haul_cost', 0):,.2f}"],
                ["Total Cost", f"${earthwork.get('total_cost', 0):,.2f}"],
            ]

            table = Table(cost_data, colWidths=[3*inch, 3*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
                ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))

            story.append(table)

        return story

    def _create_road_summary(self, data: ReportData) -> List[Any]:
        """Create road network summary section."""
        story = []
        story.append(Paragraph("6. Road Network Summary", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        roads = data.roads
        if not roads:
            story.append(Paragraph("No road network data available.", self.styles['CustomBody']))
            return story

        # Summary
        total_length = roads.get('total_length_m', 0)
        total_length_ft = total_length * 3.28084
        num_segments = roads.get('num_segments', 0)

        summary = f"""
        The proposed road network consists of {num_segments} segments with a total
        length of {total_length:.0f} meters ({total_length_ft:.0f} feet).
        """
        story.append(Paragraph(summary, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))

        # Road statistics table
        story.append(Paragraph("Road Network Statistics", self.styles['Heading2']))

        table_data = [
            ["Metric", "Value"],
            ["Total Length", f"{total_length:.0f} m ({total_length_ft:.0f} ft)"],
            ["Number of Segments", str(num_segments)],
        ]

        if 'avg_grade' in roads:
            table_data.append(["Average Grade", f"{roads['avg_grade']:.1f}%"])
        if 'max_grade' in roads:
            table_data.append(["Maximum Grade", f"{roads['max_grade']:.1f}%"])
        if 'total_cost' in roads:
            table_data.append(["Estimated Cost", f"${roads['total_cost']:,.2f}"])

        table = Table(table_data, colWidths=[3*inch, 3*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story.append(table)

        return story

    def _create_cost_summary(self, data: ReportData) -> List[Any]:
        """Create cost summary section."""
        story = []
        story.append(Paragraph("7. Cost Summary", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        costs = data.costs
        if not costs:
            story.append(Paragraph("No cost data available.", self.styles['CustomBody']))
            return story

        # Cost breakdown table
        story.append(Paragraph("Cost Breakdown", self.styles['Heading2']))

        table_data = [["Cost Category", "Amount"]]

        total = 0.0
        if 'earthwork_cost' in costs:
            amt = costs['earthwork_cost']
            table_data.append(["Earthwork", f"${amt:,.2f}"])
            total += amt
        if 'road_cost' in costs:
            amt = costs['road_cost']
            table_data.append(["Road Construction", f"${amt:,.2f}"])
            total += amt
        if 'utility_cost' in costs:
            amt = costs['utility_cost']
            table_data.append(["Utilities", f"${amt:,.2f}"])
            total += amt
        if 'site_prep_cost' in costs:
            amt = costs['site_prep_cost']
            table_data.append(["Site Preparation", f"${amt:,.2f}"])
            total += amt

        table_data.append(["Total Estimated Cost", f"${total:,.2f}"])

        table = Table(table_data, colWidths=[3.5*inch, 2.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4788')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))

        story.append(table)
        story.append(Spacer(1, 0.2*inch))

        # Cost per acre
        cost_per_acre = total / data.total_area_acres if data.total_area_acres > 0 else 0
        story.append(Paragraph(
            f"<b>Cost per Acre:</b> ${cost_per_acre:,.2f}",
            self.styles['CustomBody']
        ))

        return story

    def _create_recommendations(self, data: ReportData) -> List[Any]:
        """Create recommendations section."""
        story = []
        story.append(Paragraph("8. Recommendations", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        story.append(Paragraph(
            "Based on the analysis, the following recommendations are made:",
            self.styles['CustomBody']
        ))
        story.append(Spacer(1, 0.2*inch))

        for i, rec in enumerate(data.recommendations, 1):
            story.append(Paragraph(f"<b>{i}.</b> {rec}", self.styles['CustomBody']))
            story.append(Spacer(1, 0.1*inch))

        return story

    def _create_technical_appendix(self, data: ReportData) -> List[Any]:
        """Create technical appendix section."""
        story = []
        story.append(Paragraph("9. Technical Appendix", self.styles['Heading1']))
        story.append(Spacer(1, 0.2*inch))

        # Methodology
        story.append(Paragraph("Methodology", self.styles['Heading2']))
        methodology = """
        This analysis was performed using the Entmoot site layout optimization system.
        The system employs advanced algorithms for:
        - Constraint aggregation and validation
        - Terrain analysis and buildability assessment
        - Multi-objective optimization for asset placement
        - Earthwork volume calculation and balancing
        - Road network design and pathfinding
        - Cost estimation based on industry standards
        """
        story.append(Paragraph(methodology, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))

        # Data sources
        story.append(Paragraph("Data Sources", self.styles['Heading2']))
        sources = """
        - Digital Elevation Model (DEM): USGS 3DEP
        - Regulatory constraints: FEMA NFHL, local zoning data
        - Site boundary: User-provided KML/KMZ files
        - Cost databases: RSMeans and regional construction data
        """
        story.append(Paragraph(sources, self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))

        # Assumptions
        story.append(Paragraph("Key Assumptions", self.styles['Heading2']))
        assumptions = """
        - All regulatory constraints are current and accurate
        - Soil conditions are uniform unless otherwise noted
        - Standard construction methods and equipment
        - Costs are estimated at current market rates
        - Site access is available for construction equipment
        """
        story.append(Paragraph(assumptions, self.styles['CustomBody']))

        return story

    def _create_site_boundary_map(self, data: ReportData) -> Optional[RLImage]:
        """Create site boundary map visualization."""
        try:
            fig, ax = plt.subplots(figsize=(8, 6))

            # Plot site boundary
            if hasattr(data.site_boundary, 'exterior'):
                x, y = data.site_boundary.exterior.xy
                ax.plot(x, y, 'b-', linewidth=2, label='Site Boundary')
                ax.fill(x, y, alpha=0.3, color='lightblue')

            # Plot assets if available
            if data.assets:
                for asset in data.assets:
                    pos = asset.get('position', (0, 0))
                    ax.plot(pos[0], pos[1], 'ro', markersize=8)

            ax.set_xlabel('Easting (m)')
            ax.set_ylabel('Northing (m)')
            ax.set_title('Site Boundary and Layout')
            ax.grid(True, alpha=0.3)
            ax.axis('equal')
            ax.legend()

            # Convert to ReportLab image
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)

            return RLImage(img_buffer, width=6*inch, height=4.5*inch)

        except Exception as e:
            logger.error(f"Error creating site boundary map: {e}")
            return None

    def _create_elevation_map(self, data: ReportData) -> Optional[RLImage]:
        """Create elevation heatmap visualization."""
        try:
            if data.dem_data is None or data.dem_bounds is None:
                return None

            fig, ax = plt.subplots(figsize=(8, 6))

            # Create heatmap
            im = ax.imshow(
                data.dem_data,
                cmap='terrain',
                interpolation='bilinear',
                extent=data.dem_bounds,
                origin='upper',
            )

            # Add colorbar
            cbar = plt.colorbar(im, ax=ax, label='Elevation (m)')

            # Overlay site boundary
            if hasattr(data.site_boundary, 'exterior'):
                x, y = data.site_boundary.exterior.xy
                ax.plot(x, y, 'k-', linewidth=2, label='Site Boundary')

            ax.set_xlabel('Easting (m)')
            ax.set_ylabel('Northing (m)')
            ax.set_title('Terrain Elevation')
            ax.legend()

            # Convert to ReportLab image
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)

            return RLImage(img_buffer, width=6*inch, height=4.5*inch)

        except Exception as e:
            logger.error(f"Error creating elevation map: {e}")
            return None

    def _create_asset_layout_map(self, data: ReportData) -> Optional[RLImage]:
        """Create asset layout visualization."""
        try:
            fig, ax = plt.subplots(figsize=(8, 6))

            # Plot site boundary
            if hasattr(data.site_boundary, 'exterior'):
                x, y = data.site_boundary.exterior.xy
                ax.plot(x, y, 'b-', linewidth=2, label='Site Boundary')
                ax.fill(x, y, alpha=0.1, color='lightblue')

            # Plot constraints
            if data.constraints:
                for constraint in data.constraints:
                    # Would need geometry data to plot
                    pass

            # Plot assets
            colors_map = {
                'building': 'red',
                'equipment_yard': 'orange',
                'parking_lot': 'gray',
                'storage_tank': 'green',
            }

            for asset in data.assets:
                pos = asset.get('position', (0, 0))
                atype = asset.get('asset_type', 'building')
                color = colors_map.get(atype, 'blue')
                name = asset.get('name', 'Asset')

                ax.plot(pos[0], pos[1], 'o', color=color, markersize=10)
                ax.annotate(name, pos, fontsize=8, ha='center', va='bottom')

            ax.set_xlabel('Easting (m)')
            ax.set_ylabel('Northing (m)')
            ax.set_title('Proposed Asset Layout')
            ax.grid(True, alpha=0.3)
            ax.axis('equal')

            # Convert to ReportLab image
            img_buffer = io.BytesIO()
            fig.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
            img_buffer.seek(0)
            plt.close(fig)

            return RLImage(img_buffer, width=6*inch, height=4.5*inch)

        except Exception as e:
            logger.error(f"Error creating asset layout map: {e}")
            return None
