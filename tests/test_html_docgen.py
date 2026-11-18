"""
Unit tests for the native HTML documentation generation in pbip_doc.docgen.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.html_assets import get_html_css, get_html_js
from pbip_doc.docgen.html_layout import HtmlLayoutBuilder, get_relative_root, get_sidebar_icon_svg
from pbip_doc.docgen.html_builders import (
    HtmlIndexBuilder,
    HtmlTableBuilder,
    HtmlMeasureBuilder,
    HtmlVisualBuilder,
    HtmlExpressionBuilder,
    HtmlFunctionBuilder,
    HtmlDataflowOverviewBuilder,
)
from pbip_doc.docgen.html_engine import HtmlDocGenerator
from pbip_doc.parser import PBIPParser
from pbip_doc.report_schema import (
    PBIPReportModel,
    PageDefinition,
    VisualDefinition,
    CalculationContext,
    EvaluatedMetric,
    SlicingCoordinate,
    ActiveFilter,
    PagePanelFilter,
    SpatialPosition,
    BoundingBox,
)


class TestHtmlDocGenConfig(unittest.TestCase):
    def test_default_config_html_properties(self):
        config = DocGenConfig()
        self.assertEqual(config.output_format, "html")
        self.assertEqual(config.html_theme, "auto")
        self.assertIsNone(config.html_title)
        self.assertEqual(config.html_extension, "html")
        self.assertEqual(config.clean_html_extension, "html")
        self.assertEqual(config.html_ext_suffix, ".html")

    def test_custom_config_html_properties(self):
        config = DocGenConfig(
            output_format="html",
            html_theme="dark",
            html_title="Enterprise BI Portal",
            html_extension="aspx",
        )
        self.assertEqual(config.output_format, "html")
        self.assertEqual(config.html_theme, "dark")
        self.assertEqual(config.html_title, "Enterprise BI Portal")
        self.assertEqual(config.html_extension, "aspx")
        self.assertEqual(config.clean_html_extension, "aspx")
        self.assertEqual(config.html_ext_suffix, ".aspx")

    def test_html_extension_normalization(self):
        # Case insensitivity, leading dot, whitespace trimming, and fallback
        for raw, expected_clean, expected_sfx in [
            ("aspx", "aspx", ".aspx"),
            (".aspx", "aspx", ".aspx"),
            ("ASPX", "aspx", ".aspx"),
            (".ASPX", "aspx", ".aspx"),
            (" .aspx ", "aspx", ".aspx"),
            ("html", "html", ".html"),
            (".html", "html", ".html"),
            ("HTML", "html", ".html"),
            ("", "html", ".html"),
            ("   ", "html", ".html"),
            (".", "html", ".html"),
            (None, "html", ".html"),
        ]:
            cfg = DocGenConfig(html_extension=raw)
            self.assertEqual(cfg.clean_html_extension, expected_clean, f"Failed clean for raw '{raw}'")
            self.assertEqual(cfg.html_ext_suffix, expected_sfx, f"Failed suffix for raw '{raw}'")


class TestHtmlAssets(unittest.TestCase):
    def test_css_asset(self):
        css = get_html_css()
        self.assertIn(":root", css)
        self.assertIn("--bg-body", css)
        self.assertIn("[data-theme=\"dark\"]", css)
        self.assertIn(".wiki-layout", css)
        self.assertIn(".kpi-grid", css)
        self.assertIn(".copy-btn", css)
        self.assertIn(".wiki-sidebar", css)
        self.assertIn(".nav-link > span:first-child", css)
        self.assertIn("text-overflow: ellipsis;", css)

    def test_js_asset(self):
        js = get_html_js()
        self.assertEqual(js, "")


class TestHtmlLayoutBuilder(unittest.TestCase):
    def setUp(self):
        self.config = DocGenConfig(output_format="html", html_title="Test Model Docs")
        self.sample_data = {
            "model_name": "TestModel",
            "tables": [
                {"name": "Sales", "role": "FACT", "columns": [], "measures": []},
                {"name": "Customer", "role": "DIM", "columns": [], "measures": []},
            ],
            "measures": [
                {"name": "Total Sales", "table": "Sales", "dax_expression": "SUM(Sales[Amount])"},
            ],
        }
        self.layout = HtmlLayoutBuilder(
            project_name="Test Project",
            data=self.sample_data,
            config=self.config,
        )

    def test_get_relative_root(self):
        self.assertEqual(get_relative_root("index.html"), ".")
        self.assertEqual(get_relative_root("tables/Sales.html"), "..")
        self.assertEqual(get_relative_root("measures/Sales/Total_Sales.html"), "../..")

    def test_wrap_page_root(self):
        page_html = self.layout.wrap_page(
            current_path="index.html",
            page_title="Model Overview",
            breadcrumbs=[("Home", "./index.html")],
            content_html="<h1>Welcome</h1>",
        )
        self.assertIn("<!DOCTYPE html>", page_html)
        self.assertIn("<title>Model Overview - Test Model Docs Documentation</title>", page_html)
        self.assertIn('href="./assets/style.css"', page_html)
        self.assertNotIn('search_index.js', page_html)
        self.assertNotIn('<script', page_html)
        self.assertNotIn('assets/app.js', page_html)
        self.assertIn("Sales", page_html)
        self.assertIn("Total Sales", page_html)
        self.assertIn("<h1>Welcome</h1>", page_html)

    def test_wrap_page_nested(self):
        page_html = self.layout.wrap_page(
            current_path="measures/Sales/Total_Sales.html",
            page_title="Measure: Total Sales",
            breadcrumbs=[("Home", "../../index.html"), ("Measures", None), ("Total Sales", None)],
            content_html="<div>Measure Details</div>",
        )
        self.assertIn('href="../../assets/style.css"', page_html)
        self.assertNotIn('search_index.js', page_html)
        self.assertNotIn('<script', page_html)
        self.assertNotIn('assets/app.js', page_html)
        self.assertIn("Measure Details", page_html)


class TestHtmlBuilders(unittest.TestCase):
    def setUp(self):
        self.config = DocGenConfig(output_format="html")
        self.sample_measure = {
            "name": "Total Sales",
            "table": "Sales",
            "dax_expression": "SUM(Sales[SalesAmount])",
            "description": "Calculates gross sales revenue.",
            "displayFolder": "Financials",
            "calculation_depth": 1,
            "referenced_measures": [],
            "referenced_columns": [("Sales", "SalesAmount")],
        }
        self.sample_model = {
            "tables": [
                {
                    "name": "Sales",
                    "role": "FACT",
                    "storage_mode": "Import",
                    "description": "Fact table for sales transactions.",
                    "columns": [
                        {"name": "SalesOrderNumber", "dataType": "string"},
                        {"name": "SalesAmount", "dataType": "decimal"},
                    ],
                    "measures": [self.sample_measure],
                    "source_type": "m_partition",
                    "power_query_expression": "let\n    Source = Csv.Document(...)\nin\n    Source",
                },
                {
                    "name": "Customer",
                    "role": "DIM",
                    "storage_mode": "Import",
                    "description": "Customer demographic dimensions.",
                    "columns": [
                        {"name": "CustomerKey", "dataType": "int64"},
                        {"name": "Name", "dataType": "string"},
                    ],
                    "measures": [],
                },
            ],
            "measures": [self.sample_measure],
            "relationships": [
                {
                    "fromTable": "Sales",
                    "fromColumn": "CustomerKey",
                    "toTable": "Customer",
                    "toColumn": "CustomerKey",
                    "isActive": True,
                    "crossFilteringBehavior": "OneDirection",
                }
            ],
        }

    def test_html_index_builder(self):
        builder = HtmlIndexBuilder(self.sample_model, self.config, project_name="Sales BI")
        content = builder.build_content()
        self.assertIn("Sales BI", content)
        self.assertIn("Published Data Model Tables", content)
        self.assertIn('id="tab-summary"', content)
        self.assertIn("Description", content)
        self.assertIn("Customer", content)
        self.assertIn("Sales", content)
        self.assertIn("Total Sales", content)

    def test_html_table_builder(self):
        table_data = self.sample_model["tables"][0]
        builder = HtmlTableBuilder(table_data, self.sample_model, self.config, project_name="Sales BI")
        content = builder.build_content()
        self.assertIn("Sales", content)
        self.assertIn("SalesOrderNumber", content)
        self.assertIn("SalesAmount", content)
        self.assertIn("Total Sales", content)
        self.assertIn("page-tab-bar", content)
        self.assertIn('id="tab-summary"', content)
        self.assertIn("Fact table for sales transactions.", content)
        self.assertIn('id="tab-cols"', content)
        self.assertIn('id="tab-details"', content)
        self.assertNotIn("Power Query (M) Script", content)
        self.assertNotIn("copy-btn", content)

        # Verify engine still supports data_source_summary & power_query_lineage via layout_config
        cfg_custom = DocGenConfig(
            layout_config={
                "table": {
                    "tabs": [
                        {
                            "id": "tab-sources",
                            "label": "Data Source",
                            "blocks": [{"id": "b1", "functions": ["data_source_summary"]}],
                        },
                        {
                            "id": "tab-m",
                            "label": "M Script",
                            "blocks": [{"id": "b2", "functions": ["power_query_lineage"]}],
                        },
                    ]
                }
            }
        )
        content_custom = HtmlTableBuilder(table_data, self.sample_model, cfg_custom, project_name="Sales BI").build_content()
        self.assertIn("Power Query (M) Script", content_custom)
        self.assertIn("Data Source Summary", content_custom)

    def test_html_measure_builder(self):
        measure_data = self.sample_measure
        builder = HtmlMeasureBuilder(measure_data, self.sample_model, self.config, project_name="Sales BI")
        content = builder.build_content()
        self.assertIn("Total Sales", content)
        self.assertIn("Sales[SalesAmount]", content)
        self.assertIn("page-tab-bar", content)
        self.assertIn('id="tab-definition"', content)
        self.assertIn("Calculates gross sales revenue.", content)
        self.assertNotIn("copy-btn", content)

    def test_html_visual_builder(self):
        v_bbox = BoundingBox(x=10, y=20, width=500, height=300, z=1)
        spatial_pos = SpatialPosition(center_x=260, center_y=170, zone="Top-Left", bounding_box=v_bbox)
        metric = EvaluatedMetric(
            table="Sales",
            field="Total Sales",
            field_type="MEASURE",
            role="Values",
            model_key="[Total Sales]",
        )
        coord = SlicingCoordinate(
            role="Category",
            table="Customer",
            field="Name",
            model_key="Customer[Name]",
        )
        calc_ctx = CalculationContext(
            evaluated_metrics=[metric],
            slicing_coordinates=[coord],
            visual_active_filters=[ActiveFilter(table="Sales", field="SalesAmount", filter_type="Range", condition="> 0")],
            locked_active_filters=[PagePanelFilter(scope="Locked", table="Date", field="Year", is_locked=True, applied_values=["2024"])],
        )
        visual = VisualDefinition(
            visual_id="v_1001",
            title="Sales by Customer",
            visual_type="columnChart",
            spatial_position=spatial_pos,
            calculation_context=calc_ctx,
        )
        page = PageDefinition(
            page_id="p_1",
            display_name="Executive Summary",
            page_number=1,
            visuals=[visual],
        )
        report_model = PBIPReportModel(
            report_name="Sales Report",
            format="PBIR",
            source_path="/path/to/report",
            pages=[page],
        )

        builder = HtmlVisualBuilder(page, report_model, self.config, project_name="Sales Report")
        content = builder.build_content()
        self.assertIn("Executive Summary", content)
        self.assertIn("Sales by Customer", content)
        self.assertIn("columnChart", content)
        self.assertIn("Total Sales", content)
        self.assertIn("Customer", content)
        self.assertIn("Name", content)
        self.assertIn("Filter Pane (Page Level)", content)
        self.assertIn('id="tab-context"', content)
        self.assertIn("Description", content)

    def test_html_expression_and_function_builders(self):
        expr_data = {
            "query_name": "SharedDimCustomer",
            "is_staging": True,
            "description": "Shared ETL query for customer entities.",
            "direct_dependencies": [],
            "full_m_expression": "let\n    Source = 1\nin\n    Source",
        }
        expr_builder = HtmlExpressionBuilder(expr_data, self.sample_model, self.config)
        expr_content = expr_builder.build_content()
        self.assertIn("SharedDimCustomer", expr_content)
        self.assertIn('id="tab-definitions"', expr_content)
        self.assertIn("Shared ETL query for customer entities.", expr_content)

        fn_data = {
            "name": "CalcTax",
            "return_type": "double",
            "description": "Calculates tax based on rate.",
            "parameters": [{"name": "amount", "data_type": "double"}],
            "expression": "amount * 0.2",
            "parameters_signature": "(amount: double)",
        }
        fn_builder = HtmlFunctionBuilder(fn_data, self.sample_model, self.config)
        fn_content = fn_builder.build_content()
        self.assertIn("CalcTax", fn_content)
        self.assertIn('id="tab-definition"', fn_content)
        self.assertIn("Calculates tax based on rate.", fn_content)

    def test_kpi_cards_order_and_hierarchies(self):
        """Verifies max 4 KPI cards per page, priority ordering, hierarchy representation and elimination of redundant cards."""
        # 1. Model Overview: Tables, Measures, Physical Columns, Bound Reports (No 'Report Pages')
        idx_builder = HtmlIndexBuilder(self.sample_model, self.config, project_name="Sales BI")
        idx_content = idx_builder.build_content()
        self.assertIn('<div class="kpi-label">Tables</div>', idx_content)
        self.assertIn('<div class="kpi-label">Measures</div>', idx_content)
        self.assertIn('<div class="kpi-label">Physical Columns</div>', idx_content)
        self.assertIn('<div class="kpi-label">Bound Reports</div>', idx_content)
        self.assertNotIn('<div class="kpi-label">Report Pages</div>', idx_content)
        self.assertEqual(idx_content.count('<div class="kpi-card">'), 4)

        # 2. Table: Model, Role, Columns, Host Measures
        tbl_data = self.sample_model["tables"][0]
        tbl_builder = HtmlTableBuilder(tbl_data, self.sample_model, self.config, project_name="Sales BI")
        tbl_content = tbl_builder.build_content()
        self.assertIn('<div class="kpi-label">Model</div>', tbl_content)
        self.assertIn('<a href="../index.html">Sales BI</a>', tbl_content)
        self.assertIn('<div class="kpi-label">Role</div>', tbl_content)
        self.assertIn('<div class="kpi-label">Columns</div>', tbl_content)
        self.assertIn('<div class="kpi-label">Host Measures</div>', tbl_content)
        self.assertEqual(tbl_content.count('<div class="kpi-card">'), 4)

        # 3. Measure: Model, Host Table, Calculation Depth, Downstream Impact (No 'Format String' card)
        meas_builder = HtmlMeasureBuilder(self.sample_measure, self.sample_model, self.config, project_name="Sales BI")
        meas_content = meas_builder.build_content()
        self.assertIn('<div class="kpi-label">Model</div>', meas_content)
        self.assertIn('<a href="../../index.html">Sales BI</a>', meas_content)
        self.assertIn('<div class="kpi-label">Host Table</div>', meas_content)
        self.assertIn('<div class="kpi-label">Calculation Depth</div>', meas_content)
        self.assertIn('<div class="kpi-label">Downstream Impact</div>', meas_content)
        self.assertNotIn('<div class="kpi-label">Format String</div>', meas_content)
        self.assertEqual(meas_content.count('<div class="kpi-card">'), 4)

        # 4. Report Visual Page: Page Number, Visibility, Dynamic Visuals, Dimensions
        v_bbox = BoundingBox(x=10, y=20, width=500, height=300, z=1)
        spatial_pos = SpatialPosition(center_x=260, center_y=170, zone="Top-Left", bounding_box=v_bbox)
        visual = VisualDefinition(visual_id="v1", title="V1", visual_type="chart", spatial_position=spatial_pos)
        page = PageDefinition(page_id="p1", display_name="Page 1", page_number=1, visuals=[visual])
        rep_model = PBIPReportModel(report_name="Report 1", format="PBIR", source_path="dummy", pages=[page])
        vis_builder = HtmlVisualBuilder(page, rep_model, self.config, project_name="Report 1")
        vis_content = vis_builder.build_content()
        self.assertIn('<div class="kpi-label">Page Number</div>', vis_content)
        self.assertIn('<div class="kpi-label">Visibility</div>', vis_content)
        self.assertIn('<div class="kpi-label">Dynamic Visuals</div>', vis_content)
        self.assertIn('<div class="kpi-label">Canvas Dimensions</div>', vis_content)
        self.assertEqual(vis_content.count('<div class="kpi-card">'), 4)

    def test_conditional_dataflow_and_naming(self):
        """Tests conditional dataflow banner and Loaded naming & badge."""
        tbl_pq = {
            "name": "FactSales",
            "source_type": "PowerQuery",
            "m_code": 'let Source = Sql.Database("srv", "db") in Source',
            "columns": [],
        }
        tbl_calc = {
            "name": "DimDateCalculated",
            "source_type": "CalculatedTable",
            "expression": "CALENDAR(DATE(2020,1,1), DATE(2025,12,31))",
            "columns": [],
        }
        tbl_calcgroup = {
            "name": "TimeIntelligence",
            "source_type": "CalculationGroup",
            "calculation_items": [{"name": "YTD"}, {"name": "QTD"}],
            "columns": [],
        }
        model = {
            "tables": [tbl_pq, tbl_calc, tbl_calcgroup],
            "expressions": [],
            "measures": [],
        }

        # 1. HtmlTableBuilder: Decouples PQ from default layout; supported via layout_config
        html_pq_default = HtmlTableBuilder(tbl_pq, model, self.config, project_name="Test").build_content()
        self.assertNotIn("Dataflow Pipeline Documentation", html_pq_default)

        # When power_query_lineage is enabled in layout, standard table has dataflow banner
        cfg_lineage = DocGenConfig(
            include_dataflow=True,
            include_expression_docs=True,
            layout_config={
                "table": {
                    "tabs": [
                        {
                            "id": "tab-m",
                            "label": "Lineage",
                            "blocks": [{"id": "b", "functions": ["power_query_lineage"]}],
                        }
                    ]
                }
            },
        )
        b_pq = HtmlTableBuilder(tbl_pq, model, cfg_lineage, project_name="Test")
        html_pq = b_pq.build_content()
        self.assertIn("ETL Pipeline Documentation", html_pq)
        self.assertIn('href="../etl/FactSales.html"', html_pq)

        # 2. HtmlTableBuilder: Calculated table does NOT have broken link to expressions
        b_calc = HtmlTableBuilder(tbl_calc, model, cfg_lineage, project_name="Test")
        html_calc = b_calc.build_content()
        self.assertNotIn("ETL Pipeline Documentation", html_calc)
        self.assertNotIn("etl/DimDateCalculated.html", html_calc)
        self.assertIn("DAX Table Calculation &amp; Lineage", html_calc)
        self.assertIn("CALENDAR", html_calc)

        # 3. HtmlTableBuilder: Calculation group does NOT have broken link to expressions
        b_cg = HtmlTableBuilder(tbl_calcgroup, model, cfg_lineage, project_name="Test")
        html_cg = b_cg.build_content()
        self.assertNotIn("ETL Pipeline Documentation", html_cg)
        self.assertNotIn("etl/TimeIntelligence.html", html_cg)
        self.assertIn("Calculation Group &amp; Lineage", html_cg)
        self.assertIn("YTD", html_cg)

        # 4. TableDocBuilder (Markdown): Parity
        from pbip_doc.docgen.table_doc import TableDocBuilder
        md_pq = TableDocBuilder(tbl_pq, model, self.config, project_name="Test").build_markdown()
        self.assertIn("`FactSales`](../etl/FactSales.md)", md_pq)

        md_calc = TableDocBuilder(tbl_calc, model, self.config, project_name="Test").build_markdown()
        self.assertNotIn("../etl/DimDateCalculated.md", md_calc)
        self.assertIn("CALENDAR", md_calc)

        md_cg = TableDocBuilder(tbl_calcgroup, model, self.config, project_name="Test").build_markdown()
        self.assertNotIn("../etl/TimeIntelligence.md", md_cg)
        self.assertIn("Calculation Group & Lineage", md_cg)
        self.assertIn("YTD", md_cg)

        # 5. HtmlDataflowOverviewBuilder: Loaded naming
        df_builder = HtmlDataflowOverviewBuilder(model, self.config, project_name="Test")
        df_html = df_builder.build_content()
        self.assertIn("Loaded (1)", df_html)
        self.assertNotIn("Loaded Tables", df_html)

        # 6. HtmlExpressionBuilder: Loaded badge
        expr_table_data = {
            "query_name": "FactSales",
            "name": "FactSales",
            "expression_kind": "table",
            "is_loaded_table": True,
            "full_m_expression": tbl_pq["m_code"],
        }
        b_expr = HtmlExpressionBuilder(expr_table_data, model, self.config, project_name="Test")
        expr_html = b_expr.build_content()
        self.assertIn('<span class="badge badge-etl-loaded">Loaded</span>', expr_html)
        self.assertNotIn("Loaded Table", expr_html)


class TestHtmlDocGeneratorEndToEnd(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="pbip_html_test_")
        self.sample_dir = Path(__file__).resolve().parent.parent / "samples" / "Ecommerce_Sales"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_ecommerce_sales_html_generation(self):
        if not self.sample_dir.exists():
            self.skipTest("Sample directory 'Ecommerce_Sales' not found.")

        parser = PBIPParser()
        model = parser.parse(str(self.sample_dir))

        config = DocGenConfig(
            output_format="html",
            output_dir=self.temp_dir,
            html_title="Ecommerce Sales KB",
        )
        generator = HtmlDocGenerator(config=config)
        docs = generator.write_to_directory(str(self.sample_dir), target_dir=self.temp_dir)

        # 1. Entry portal
        self.assertIn("index.html", docs)
        index_file = Path(self.temp_dir) / "index.html"
        self.assertTrue(index_file.exists())
        with open(index_file, "r", encoding="utf-8") as f:
            index_content = f.read()
        self.assertIn("Ecommerce Sales KB", index_content)
        self.assertIn("Model Overview", index_content)

        # 2. Assets (Zero-JS: only style.css emitted)
        self.assertTrue((Path(self.temp_dir) / "assets" / "style.css").exists())
        self.assertFalse((Path(self.temp_dir) / "assets" / "app.js").exists())
        self.assertFalse((Path(self.temp_dir) / "assets" / "search_index.js").exists())

        # 3. Tables & Functions
        self.assertTrue((Path(self.temp_dir) / "tables" / "Orders.html").exists())
        self.assertTrue((Path(self.temp_dir) / "tables" / "Customers.html").exists())
        self.assertTrue((Path(self.temp_dir) / "functions" / "SafeDivide.html").exists())

        # 4. Measures
        self.assertTrue((Path(self.temp_dir) / "measures" / "Orders" / "Total_Revenue.html").exists())

        # 5. Visuals & SVG Maps
        self.assertTrue((Path(self.temp_dir) / "visuals" / "Executive_Summary.html").exists())
        svg_maps = list((Path(self.temp_dir) / "visuals" / "assets" / "Executive_Summary").glob("*.svg"))
        self.assertGreater(len(svg_maps), 0)

    def test_config_scoped_overrides(self):
        cfg = DocGenConfig(
            include_visual_svg_maps=True,
            include_table_m_code=True,
            overrides={
                "reports/adhoc/*": {
                    "include_visual_svg_maps": False,
                },
                "Special.Report": {
                    "include_visual_svg_maps": False,
                },
                "models/HR": {
                    "include_table_m_code": False,
                }
            }
        )

        # 1. Unmatched report uses defaults
        c1 = cfg.get_scoped_config("reports/standard/Sales.Report")
        self.assertTrue(c1.include_visual_svg_maps)
        self.assertTrue(c1.include_table_m_code)

        # 2. Matched glob pattern overrides setting
        c2 = cfg.get_scoped_config("reports/adhoc/QuickTest.Report")
        self.assertFalse(c2.include_visual_svg_maps)
        self.assertTrue(c2.include_table_m_code)

        # 3. Exact artifact name match
        c3 = cfg.get_scoped_config("Special.Report")
        self.assertFalse(c3.include_visual_svg_maps)

        # 4. Model override
        c4 = cfg.get_scoped_config("models/HR")
        self.assertFalse(c4.include_table_m_code)
        self.assertTrue(c4.include_visual_svg_maps)


    def test_measure_table_name_collision_and_html_markdown_parity(self):
        """Verifies that a measure named identically to its host table (e.g. Sales[Sales])
        is retained, resolves correctly in DAX DAG (Profit = [Sales] - [Cost]),
        and renders upstream dependencies and full DAX formula consistently in both Markdown and HTML."""
        from pbip_doc.model_schema import PBIPSemanticModel, TableDefinition, MeasureDefinition, TableRole, TableRoleClassification
        from pbip_doc.measure_analyzer import MeasureDependencyResolver
        from pbip_doc.docgen.engine import MarkdownDocGenerator
        from pbip_doc.docgen.html_engine import HtmlDocGenerator

        tbl_sales = TableDefinition(
            name="Sales",
            role=TableRole.FACT,
            classification_reasoning=TableRoleClassification(TableRole.FACT, 0.95),
            columns=[],
        )
        m_sales = MeasureDefinition(name="Sales", table="Sales", dax_expression="SUM('Sales'[Sales Amount])")
        m_cost = MeasureDefinition(name="Cost", table="Sales", dax_expression="SUM('Sales'[Total Product Cost])")
        m_profit = MeasureDefinition(name="Profit", table="Sales", dax_expression="[Sales] - [Cost]")

        measures = [m_sales, m_cost, m_profit]
        resolver = MeasureDependencyResolver(measures, [tbl_sales])
        resolver.analyze()

        self.assertIn("Sales", m_profit.direct_measure_dependencies)
        self.assertIn("Cost", m_profit.direct_measure_dependencies)
        self.assertEqual(m_profit.direct_measure_dependencies, ["Cost", "Sales"])
        self.assertIn("Profit", m_sales.downstream_measures)

        model = PBIPSemanticModel(
            model_name="AW_Sales",
            source_format="TMDL",
            compatibility_level=1600,
            culture="en-US",
            tables=[tbl_sales],
            relationships=[],
            measures=measures,
            measure_dependency_dag={m.name: m.direct_measure_dependencies for m in measures},
        )
        model_dict = model.to_dict()

        # Markdown Verification
        cfg = DocGenConfig(include_expression_chapter=True)
        md_gen = MarkdownDocGenerator(cfg)
        md_docs = md_gen.generate_all_documents(model_dict)
        profit_md = md_docs["measures/Sales/Profit.md"]
        self.assertIn("- [Cost](../Sales/Cost.md)", profit_md)
        self.assertIn("- [Sales](../Sales/Sales.md)", profit_md)
        self.assertIn("[Profit] =", profit_md)
        self.assertIn("[Sales] - [Cost]", profit_md)

        # HTML Verification
        html_gen = HtmlDocGenerator(cfg)
        html_docs = html_gen.generate_all_documents(model_dict)
        profit_html = html_docs["measures/Sales/Profit.html"]
        self.assertIn("[Cost]", profit_html)
        self.assertIn("[Sales]", profit_html)
        self.assertIn("measures/Sales/Cost.html", profit_html)
        self.assertIn("measures/Sales/Sales.html", profit_html)
        self.assertIn("Upstream Dependency (Preceding Measures in DAG - 2)", profit_html)
        self.assertIn("2 Upstream Precedents", profit_html)
        self.assertIn("[Profit] =\n[Sales] - [Cost]", profit_html)

    def test_sidebar_icon_resolution(self):
        """Verifies resolution of sidebar icon parameter: default/large logo, compact logo, presets, inline, and custom."""
        # 1. Default / extended large logo and compact logo preset
        default_svg = get_sidebar_icon_svg("default")
        self.assertIn("<svg", default_svg)
        self.assertIn('viewBox="0 0 500 180"', default_svg)
        self.assertIn("pbip-doc", default_svg)
        self.assertIn("currentColor", default_svg)
        self.assertIn("translate(86, 22)", default_svg)

        large_logo_svg = get_sidebar_icon_svg("pbip_doc_logo_large.svg")
        self.assertEqual(large_logo_svg, default_svg)

        compact_logo_svg = get_sidebar_icon_svg("pbip_doc_logo.svg")
        self.assertIn("<svg", compact_logo_svg)
        self.assertIn('viewBox="0 0 180 180"', compact_logo_svg)
        self.assertIn("translate(86, 22)", compact_logo_svg)
        self.assertNotIn("pbip-doc", compact_logo_svg)

        # 2. Presets
        cube_svg = get_sidebar_icon_svg("cube")
        self.assertIn("<svg", cube_svg)
        db_svg = get_sidebar_icon_svg("database")
        self.assertIn("<svg", db_svg)

        # 3. Raw inline SVG
        raw_svg = '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="5"/></svg>'
        res_raw = get_sidebar_icon_svg(raw_svg)
        self.assertIn("<circle", res_raw)

        # 4. Config integration
        cfg = DocGenConfig(sidebar_icon="barchart")
        layout = HtmlLayoutBuilder(project_name="Test", data={"tables": []}, config=cfg)
        wrapped = layout.wrap_page("index.html", "Test", [], "<p>Content</p>")
        self.assertIn("sidebar-title-icon", wrapped)
        self.assertIn("<line x1=\"18\"", wrapped)

        # 5. PNG image file support (Base64 Data-URI)
        import tempfile
        import os
        sample_png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?"
            b"\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
            tf.write(sample_png_bytes)
            tf_path = tf.name

        try:
            res_png = get_sidebar_icon_svg(tf_path)
            self.assertIn('<img src="data:image/png;base64,', res_png)
            self.assertIn('class="sidebar-title-icon"', res_png)

            # In wrap_page via config
            cfg_png = DocGenConfig(sidebar_icon=tf_path)
            layout_png = HtmlLayoutBuilder(project_name="TestPNG", data={"tables": []}, config=cfg_png)
            wrapped_png = layout_png.wrap_page("index.html", "Test", [], "<p>Content</p>")
            self.assertIn('<img src="data:image/png;base64,', wrapped_png)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

        # 6. Direct Data-URI and raw <img> tag
        data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJ"
        res_uri = get_sidebar_icon_svg(data_uri)
        self.assertIn(f'<img src="{data_uri}"', res_uri)

        raw_img = '<img src="my_logo.png" alt="Company">'
        res_img = get_sidebar_icon_svg(raw_img)
        self.assertIn('<img class="sidebar-title-icon"', res_img)

        # 7. Non-existent PNG falls back safely to default SVG
        res_nonexistent = get_sidebar_icon_svg("non_existent_brand_logo.png")
        self.assertIn("<svg", res_nonexistent)
        self.assertEqual(res_nonexistent, default_svg)

    def test_html_visual_builder_reordered_filter_context_first(self):
        """Verifies that HtmlVisualBuilder presents Filter Context BEFORE dynamic visual details."""
        from pbip_doc.report_schema import PageSlicer

        calc = CalculationContext(
            all_pages_filters=[
                PagePanelFilter(scope="Report Filter Panel (Locked)", table="Geography", field="Continent", is_locked=True, applied_values=["Europe"]),
            ],
            locked_active_filters=[
                PagePanelFilter(scope="Page Filter Panel (Locked)", table="Sales", field="Year", is_locked=True, applied_values=["2024"]),
            ],
            unlocked_available_filters=[
                PagePanelFilter(scope="Page Filter Panel (Interactive)", table="Product", field="Category", is_locked=False, default_value="All"),
            ],
            page_slicers=[
                PageSlicer(slicer_visual_id="s1", table="Date", field="Month", model_key="Date[Month]", is_synced_across_pages=True),
            ],
            evaluated_metrics=[
                EvaluatedMetric(table="Sales", field="Revenue", field_type="MEASURE", role="Values", model_key="Sales[Revenue]"),
            ],
        )

        visual = VisualDefinition(
            visual_id="v_chart",
            visual_type="barChart",
            title="Monthly Revenue",
            calculation_context=calc,
        )

        page = PageDefinition(
            page_id="p1",
            display_name="Overview",
            page_number=1,
            visuals=[visual],
        )

        report = PBIPReportModel(
            report_name="Revenue Report",
            format="PBIR",
            source_path="/path/to/report",
            pages=[page],
            report_filters=calc.all_pages_filters,
        )

        builder = HtmlVisualBuilder(page, report, DocGenConfig(), project_name="Revenue Report")
        html_out = builder.build_content()

        # 1. Quicknav verifies tab order
        qnav_context = html_out.find('for="page-tab-tab-context"')
        qnav_visuals = html_out.find('for="page-tab-tab-visuals"')
        self.assertGreater(qnav_context, 0)
        self.assertGreater(qnav_visuals, qnav_context, "Page context with filter context must precede dynamic visuals in quicknav")

        # 2. Section order in page body
        pos_context = html_out.find('id="tab-context"')
        pos_visuals = html_out.find('id="tab-visuals"')
        self.assertGreater(pos_context, 0)
        self.assertGreater(pos_visuals, pos_context, "Page context section must appear before dynamic visuals section")

        # 3. Check single "Report Page Filter Context" panel and Visual-Level Filters inside visual details
        self.assertIn("Report Page Filter Context", html_out)
        self.assertIn("1. Filter Pane (Report Level)", html_out)
        self.assertIn("Geography", html_out)
        self.assertIn("Europe", html_out)

        self.assertIn("2. Filter Pane (Page Level)", html_out)
        self.assertIn("Sales", html_out)
        self.assertIn("2024", html_out)

        self.assertIn("3. Interactive Filters", html_out)
        self.assertIn("Product", html_out)
        self.assertIn("Yes (Synchronized)", html_out)

        self.assertNotIn("4. Visual-Level Filters", html_out)
        self.assertIn('<div class="spec-group-title">Visual-Level Filters</div>', html_out)
        self.assertNotIn("Filter Perimeter", html_out)

    def test_section_engine_and_tab_ordering_synchronization(self):
        """Verifies section ordering and automatic quicknav tab synchronization."""
        import re
        from pbip_doc.docgen.index_doc import IndexDocBuilder
        from pbip_doc.docgen.table_doc import TableDocBuilder
        from pbip_doc.docgen.measure_doc import MeasureDocBuilder
        from pbip_doc.docgen.function_doc import FunctionDocBuilder

        model_data = {
            "model_name": "OrderModel",
            "source_format": "TMDL",
            "compatibility_level": 1600,
            "culture": "en-US",
            "description": "Test model description",
            "data_sources_summary": [{"source_type": "SQL", "connection_string": "srv/db", "server": "srv", "database": "db"}],
            "tables": [
                {
                    "name": "Sales",
                    "role": "FACT",
                    "description": "Sales table desc",
                    "columns": [
                        {"name": "ID", "data_type": "int64"},
                        {"name": "CalcCol", "data_type": "decimal", "is_calculated": True, "expression": "[ID] * 2"},
                        {"name": "PQCol", "data_type": "string", "origin": "power_query", "m_expression": "each [ID]"},
                    ],
                    "power_query_expression": "let Source = 1 in Source",
                }
            ],
            "measures": [
                {
                    "name": "Rev",
                    "table": "Sales",
                    "dax_expression": "SUM(Sales[ID])",
                    "calculation_depth": 1,
                    "direct_measure_dependencies": ["BaseM"],
                    "downstream_measures": ["NetRev"],
                    "referenced_columns": [{"table": "Sales", "column": "ID"}],
                }
            ],
            "functions": [
                {
                    "name": "MyUDF",
                    "return_type": "double",
                    "description": "UDF desc",
                    "parameters": [{"name": "x", "data_type": "double"}],
                    "parameters_signature": "(x: double)",
                    "expression": "x * 2",
                    "referenced_columns": [{"table": "Sales", "column": "ID"}],
                    "referenced_functions": ["OtherUDF"],
                    "downstream_measures": ["Rev"],
                }
            ],
            "expressions": [
                {
                    "query_name": "StagingSales",
                    "is_staging": True,
                    "full_m_expression": "let Source = 1 in Source",
                }
            ],
            "relationships": [
                {"from_table": "Sales", "from_column": "ID", "to_table": "Sales", "to_column": "ID", "is_active": True}
            ],
            "bound_reports_info": [
                {"name": "ExecReport", "format": "PBIR", "pages_count": 3, "md_url": "../../reports/ExecReport/README.md", "html_url": "../../reports/ExecReport/index.html"}
            ],
        }
        cfg = DocGenConfig(include_expression_chapter=True)

        def assert_quicknav_matches_sections(html_str: str):
            nav_match = re.search(r'<nav class="page-tab-bar">(.*?)</nav>', html_str, re.DOTALL)
            self.assertIsNotNone(nav_match)
            nav_ids = re.findall(r'for="page-tab-([^"]+)"', nav_match.group(1))
            sec_ids = re.findall(r'<section id="([^"]+)" class="content-section">', html_str)
            self.assertEqual(nav_ids, sec_ids, "Tab bar buttons must match section order 1:1")
            return sec_ids

        # 1. Model Overview (Streamlined to 7 clean tabs)
        idx_html = HtmlIndexBuilder(model_data, cfg).build_content()
        idx_sec_ids = assert_quicknav_matches_sections(idx_html)
        self.assertEqual(
            idx_sec_ids,
            [
                "tab-summary",
                "tab-tables",
                "tab-relationships",
                "tab-functions",
                "tab-measures",
                "tab-reports",
                "tab-details",
            ],
        )

        # 2. Table (Streamlined to 6 clean tabs)
        tbl_html = HtmlTableBuilder(model_data["tables"][0], model_data, cfg).build_content()
        tbl_sec_ids = assert_quicknav_matches_sections(tbl_html)
        self.assertEqual(
            tbl_sec_ids,
            [
                "tab-summary",
                "tab-cols",
                "tab-calc-cols",
                "tab-rels",
                "tab-meas",
                "tab-details",
            ],
        )

        # 3. Measure (Streamlined to 3 tabs: Definition, Dependencies, Details)
        meas_html = HtmlMeasureBuilder(model_data["measures"][0], model_data, cfg).build_content()
        meas_sec_ids = assert_quicknav_matches_sections(meas_html)
        self.assertEqual(
            meas_sec_ids,
            [
                "tab-definition",
                "tab-dependencies",
                "tab-details",
            ],
        )

        # 4. Function (UDF Streamlined to 3 tabs: Definition, Dependencies, Details)
        fn_html = HtmlFunctionBuilder(model_data["functions"][0], model_data, cfg).build_content()
        fn_sec_ids = assert_quicknav_matches_sections(fn_html)
        self.assertEqual(
            fn_sec_ids,
            [
                "tab-definition",
                "tab-dependencies",
                "tab-details",
            ],
        )

    def test_legend_subtitles_and_visual_refinements(self):
        """Validates legend tabs, contextual subtitles, topN measure link, and styles."""
        cfg = DocGenConfig(output_format="html")
        model_data = {
            "tables": [
                {
                    "name": "Sales",
                    "description": "Core fact table with all revenue transactions.",
                    "role": "FACT",
                    "columns": [{"name": "Amount", "data_type": "Decimal", "source_type": "Calculated"}],
                }
            ],
            "expressions": [
                {
                    "query_name": "DimCustomer",
                    "description": "Customer transformation query.",
                    "is_staging": False,
                    "target_table": "Customer",
                }
            ],
            "functions": [
                {
                    "name": "fx_CalculateTax",
                    "description": "Computes regional tax rates.",
                    "return_type": "Currency",
                }
            ],
        }

        # 1. Subtitle cleanup and Contextual Subtitle Standardization
        tbl_html = HtmlTableBuilder(model_data["tables"][0], model_data, cfg).build_content()
        self.assertNotIn("Core fact table with all revenue transactions.", tbl_html.split('class="page-subtitle"')[1].split("</p>")[0])
        self.assertIn("Table schema definition, column data dictionary, and relational dependencies.", tbl_html)
        self.assertIn('<div class="kpi-label">Role</div>', tbl_html)

        exp_html = HtmlExpressionBuilder(model_data["expressions"][0], model_data, cfg).build_content()
        self.assertNotIn("Customer transformation query.", exp_html.split('class="page-subtitle"')[1].split("</p>")[0])
        self.assertIn("Power Query M transformation pipeline, staging dependencies, and loaded model impact.", exp_html)
        self.assertIn('<div class="kpi-label">Pipeline Role</div>', exp_html)

        fn_html = HtmlFunctionBuilder(model_data["functions"][0], model_data, cfg).build_content()
        self.assertNotIn("Computes regional tax rates.", fn_html.split('class="page-subtitle"')[1].split("</p>")[0])
        self.assertIn("Parameterized DAX function signature, evaluation logic, and dependent measures.", fn_html)
        self.assertIn('<div class="kpi-label">Return Type</div>', fn_html)

        sample_measure = {
            "name": "Total Sales",
            "table": "Sales",
            "expression": "SUM(Sales[Amount])",
            "description": "Total sales amount.",
            "data_type": "Decimal",
        }
        m_builder = HtmlMeasureBuilder(
            sample_measure,
            model_data,
            cfg,
            project_name="TestModel",
        )
        m_html = m_builder.build_content()
        self.assertIn("DAX expression logic, referenced column bindings, and calculation DAG dependencies.", m_html)
        self.assertIn('<div class="kpi-label">Host Table</div>', m_html)

        # 2. Table Legend includes Snow, Utility, Date, CalcGroup
        self.assertIn("Snow", tbl_html)
        self.assertIn("Utility", tbl_html)
        self.assertIn("Date", tbl_html)
        self.assertIn("CalcGroup", tbl_html)
        self.assertNotIn('>Lookup<', tbl_html)

        # 3. Dataflow Overview Legend Tab
        df_builder = HtmlDataflowOverviewBuilder(model_data, cfg, project_name="TestModel")
        df_html = df_builder.build_content()
        self.assertIn('id="tab-legend"', df_html)
        self.assertIn('Dataflow &amp; ETL Badges &amp; Tags Legend', df_html)
        self.assertIn('badge-etl-loaded">Loaded</span>', df_html)
        self.assertIn('badge-etl-staging">Staging</span>', df_html)
        self.assertIn('badge-etl-param">Param</span>', df_html)
        self.assertIn('badge-etl-func">Func</span>', df_html)
        self.assertIn('badge-etl-inline">Inline</span>', df_html)
        self.assertIn('badge-role-utility">Utility</span>', df_html)

        # 4. TopN measure hyperlink
        page = PageDefinition(
            page_id="p1",
            page_number=1,
            display_name="Overview",
            width=1280.0,
            height=720.0,
            is_hidden=False,
            visuals=[
                VisualDefinition(
                    visual_id="v1",
                    title="Top 10 Regions",
                    visual_type="barChart",
                    calculation_context=CalculationContext(
                        visual_active_filters=[
                            ActiveFilter(
                                table="Geo",
                                field="City",
                                filter_type="TopN",
                                condition="Top 10 by [Units Sold]",
                                is_locked=True,
                                operator="TopN",
                                order_by_table="Calculations",
                                order_by_measure="Units Sold",
                            )
                        ]
                    ),
                )
            ],
        )
        report_model = PBIPReportModel(
            report_name="TestReport",
            format="PBIR",
            source_path="TestReport.Report",
            pages=[page],
        )
        from pbip_doc.docgen.html_builders import HtmlVisualBuilder
        page_html = HtmlVisualBuilder(
            page=page,
            report_model=report_model,
            config=cfg,
            measure_url_resolver=lambda tbl, m: f"../../measures/{tbl}/{m}.html",
        ).build_content()
        self.assertIn('Top 10 by <a href="../../measures/Calculations/Units Sold.html">[Units Sold]</a>', page_html)
        self.assertIn('badge-filter-locked', page_html)

        # 5. CSS Palette Harmonization
        css = get_html_css()
        self.assertIn('--badge-filter-locked-bg:', css)
        self.assertIn('--badge-filter-unlocked-bg:', css)
        self.assertIn('.badge-calc, .badge-pq {', css)
        self.assertIn('color: var(--link-color);', css)
        self.assertIn('--status-active-bg: #ecfdf5;', css)
        self.assertIn('--status-active-text: #065f46;', css)

    def test_card_wrapping_depth_badges_and_markdown_parity(self):
        """Validates card wrapping, neutral depth badges, expression calc cols, and markdown parity."""
        cfg = DocGenConfig()

        # 1. Measure Depth Badges Neutralized (badge-dim)
        meas_data = {
            "name": "Total Profit",
            "table": "Sales",
            "dax_expression": "[Total Revenue] - [Total Cost]",
            "calculation_depth": 2,
            "direct_measure_dependencies": ["Total Revenue", "Total Cost"],
        }
        full_model = {
            "project_name": "TestModel",
            "model_name": "TestModel",
            "tables": [{"name": "Sales", "role": "FACT", "columns": [], "measures": [meas_data]}],
            "measures": [meas_data],
            "relationships": [],
        }
        meas_builder = HtmlMeasureBuilder(meas_data, full_model, cfg, project_name="TestModel")
        meas_html = meas_builder.build_content()
        self.assertIn('<span class="badge badge-dim">Depth 2</span>', meas_html)
        self.assertIn('<td><span class="badge badge-dim">Depth 0</span></td>', meas_html)
        self.assertIn('<td><span class="badge badge-dim">Depth 1+</span></td>', meas_html)

        # 2. Expression Default Layout & Calculated Columns Tab
        from pbip_doc.docgen.layout_engine import DEFAULT_LAYOUT_CONFIG
        expr_tabs = [t["id"] for t in DEFAULT_LAYOUT_CONFIG["expression"]["tabs"]]
        self.assertIn("tab-calc-cols", expr_tabs)

        expr_data = {
            "query_name": "Sales",
            "target_table": "Sales",
            "is_loaded_table": True,
            "full_m_expression": "let Source = Csv.Document() in Source",
            "steps": [{"step_name": "Added Custom", "operation": "Calculated Column", "transformed_column": "Margin", "raw_m_code": "[Revenue] - [Cost]"}],
            "direct_dependencies": [],
        }
        model_with_cols = {
            "project_name": "TestModel",
            "tables": [{
                "name": "Sales",
                "role": "FACT",
                "columns": [{
                    "name": "Margin",
                    "data_type": "Decimal",
                    "origin": "power_query",
                    "m_operation": "Calculated Column",
                    "m_expression": "[Revenue] - [Cost]",
                    "m_step_name": "Added Custom",
                }],
                "measures": [],
            }],
            "expressions": [expr_data],
        }
        b_expr = HtmlExpressionBuilder(expr_data, model_with_cols, cfg, project_name="TestModel")
        expr_html = b_expr.build_content()
        self.assertIn('id="tab-calc-cols"', expr_html)
        self.assertIn('Calculated &amp; Transformed Columns (1)', expr_html)
        self.assertIn('code-pq-col-Margin', expr_html)

        from pbip_doc.docgen.expression_doc import ExpressionDocBuilder
        md_expr = ExpressionDocBuilder(expr_data, model_with_cols, cfg, project_name="TestModel").build_markdown()
        self.assertIn("## Calculated & Transformed Columns (1)", md_expr)
        self.assertIn("| `Margin` | Calculated Column | `Added Custom` |", md_expr)

        # 3. Workspace Catalog Table Card Wrapping & Sidebar-Aligned Header SVGs
        from pbip_doc.codebase_scanner import WorkspaceScanResult, DiscoveredModel, DiscoveredReport
        from pbip_doc.docgen.workspace_engine import WorkspaceDocGenerator
        from pathlib import Path
        m1 = DiscoveredModel(name="Model1", path=Path("test_ws/Model1"), rel_path="Model1/Model1.SemanticModel", raw_name="Model1", model_format="TMDL")
        r1 = DiscoveredReport(name="Report1", path=Path("test_ws/Report1"), rel_path="Report1/Report1.Report", raw_name="Report1", report_format="PBIR")
        scan = WorkspaceScanResult(root_path=Path("test_ws"), models={"m1": m1}, reports={"r1": r1})
        gen = WorkspaceDocGenerator(cfg)
        ws_html = gen._build_workspace_index_html(scan)

        self.assertIn('<div class="content-card">', ws_html)
        self.assertIn('<div class="table-responsive">', ws_html)
        self.assertIn('svg-icon-dataflow table-header-icon', ws_html)
        self.assertIn('svg-icon-datamodel table-header-icon', ws_html)
        self.assertIn('svg-icon-report table-header-icon', ws_html)
        self.assertIn('project-folder-icon table-header-icon', ws_html)

        # 4. Markdown Table Parity
        ws_md = gen._build_workspace_index_markdown(scan)
        self.assertIn("| Project Directory | ETL & Data Pipeline | Semantic Models | Reports & Dashboards |", ws_md)
        self.assertNotIn("Data Lineage & Dependency Matrix", ws_md)
        self.assertNotIn("Power Query Dataflow Inventory", ws_md)
        self.assertIn("| Model Name | Format | Project Directory | Tables | Measures | Dependent Reports |", ws_md)
        self.assertIn("| Report Name | Format | Project Directory | Pages | Bound Semantic Model |", ws_md)
        self.assertNotIn("| Documentation |", ws_md)
        self.assertNotIn("| Link |", ws_md)

    def test_etl_badge_parity_and_nomenclature(self):
        """Verifies complete nomenclature and style parity for ETL badges across sidebar, header, and body."""
        from pbip_doc.docgen.html_layout import get_expression_badge_info, HtmlLayoutBuilder

        # 1. Classification & canonical tuple mapping
        self.assertEqual(get_expression_badge_info("LOADED_TABLE"), ("badge-etl-loaded", "Loaded", "Loaded"))
        self.assertEqual(get_expression_badge_info("STAGING_QUERY"), ("badge-etl-staging", "Staging", "Staging"))
        self.assertEqual(get_expression_badge_info("PARAMETER"), ("badge-etl-param", "Param", "Param"))
        self.assertEqual(get_expression_badge_info("CUSTOM_FUNCTION"), ("badge-etl-func", "Func", "Func"))
        self.assertEqual(get_expression_badge_info("INLINE_TABLE"), ("badge-etl-inline", "Inline", "Inline"))

        # 2. Expression dicts
        e_param = {"query_name": "ServerName", "expression_kind": "parameter", "full_m_expression": '"localhost" meta [IsParameterQuery=true]'}
        e_func = {"query_name": "fxClean", "is_m_function": True, "full_m_expression": "(txt) => Text.Trim(txt)"}
        e_stage = {"query_name": "Stg_Orders", "is_staging": True, "full_m_expression": "let Source = ... in Source"}
        e_load = {"query_name": "DimCust", "is_loaded_table": True, "full_m_expression": "let Source = ... in Source"}
        e_inline = {"query_name": "StatusRef", "is_inline_table": True, "full_m_expression": "#table(...)"}

        for item, exp_cls, exp_lbl in [
            (e_param, "badge-etl-param", "Param"),
            (e_func, "badge-etl-func", "Func"),
            (e_stage, "badge-etl-staging", "Staging"),
            (e_load, "badge-etl-loaded", "Loaded"),
            (e_inline, "badge-etl-inline", "Inline"),
        ]:
            cls, lbl, short = get_expression_badge_info(item)
            self.assertEqual(cls, exp_cls)
            self.assertEqual(lbl, exp_lbl)
            self.assertEqual(short, exp_lbl)

        # 3. Sidebar rendering in HtmlLayoutBuilder
        cfg = DocGenConfig(output_format="html")
        cfg.include_expression_docs = True
        cfg.include_expression_sidebar_chapter = True
        model_data = {
            "name": "TestModel",
            "expressions": [e_param, e_func, e_stage, e_load, e_inline],
            "tables": [],
        }
        layout = HtmlLayoutBuilder(project_name="TestModel", data=model_data, config=cfg)
        sidebar = layout._build_sidebar("index.html", ".")

        # Must contain modern badge-etl classes and aligned short labels
        self.assertIn('class="nav-item-badge badge badge-etl-param">Param</span>', sidebar)
        self.assertIn('class="nav-item-badge badge badge-etl-func">Func</span>', sidebar)
        self.assertIn('class="nav-item-badge badge badge-etl-staging">Staging</span>', sidebar)
        self.assertIn('class="nav-item-badge badge badge-etl-loaded">Loaded</span>', sidebar)
        self.assertIn('class="nav-item-badge badge badge-etl-inline">Inline</span>', sidebar)

        # Obsolete / inconsistent artifacts must be completely gone
        self.assertNotIn('>M</span>', sidebar)
        self.assertNotIn('badge-accent', sidebar)
        self.assertNotIn('badge-primary', sidebar)

        # 4. HtmlExpressionBuilder Title & KPI badge parity
        for item, exp_cls, exp_lbl in [
            (e_param, "badge-etl-param", "Param"),
            (e_func, "badge-etl-func", "Func"),
            (e_stage, "badge-etl-staging", "Staging"),
            (e_load, "badge-etl-loaded", "Loaded"),
            (e_inline, "badge-etl-inline", "Inline"),
        ]:
            builder = HtmlExpressionBuilder(item, model_data, cfg, project_name="TestModel")
            content = builder.build_content()
            # Title badge
            self.assertIn(f'<span class="badge {exp_cls}">{exp_lbl}</span>', content)


class TestHtmlExtensionDocGen(unittest.TestCase):
    """Verifies that configurable HTML extensions (e.g. .aspx) are respected end-to-end."""

    def test_single_model_html_generation_aspx(self):
        cfg = DocGenConfig(
            output_format="html",
            html_extension="aspx",
            include_expression_docs=True,
            include_expression_sidebar_chapter=True,
        )
        sample_model = {
            "model_name": "SalesModel",
            "tables": [
                {
                    "name": "FactOrders",
                    "role": "FACT",
                    "columns": [{"name": "OrderID", "data_type": "Int64"}],
                    "measures": [{"name": "Revenue", "dax_expression": "SUM(FactOrders[Amount])"}],
                },
                {
                    "name": "DimCustomer",
                    "role": "DIM",
                    "columns": [{"name": "CustomerID", "data_type": "Int64"}],
                    "measures": [],
                },
            ],
            "measures": [
                {"name": "Revenue", "table": "FactOrders", "dax_expression": "SUM(FactOrders[Amount])"},
            ],
            "expressions": [
                {"query_name": "Stg_Orders", "is_staging": True, "full_m_expression": "let Source = ... in Source"},
            ],
        }

        gen = HtmlDocGenerator(cfg)
        docs = gen.generate_all_documents(sample_model)

        # 1. Verify file keys
        self.assertIn("index.aspx", docs)
        self.assertIn("tables/FactOrders.aspx", docs)
        self.assertIn("tables/DimCustomer.aspx", docs)
        self.assertIn("measures/FactOrders/Revenue.aspx", docs)
        self.assertIn("etl/index.aspx", docs)
        self.assertIn("etl/Stg_Orders.aspx", docs)

        # No .html file keys should exist
        for k in docs.keys():
            self.assertFalse(k.endswith(".html"), f"Unexpected .html document key: {k}")

        # 2. Verify hyperlinks in content
        index_html = docs["index.aspx"]
        self.assertIn('href="tables/FactOrders.aspx"', index_html)
        self.assertIn('href="tables/DimCustomer.aspx"', index_html)
        self.assertIn('href="measures/FactOrders/Revenue.aspx"', index_html)
        self.assertIn('etl/index.aspx', index_html)
        self.assertNotIn(".html", index_html)

        table_html = docs["tables/FactOrders.aspx"]
        self.assertIn('href="../index.aspx"', table_html)
        self.assertNotIn(".html", table_html)

        measure_html = docs["measures/FactOrders/Revenue.aspx"]
        self.assertIn('href="../../index.aspx"', measure_html)
        self.assertNotIn(".html", measure_html)

        etl_html = docs["etl/Stg_Orders.aspx"]
        self.assertIn('href="../index.aspx"', etl_html)
        self.assertNotIn(".html", etl_html)

    def test_workspace_html_generation_aspx(self):
        from pbip_doc.codebase_scanner import WorkspaceScanResult, DiscoveredModel, DiscoveredReport
        from pbip_doc.docgen.workspace_engine import WorkspaceDocGenerator
        from pbip_doc.report_schema import PBIPReportModel, PageDefinition, VisualDefinition, CalculationContext

        cfg = DocGenConfig(
            output_format="html",
            html_extension=".ASPX",  # Test robust normalization of leading dot and uppercase
            include_visual_docs=True,
            include_expression_docs=True,
            include_expression_sidebar_chapter=True,
        )

        p1 = PageDefinition(page_id="Page1", display_name="Overview", page_number=1, visuals=[])
        rep_obj = PBIPReportModel(report_name="SalesReport", format="PBIR", source_path="test_ws/SalesReport", pages=[p1])

        m1 = DiscoveredModel(
            name="SalesModel",
            path=Path("test_ws/SalesModel"),
            rel_path="SalesModel/SalesModel.SemanticModel",
            raw_name="SalesModel",
            model_format="TMDL",
            tables=["Sales"],
            measures={"Total_Sales": "Sales"},
            model_obj=type("ModelObj", (), {
                "to_dict": lambda s: {
                    "tables": [{"name": "Sales", "columns": [], "measures": []}],
                    "measures": [{"name": "Total_Sales", "table": "Sales"}],
                    "expressions": [],
                },
                "expressions": [],
                "bound_reports_count": 0,
                "bound_reports_info": [],
            })(),
        )
        r1 = DiscoveredReport(
            name="SalesReport",
            path=Path("test_ws/SalesReport"),
            rel_path="SalesReport/SalesReport.Report",
            raw_name="SalesReport",
            report_format="PBIR",
            page_names=["Overview"],
            report_obj=rep_obj,
            bound_model_name="SalesModel",
        )
        scan = WorkspaceScanResult(
            root_path=Path("test_ws"),
            models={"m1": m1},
            reports={"r1": r1},
        )

        gen = WorkspaceDocGenerator(cfg)
        docs = gen.generate_all_html_documents(scan)

        # 1. Master index and sub-artifacts must be .aspx
        self.assertIn("index.aspx", docs)
        self.assertIn("models/SalesModel/index.aspx", docs)
        self.assertIn("models/SalesModel/tables/Sales.aspx", docs)
        self.assertIn("reports/SalesReport/index.aspx", docs)
        self.assertIn("reports/SalesReport/visuals/Overview.aspx", docs)

        for k in docs.keys():
            if not k.endswith(".css") and not k.endswith(".svg"):
                self.assertFalse(k.endswith(".html"), f"Unexpected .html file key in workspace docs: {k}")

        # 2. Workspace index hyperlinks
        ws_idx = docs["index.aspx"]
        self.assertIn('href="models/SalesModel/index.aspx"', ws_idx)
        self.assertIn('href="reports/SalesReport/index.aspx"', ws_idx)
        self.assertNotIn(".html", ws_idx)

        # 3. Report overview hyperlinks
        rep_idx = docs["reports/SalesReport/index.aspx"]
        self.assertIn('href="../../index.aspx"', rep_idx)
        self.assertIn('href="visuals/Overview.aspx"', rep_idx)
        self.assertNotIn(".html", rep_idx)

        # 4. Report visual page breadcrumbs
        vis_page = docs["reports/SalesReport/visuals/Overview.aspx"]
        self.assertIn('href="../../../index.aspx"', vis_page)
        self.assertIn('href="../index.aspx"', vis_page)
        self.assertNotIn(".html", vis_page)

    def test_cli_html_extension_option(self):
        from pbip_doc.cli import build_parser, _load_cli_config

        parser = build_parser()
        args = parser.parse_args(["docgen", "fake_path", "--html-extension", "aspx"])
        self.assertEqual(args.html_extension, "aspx")

        config = _load_cli_config(args)
        self.assertEqual(config.html_extension, "aspx")
        self.assertEqual(config.clean_html_extension, "aspx")
        self.assertEqual(config.html_ext_suffix, ".aspx")

    def test_cli_default_and_explicit_output_format(self):
        from pbip_doc.cli import build_parser, _load_cli_config

        parser = build_parser()

        # 1. Default invocation (no format specified) -> defaults to "html"
        args_default = parser.parse_args(["docgen", "dummy_path"])
        self.assertIsNone(args_default.format)
        cfg_default = _load_cli_config(args_default)
        self.assertEqual(cfg_default.output_format, "html")

        # 2. Explicit -f markdown
        args_md = parser.parse_args(["docgen", "dummy_path", "-f", "markdown"])
        self.assertEqual(args_md.format, "markdown")
        cfg_md = _load_cli_config(args_md)
        self.assertEqual(cfg_md.output_format, "markdown")

        # 3. Explicit -f both
        args_both = parser.parse_args(["docgen", "dummy_path", "-f", "both"])
        self.assertEqual(args_both.format, "both")
        cfg_both = _load_cli_config(args_both)
        self.assertEqual(cfg_both.output_format, "both")

        # 4. Explicit --format html
        args_html = parser.parse_args(["docgen", "dummy_path", "--format", "html"])
        self.assertEqual(args_html.format, "html")
        cfg_html = _load_cli_config(args_html)
        self.assertEqual(cfg_html.output_format, "html")


class TestHtmlThemePropagation(unittest.TestCase):
    def test_css_dark_token_parity_and_color_scheme(self):
        import re

        css = get_html_css()
        self.assertIn("color-scheme: light;", css)
        self.assertIn(':root[data-theme="light"] {', css)
        self.assertIn(':root[data-theme="dark"],', css)
        self.assertIn("--badge-pk-text: #1e3a8a;", css)
        self.assertIn("--badge-fk-text: #475569;", css)
        self.assertIn(".badge-pk {", css)
        self.assertIn(".badge-fk {", css)

        m_media = re.search(
            r'@media \(prefers-color-scheme: dark\) \{\s*:root:not\(\[data-theme="light"\]\) \{(.*?)\n  \}\s*\}',
            css,
            re.S,
        )
        m_data = re.search(r':root\[data-theme="dark"\],\s*\[data-theme="dark"\] \{(.*?)\n\}', css, re.S)
        self.assertIsNotNone(m_media)
        self.assertIsNotNone(m_data)

        def _extract_props(block: str):
            return dict(re.findall(r'(--[\w-]+|color-scheme)\s*:\s*([^;]+);', block))

        media_props = _extract_props(m_media.group(1))
        data_props = _extract_props(m_data.group(1))
        self.assertEqual(media_props.get("color-scheme"), "dark")
        self.assertEqual(data_props.get("color-scheme"), "dark")
        self.assertEqual(media_props.get("--badge-pk-text"), "#93c5fd")
        self.assertEqual(media_props.get("--badge-fk-text"), "#cbd5e1")
        self.assertEqual(
            media_props,
            data_props,
            "Dark CSS variables in @media and [data-theme=\"dark\"] must stay 1:1 aligned",
        )

    def test_get_html_theme_attr_and_wrap_page(self):
        from pbip_doc.docgen.html_layout import get_html_theme_attr, resolve_html_theme_mode

        self.assertIsNone(resolve_html_theme_mode(None))
        self.assertIsNone(resolve_html_theme_mode("auto"))
        self.assertIsNone(resolve_html_theme_mode("  AUTO "))
        self.assertEqual(resolve_html_theme_mode("Light "), "light")
        self.assertEqual(resolve_html_theme_mode(" DARK"), "dark")

        self.assertEqual(get_html_theme_attr("auto"), "")
        self.assertEqual(get_html_theme_attr(None), "")
        self.assertEqual(get_html_theme_attr("light"), ' data-theme="light"')
        self.assertEqual(get_html_theme_attr("dark"), ' data-theme="dark"')

        sample_data = {
            "model_name": "ThemeModel",
            "tables": [{"name": "Sales", "role": "FACT", "columns": [], "measures": []}],
            "measures": [],
        }
        for theme, expected_tag in [
            ("auto", '<html lang="en">'),
            ("light", '<html lang="en" data-theme="light">'),
            ("dark", '<html lang="en" data-theme="dark">'),
        ]:
            cfg = DocGenConfig(output_format="html", html_theme=theme)
            layout = HtmlLayoutBuilder("ThemeProj", sample_data, cfg)
            html_out = layout.wrap_page("index.html", "Overview", [("Home", None)], "<p>Hi</p>")
            self.assertIn(expected_tag, html_out)

    def test_single_model_html_theme_propagation(self):
        model_data = {
            "model_name": "GalaxyThemeModel",
            "tables": [
                {
                    "name": "FactSales",
                    "role": "FACT",
                    "columns": [
                        {"name": "DateKey", "dataType": "int64"},
                        {"name": "Amount", "dataType": "decimal"},
                    ],
                    "measures": [],
                },
                {
                    "name": "FactBudget",
                    "role": "FACT",
                    "columns": [
                        {"name": "DateKey", "dataType": "int64"},
                        {"name": "Budget", "dataType": "decimal"},
                    ],
                    "measures": [],
                },
                {
                    "name": "DimDate",
                    "role": "DATE",
                    "columns": [{"name": "DateKey", "dataType": "int64"}],
                    "measures": [],
                },
                {
                    "name": "ParamTable",
                    "role": "UTILITY",
                    "columns": [{"name": "Param", "dataType": "string"}],
                    "measures": [],
                },
            ],
            "relationships": [
                {
                    "from_table": "FactSales",
                    "from_column": "DateKey",
                    "to_table": "DimDate",
                    "to_column": "DateKey",
                    "cardinality": "N:1",
                    "is_active": True,
                },
                {
                    "from_table": "FactBudget",
                    "from_column": "DateKey",
                    "to_table": "DimDate",
                    "to_column": "DateKey",
                    "cardinality": "N:1",
                    "is_active": True,
                },
            ],
            "measures": [],
            "expressions": [],
        }

        # Light theme
        gen_light = HtmlDocGenerator(DocGenConfig(output_format="html", html_theme="light"))
        docs_light = gen_light.generate_all_documents(model_data)
        idx_light = docs_light["index.html"]
        tbl_light = docs_light["tables/FactSales.html"]
        self.assertIn('<html lang="en" data-theme="light">', idx_light)
        self.assertIn('<html lang="en" data-theme="light">', tbl_light)
        self.assertIn('class="model-relationship-diagram theme-force-light"', idx_light)
        self.assertIn('class="model-relationship-diagram theme-force-light"', tbl_light)
        self.assertNotIn('class="model-relationship-diagram theme-force-dark"', idx_light)
        self.assertNotIn('class="model-relationship-diagram theme-force-dark"', tbl_light)
        self.assertIn('@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) #page-tab-', idx_light)
        self.assertIn('@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) #sc-tab-galaxy:checked', idx_light)
        self.assertNotIn('@media (prefers-color-scheme: dark) { #page-tab-', idx_light)
        self.assertNotIn('@media (prefers-color-scheme: dark) { #sc-tab-', idx_light)

        # Dark theme
        gen_dark = HtmlDocGenerator(DocGenConfig(output_format="html", html_theme="dark"))
        docs_dark = gen_dark.generate_all_documents(model_data)
        idx_dark = docs_dark["index.html"]
        tbl_dark = docs_dark["tables/FactSales.html"]
        self.assertIn('<html lang="en" data-theme="dark">', idx_dark)
        self.assertIn('<html lang="en" data-theme="dark">', tbl_dark)
        self.assertIn('class="model-relationship-diagram theme-force-dark"', idx_dark)
        self.assertIn('class="model-relationship-diagram theme-force-dark"', tbl_dark)
        self.assertNotIn('class="model-relationship-diagram theme-force-light"', idx_dark)
        self.assertNotIn('class="model-relationship-diagram theme-force-light"', tbl_dark)
        self.assertIn(':root[data-theme="dark"] #page-tab-', idx_dark)
        self.assertIn(':root[data-theme="dark"] #sc-tab-galaxy:checked', idx_dark)
        self.assertIn(':root[data-theme="dark"] #sc-tab-utility:checked', idx_dark)

        # Auto theme
        gen_auto = HtmlDocGenerator(DocGenConfig(output_format="html", html_theme="auto"))
        docs_auto = gen_auto.generate_all_documents(model_data)
        idx_auto = docs_auto["index.html"]
        tbl_auto = docs_auto["tables/FactSales.html"]
        self.assertIn('<html lang="en">', idx_auto)
        self.assertNotIn("data-theme=", idx_auto.split("<head>", 1)[0])
        self.assertNotIn("data-theme=", tbl_auto.split("<head>", 1)[0])
        self.assertIn('class="model-relationship-diagram "', idx_auto)
        self.assertIn('class="model-relationship-diagram "', tbl_auto)
        self.assertNotIn('class="model-relationship-diagram theme-force-light"', idx_auto)
        self.assertNotIn('class="model-relationship-diagram theme-force-dark"', idx_auto)
        self.assertNotIn('class="model-relationship-diagram theme-force-light"', tbl_auto)
        self.assertNotIn('class="model-relationship-diagram theme-force-dark"', tbl_auto)

    def test_table_legend_pk_fk_badges(self):
        tbl_builder = HtmlTableBuilder(
            table_data={"name": "Sales", "role": "FACT", "columns": [], "measures": []},
            full_model={"tables": [{"name": "Sales", "role": "FACT", "columns": [], "measures": []}], "relationships": []},
            config=DocGenConfig(output_format="html"),
        )
        legend_sec = tbl_builder._section_badge_legend()
        self.assertIsNotNone(legend_sec)
        self.assertIn('<span class="badge badge-pk">PK</span>', legend_sec.content)
        self.assertIn('<span class="badge badge-fk">FK</span>', legend_sec.content)
        self.assertNotIn("col-badge-text-pk", legend_sec.content)
        self.assertNotIn("col-badge-text-fk", legend_sec.content)

    def test_svg_theme_scoping_and_legend_consistency(self):
        import re
        from pbip_doc.docgen.relationship_diagram import RelationshipSvgGenerator

        model_data = {
            "model_name": "SvgLegendModel",
            "tables": [
                {"name": "Sales", "role": "FACT", "columns": [{"name": "DateKey", "dataType": "int64"}], "measures": []},
                {"name": "Date", "role": "DATE", "columns": [{"name": "DateKey", "dataType": "int64"}], "measures": []},
            ],
            "relationships": [
                {"from_table": "Sales", "from_column": "DateKey", "to_table": "Date", "to_column": "DateKey", "cardinality": "N:1", "is_active": True},
            ],
        }
        svg = RelationshipSvgGenerator(model_data).generate_model_svg(theme_mode="light")

        # 1. @media (prefers-color-scheme: dark) must be scoped against [data-theme="light"] and .theme-force-light
        m_media = re.search(r'@media \(prefers-color-scheme: dark\) \{(.*?)\n    \}', svg, re.S)
        self.assertIsNotNone(m_media)
        media_body = m_media.group(1)
        self.assertNotIn(":root, .model-relationship-diagram {", media_body)
        self.assertIn(':root.model-relationship-diagram:not([data-theme="light"]):not(.theme-force-light)', media_body)
        self.assertIn(':root:not([data-theme="light"]) .model-relationship-diagram:not(.theme-force-light)', media_body)
        # Ensure no bare unscoped .canvas-bg / .header-fact lines exist inside @media
        for line in media_body.splitlines():
            stripped = line.strip()
            if stripped.startswith("."):
                self.fail(f"Unscoped selector inside SVG @media dark block: {stripped}")

        # 2. Forced light includes all 6 high-contrast .diagram-legend rules AFTER generic rules
        pos_generic_bidi = svg.find('.theme-force-light .bidi-badge-text,')
        self.assertNotEqual(pos_generic_bidi, -1)
        for sel, expected_val in [
            ('.diagram-legend .legend-text', 'fill: #1e293b !important;'),
            ('.diagram-legend .cardinality-badge', 'fill: #0f172a !important;'),
            ('.diagram-legend .bidi-badge-text', 'fill: #0f172a !important;'),
            ('.diagram-legend .bidi-badge-bg', 'fill: #ffffff !important; stroke: #64748b !important;'),
            ('.diagram-legend .rel-path', 'stroke: #64748b !important;'),
            ('.diagram-legend .port-dot', 'fill: #64748b !important; stroke: #ffffff !important;'),
        ]:
            rule_marker = f':root[data-theme="light"] .model-relationship-diagram {sel},'
            pos_legend = svg.find(rule_marker)
            self.assertNotEqual(pos_legend, -1, f"Missing forced-light legend rule for {sel}")
            self.assertGreater(pos_legend, pos_generic_bidi, f"Forced-light {sel} must follow generic rules")
            self.assertIn(expected_val, svg[pos_legend:pos_legend + 350])

        # 3. Light default PK/FK/Calc badges align with forced-light transparent bordered style
        self.assertIn('.col-badge-bg-pk { fill: transparent; stroke: #1e3a8a; stroke-width: 0.8px; rx: 2px; }', svg)
        self.assertIn('.col-badge-text-pk { fill: #1e3a8a; font-weight: 700; }', svg)
        self.assertIn('.col-badge-bg-fk { fill: transparent; stroke: #475569; stroke-width: 0.8px; rx: 2px; }', svg)
        self.assertIn('.col-badge-text-fk { fill: #475569; font-weight: 700; }', svg)
        self.assertIn('.col-badge-bg-calc { fill: transparent; stroke: #6b21a8; stroke-width: 0.8px; rx: 2px; }', svg)
        self.assertIn('.col-badge-text-calc { fill: #6b21a8; font-weight: 700; }', svg)

    def test_html_function_builder_variant_fallback_and_clean_parameter_names(self):
        """Verifies HtmlFunctionBuilder defaults empty return_type to Variant and renders clean parameter <code> tags."""
        cfg = DocGenConfig(output_format="html")
        sample_model = {"model_name": "Sales BI", "tables": [], "measures": []}
        fn_data = {
            "name": "SafeDivide",
            "expression": "DIVIDE(Numerator, Denominator)",
            "parameters": [
                {"name": "Numerator", "data_type": "Double", "description": "Dividend"},
                {"name": "`Denominator`", "data_type": "", "description": ""},
            ],
            "parameters_signature": "(Numerator: Double, Denominator)",
            "return_type": "",
            "downstream_measures": [],
        }
        builder = HtmlFunctionBuilder(fn_data, sample_model, cfg, project_name="Sales BI")
        html_out = builder.build_content()

        self.assertIn("<code>Variant</code>", html_out)
        self.assertIn("<td><code>Numerator</code></td>", html_out)
        self.assertIn("<td><code>Denominator</code></td>", html_out)
        self.assertNotIn("`Numerator`", html_out)
        self.assertNotIn("`Denominator`", html_out)

    def test_html_index_bound_reports_count_with_report_model(self):
        """Verifies HtmlIndexBuilder reports 1 Bound Report when model_data defaults bound_reports_count to 0 and report is attached."""
        cfg = DocGenConfig(output_format="html")
        model_with_zero_default = {
            "model_name": "Sales BI",
            "tables": [],
            "measures": [],
            "bound_reports_count": 0,
        }
        fake_report = type("FakeReport", (), {"report_name": "SalesReport", "pages": []})()
        idx_builder = HtmlIndexBuilder(model_with_zero_default, cfg, report_model=fake_report, project_name="Sales BI")
        html_out = idx_builder.build_content()
        self.assertIn('<div class="kpi-label">Bound Reports</div>', html_out)
        self.assertIn('<div class="kpi-value">1</div>', html_out)
        self.assertIn('<div class="kpi-sub">Consuming Report</div>', html_out)


if __name__ == "__main__":
    unittest.main()
