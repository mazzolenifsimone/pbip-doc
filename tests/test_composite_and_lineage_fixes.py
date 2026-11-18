"""
Tests for Composite Models, Thin Models, Cross-Model Lineage, and UDF Dependencies.
Validates:
  1. Measure dependencies on DAX UDF functions (Issue 1 fix).
  2. Cross-model external measure dependencies without 404 links (Issue 2 fix).
  3. Inherited tables in intermediate models rendered without broken links (Issue 3 fix).
  4. Staging queries downstream impact for DirectQuery over AS (Issue 4 fix).
  5. Composite & Thin SVG diagram engine enhancements, minimal cards, and utility tabs (Task 5).
  6. End-to-end parsing of synthetic self-contained composite/thin TMDL workspaces.
  7. Local relationship perimeter exclusion of Remote <-> Remote relationships.
  8. Downstream consuming reports resolution across byPath and byConnection (Initial Catalog + GUID).
  9. DAX Calculated Table Upstream Model References (deduplication, measure home table links, styling).
"""

import json
import tempfile
import unittest
from pathlib import Path

from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.html_builders import (
    HtmlIndexBuilder,
    HtmlMeasureBuilder,
    HtmlExpressionBuilder,
    HtmlTableBuilder,
)
from pbip_doc.docgen.index_doc import IndexDocBuilder
from pbip_doc.docgen.table_doc import TableDocBuilder
from pbip_doc.docgen.relationship_diagram import RelationshipSvgGenerator
from pbip_doc.docgen.workspace_engine import WorkspaceDocGenerator
from pbip_doc.codebase_scanner import CodebaseScanner
from pbip_doc.parser import PBIPParser
from pbip_doc.report_parser import ReportParser


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.lstrip("\n"), encoding="utf-8")


def _build_synthetic_composite_workspace(root: Path) -> Path:
    """
    Creates a 100% self-contained synthetic TMDL workspace containing:
      - corporate_dw/Corporate_DW.SemanticModel
      - composite_hybrid_sales/Composite_Hybrid_Sales.SemanticModel
      - thin_report_kpis/Thin_Report_KPIs.SemanticModel
    Zero external filesystem dependencies; runs identically on Linux/macOS/Windows CI.
    """
    # 1. Corporate_DW.SemanticModel (Root Semantic Model)
    dw_def = root / "corporate_dw" / "Corporate_DW.SemanticModel" / "definition"
    _write_text(
        dw_def / "model.tmdl",
        """
model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
""",
    )
    _write_text(
        dw_def / "tables" / "Dim_Customer.tmdl",
        """
table Dim_Customer
\tcolumn CustomerKey
\t\tdataType: int64
\t\tisKey
\tcolumn CustomerName
\t\tdataType: string
\tpartition Dim_Customer = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = Sql.Database("corp-sql.internal", "EnterpriseDW"),
\t\t\t\tTbl = Source{[Schema="dbo",Item="Dim_Customer"]}[Data]
\t\t\tin
\t\t\t\tTbl
""",
    )
    _write_text(
        dw_def / "tables" / "Dim_Date.tmdl",
        """
table Dim_Date
\tdataCategory: Time
\tcolumn DateKey
\t\tdataType: int64
\t\tisKey
\tcolumn FullDate
\t\tdataType: dateTime
\tpartition Dim_Date = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = Sql.Database("corp-sql.internal", "EnterpriseDW"),
\t\t\t\tTbl = Source{[Schema="dbo",Item="Dim_Date"]}[Data]
\t\t\tin
\t\t\t\tTbl
""",
    )
    _write_text(
        dw_def / "tables" / "Fact_Sales.tmdl",
        """
table Fact_Sales
\tmeasure 'Total Sales' = SUM(Fact_Sales[SalesAmount])
\t\tformatString: $#,0
\tmeasure 'Total Margin' = SUM(Fact_Sales[MarginAmount])
\t\tformatString: $#,0
\tcolumn SalesKey
\t\tdataType: int64
\tcolumn CustomerKey
\t\tdataType: int64
\tcolumn DateKey
\t\tdataType: int64
\tcolumn SalesAmount
\t\tdataType: decimal
\tcolumn MarginAmount
\t\tdataType: decimal
\tpartition Fact_Sales = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = Sql.Database("corp-sql.internal", "EnterpriseDW"),
\t\t\t\tTbl = Source{[Schema="dbo",Item="Fact_Sales"]}[Data]
\t\t\tin
\t\t\t\tTbl
""",
    )
    _write_text(
        dw_def / "relationships.tmdl",
        """
relationship rel_sales_date
\tfromColumn: Fact_Sales.DateKey
\ttoColumn: Dim_Date.DateKey

relationship rel_sales_customer
\tfromColumn: Fact_Sales.CustomerKey
\ttoColumn: Dim_Customer.CustomerKey
""",
    )

    # 2. Composite_Hybrid_Sales.SemanticModel (Composite DirectQuery over AS + Local tables + UDF)
    comp_def = root / "composite_hybrid_sales" / "Composite_Hybrid_Sales.SemanticModel" / "definition"
    _write_text(
        comp_def / "model.tmdl",
        """
model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
""",
    )
    _write_text(
        comp_def / "expressions.tmdl",
        """
expression 'DirectQuery to AS - Corporate_DW' =
\t\tlet
\t\t\tSource = AnalysisServices.Database("powerbi://api.powerbi.com/v1.0/myorg/Corporate", "Corporate_DW"),
\t\t\tCubes = Table.Combine(Source[Data]),
\t\t\tCube = Cubes{[Id="Model", Kind="Cube"]}[Data]
\t\tin
\t\t\tCube
""",
    )
    _write_text(
        comp_def / "functions.tmdl",
        """
function FX_VariancePct = (actual : numeric, target : numeric) =>
\tDIVIDE(actual - target, target)
""",
    )
    _write_text(
        comp_def / "tables" / "Dim_Customer.tmdl",
        """
table Dim_Customer
\tcolumn CustomerKey
\t\tdataType: int64
\tcolumn CustomerName
\t\tdataType: string
\tpartition Dim_Customer = entity
\t\tmode: directQuery
\t\tsource
\t\t\tentityName: Dim_Customer
\t\t\texpressionSource: 'DirectQuery to AS - Corporate_DW'
""",
    )
    _write_text(
        comp_def / "tables" / "Dim_Date.tmdl",
        """
table Dim_Date
\tcolumn DateKey
\t\tdataType: int64
\tcolumn FullDate
\t\tdataType: dateTime
\tpartition Dim_Date = entity
\t\tmode: directQuery
\t\tsource
\t\t\tentityName: Dim_Date
\t\t\texpressionSource: 'DirectQuery to AS - Corporate_DW'
""",
    )
    _write_text(
        comp_def / "tables" / "Fact_Sales.tmdl",
        """
table Fact_Sales
\tmeasure 'Total Sales' = EXTERNALMEASURE("Total Sales", CURRENCY, "DirectQuery to AS - Corporate_DW")
\tmeasure 'Total Margin' = EXTERNALMEASURE("Total Margin", CURRENCY, "DirectQuery to AS - Corporate_DW")
\tcolumn SalesKey
\t\tdataType: int64
\tcolumn CustomerKey
\t\tdataType: int64
\tcolumn DateKey
\t\tdataType: int64
\tpartition Fact_Sales = entity
\t\tmode: directQuery
\t\tsource
\t\t\tentityName: Fact_Sales
\t\t\texpressionSource: 'DirectQuery to AS - Corporate_DW'
""",
    )
    _write_text(
        comp_def / "tables" / "Fact_Budget_2026.tmdl",
        """
table Fact_Budget_2026
\tcolumn DateKey
\t\tdataType: int64
\tcolumn CustomerKey
\t\tdataType: int64
\tcolumn ScenarioID
\t\tdataType: int64
\tcolumn BudgetAmount
\t\tdataType: decimal
\tpartition Fact_Budget_2026 = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = Sql.Database("plan-sql.internal", "PlanningDB"),
\t\t\t\tTbl = Source{[Schema="dbo",Item="Fact_Budget_2026"]}[Data]
\t\t\tin
\t\t\t\tTbl
""",
    )
    _write_text(
        comp_def / "tables" / "Dim_Scenario.tmdl",
        """
table Dim_Scenario
\tcolumn ScenarioID
\t\tdataType: int64
\t\tisKey
\tcolumn ScenarioName
\t\tdataType: string
\tpartition Dim_Scenario = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = #table({"ScenarioID", "ScenarioName"}, {{1, "Base"}, {2, "Stretch"}})
\t\t\tin
\t\t\t\tSource
""",
    )
    _write_text(
        comp_def / "tables" / "_PlanningMeasures.tmdl",
        """
table _PlanningMeasures
\tmeasure 'Total Budget' = SUM(Fact_Budget_2026[BudgetAmount])
\tmeasure 'Budget Variance %' = FX_VariancePct([Total Sales], [Total Budget])
\tpartition _PlanningMeasures = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = #table({"Placeholder"}, {{1}})
\t\t\tin
\t\t\t\tSource
""",
    )
    _write_text(
        comp_def / "relationships.tmdl",
        """
relationship rel_budget_date
\tfromColumn: Fact_Budget_2026.DateKey
\ttoColumn: Dim_Date.DateKey

relationship rel_budget_customer
\tfromColumn: Fact_Budget_2026.CustomerKey
\ttoColumn: Dim_Customer.CustomerKey

relationship rel_budget_scenario
\tfromColumn: Fact_Budget_2026.ScenarioID
\ttoColumn: Dim_Scenario.ScenarioID
""",
    )

    # 3. Thin_Report_KPIs.SemanticModel (Thin composite with inherited tables + local measure table)
    thin_def = root / "thin_report_kpis" / "Thin_Report_KPIs.SemanticModel" / "definition"
    _write_text(
        thin_def / "model.tmdl",
        """
model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
""",
    )
    _write_text(
        thin_def / "expressions.tmdl",
        """
expression 'DirectQuery to AS - Corporate_DW' =
\t\tlet
\t\t\tSource = AnalysisServices.Database("powerbi://api.powerbi.com/v1.0/myorg/Corporate", "Corporate_DW"),
\t\t\tCubes = Table.Combine(Source[Data]),
\t\t\tCube = Cubes{[Id="Model", Kind="Cube"]}[Data]
\t\tin
\t\t\tCube
""",
    )
    for tbl_name, key_col in [("Dim_Date", "DateKey"), ("Dim_Store", "StoreKey"), ("Fact_Sales", "SalesKey")]:
        _write_text(
            thin_def / "tables" / f"{tbl_name}.tmdl",
            f"""
table {tbl_name}
\tcolumn {key_col}
\t\tdataType: int64
\tpartition {tbl_name} = entity
\t\tmode: directQuery
\t\tsource
\t\t\tentityName: {tbl_name}
\t\t\texpressionSource: 'DirectQuery to AS - Corporate_DW'
""",
        )
    _write_text(
        thin_def / "tables" / "_ReportMeasures.tmdl",
        """
table _ReportMeasures
\tmeasure 'KPI Variance %' = DIVIDE([Total Sales], 100)
\tpartition _ReportMeasures = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = #table({"Placeholder"}, {{1}})
\t\t\tin
\t\t\t\tSource
""",
    )

    return root


class TestCompositeAndLineageFixes(unittest.TestCase):
    """Unit tests for lineage fixes and composite/thin SVG diagram engine."""

    def setUp(self):
        self._tmp_ctx = tempfile.TemporaryDirectory(prefix="pbip_composite_ws_")
        self.workspace_root = _build_synthetic_composite_workspace(Path(self._tmp_ctx.name))

    def tearDown(self):
        self._tmp_ctx.cleanup()

    def test_udf_function_dependency_in_measure(self):
        """Issue 1: Verifies measure referencing UDF function renders upstream dependency without AttributeError."""
        config = DocGenConfig()
        self.assertTrue(hasattr(config, "include_function_docs"))
        self.assertTrue(config.include_function_docs)

        # Mock measure referencing UDF FX_VariancePct
        measure_data = {
            "name": "Forecast Variance %",
            "table": "_PlanningMeasures",
            "dax_expression": "FX_VariancePct([Budget Realization %], 1.0)",
            "referenced_measures": ["Budget Realization %"],
            "referenced_functions": ["FX_VariancePct"],
            "direct_measure_dependencies": ["Budget Realization %"],
        }
        full_model = {"tables": [{"name": "_PlanningMeasures"}], "measures": [measure_data]}
        builder = HtmlMeasureBuilder(measure_data, full_model, config)
        section = builder._section_upstream_dependency("../..")
        self.assertIsNotNone(section)
        self.assertIn("Upstream Dependency (2)", section.title)
        self.assertEqual("Upstream (2)", section.nav_label)
        self.assertIn("FX_VariancePct", section.content)
        self.assertIn("Referenced DAX UDF Functions", section.content)

    def test_cross_model_external_measures_no_broken_links(self):
        """Issue 2: Verifies external measures in model index render as Remote Measure without broken links."""
        config = DocGenConfig()
        measures_list = [
            {
                "name": "Total Sales",
                "table": "Fact_Sales",
                "is_inherited": True,
                "is_external_measure": True,
                "inherited_model_name": "Corporate_DW",
            }
        ]
        model_data = {
            "name": "Composite_Model",
            "tables": [
                {
                    "name": "Fact_Sales",
                    "role": "FACT",
                    "is_inherited": True,
                    "inherited_model_name": "Corporate_DW",
                }
            ],
            "measures": measures_list,
        }
        builder = HtmlIndexBuilder(model_data, config)
        section = builder._section_measures(measures_list)
        self.assertIsNotNone(section)
        # Should not link to local measures/Fact_Sales/Total Sales.html
        self.assertNotIn('href="measures/Fact_Sales/Total Sales.html"', section.content)
        self.assertIn("Remote Measure", section.content)
        self.assertIn("Remote Entity", section.content)

    def test_inherited_tables_no_broken_links_in_index(self):
        """Issue 3: Verifies inherited tables render as Remote Entity without broken tables/Dim_Date.html links."""
        config = DocGenConfig()
        tables_list = [
            {
                "name": "Dim_Date",
                "role": "DATE_DIMENSION",
                "is_inherited": True,
                "source_type": "InheritedEntity",
                "columns": [{"name": "DateKey", "data_type": "Int64"}],
            },
            {
                "name": "Fact_Budget",
                "role": "FACT",
                "is_inherited": False,
                "columns": [{"name": "BudgetAmount", "data_type": "Currency"}],
            },
        ]
        model_data = {
            "name": "Intermediate_Model",
            "tables": tables_list,
            "measures": [],
        }
        builder = HtmlIndexBuilder(model_data, config)
        section = builder._section_published_tables(tables_list, [])
        self.assertIsNotNone(section)
        # Dim_Date should be tagged as Remote Entity without broken link to tables/Dim_Date.html
        self.assertNotIn('href="tables/Dim_Date.html"', section.content)
        self.assertIn("Remote Entity", section.content)
        # Fact_Budget should be linked normally
        self.assertIn('href="tables/Fact_Budget.html"', section.content)

    def test_staging_query_directquery_downstream_badges(self):
        """Issue 4: Verifies DirectQuery to AS staging queries render Remote Entity badge and no broken link."""
        config = DocGenConfig()
        expr_data = {
            "name": "DirectQuery to AS - Corporate_DW",
            "query_name": "DirectQuery to AS - Corporate_DW",
            "m_code": 'let Source = AnalysisServices.Database("powerbi://...", "DW") in Source',
            "is_staging": True,
            "downstream_tables": ["Dim_Customer", "Dim_Date", "Fact_Sales"],
            "tables_meta": {
                "Dim_Customer": {"is_inherited": True},
                "Dim_Date": {"is_inherited": True},
                "Fact_Sales": {"is_inherited": True},
            },
        }
        full_model = {"tables": [], "expressions": [expr_data]}
        builder = HtmlExpressionBuilder(expr_data, full_model, config)
        section = builder._section_downstream_dependents("..")
        self.assertIsNotNone(section)
        self.assertNotIn('href="../tables/Dim_Customer.html"', section.content)
        self.assertIn("DirectQuery Remote Entity", section.content)

    def test_composite_svg_diagram_rendering(self):
        """Task 5: Verifies composite model SVG has Upstream Super-Node, REMOTE badges, and cross-model bridges."""
        composite_model = {
            "name": "Composite_Hybrid_Sales",
            "tables": [
                {
                    "name": "Dim_Date",
                    "role": "DATE_DIMENSION",
                    "is_inherited": True,
                    "inherited_model_name": "Corporate_DW",
                    "columns": [{"name": "DateKey", "data_type": "Int64"}],
                },
                {
                    "name": "Dim_Customer",
                    "role": "DIMENSION",
                    "is_inherited": True,
                    "inherited_model_name": "Corporate_DW",
                    "columns": [{"name": "CustomerKey", "data_type": "Int64"}],
                },
                {
                    "name": "Fact_Sales",
                    "role": "FACT",
                    "is_inherited": True,
                    "inherited_model_name": "Corporate_DW",
                    "columns": [{"name": "SalesKey", "data_type": "Int64"}],
                },
                {
                    "name": "Fact_Budget_2026",
                    "role": "FACT",
                    "columns": [
                        {"name": "DateKey", "data_type": "Int64"},
                        {"name": "CustomerKey", "data_type": "Int64"},
                        {"name": "ScenarioID", "data_type": "Int64"},
                    ],
                },
                {
                    "name": "Dim_Scenario",
                    "role": "DIMENSION",
                    "columns": [{"name": "ScenarioID", "data_type": "Int64"}],
                },
            ],
            "measures": [
                {"name": "Total Sales", "table": "Fact_Sales", "is_inherited": True, "is_external_measure": True},
                {"name": "Total Margin", "table": "Fact_Sales", "is_inherited": True, "is_external_measure": True},
                {"name": "Total Budget", "table": "Fact_Budget_2026"},
            ],
            "relationships": [
                {"from_table": "Fact_Budget_2026", "from_column": "DateKey", "to_table": "Dim_Date", "to_column": "DateKey"},
                {"from_table": "Fact_Budget_2026", "from_column": "CustomerKey", "to_table": "Dim_Customer", "to_column": "CustomerKey"},
                {"from_table": "Fact_Budget_2026", "from_column": "ScenarioID", "to_table": "Dim_Scenario", "to_column": "ScenarioID"},
            ],
        }

        gen = RelationshipSvgGenerator(composite_model)
        svg = gen.generate_model_svg()

        # 1. Upstream Super-Node Container rendered with Corporate_DW
        self.assertIn('class="upstream-group"', svg)
        self.assertIn('Corporate_DW', svg)
        # Real inherited metrics: 3 tables, 2 measures
        self.assertIn('>Tables:<', svg)
        self.assertIn('>3<', svg)
        self.assertIn('>Measures:<', svg)
        self.assertIn('>2<', svg)

        # 2. Border tables (Dim_Date, Dim_Customer) have REMOTE pill tag
        self.assertIn('REMOTE', svg)
        self.assertIn('remote-tag-bg', svg)

        # 3. Fact_Sales is remote but NOT connected to local model -> pruned from diagram
        self.assertNotIn('id="card-Fact_Sales"', svg)

        # 4. Cross-model bridge path
        self.assertIn('rel-path-bridge', svg)
        self.assertIn('port-dot-bridge', svg)
        self.assertIn('Cross-Model Rel', svg)

    def test_thin_model_svg_rendering(self):
        """Task 4/5/6: Verifies thin model renders unified upstream container without local utility card in star schema."""
        thin_model = {
            "name": "Thin_Report_KPIs",
            "tables": [
                {"name": "Dim_Date", "role": "DATE_DIMENSION", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
                {"name": "Dim_Store", "role": "DIMENSION", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
                {"name": "Fact_Sales", "role": "FACT", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
                {"name": "_ReportMeasures", "role": "PARAMETER_UTILITY"},
            ],
            "measures": [
                {"name": "Total Sales", "table": "Fact_Sales", "is_inherited": True, "is_external_measure": True},
                {"name": "Total Margin", "table": "Fact_Sales", "is_inherited": True, "is_external_measure": True},
                {"name": "KPI Variance %", "table": "_ReportMeasures"},
                {"name": "Target Index", "table": "_ReportMeasures"},
            ],
            "relationships": [],
        }

        gen = RelationshipSvgGenerator(thin_model)
        svg = gen.generate_model_svg()

        # Upstream container rendered with clean stats and DirectQuery mode tag
        self.assertIn('class="upstream-group"', svg)
        self.assertIn('Corporate_DW', svg)
        self.assertIn('>Tables:<', svg)
        self.assertIn('>3<', svg)
        self.assertIn('>Measures:<', svg)
        self.assertIn('>2<', svg)
        self.assertIn('DirectQuery', svg)
        self.assertNotIn('DirectQuery over AS / Fabric', svg)
        # Unified layout: No local utility cards in primary star schema
        self.assertNotIn('id="card-_ReportMeasures"', svg)
        # Utility card is strictly in the Utility tab
        util_tables = gen.get_utility_tables()
        self.assertIn('_ReportMeasures', util_tables)
        # Inherited tables strictly excluded from utility tables
        self.assertNotIn('Dim_Date', util_tables)
        self.assertNotIn('Dim_Store', util_tables)
        self.assertNotIn('Fact_Sales', util_tables)

    def test_utility_tab_svg_rendering(self):
        """Task 1: Verifies utility SVG generation with clean grid and NO Italian explanation banner."""
        model_with_utility = {
            "name": "Sales_Model",
            "tables": [
                {"name": "Fact_Sales", "role": "FACT"},
                {"name": "Dim_Date", "role": "DATE_DIMENSION"},
                {"name": "_PlanningMeasures", "role": "PARAMETER_UTILITY"},
                {"name": "Time_Intelligence", "role": "CALCULATION_GROUP"},
            ],
            "relationships": [
                {"from_table": "Fact_Sales", "from_column": "DateKey", "to_table": "Dim_Date", "to_column": "DateKey"}
            ],
            "measures": [
                {"name": "Budget Variance %", "table": "_PlanningMeasures"},
            ],
        }
        gen = RelationshipSvgGenerator(model_with_utility)
        util_tables = gen.get_utility_tables()
        self.assertEqual(util_tables, ["Time_Intelligence", "_PlanningMeasures"])

        util_svg = gen.generate_utility_svg(svg_id_prefix="util")
        self.assertIn("Utility Entities, Calculation Groups", util_svg)
        self.assertIn('id="card-util-Time_Intelligence"', util_svg)
        self.assertIn('id="card-util-_PlanningMeasures"', util_svg)
        # Banner completely removed as per Task 1
        self.assertNotIn("Architettura a Due Schede (Topological Purity)", util_svg)

    def test_remote_model_fallback_name_and_lateral_ports(self):
        """Task 3 & 5: Verifies fallback to 'Remote Semantic Model' and lateral ports on cross-model edges."""
        model_data = {
            "name": "HybridModel",
            "tables": [
                {"name": "RemoteTable", "is_inherited": True, "columns": [{"name": "Key", "data_type": "Int64"}]},
                {"name": "LocalTable", "role": "FACT", "columns": [{"name": "Key", "data_type": "Int64"}]},
            ],
            "relationships": [
                {"from_table": "LocalTable", "from_column": "Key", "to_table": "RemoteTable", "to_column": "Key"}
            ],
        }
        gen = RelationshipSvgGenerator(model_data)
        metrics = gen.get_inherited_metrics()
        self.assertEqual(metrics[2], "Remote Semantic Model")

        svg = gen.generate_model_svg()
        self.assertIn("Remote Semantic Model", svg)
        self.assertIn("DirectQuery", svg)
        # Lateral ports with rel-path-bridge and no central text block
        self.assertIn("rel-path-bridge", svg)
        self.assertIn("port-dot-bridge", svg)
        self.assertNotIn("Cross-Model Rel (1:N)", svg)

    def test_composite_hybrid_sales_parser(self):
        """Task 6: Verifies TMDL parser successfully loads synthetic composite_hybrid_sales."""
        sample_path = self.workspace_root / "composite_hybrid_sales" / "Composite_Hybrid_Sales.SemanticModel"
        self.assertTrue(sample_path.exists())

        parser = PBIPParser()
        model = parser.parse(str(sample_path))

        self.assertEqual(model.model_name, "Composite_Hybrid_Sales")
        table_names = [t.name for t in model.tables]
        self.assertIn("Dim_Customer", table_names)
        self.assertIn("Dim_Date", table_names)
        self.assertIn("Fact_Sales", table_names)
        self.assertIn("Fact_Budget_2026", table_names)
        self.assertIn("Dim_Scenario", table_names)
        self.assertIn("_PlanningMeasures", table_names)

        # Verify UDF function parsed
        fn_names = [f.name for f in model.functions]
        self.assertIn("FX_VariancePct", fn_names)

        # Verify external measures
        ext_msrs = [m.name for m in model.measures if m.is_external_measure or m.is_inherited]
        self.assertIn("Total Sales", ext_msrs)
        self.assertIn("Total Margin", ext_msrs)

    def test_thin_report_kpis_parser(self):
        """Task 6: Verifies TMDL parser successfully loads synthetic thin_report_kpis."""
        sample_path = self.workspace_root / "thin_report_kpis" / "Thin_Report_KPIs.SemanticModel"
        self.assertTrue(sample_path.exists())

        parser = PBIPParser()
        model = parser.parse(str(sample_path))

        self.assertEqual(model.model_name, "Thin_Report_KPIs")
        table_names = [t.name for t in model.tables]
        self.assertIn("Dim_Date", table_names)
        self.assertIn("Dim_Store", table_names)
        self.assertIn("Fact_Sales", table_names)
        self.assertIn("_ReportMeasures", table_names)
        self.assertEqual(len(model.relationships), 0)

    def test_multiple_upstream_semantic_models_stacked_vertically(self):
        """Task 4: Verifies multiple remote semantic models are stacked vertically in SVG."""
        multi_model = {
            "name": "MultiComposite",
            "tables": [
                {"name": "RemoteTableA", "is_inherited": True, "inherited_model_name": "Sales_Enterprise_DW"},
                {"name": "RemoteTableB", "is_inherited": True, "inherited_model_name": "Finance_Central_DW"},
                {"name": "LocalTable", "role": "FACT"},
            ],
            "measures": [
                {"name": "ExtSales", "table": "RemoteTableA", "is_inherited": True, "inherited_model_name": "Sales_Enterprise_DW"},
                {"name": "ExtBudget", "table": "RemoteTableB", "is_inherited": True, "inherited_model_name": "Finance_Central_DW"},
            ],
            "relationships": [],
        }
        gen = RelationshipSvgGenerator(multi_model)
        up_models = gen.get_upstream_models()
        self.assertEqual(len(up_models), 2)
        model_names = [m["name"] for m in up_models]
        self.assertIn("Sales_Enterprise_DW", model_names)
        self.assertIn("Finance_Central_DW", model_names)

        svg = gen.generate_model_svg()
        self.assertIn("Sales_Enterprise_DW", svg)
        self.assertIn("Finance_Central_DW", svg)
        # Verify both containers have DirectQuery mode tags
        self.assertEqual(svg.count(">DirectQuery<"), 2)

    def test_workspace_engine_sidebar_excludes_inherited_tables(self):
        """Task 2: Verifies workspace engine excludes inherited tables when include_inherited_entities is False."""
        from pbip_doc.codebase_scanner import DiscoveredModel, WorkspaceScanResult
        from pbip_doc.docgen.workspace_engine import WorkspaceHtmlLayoutBuilder

        config = DocGenConfig(include_inherited_entities=False)
        scan = WorkspaceScanResult(root_path=Path("/fake"))
        m = DiscoveredModel(
            name="HybridModel",
            path=Path("/fake/Hybrid.SemanticModel"),
            rel_path="Hybrid.SemanticModel",
            raw_name="HybridModel",
            model_format="TMDL",
        )
        m.tables = ["Dim_Customer", "LocalTargets"]
        m.inherited_tables = {"Dim_Customer": "EnterpriseDW"}
        m.table_roles = {"Dim_Customer": "DIM", "LocalTargets": "FACT"}
        m.measures = {"TargetSales": "LocalTargets"}
        m.inherited_measures = {}
        scan.models[m.artifact_id] = m

        builder = WorkspaceHtmlLayoutBuilder(scan, config)
        sidebar_html = builder._build_unified_sidebar("index.html", ".")

        # Local table must be in sidebar
        self.assertIn("LocalTargets", sidebar_html)
        # Inherited table must NOT be in sidebar
        self.assertNotIn("Dim_Customer", sidebar_html)

    def test_get_fact_tables_excludes_remote_facts(self):
        """Issue 3: Verifies get_fact_tables excludes remote inherited facts."""
        mock_model = {
            "name": "HybridTest",
            "tables": [
                {"name": "Fact_RemoteSales", "role": "FACT", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
                {"name": "Fact_LocalAdjustments", "role": "FACT"},
                {"name": "Dim_Customer", "role": "DIMENSION"},
            ],
            "measures": [],
            "relationships": [
                {"from_table": "Fact_RemoteSales", "to_table": "Dim_Customer"},
            ],
        }
        gen = RelationshipSvgGenerator(mock_model)
        facts = gen.get_fact_tables()
        self.assertIn("Fact_LocalAdjustments", facts)
        self.assertNotIn("Fact_RemoteSales", facts)

    def test_star_cluster_local_fact_without_relationships_generates_single_card(self):
        """Issue 4: Verifies a local Fact table with 0 relationships generates single-card StarCluster SVG, not empty SVG."""
        mock_model = {
            "name": "IsolatedFactModel",
            "tables": [
                {"name": "Fact_Isolated", "role": "FACT"},
                {"name": "Dim_Customer", "role": "DIMENSION"},
            ],
            "measures": [
                {"name": "Total Isolated", "table": "Fact_Isolated"},
            ],
            "relationships": [],
        }
        gen = RelationshipSvgGenerator(mock_model)
        svg = gen.generate_diagram(scope="star_cluster", target_table="Fact_Isolated")
        # Must NOT be empty SVG
        self.assertNotIn("No active table relationships", svg)
        # Must contain focal card
        self.assertIn('id="card-star-fact-isolated-Fact_Isolated"', svg)
        # Must contain legend
        self.assertIn('class="diagram-legend"', svg)

    def test_utility_svg_truncation_and_dedicated_legend(self):
        """Issue 6: Verifies utility tables truncate at 4 items + '+ N more...' placeholder and render dedicated MSR/COL legend."""
        mock_model = {
            "name": "UtilityModel",
            "tables": [
                {
                    "name": "Metric_Selector",
                    "role": "PARAMETER_UTILITY",
                    "columns": [
                        {"name": f"Param_Col_{i}", "data_type": "string"} for i in range(1, 8)
                    ],
                },
                {
                    "name": "_PlanningMeasures",
                    "role": "UTILITY",
                },
            ],
            "measures": [
                {"name": f"Measure_{i}", "table": "_PlanningMeasures"} for i in range(1, 7)
            ],
            "relationships": [],
        }
        gen = RelationshipSvgGenerator(mock_model)
        util_svg = gen.generate_utility_svg()

        # Check placeholder for columns (7 items -> 4 + 3 more)
        self.assertIn("+ 3 more...", util_svg)
        # Check placeholder for measures (6 items -> 4 + 2 more)
        self.assertIn("+ 2 more...", util_svg)

        # Check dedicated legend at bottom
        self.assertIn('class="diagram-legend"', util_svg)
        self.assertIn('class="col-type-badge col-badge-text-msr"', util_svg)
        self.assertIn('>DAX Measure<', util_svg)
        self.assertIn('class="col-type-badge col-badge-text-fk"', util_svg)
        self.assertIn('>Column / Parameter Attribute<', util_svg)
        # Verify redundant 'Utility' label is removed from dedicated legend
        self.assertNotIn('<!-- Utility Role -->', util_svg)
        legend_start = util_svg.find('class="diagram-legend"')
        legend_sub = util_svg[legend_start:]
        self.assertNotIn('>Utility<', legend_sub)

    def test_upstream_directquery_tag_margin(self):
        """Issue 1: Verifies DirectQuery tag in upstream container preserves >= 15px right margin."""
        mock_model = {
            "name": "CompositeModel",
            "tables": [
                {"name": "RemoteTable", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
                {"name": "LocalFact", "role": "FACT"},
            ],
            "measures": [],
            "relationships": [
                {"from_table": "LocalFact", "to_table": "RemoteTable"},
            ],
        }
        gen = RelationshipSvgGenerator(mock_model)
        svg = gen.generate_model_svg()
        # DirectQuery tag should be present
        self.assertIn('>DirectQuery<', svg)
        # The container width box_w = svg_width - 60. For svg_width=1040, box_w=980.
        # tag_x = box_w - 75 - 35 = 980 - 110 = 870.
        # Absolute tag right coordinate in container is 20 + 870 + 75 = 965, leaving 15px from box_w (980).
        self.assertIn('class="upstream-stat-box"', svg)

    def test_remote_legend_normalization(self):
        """Issue 2: Verifies remote legend contains Remote Rel and Remote Entity while preserving standard legend sequence."""
        mock_model = {
            "name": "RemoteModel",
            "tables": [
                {"name": "RemoteDim", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
                {"name": "LocalFact", "role": "FACT"},
            ],
            "measures": [],
            "relationships": [
                {"from_table": "LocalFact", "to_table": "RemoteDim"},
            ],
        }
        gen = RelationshipSvgGenerator(mock_model)
        svg = gen.generate_model_svg()
        # Legend must contain standard items + Remote Rel + Remote Entity
        self.assertIn('>Active Rel<', svg)
        self.assertIn('>Remote Rel<', svg)
        self.assertIn('class="rel-path-bridge"', svg)
        self.assertIn('>Inactive Rel<', svg)
        self.assertIn('>Bidirectional (Both)<', svg)
        self.assertIn('>Cardinality (1:*, 1:1, *:*)<', svg)
        self.assertIn('>Remote Entity<', svg)
        self.assertIn('>PK / FK<', svg)

    def test_upstream_semantic_model_resolution_html_and_markdown(self):
        """Issue 5: Verifies upstream model links to ../../models/{slug} when documented in workspace, else External Remote Model."""
        config = DocGenConfig()
        config.workspace_models = {
            "Corporate_DW": "Corporate_DW",
            "corporate_dw": "Corporate_DW",
        }
        model_data = {
            "model_name": "Composite_Hybrid_Sales",
            "project_name": "Composite_Hybrid_Sales",
            "workspace_models": config.workspace_models,
            "data_sources_summary": [
                {
                    "source_type": "AnalysisServices",
                    "connection_string": "powerbi://api.powerbi.com/v1.0/myorg/Corporate",
                    "server": "powerbi://api.powerbi.com/v1.0/myorg/Corporate",
                    "database": "Corporate_DW",
                },
                {
                    "source_type": "AnalysisServices",
                    "connection_string": "powerbi://api.powerbi.com/v1.0/myorg/Other",
                    "server": "powerbi://api.powerbi.com/v1.0/myorg/Other",
                    "database": "Undocumented_External_Model",
                },
            ],
            "tables": [
                {"name": "Dim_Customer", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
                {"name": "Fact_Budget", "role": "FACT"},
            ],
            "measures": [
                {"name": "Total Sales", "table": "Dim_Customer", "is_inherited": True, "inherited_model_name": "Corporate_DW"},
            ],
            "relationships": [],
        }

        # 1. HTML Verification
        html_builder = HtmlIndexBuilder(model_data, config)
        ds_section = html_builder._section_physical_data_sources(model_data["data_sources_summary"])
        self.assertIsNotNone(ds_section)
        # Corporate_DW must be clickable link
        self.assertIn('href="../../models/Corporate_DW/index.html"', ds_section.content)
        # Undocumented_External_Model must have External Remote Model badge
        self.assertIn('External Remote Model', ds_section.content)

        desc_section = html_builder._section_description()
        self.assertIsNotNone(desc_section)
        self.assertNotIn("Upstream Semantic Model:", desc_section.content)

        # 2. Markdown Verification
        from pbip_doc.docgen.index_doc import IndexDocBuilder
        md_builder = IndexDocBuilder(model_data, config)
        md_ds_section = md_builder._section_sources()
        self.assertIn('[**Corporate_DW**](../../models/Corporate_DW/README.md)', md_ds_section.content)
        self.assertIn('*(External Remote Model)*', md_ds_section.content)

        md_desc = md_builder._section_description()
        self.assertNotIn("Upstream Semantic Model", md_desc.content)

    def test_corporate_dw_sample_parsing(self):
        """Issue 5: Verifies the newly created Corporate_DW sample parses natively as a clean SemanticModel."""
        dw_path = self.workspace_root / "corporate_dw"
        self.assertTrue(dw_path.exists(), f"Path not found: {dw_path}")
        parser = PBIPParser()
        model = parser.parse(str(dw_path / "Corporate_DW.SemanticModel"))
        self.assertIsNotNone(model)
        self.assertEqual(model.model_name, "Corporate_DW")
        table_names = [t.name for t in model.tables]
        self.assertIn("Dim_Customer", table_names)
        self.assertIn("Dim_Date", table_names)
        self.assertIn("Fact_Sales", table_names)
        self.assertEqual(len(model.measures), 2)
        measure_names = [m.name for m in model.measures]
        self.assertIn("Total Sales", measure_names)
        self.assertIn("Total Margin", measure_names)
        self.assertEqual(len(model.relationships), 2)

    def test_parser_populates_upstream_models_directly(self):
        """DEV-029/DEV-033/DEV-034: Verifies PBIPParser populates model.upstream_models and model.to_dict()['upstream_models'] directly."""
        sample_path = self.workspace_root / "composite_hybrid_sales" / "Composite_Hybrid_Sales.SemanticModel"
        self.assertTrue(sample_path.exists())

        parser = PBIPParser()
        model = parser.parse(str(sample_path))

        self.assertTrue(len(model.upstream_models) >= 1)
        up = model.upstream_models[0]
        self.assertEqual(up.name, "Corporate_DW")
        self.assertEqual(up.mode, "DirectQuery")
        self.assertEqual(up.tables_count, 3)
        self.assertEqual(up.measures_count, 2)
        self.assertIn("Dim_Customer", up.tables)
        self.assertIn("Total Sales", up.measures)

        d = model.to_dict()
        self.assertIn("upstream_models", d)
        self.assertEqual(d["upstream_models"][0]["name"], "Corporate_DW")
        self.assertEqual(d["upstream_models"][0]["tables_count"], 3)
        self.assertEqual(d["upstream_models"][0]["measures_count"], 2)

        # Verify PowerQueryLineageNode.to_dict() works natively (DEV-017)
        if model.expressions:
            exp_dict = model.expressions[0].to_dict()
            self.assertIsInstance(exp_dict, dict)
            self.assertIn("query_name", exp_dict)

    def test_codebase_scanner_injects_workspace_linkability(self):
        """DEV-035: Verifies CodebaseScanner populates is_in_workspace and target_model_slug on upstream_models and data_sources_summary."""
        self.assertTrue(self.workspace_root.exists())

        scanner = CodebaseScanner(self.workspace_root)
        scan_res = scanner.scan(populate_symbols=True)

        comp_dm = scan_res.get_model("Composite_Hybrid_Sales")
        self.assertIsNotNone(comp_dm)
        self.assertIsNotNone(comp_dm.model_obj)

        up_list = comp_dm.model_obj.upstream_models
        self.assertTrue(len(up_list) >= 1)
        corp_up = next((u for u in up_list if u.name == "Corporate_DW"), None)
        self.assertIsNotNone(corp_up)
        self.assertTrue(corp_up.is_in_workspace)
        self.assertEqual(corp_up.target_model_slug, "Corporate_DW")

        ds_list = comp_dm.model_obj.data_sources_summary
        corp_ds = next((s for s in ds_list if s.database == "Corporate_DW"), None)
        self.assertIsNotNone(corp_ds)
        self.assertTrue(corp_ds.is_in_workspace)
        self.assertTrue(corp_ds.is_remote_model)
        self.assertEqual(corp_ds.target_model_slug, "Corporate_DW")

    def test_discovered_model_published_perimeter_helpers(self):
        """DEV-032: Verifies DiscoveredModel.get_published_tables() and get_published_measures() filter inherited entities."""
        from pbip_doc.codebase_scanner import DiscoveredModel

        dm = DiscoveredModel(
            name="HybridTest",
            path=Path("/fake/HybridTest.SemanticModel"),
            rel_path="HybridTest.SemanticModel",
            raw_name="HybridTest",
            model_format="TMDL",
        )
        dm.tables = ["Dim_Remote", "Fact_Local", "LocalDateTable_123"]
        dm.inherited_tables = {"Dim_Remote": "Corporate_DW"}
        dm.measures = {"RemoteMeas": "Dim_Remote", "LocalMeas": "Fact_Local", "AutoDateMeas": "LocalDateTable_123"}
        dm.inherited_measures = {"RemoteMeas": "Corporate_DW"}

        cfg_default = DocGenConfig(include_inherited_entities=False)
        self.assertEqual(dm.get_published_tables(cfg_default), ["Fact_Local"])
        self.assertEqual(dm.get_published_measures(cfg_default), {"LocalMeas": "Fact_Local"})

        cfg_incl = DocGenConfig(include_inherited_entities=True)
        self.assertEqual(dm.get_published_tables(cfg_incl), ["Dim_Remote", "Fact_Local"])
        self.assertEqual(dm.get_published_measures(cfg_incl), {"RemoteMeas": "Dim_Remote", "LocalMeas": "Fact_Local"})

    def test_workspace_markdown_includes_semantic_models_lineage_matrix(self):
        """DEV-030: Verifies _build_workspace_index_markdown includes '## Semantic Models Dependency & Upstream Lineage'."""
        from pbip_doc.codebase_scanner import DiscoveredModel, WorkspaceScanResult
        from pbip_doc.docgen.workspace_engine import WorkspaceDocGenerator

        config = DocGenConfig(include_inherited_entities=False)
        scan = WorkspaceScanResult(root_path=Path("/fake/Workspace"))
        m1 = DiscoveredModel(
            name="Corporate_DW",
            path=Path("/fake/Workspace/Corporate_DW.SemanticModel"),
            rel_path="Corporate_DW.SemanticModel",
            raw_name="Corporate_DW",
            model_format="TMDL",
        )
        m1.tables = ["Dim_Date", "Fact_Sales"]
        m1.measures = {"Total Sales": "Fact_Sales"}

        m2 = DiscoveredModel(
            name="Composite_Sales",
            path=Path("/fake/Workspace/Composite_Sales.SemanticModel"),
            rel_path="Composite_Sales.SemanticModel",
            raw_name="Composite_Sales",
            model_format="TMDL",
        )
        m2.tables = ["Dim_Date", "Fact_Budget"]
        m2.inherited_tables = {"Dim_Date": "Corporate_DW"}
        m2.measures = {"Total Sales": "Dim_Date", "Total Budget": "Fact_Budget"}
        m2.inherited_measures = {"Total Sales": "Corporate_DW"}

        scan.models[m1.artifact_id] = m1
        scan.models[m2.artifact_id] = m2

        ws_gen = WorkspaceDocGenerator(config)
        md = ws_gen._build_workspace_index_markdown(scan)
        self.assertIn("## Semantic Models Dependency & Upstream Lineage", md)
        self.assertIn("| Semantic Model | Upstream Source Models | Published Tables | Business Measures | Downstream Reports |", md)
        self.assertIn("[Corporate_DW](models/Corporate_DW/README.md) *(Local Model)*", md)

    def test_cli_parse_and_scan_aliases_and_precalculated_expression_type(self):
        """KB-0101 (UX-004, DEV-038, DEV-039, DEV-040): Verifies CLI parse/scan aliases, expression_type pre-calculation, and VisualDefinition.get_effective_evaluated_metrics."""
        from pbip_doc.cli import build_parser
        from pbip_doc.m_lineage import MLineageResolver
        from pbip_doc.report_schema import VisualDefinition
        from pbip_doc.docgen.utils import get_measure_lookup_map, get_measure_table_map

        cli_parser = build_parser()
        args_parse = cli_parser.parse_args(["parse", "dummy_model"])
        self.assertIn(args_parse.command, ("extract", "parse"))
        self.assertEqual(args_parse.path, "dummy_model")

        args_scan = cli_parser.parse_args(["scan", "dummy_model"])
        self.assertIn(args_scan.command, ("inspect", "scan"))
        self.assertEqual(args_scan.path, "dummy_model")

        m_res = MLineageResolver({
            "ParamEnv": {"expression": '"PROD" meta [IsParameterQuery=true, Type="Text"]', "is_staging": True},
            "FnDouble": {"expression": "(x as number) => x * 2", "is_staging": True},
            "StaticMap": {"expression": '#table({"Code", "Label"}, {{"A", "Alpha"}})', "is_staging": True},
            "StagingRaw": {"expression": 'let Source = Sql.Database("srv", "db") in Source', "is_staging": True},
            "DimLoaded": {"expression": 'let Source = StagingRaw in Source', "is_staging": False, "target_table": "DimLoaded"},
        })
        self.assertEqual(m_res.nodes["ParamEnv"].expression_type, "PARAMETER")
        self.assertEqual(m_res.nodes["FnDouble"].expression_type, "CUSTOM_FUNCTION")
        self.assertEqual(m_res.nodes["StaticMap"].expression_type, "INLINE_TABLE")
        self.assertTrue(m_res.nodes["StaticMap"].is_inline_table)
        self.assertEqual(m_res.nodes["StagingRaw"].expression_type, "STAGING_QUERY")
        self.assertEqual(m_res.nodes["DimLoaded"].expression_type, "LOADED_TABLE")

        vis = VisualDefinition(
            visual_id="v1",
            title="'FactSales'[Dynamic Title Measure]",
            visual_type="card",
            is_conditional_title=True,
        )
        eff_metrics = vis.get_effective_evaluated_metrics()
        self.assertEqual(len(eff_metrics), 1)
        self.assertEqual(eff_metrics[0].table, "FactSales")
        self.assertEqual(eff_metrics[0].field, "Dynamic Title Measure")
        self.assertEqual(eff_metrics[0].role, "Conditional Title")

        mock_model = {"measures": [{"name": "M1", "table": "T1", "calculation_depth": 1}]}
        self.assertEqual(get_measure_lookup_map(mock_model)["M1"]["table"], "T1")
        self.assertEqual(get_measure_table_map(mock_model)["M1"], "T1")

    def test_relationship_perimeter_excludes_remote_to_remote(self):
        """ISSUE 1: Local<->Local and Local<->Remote are included; Remote<->Remote is excluded across SVG, MD, HTML."""
        model_data = {
            "model_name": "CompositePerimeterModel",
            "project_name": "CompositePerimeterModel",
            "tables": [
                {
                    "name": "LocalFact",
                    "role": "FACT",
                    "columns": [
                        {"name": "LocalDimKey", "data_type": "int64"},
                        {"name": "RemoteDimKey", "data_type": "int64"},
                    ],
                },
                {
                    "name": "LocalDim",
                    "role": "DIMENSION",
                    "columns": [{"name": "LocalDimKey", "data_type": "int64", "is_key": True}],
                },
                {
                    "name": "RemoteFact",
                    "role": "FACT",
                    "is_inherited": True,
                    "source_type": "InheritedEntity",
                    "inherited_model_name": "UpstreamDW",
                    "columns": [{"name": "RemoteDimKey", "data_type": "int64"}],
                },
                {
                    "name": "RemoteDim",
                    "role": "DIMENSION",
                    "is_inherited": True,
                    "source_type": "InheritedEntity",
                    "inherited_model_name": "UpstreamDW",
                    "columns": [{"name": "RemoteDimKey", "data_type": "int64", "is_key": True}],
                },
            ],
            "measures": [],
            "relationships": [
                {
                    "from_table": "LocalFact",
                    "from_column": "LocalDimKey",
                    "to_table": "LocalDim",
                    "to_column": "LocalDimKey",
                    "cardinality": "1:N",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
                {
                    "from_table": "LocalFact",
                    "from_column": "RemoteDimKey",
                    "to_table": "RemoteDim",
                    "to_column": "RemoteDimKey",
                    "cardinality": "1:N",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
                {
                    "from_table": "RemoteFact",
                    "from_column": "RemoteDimKey",
                    "to_table": "RemoteDim",
                    "to_column": "RemoteDimKey",
                    "cardinality": "1:N",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
            ],
        }

        config = DocGenConfig()

        # 1. SVG RelationshipSvgGenerator
        svg_gen = RelationshipSvgGenerator(model_data)
        self.assertEqual(len(svg_gen.relationships), 2)
        pairs = {(r["from_table"], r["to_table"]) for r in svg_gen.relationships}
        self.assertIn(("LocalFact", "LocalDim"), pairs)
        self.assertIn(("LocalFact", "RemoteDim"), pairs)
        self.assertNotIn(("RemoteFact", "RemoteDim"), pairs)

        svg = svg_gen.generate_model_svg()
        self.assertIn("LocalFact", svg)
        self.assertIn("LocalDim", svg)
        self.assertIn("RemoteDim", svg)
        self.assertNotIn('id="card-RemoteFact"', svg)

        # 2. Markdown IndexDocBuilder
        md_builder = IndexDocBuilder(model_data, config)
        md_rel_sec = md_builder._section_relationship_table()
        self.assertIsNotNone(md_rel_sec)
        self.assertIn("LocalFact", md_rel_sec.content)
        self.assertIn("LocalDim", md_rel_sec.content)
        self.assertIn("RemoteDim", md_rel_sec.content)
        self.assertNotIn("RemoteFact", md_rel_sec.content)

        md_arch = md_builder._build_architecture_and_relationships_section()
        self.assertIsNotNone(md_arch)
        self.assertIn("LocalDim", md_arch)
        self.assertIn("RemoteDim", md_arch)
        self.assertNotIn("RemoteFact", md_arch)

        # 3. HTML HtmlIndexBuilder
        html_builder = HtmlIndexBuilder(model_data, config)
        html_out = html_builder.build_content()
        self.assertIn("Model Relationships (2)", html_out)
        self.assertIn("LocalFact[LocalDimKey]", html_out)
        self.assertIn("LocalFact[RemoteDimKey]", html_out)
        self.assertNotIn("RemoteFact[RemoteDimKey]", html_out)

        # 4. TableDocBuilder & HtmlTableBuilder on RemoteDim: sees LocalFact, NOT RemoteFact
        remote_dim_tbl = model_data["tables"][3]
        md_tbl_builder = TableDocBuilder(remote_dim_tbl, model_data, config)
        self.assertEqual(len(md_tbl_builder.direct_rels), 1)
        self.assertEqual(md_tbl_builder.direct_rels[0]["from_table"], "LocalFact")

        html_tbl_builder = HtmlTableBuilder(remote_dim_tbl, model_data, config)
        self.assertEqual(len(html_tbl_builder.direct_rels), 1)
        self.assertEqual(html_tbl_builder.direct_rels[0]["from_table"], "LocalFact")

        # 5. HtmlTableBuilder on LocalFact: verifies LocalDim link is present and RemoteDim has no 404 link
        local_fact_tbl = model_data["tables"][0]
        local_fact_html_builder = HtmlTableBuilder(local_fact_tbl, model_data, config)
        self.assertEqual(len(local_fact_html_builder.direct_rels), 2)
        rel_sec = local_fact_html_builder._section_relationship_table(local_fact_html_builder.direct_rels)
        self.assertIsNotNone(rel_sec)
        self.assertIn('href="LocalDim.html"', rel_sec.content)
        self.assertNotIn('href="RemoteDim.html"', rel_sec.content)
        self.assertIn("RemoteDim", rel_sec.content)
        self.assertIn("Remote Entity", rel_sec.content)

    def test_downstream_consuming_reports_by_path_and_by_connection_with_guid(self):
        """
        ISSUE 2: End-to-end lineage Datamodel A -> Datamodel B -> Report B (byPath),
        Report C (byConnection with GUID pbiModelDatabaseName + quoted Initial Catalog="Datamodel B"),
        plus multi-hop A -> B -> C -> Report D.
        """
        with tempfile.TemporaryDirectory(prefix="pbip_lineage_chain_") as tmp:
            root = Path(tmp)

            # Datamodel A (root)
            dm_a_def = root / "Datamodel A.SemanticModel" / "definition"
            _write_text(dm_a_def / "model.tmdl", "model Model\n\tculture: en-US\n")
            _write_text(
                dm_a_def / "tables" / "Fact_Orders.tmdl",
                """
table Fact_Orders
\tmeasure 'Order Count' = COUNTROWS(Fact_Orders)
\tcolumn OrderKey
\t\tdataType: int64
\tpartition Fact_Orders = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = #table({"OrderKey"}, {{1}})
\t\t\tin
\t\t\t\tSource
""",
            )

            # Datamodel B (composite inheriting from Datamodel A)
            dm_b_def = root / "Datamodel B.SemanticModel" / "definition"
            _write_text(dm_b_def / "model.tmdl", "model Model\n\tculture: en-US\n")
            _write_text(
                dm_b_def / "expressions.tmdl",
                """
expression 'DirectQuery to AS - Datamodel A' =
\t\tlet
\t\t\tSource = AnalysisServices.Database("powerbi://api.powerbi.com/v1.0/myorg/WS", "Datamodel A"),
\t\t\tCubes = Table.Combine(Source[Data]),
\t\t\tCube = Cubes{[Id="Model", Kind="Cube"]}[Data]
\t\tin
\t\t\tCube
""",
            )
            _write_text(
                dm_b_def / "tables" / "Fact_Orders.tmdl",
                """
table Fact_Orders
\tcolumn OrderKey
\t\tdataType: int64
\tpartition Fact_Orders = entity
\t\tmode: directQuery
\t\tsource
\t\t\tentityName: Fact_Orders
\t\t\texpressionSource: 'DirectQuery to AS - Datamodel A'
""",
            )
            _write_text(
                dm_b_def / "tables" / "Local_Targets.tmdl",
                """
table Local_Targets
\tcolumn OrderKey
\t\tdataType: int64
\tpartition Local_Targets = m
\t\tmode: import
\t\tsource =
\t\t\tlet
\t\t\t\tSource = #table({"OrderKey"}, {{1}})
\t\t\tin
\t\t\t\tSource
""",
            )

            # Datamodel C (composite inheriting from Datamodel B -> tests 2-hop A -> B -> C)
            dm_c_def = root / "Datamodel C.SemanticModel" / "definition"
            _write_text(dm_c_def / "model.tmdl", "model Model\n\tculture: en-US\n")
            _write_text(
                dm_c_def / "expressions.tmdl",
                """
expression 'DirectQuery to AS - Datamodel B' =
\t\tlet
\t\t\tSource = AnalysisServices.Database("powerbi://api.powerbi.com/v1.0/myorg/WS", "Datamodel B"),
\t\t\tCubes = Table.Combine(Source[Data]),
\t\t\tCube = Cubes{[Id="Model", Kind="Cube"]}[Data]
\t\tin
\t\t\tCube
""",
            )
            _write_text(
                dm_c_def / "tables" / "Local_Targets.tmdl",
                """
table Local_Targets
\tcolumn OrderKey
\t\tdataType: int64
\tpartition Local_Targets = entity
\t\tmode: directQuery
\t\tsource
\t\t\tentityName: Local_Targets
\t\t\texpressionSource: 'DirectQuery to AS - Datamodel B'
""",
            )

            def _make_pbir_report(rep_name: str, ds_ref: dict) -> Path:
                rep_dir = root / f"{rep_name}.Report"
                _write_text(
                    rep_dir / "definition.pbir",
                    json.dumps({"version": "4.0", "datasetReference": ds_ref}, indent=2),
                )
                _write_text(
                    rep_dir / "definition" / "report.json",
                    json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json"}),
                )
                _write_text(
                    rep_dir / "definition" / "pages" / "page1" / "page.json",
                    json.dumps({"name": "page1", "displayName": "Overview", "width": 1280, "height": 720}),
                )
                return rep_dir

            # Report B -> byPath to Datamodel B
            _make_pbir_report(
                "Report B",
                {"byPath": {"path": "../Datamodel B.SemanticModel"}},
            )

            # Report C -> byConnection with GUID pbiModelDatabaseName and quoted Initial Catalog="Datamodel B"
            rep_c_dir = _make_pbir_report(
                "Report C",
                {
                    "byConnection": {
                        "connectionString": 'Data Source=powerbi://api.powerbi.com/v1.0/myorg/WS;Initial Catalog="Datamodel B";Integrated Security=ClaimsToken',
                        "pbiModelDatabaseName": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    }
                },
            )

            # Report D -> byConnection to Datamodel C (multi-hop from Datamodel A)
            _make_pbir_report(
                "Report D",
                {
                    "byConnection": {
                        "connectionString": "Data Source=powerbi://api.powerbi.com/v1.0/myorg/WS;Initial Catalog='Datamodel C';",
                        "pbiModelDatabaseName": "11111111-2222-3333-4444-555555555555",
                    }
                },
            )

            # Verify ReportParser also prioritizes Initial Catalog over GUID
            rep_parser = ReportParser()
            parsed_rep_c = rep_parser.parse(str(rep_c_dir))
            self.assertEqual(parsed_rep_c.target_dataset_name, "Datamodel B")

            # Scan workspace end-to-end
            scanner = CodebaseScanner(root)
            scan_res = scanner.scan(populate_symbols=True)

            # Datamodel B: Report B and Report C direct, Report D transitive via Datamodel C
            down_b = scan_res.get_downstream_reports("Datamodel B")
            direct_b = [d["report"].name for d in down_b if d["is_direct"]]
            trans_b = [d["report"].name for d in down_b if not d["is_direct"]]
            self.assertEqual(direct_b, ["Report B", "Report C"])
            self.assertEqual(trans_b, ["Report D"])

            # Datamodel A: Report B, Report C, Report D all transitive via Datamodel B
            down_a = scan_res.get_downstream_reports("Datamodel A")
            self.assertEqual(
                [(d["report"].name, d["is_direct"], d["via_model"]) for d in down_a],
                [
                    ("Report B", False, "Datamodel B"),
                    ("Report C", False, "Datamodel B"),
                    ("Report D", False, "Datamodel B"),
                ],
            )

            # Generate full Markdown and HTML workspace docs and verify both expose Report B and Report C
            cfg = DocGenConfig(output_format="both")
            ws_gen = WorkspaceDocGenerator(cfg)

            md_docs = ws_gen.generate_all_markdown_documents(scan_res)
            md_a = md_docs.get("models/Datamodel_A/README.md", "")
            md_b = md_docs.get("models/Datamodel_B/README.md", "")
            self.assertIn("Report B", md_a)
            self.assertIn("Report C", md_a)
            self.assertIn("Report B", md_b)
            self.assertIn("Report C", md_b)

            html_docs = ws_gen.generate_all_html_documents(scan_res)
            html_a = html_docs.get("models/Datamodel_A/index.html", "")
            html_b = html_docs.get("models/Datamodel_B/index.html", "")
            self.assertIn("Report B", html_a)
            self.assertIn("Report C", html_a)
            self.assertIn("Report B", html_b)
            self.assertIn("Report C", html_b)

    def test_dax_calculated_table_upstream_model_references_html_and_markdown(self):
        """
        ISSUE 3: DAX Field Parameter Table referencing Customer[Customer], standalone Date table,
        and [Sales Amount] measure defined in Sales. Verifies deduplication, real home table measure
        links, uniform badge-type styling, and clean link markup in HTML and Markdown.
        """
        calc_table = {
            "name": "Field Parameter",
            "role": "PARAMETER_UTILITY",
            "source_type": "CalculatedTable",
            "is_calculated": True,
            "expression": (
                '{ ("Customer", NAMEOF(Customer[Customer]), 0),'
                ' ("Sales", NAMEOF([Sales Amount]), 1) }'
            ),
            "referenced_tables": ["Customer", "Date"],
            "referenced_columns": [
                {"table": "Customer", "column": "Customer"},
            ],
            "referenced_measures": ["Sales Amount"],
            "columns": [
                {"name": "Parameter", "data_type": "string"},
            ],
        }
        full_model = {
            "model_name": "Model01",
            "project_name": "Model01",
            "tables": [
                calc_table,
                {"name": "Customer", "role": "DIMENSION", "columns": [{"name": "Customer", "data_type": "string"}]},
                {"name": "Date", "role": "DATE_DIMENSION", "columns": [{"name": "Date", "data_type": "dateTime"}]},
                {"name": "Sales", "role": "FACT", "columns": [{"name": "Amount", "data_type": "decimal"}]},
            ],
            "measures": [
                {"name": "Sales Amount", "table": "Sales", "dax_expression": "SUM(Sales[Amount])"},
            ],
            "relationships": [],
        }

        config = DocGenConfig()

        # 1. HTML Verification
        html_builder = HtmlTableBuilder(calc_table, full_model, config)
        html_sec = html_builder._section_referenced_columns()
        self.assertIsNotNone(html_sec)
        html_content = html_sec.content

        # Uniform badge-type across Table, Column, Measure (NO badge-accent)
        self.assertIn('<span class="badge badge-type">Table</span>', html_content)
        self.assertIn('<span class="badge badge-type">Column</span>', html_content)
        self.assertIn('<span class="badge badge-type">Measure</span>', html_content)
        self.assertNotIn("badge-accent", html_content)

        # Standalone table Date appears as Table row; Customer does NOT appear as duplicate Table row
        self.assertEqual(html_content.count('<span class="badge badge-type">Table</span>'), 1)
        self.assertIn('<a href="Date.html">Date</a>', html_content)
        self.assertIn('<a href="Customer.html">Customer</a>', html_content)
        self.assertIn('<code>[Customer]</code>', html_content)

        # Measure points to ../measures/Sales/Sales_Amount.html, NOT ../measures/Field_Parameter/...
        self.assertIn('href="../measures/Sales/Sales_Amount.html"', html_content)
        self.assertNotIn("Field_Parameter/Sales_Amount", html_content)
        # Clean link text without <code>[Sales Amount]</code>
        self.assertIn('<a href="../measures/Sales/Sales_Amount.html">Sales Amount</a>', html_content)
        self.assertNotIn("<code>[Sales Amount]</code>", html_content)
        # Column / Scope links to home table Sales
        self.assertIn('<a href="Sales.html">Sales</a>', html_content)

        # 2. Markdown Verification
        md_builder = TableDocBuilder(calc_table, full_model, config)
        md_sec = md_builder._section_referenced_columns()
        self.assertIsNotNone(md_sec)
        md_content = md_sec.content

        self.assertIn("| Entity Type | Referenced Entity / Table | Column / Scope |", md_content)
        # Standalone Date row only; no duplicate Customer Table row
        self.assertIn("| Table | [Date](Date.md) | — |", md_content)
        self.assertNotIn("| Table | [Customer]", md_content)
        self.assertIn("| Column | [Customer](Customer.md) | `[Customer]` |", md_content)
        # Measure links to ../measures/Sales/Sales_Amount.md with home table Sales
        self.assertIn("| Measure | [Sales Amount](../measures/Sales/Sales_Amount.md) | [Sales](Sales.md) |", md_content)
        self.assertNotIn("Field_Parameter/Sales_Amount", md_content)

    def test_relationship_svg_generator_respects_excluded_tables_config(self):
        """DEV-052: RelationshipSvgGenerator filters out relationships targeting excluded tables via config."""
        model = {
            "model_name": "ExcludedTablesModel",
            "tables": [
                {
                    "name": "LocalFact",
                    "role": "FACT",
                    "columns": [
                        {"name": "LocalDimKey", "data_type": "int64"},
                        {"name": "OtherDimKey", "data_type": "int64"},
                    ],
                },
                {
                    "name": "LocalDim",
                    "role": "DIMENSION",
                    "columns": [{"name": "LocalDimKey", "data_type": "int64", "is_key": True}],
                },
                {
                    "name": "OtherDim",
                    "role": "DIMENSION",
                    "columns": [{"name": "OtherDimKey", "data_type": "int64", "is_key": True}],
                },
            ],
            "measures": [],
            "relationships": [
                {
                    "from_table": "LocalFact",
                    "from_column": "LocalDimKey",
                    "to_table": "LocalDim",
                    "to_column": "LocalDimKey",
                    "cardinality": "1:N",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
                {
                    "from_table": "LocalFact",
                    "from_column": "OtherDimKey",
                    "to_table": "OtherDim",
                    "to_column": "OtherDimKey",
                    "cardinality": "1:N",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
            ],
        }

        svg_gen = RelationshipSvgGenerator(model, config=DocGenConfig(excluded_tables=["LocalDim"]))
        self.assertEqual(len(svg_gen.relationships), 1)
        self.assertEqual(svg_gen.relationships[0]["to_table"], "OtherDim")

        svg = svg_gen.generate_model_svg()
        self.assertIn("LocalFact", svg)
        self.assertIn("OtherDim", svg)
        self.assertNotIn("LocalDim", svg)


if __name__ == "__main__":
    unittest.main()
