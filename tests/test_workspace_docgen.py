"""
Unit tests for PBIP Multi-Artifact Workspace Documentation Generation.
Tests full catalog generation, lineage matrix, and relative link resolution across models and reports.
"""

import os
import tempfile
import unittest
from pathlib import Path

from html import escape
from pbip_doc.codebase_scanner import (
    CodebaseScanner,
    DiscoveredModel,
    DiscoveredReport,
    WorkspaceScanResult,
)
from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.utils import sanitize_filename
from pbip_doc.docgen.workspace_engine import (
    WorkspaceDocGenerator,
    WorkspaceHtmlLayoutBuilder,
)


class TestWorkspaceDocGenerator(unittest.TestCase):

    def setUp(self):
        self.samples_dir = Path(__file__).resolve().parent.parent / "samples"
        self.scanner = CodebaseScanner(self.samples_dir)
        self.scan_result = self.scanner.scan(populate_symbols=True)
        self.config = DocGenConfig()

    def test_generate_workspace_markdown_documents(self):
        generator = WorkspaceDocGenerator(self.config)
        docs = generator.generate_all_markdown_documents(self.scan_result)

        # 1. Root Master Catalog
        self.assertIn("README.md", docs)
        root_content = docs["README.md"]
        self.assertIn("Workspace Documentation Catalog", root_content)
        self.assertNotIn("Data Lineage & Dependency Matrix", root_content)
        self.assertIn("Semantic Models Inventory", root_content)
        self.assertIn("Reports & Dashboards Inventory", root_content)

        # Verify lineage entries
        self.assertIn("Ecommerce Sales", root_content)
        self.assertIn("retail_sales_bim", root_content)

        # 2. Model Markdowns
        # Should have models/Ecommerce_Sales/README.md
        self.assertIn("models/Ecommerce_Sales/README.md", docs)
        ecom_model_index = docs["models/Ecommerce_Sales/README.md"]
        self.assertIn("Semantic Model Documentation", ecom_model_index)

        # Tables should be in models/Ecommerce_Sales/tables/
        ecom_tables = [p for p in docs if p.startswith("models/Ecommerce_Sales/tables/")]
        self.assertGreater(len(ecom_tables), 0)

        # Measures should be in models/Ecommerce_Sales/measures/
        ecom_measures = [p for p in docs if p.startswith("models/Ecommerce_Sales/measures/")]
        self.assertGreater(len(ecom_measures), 0)

        # 3. Report Markdowns
        # Should have reports/Ecommerce_Sales/README.md
        self.assertIn("reports/Ecommerce_Sales/README.md", docs)
        ecom_rep_index = docs["reports/Ecommerce_Sales/README.md"]
        self.assertIn("Report Identity & Dataset Binding", ecom_rep_index)
        self.assertIn("../../models/Ecommerce_Sales/README.md", ecom_rep_index)

        # Visual pages
        ecom_visuals = [p for p in docs if p.startswith("reports/Ecommerce_Sales/visuals/") and p.endswith(".md")]
        self.assertGreater(len(ecom_visuals), 0)

    def test_generate_workspace_html_documents(self):
        generator = WorkspaceDocGenerator(self.config)
        docs = generator.generate_all_html_documents(self.scan_result)

        # 1. Root Master Portal (Streamlined to Projects, Models, and Reports)
        self.assertIn("index.html", docs)
        root_html = docs["index.html"]
        self.assertIn("Unified inventory and cross-artifact lineage", root_html)
        self.assertIn("Repository Projects & Directory Structure", root_html)
        self.assertNotIn("Data Lineage & Dependency Matrix", root_html)
        self.assertIn("Semantic Models Inventory", root_html)
        self.assertIn("Reports & Dashboards Inventory", root_html)

        # 2. Centralized Static Assets (Zero dependency, pure CSS, no JS)
        self.assertIn("assets/style.css", docs)
        self.assertNotIn("assets/app.js", docs)
        self.assertNotIn("assets/search_index.js", docs)
        self.assertNotIn("<script", root_html)

        # 3. Model HTML pages
        self.assertIn("models/Ecommerce_Sales/index.html", docs)
        ecom_tables_html = [p for p in docs if p.startswith("models/Ecommerce_Sales/tables/") and p.endswith(".html")]
        self.assertGreater(len(ecom_tables_html), 0)

        # 4. Report HTML pages
        self.assertIn("reports/Ecommerce_Sales/index.html", docs)
        ecom_rep_html = docs["reports/Ecommerce_Sales/index.html"]
        self.assertIn("Report Overview", ecom_rep_html)
        self.assertIn("models/Ecommerce_Sales/index.html", ecom_rep_html)

        # 5. Table exclusions in sidebar and documents adhere to configuration
        for m_id, model in self.scan_result.models.items():
            scoped_cfg = self.config.get_scoped_config(model.artifact_id)
            for tbl in model.tables:
                clean_t = sanitize_filename(tbl)
                tbl_rel = f"models/{sanitize_filename(model.name)}/tables/{clean_t}.html"
                if scoped_cfg.is_table_excluded(tbl):
                    self.assertNotIn(tbl_rel, docs, f"Excluded table {tbl} must not have document")
                    self.assertNotIn(f">{escape(tbl)}<", root_html, f"Excluded table {tbl} must not appear in sidebar")
                else:
                    self.assertIn(tbl_rel, docs, f"Non-excluded table {tbl} must have document")

    def test_write_to_directory_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = WorkspaceDocGenerator(self.config)
            results = generator.write_to_directory(self.scan_result, tmpdir, output_format="both")

            md_files = results["markdown"]
            html_files = results["html"]

            self.assertGreater(len(md_files), 10)
            self.assertGreater(len(html_files), 10)

            # Check files exist on disk
            self.assertTrue((Path(tmpdir) / "markdown" / "README.md").is_file())
            self.assertTrue((Path(tmpdir) / "markdown" / "models" / "Ecommerce_Sales" / "README.md").is_file())
            self.assertTrue((Path(tmpdir) / "markdown" / "reports" / "Ecommerce_Sales" / "README.md").is_file())

            self.assertTrue((Path(tmpdir) / "html" / "index.html").is_file())
            self.assertTrue((Path(tmpdir) / "html" / "assets" / "style.css").is_file())
            self.assertFalse((Path(tmpdir) / "html" / "assets" / "app.js").exists())
            self.assertFalse((Path(tmpdir) / "html" / "assets" / "search_index.js").exists())
            self.assertTrue((Path(tmpdir) / "html" / "models" / "Ecommerce_Sales" / "index.html").is_file())
            self.assertTrue((Path(tmpdir) / "html" / "reports" / "Ecommerce_Sales" / "index.html").is_file())

            # Verify on disk that tables declared excludable by configuration are absent
            for m_id, model in self.scan_result.models.items():
                scoped_cfg = self.config.get_scoped_config(model.artifact_id)
                for tbl in model.tables:
                    clean_t = sanitize_filename(tbl)
                    tbl_file = Path(tmpdir) / "html" / "models" / sanitize_filename(model.name) / "tables" / f"{clean_t}.html"
                    if scoped_cfg.is_table_excluded(tbl):
                        self.assertFalse(tbl_file.exists(), f"Excluded table {tbl} must not exist on disk")
                    else:
                        self.assertTrue(tbl_file.is_file(), f"Active table {tbl} must exist on disk")

    def test_configurable_table_exclusions(self):
        """
        Verifies that tables declared excludable via configuration
        (either by explicit name or regex pattern) are dynamically excluded
        from the sidebar navigation tree, workspace index, and generated documents,
        while non-excluded tables are preserved.
        """
        custom_config = DocGenConfig(
            excluded_tables=["Customers", "Products"],
            excluded_table_patterns=["^Channels$"],
        )

        scanner = CodebaseScanner(self.samples_dir, config=custom_config)
        scan_result = scanner.scan(populate_symbols=True)

        generator = WorkspaceDocGenerator(custom_config)
        docs = generator.generate_all_html_documents(scan_result)
        root_html = docs["index.html"]

        # 1. Configured exclusions must be excluded from navigation and documents
        for ex_table in ["Customers", "Products", "Channels"]:
            self.assertTrue(custom_config.is_table_excluded(ex_table))
            clean_ex = sanitize_filename(ex_table)
            matching_docs = [p for p in docs if p.endswith(f"/tables/{clean_ex}.html")]
            self.assertEqual(len(matching_docs), 0, f"No document should be generated for excluded table {ex_table}")
            self.assertNotIn(f"/tables/{clean_ex}.html", root_html, f"Excluded table {ex_table} must not be in sidebar links")

        # 2. Non-excluded tables must be preserved in navigation and documents
        for active_table in ["Orders", "Date", "DimStore", "DimCity"]:
            self.assertFalse(custom_config.is_table_excluded(active_table))
            clean_active = sanitize_filename(active_table)
            matching_docs = [p for p in docs if p.endswith(f"/tables/{clean_active}.html")]
            self.assertGreater(len(matching_docs), 0, f"Document should be generated for active table {active_table}")
            self.assertIn(f"/tables/{clean_active}.html", root_html, f"Active table {active_table} must be in sidebar links")

    def test_workspace_sidebar_table_nature_badges(self):
        """Verifies that table nature badges (Fact, Dim, Date, etc.) are rendered in the workspace sidebar."""
        generator = WorkspaceDocGenerator(self.config)
        docs = generator.generate_all_html_documents(self.scan_result)
        root_html = docs["index.html"]

        # Check for nature badges in sidebar navigation
        self.assertIn("nav-item-badge badge badge-role-", root_html)
        self.assertIn(">Fact<", root_html)
        self.assertIn(">Dim<", root_html)

    def test_workspace_index_streamlined(self):
        """Verifies that workspace index HTML is streamlined without redundant badges or Sections quicknav."""
        generator = WorkspaceDocGenerator(self.config)
        docs = generator.generate_all_html_documents(self.scan_result)
        root_html = docs["index.html"]

        # Ensure cluttered/pompous tags and Sections: quicknav are removed
        self.assertNotIn("PBIP Enterprise Workspace", root_html)
        self.assertNotIn("Sections:", root_html)
        self.assertNotIn('class="page-quicknav"', root_html)
        self.assertNotIn('id="tab-desc"', root_html)

        # Verify direct transition from KPIs to Projects section
        kpi_pos = root_html.find('class="kpi-grid"')
        projects_pos = root_html.find('id="tab-projects"')
        self.assertGreater(kpi_pos, 0)
        self.assertGreater(projects_pos, kpi_pos)

    def test_workspace_grouping_by_folder(self):
        """
        Verifies that when workspace_grouping is 'folder' (default),
        artifacts are organized by repository directory, with folder SVG icons,
        folder names, and Model/Report distinction badges in the sidebar.
        """
        self.assertEqual(self.config.workspace_grouping, "folder")
        generator = WorkspaceDocGenerator(self.config)
        docs = generator.generate_all_html_documents(self.scan_result)
        root_html = docs["index.html"]

        # 1. Check folder-centric sidebar elements
        self.assertIn("nav-folder-icon", root_html)
        self.assertIn("Ecommerce_Sales", root_html)
        self.assertIn("retail_sales_bim", root_html)

        # 2. Check artifact SVG icons in sidebar
        self.assertIn("svg-icon-datamodel", root_html)
        self.assertIn("svg-icon-report", root_html)

        # 3. Check get_artifacts_by_folder structure
        folders = self.scan_result.get_artifacts_by_folder()
        self.assertIn("Ecommerce_Sales", folders)
        ecom_f = folders["Ecommerce_Sales"]
        self.assertEqual(len(ecom_f["models"]), 1)
        self.assertEqual(len(ecom_f["reports"]), 1)

    def test_workspace_grouping_flat_fallback(self):
        """Verifies that setting workspace_grouping to 'flat' restores the legacy flat sections."""
        flat_config = DocGenConfig(workspace_grouping="flat")
        generator = WorkspaceDocGenerator(flat_config)
        docs = generator.generate_all_html_documents(self.scan_result)
        root_html = docs["index.html"]

        self.assertIn("<span>Semantic Models</span>", root_html)
        self.assertIn("<span>Reports & Dashboards</span>", root_html)
        self.assertNotIn("nav-folder-icon", root_html)

    def test_workspace_index_directory_structure_table(self):
        """
        Verifies that Workspace Catalog (both index.html and README.md)
        features the 'Repository Projects & Directory Structure' section and
        includes project folder paths in inventories and lineage matrices.
        """
        generator = WorkspaceDocGenerator(self.config)
        docs_html = generator.generate_all_html_documents(self.scan_result)
        docs_md = generator.generate_all_markdown_documents(self.scan_result)

        root_html = docs_html["index.html"]
        root_md = docs_md["README.md"]

        # HTML assertions
        self.assertIn("Repository Projects & Directory Structure", root_html)
        self.assertIn("<th>Project Directory</th>", root_html)
        self.assertIn("<code>Ecommerce_Sales</code>", root_html)
        self.assertIn("<code>retail_sales_bim</code>", root_html)

        # Markdown assertions
        self.assertIn("## Repository Directory Structure & Projects", root_md)
        self.assertIn("| Project Directory |", root_md)
        self.assertIn("**`Ecommerce_Sales`**", root_md)
        self.assertIn("**`retail_sales_bim`**", root_md)

    def test_no_visuals_workspace_behavior(self):
        """
        Verifies that when include_visual_docs is False:
        1. No visual pages are generated.
        2. Visual pages are omitted from the sidebar tree.
        3. Report overview explains that visuals were excluded by configuration.
        """
        no_vis_cfg = DocGenConfig(include_visual_docs=False)
        generator = WorkspaceDocGenerator(no_vis_cfg)
        docs_html = generator.generate_all_html_documents(self.scan_result)
        docs_md = generator.generate_all_markdown_documents(self.scan_result)

        # 1. No visual pages generated
        visual_html = [p for p in docs_html if "/visuals/" in p and p.endswith(".html")]
        visual_md = [p for p in docs_md if "/visuals/" in p and p.endswith(".md")]
        self.assertEqual(len(visual_html), 0)
        self.assertEqual(len(visual_md), 0)

        # 2. No visual page links in sidebar
        root_html = docs_html["index.html"]
        self.assertNotIn("/visuals/", root_html)

        # 3. Report overview notes exclusion
        rep_html = docs_html["reports/Ecommerce_Sales/index.html"]
        rep_md = docs_md["reports/Ecommerce_Sales/README.md"]
        self.assertIn("Visual page documentation has been excluded by configuration", rep_html)
        self.assertIn("Visual page documentation has been excluded by configuration", rep_md)

    def test_visual_cross_artifact_link_resolution(self):
        """
        Verifies that links inside visual pages in multi-artifact workspace
        resolve dynamically via relative path to target models, and never contain broken ../tables/
        or ../measures/ paths.
        """
        generator = WorkspaceDocGenerator(self.config)
        docs_html = generator.generate_all_html_documents(self.scan_result)
        docs_md = generator.generate_all_markdown_documents(self.scan_result)

        # 1. HTML visual page checks
        ecom_html = docs_html.get("reports/Ecommerce_Sales/visuals/Executive_Summary.html")
        self.assertIsNotNone(ecom_html)
        self.assertNotIn('href="../tables/', ecom_html)
        self.assertNotIn('href="../measures/', ecom_html)
        self.assertIn('href="../../../models/Ecommerce_Sales/tables/Products.html"', ecom_html)
        self.assertIn('href="../../../models/Ecommerce_Sales/measures/Orders/Gross_Margin.html"', ecom_html)

        # 2. Markdown visual page checks
        ecom_md = docs_md.get("reports/Ecommerce_Sales/visuals/Executive_Summary.md")
        self.assertIsNotNone(ecom_md)
        self.assertNotIn('](../tables/', ecom_md)
        self.assertNotIn('](../measures/', ecom_md)
        self.assertIn('](../../../models/Ecommerce_Sales/tables/Products.md)', ecom_md)
        self.assertIn('](../../../models/Ecommerce_Sales/measures/Orders/Gross_Margin.md)', ecom_md)

    def test_workspace_folder_depth_clustering(self):
        """
        Verifies that get_artifacts_by_folder clusters artifacts by top-level
        domain when folder_depth=1 (default), avoiding 1-to-1 leaf folder explosion,
        and clusters deeper subfolders when folder_depth=2.
        """
        root = Path("repo")
        m1 = DiscoveredModel(
            name="GeneralLedger",
            path=root / "finance" / "core" / "GeneralLedger.SemanticModel",
            rel_path="finance/core/GeneralLedger.SemanticModel",
            raw_name="GeneralLedger.SemanticModel",
            model_format="TMDL",
        )
        r1 = DiscoveredReport(
            name="MonthlyPnL",
            path=root / "finance" / "reports" / "monthly" / "MonthlyPnL.Report",
            rel_path="finance/reports/monthly/MonthlyPnL.Report",
            raw_name="MonthlyPnL.Report",
            report_format="PBIR",
        )
        r2 = DiscoveredReport(
            name="AnnualBalanceSheet",
            path=root / "finance" / "reports" / "annual" / "AnnualBalanceSheet.Report",
            rel_path="finance/reports/annual/AnnualBalanceSheet.Report",
            raw_name="AnnualBalanceSheet.Report",
            report_format="PBIR",
        )
        r3 = DiscoveredReport(
            name="SalesPipeline",
            path=root / "sales" / "direct" / "SalesPipeline.Report",
            rel_path="sales/direct/SalesPipeline.Report",
            raw_name="SalesPipeline.Report",
            report_format="PBIR",
        )

        mock_scan = WorkspaceScanResult(
            root_path=root,
            models={m1.artifact_id: m1},
            reports={r1.artifact_id: r1, r2.artifact_id: r2, r3.artifact_id: r3},
        )

        # 1. Depth = 1 (default domain clustering)
        folders_d1 = mock_scan.get_artifacts_by_folder(folder_depth=1)
        self.assertIn("finance", folders_d1)
        self.assertIn("sales", folders_d1)
        self.assertEqual(len(folders_d1), 2)
        # All 3 finance artifacts grouped together
        self.assertEqual(folders_d1["finance"]["total_count"], 3)
        self.assertEqual(len(folders_d1["finance"]["models"]), 1)
        self.assertEqual(len(folders_d1["finance"]["reports"]), 2)
        # 1 sales artifact
        self.assertEqual(folders_d1["sales"]["total_count"], 1)

        # 2. Depth = 2 (subfolder clustering)
        folders_d2 = mock_scan.get_artifacts_by_folder(folder_depth=2)
        self.assertIn("finance/core", folders_d2)
        self.assertIn("finance/reports", folders_d2)
        self.assertIn("sales/direct", folders_d2)
        self.assertEqual(len(folders_d2), 3)
        self.assertEqual(folders_d2["finance/reports"]["total_count"], 2)

        # 3. Test WorkspaceHtmlLayoutBuilder sidebar with workspace_folder_depth=1
        cfg_d1 = DocGenConfig(workspace_folder_depth=1)
        layout_d1 = WorkspaceHtmlLayoutBuilder(workspace_scan=mock_scan, config=cfg_d1)
        sidebar_html = layout_d1._build_unified_sidebar(current_path="index.html", rel_root=".")
        # HTML sidebar section titles should feature the top-level domains
        self.assertIn('title="finance"', sidebar_html)
        self.assertIn('title="sales"', sidebar_html)

        # 4. Test WorkspaceDocGenerator index HTML directory table with workspace_folder_depth=1
        gen_d1 = WorkspaceDocGenerator(cfg_d1)
        index_html = gen_d1._build_workspace_index_html(mock_scan)
        self.assertIn('<code>finance</code>', index_html)
        self.assertIn('<code>sales</code>', index_html)

    def test_sidebar_refinements_and_page_numbering(self):
        """Verifies report page numbering badges, right-aligned model/report tags, and removal of v0.2.0 footer."""
        r = DiscoveredReport(
            name="Sales Performance",
            path=Path("/workspace/sales/Sales.Report"),
            rel_path="sales/Sales.Report",
            raw_name="Sales.Report",
            report_format="PBIR",
            page_names=["Overview", "Regional Breakdown"],
        )
        mock_scan = WorkspaceScanResult(
            root_path=Path("/workspace"),
            models={},
            reports={r.artifact_id: r},
        )
        cfg = DocGenConfig(workspace_folder_depth=1)
        layout = WorkspaceHtmlLayoutBuilder(workspace_scan=mock_scan, config=cfg)
        sidebar_html = layout._build_unified_sidebar(current_path="index.html", rel_root=".")

        # 1. Report page numbering badges
        self.assertIn("badge-dim", sidebar_html)
        self.assertIn("#1", sidebar_html)
        self.assertIn("#2", sidebar_html)

        # 2. SVG Report icon in sidebar subgroup header
        self.assertIn("svg-icon-report", sidebar_html)

        # 3. Presence of pbip-doc version in sidebar footer
        wrapped = layout.wrap_page("index.html", "Catalog", [], "<p>Test</p>")
        self.assertIn("sidebar-footer", wrapped)
        self.assertIn("pbip-doc", wrapped)

    def test_report_overview_tags_cards_order_and_composite_models(self):
        """Verifies Report header tags, KPI cards, chapter order (Pages -> Models List), and composite model resolution per page."""
        from pbip_doc.report_schema import (
            PBIPReportModel,
            PageDefinition,
            VisualDefinition,
            CalculationContext,
            EvaluatedMetric,
        )

        m_core = DiscoveredModel(
            name="CoreSales",
            path=Path("/workspace/CoreSales.SemanticModel"),
            rel_path="CoreSales.SemanticModel",
            raw_name="CoreSales.SemanticModel",
            model_format="TMDL",
            tables=["Sales"],
            measures={"Total Revenue": "Sales"},
        )
        m_ext = DiscoveredModel(
            name="FinanceBudget",
            path=Path("/workspace/FinanceBudget.SemanticModel"),
            rel_path="FinanceBudget.SemanticModel",
            raw_name="FinanceBudget.SemanticModel",
            model_format="BIM",
            tables=["Budget"],
            measures={"Budget Target": "Budget"},
        )

        p1 = PageDefinition(
            page_id="p1",
            display_name="Composite Executive View",
            page_number=1,
            visuals=[
                VisualDefinition(
                    visual_id="v1",
                    visual_type="barChart",
                    title="Revenue vs Budget",
                    calculation_context=CalculationContext(
                        evaluated_metrics=[
                            EvaluatedMetric(table="Sales", field="Total Revenue", field_type="MEASURE", role="Y", model_key="Sales[Total Revenue]"),
                            EvaluatedMetric(table="Budget", field="Budget Target", field_type="MEASURE", role="Y", model_key="Budget[Budget Target]"),
                        ]
                    ),
                )
            ],
        )

        rep_obj = PBIPReportModel(
            report_name="ExecComposite",
            format="PBIR",
            source_path="/workspace/ExecComposite.Report",
            pages=[p1],
        )
        r = DiscoveredReport(
            name="ExecComposite",
            path=Path("/workspace/ExecComposite.Report"),
            rel_path="ExecComposite.Report",
            raw_name="ExecComposite.Report",
            report_format="PBIR",
            bound_model_id=m_core.artifact_id,
            bound_model_name="CoreSales",
            page_names=["Composite Executive View"],
            report_obj=rep_obj,
        )

        mock_scan = WorkspaceScanResult(
            root_path=Path("/workspace"),
            models={m_core.artifact_id: m_core, m_ext.artifact_id: m_ext},
            reports={r.artifact_id: r},
        )

        gen = WorkspaceDocGenerator(self.config)
        md_out = gen._build_report_overview_markdown(r, mock_scan, m_core)
        html_out = gen._build_report_overview_html(r, mock_scan, m_core)

        # 1. Markdown chapter order: Pages before Models List
        self.assertLess(md_out.find("## Report Canvas Pages"), md_out.find("## Models List"))
        self.assertIn("[CoreSales](../../models/CoreSales/README.md)", md_out)
        self.assertIn("[FinanceBudget](../../models/FinanceBudget/README.md)", md_out)
        self.assertIn("Composite Model Reference (Local Workspace)", md_out)

        # 2. HTML header tags (no single hardcoded Bound Model badge in title) & KPI cards
        self.assertNotIn("Bound Model:", html_out)
        self.assertIn("header-icon-report", html_out)
        self.assertIn('<code>PBIR</code>', html_out)
        self.assertIn('<div class="kpi-label">Semantic Models</div>', html_out)
        self.assertIn('<div class="kpi-label">Dynamic Visuals</div>', html_out)

        # 3. HTML chapter blocks: Description -> Models List -> Pages
        self.assertIn('id="tab-summary"', html_out)
        self.assertLess(html_out.find('id="block-desc_block"'), html_out.find('id="block-models_block"'))
        self.assertLess(html_out.find('id="block-models_block"'), html_out.find('id="block-pages_block"'))
        self.assertIn("CoreSales", html_out)
        self.assertIn("FinanceBudget", html_out)

    def test_sidebar_expression_chapter_toggled_on_by_default_and_ordered_etl_model_report(self):
        """Verifies that expressions are included in sidebar by default (ETL -> Model -> Report order), and omitted when include_expression_chapter=False."""
        m = DiscoveredModel(
            name="ModelWithExpr",
            path=Path("/workspace/ModelWithExpr.SemanticModel"),
            rel_path="ModelWithExpr.SemanticModel",
            raw_name="ModelWithExpr.SemanticModel",
            model_format="TMDL",
            tables=["Sales", "Products"],
            expressions=["Staging_Query", "EndpointParam"],
        )
        mock_scan = WorkspaceScanResult(
            root_path=Path("/workspace"),
            models={m.artifact_id: m},
            reports={},
        )

        # 1. Default config: expressions MUST appear in sidebar by default and precede Model tables (ETL, Model, Report)
        cfg_default = DocGenConfig()
        self.assertTrue(cfg_default.include_expression_chapter)
        self.assertTrue(cfg_default.include_expression_sidebar_chapter)
        layout_default = WorkspaceHtmlLayoutBuilder(workspace_scan=mock_scan, config=cfg_default)
        sidebar_default = layout_default._build_unified_sidebar(current_path="index.html", rel_root=".")
        self.assertIn("Sales", sidebar_default)
        self.assertIn("Products", sidebar_default)
        self.assertIn("<span>ModelWithExpr</span>", sidebar_default)
        self.assertIn('title="ETL &amp; Data Pipelines - ModelWithExpr"', sidebar_default)
        self.assertIn("ETL Overview", sidebar_default)
        self.assertIn("Staging_Query", sidebar_default)
        self.assertIn("EndpointParam", sidebar_default)

        # Check order: ETL precedes Model tables in sidebar
        idx_etl = sidebar_default.find('title="ETL &amp; Data Pipelines - ModelWithExpr"')
        idx_model = sidebar_default.find("Model Overview")
        self.assertTrue(idx_etl < idx_model, "ETL section must precede Model section in sidebar (ETL -> Model -> Report)")

        # 2. Disabled config: include_expression_chapter=False
        cfg_disabled = DocGenConfig(include_expression_chapter=False)
        self.assertFalse(cfg_disabled.include_expression_chapter)
        self.assertFalse(cfg_disabled.include_expression_sidebar_chapter)
        layout_disabled = WorkspaceHtmlLayoutBuilder(workspace_scan=mock_scan, config=cfg_disabled)
        sidebar_disabled = layout_disabled._build_unified_sidebar(current_path="index.html", rel_root=".")
        self.assertIn("Sales", sidebar_disabled)
        self.assertIn("Products", sidebar_disabled)
        self.assertNotIn("Staging_Query", sidebar_disabled)
        self.assertNotIn("EndpointParam", sidebar_disabled)

    def test_workspace_inventories_ordered_etl_model_report(self):
        """Verifies that workspace index documentation displays in Projects -> Model -> Report sequence in both Markdown and HTML."""
        generator = WorkspaceDocGenerator(config=DocGenConfig())
        docs_md = generator.generate_all_markdown_documents(self.scan_result)
        root_md = docs_md["README.md"]

        idx_projects_md = root_md.find("## Repository Directory Structure & Projects")
        idx_model_md = root_md.find("## Semantic Models Inventory")
        idx_report_md = root_md.find("## Reports & Dashboards Inventory")

        self.assertNotEqual(idx_projects_md, -1, "Projects must be present in master markdown by default")
        self.assertNotEqual(idx_model_md, -1, "Semantic Models Inventory must be present in master markdown")
        self.assertNotEqual(idx_report_md, -1, "Reports & Dashboards Inventory must be present in master markdown")
        self.assertTrue(
            idx_projects_md < idx_model_md < idx_report_md,
            f"Expected Projects < Model < Report order in Markdown index, got indices: Projects={idx_projects_md}, Model={idx_model_md}, Report={idx_report_md}"
        )

        docs_html = generator.generate_all_html_documents(self.scan_result)
        root_html = docs_html["index.html"]

        # Workspace catalog navigation streamlined to 3 primary tabs: Projects -> Models -> Reports
        idx_projects_html = root_html.find('id="tab-projects"')
        idx_model_html = root_html.find('id="tab-models"')
        idx_report_html = root_html.find('id="tab-reports"')

        self.assertNotEqual(idx_projects_html, -1, "Projects section must be present in master HTML by default")
        self.assertNotEqual(idx_model_html, -1, "Semantic Models section must be present in master HTML")
        self.assertNotEqual(idx_report_html, -1, "Reports section must be present in master HTML")
        self.assertTrue(
            idx_projects_html < idx_model_html < idx_report_html,
            f"Expected Projects < Model < Report order in HTML index, got indices: Projects={idx_projects_html}, Model={idx_model_html}, Report={idx_report_html}"
        )
        self.assertEqual(root_html.find('id="tab-powerquery"'), -1, "Redundant global Dataflow tab must be removed from master HTML")
        self.assertEqual(root_html.find('id="tab-lineage"'), -1, "Redundant global Lineage Matrix tab must be removed from master HTML")

    def test_transitive_table_and_measure_link_resolution(self):
        """Issue 1: When a report inherits tables/measures via intermediate models, links ascend to originating Datamodel."""
        m_origin = DiscoveredModel(
            name="Datamodel",
            path=Path("/workspace/Datamodel.SemanticModel"),
            rel_path="Datamodel.SemanticModel",
            raw_name="Datamodel.SemanticModel",
            model_format="TMDL",
            tables=["TabellaA"],
            measures={"Total Revenue": "TabellaA"},
        )
        m_intermediate = DiscoveredModel(
            name="ReportA_Model",
            path=Path("/workspace/ReportA.SemanticModel"),
            rel_path="ReportA.SemanticModel",
            raw_name="ReportA.SemanticModel",
            model_format="TMDL",
            tables=["TabellaA"],
            inherited_tables={"TabellaA": "Datamodel"},
            measures={"Total Revenue": "TabellaA"},
            inherited_measures={"Total Revenue": "Datamodel"},
        )
        r_downstream = DiscoveredReport(
            name="ReportB",
            path=Path("/workspace/ReportB.Report"),
            rel_path="ReportB.Report",
            raw_name="ReportB.Report",
            report_format="PBIR",
            bound_model_name="ReportA_Model",
            bound_model_id=m_intermediate.artifact_id,
        )
        mock_scan = WorkspaceScanResult(
            root_path=Path("/workspace"),
            models={m_origin.artifact_id: m_origin, m_intermediate.artifact_id: m_intermediate},
            reports={r_downstream.artifact_id: r_downstream},
        )
        m_intermediate.bound_reports = [r_downstream.artifact_id]

        gen = WorkspaceDocGenerator(self.config)
        res_t, res_m = gen._create_link_resolvers(
            mock_scan, r_downstream, m_intermediate, current_doc_dir="reports/ReportB/visuals", ext="html"
        )
        t_url = res_t("TabellaA")
        m_url = res_m("TabellaA", "Total Revenue")

        # Must ascend to Datamodel, NOT stay on ReportA_Model
        self.assertIsNotNone(t_url)
        self.assertIn("models/Datamodel/tables/TabellaA.html", t_url)
        self.assertNotIn("ReportA", t_url)

        self.assertIsNotNone(m_url)
        self.assertIn("models/Datamodel/measures/TabellaA/Total_Revenue.html", m_url)
        self.assertNotIn("ReportA", m_url)

    def test_transitive_connected_reports_lineage(self):
        """Issue 2: Reports connected to downstream semantic models appear in originating Datamodel's connected reports."""
        m_origin = DiscoveredModel(
            name="Datamodel",
            path=Path("/workspace/Datamodel.SemanticModel"),
            rel_path="Datamodel.SemanticModel",
            raw_name="Datamodel.SemanticModel",
            model_format="TMDL",
            tables=["TabellaA"],
        )
        m_intermediate = DiscoveredModel(
            name="ReportA_Model",
            path=Path("/workspace/ReportA.SemanticModel"),
            rel_path="ReportA.SemanticModel",
            raw_name="ReportA.SemanticModel",
            model_format="TMDL",
            tables=["TabellaA"],
            inherited_tables={"TabellaA": "Datamodel"},
        )
        r_a = DiscoveredReport(
            name="ReportA",
            path=Path("/workspace/ReportA.Report"),
            rel_path="ReportA.Report",
            raw_name="ReportA.Report",
            report_format="PBIR",
            bound_model_name="ReportA_Model",
            bound_model_id=m_intermediate.artifact_id,
            page_names=["Page A"],
        )
        r_b = DiscoveredReport(
            name="ReportB",
            path=Path("/workspace/ReportB.Report"),
            rel_path="ReportB.Report",
            raw_name="ReportB.Report",
            report_format="PBIR",
            bound_model_name="ReportA_Model",
            bound_model_id=m_intermediate.artifact_id,
            page_names=["Page B1", "Page B2"],
        )
        m_intermediate.bound_reports = [r_a.artifact_id, r_b.artifact_id]

        mock_scan = WorkspaceScanResult(
            root_path=Path("/workspace"),
            models={m_origin.artifact_id: m_origin, m_intermediate.artifact_id: m_intermediate},
            reports={r_a.artifact_id: r_a, r_b.artifact_id: r_b},
        )

        downstream = mock_scan.get_downstream_reports(m_origin.artifact_id)
        downstream_names = [d["report"].name for d in downstream]
        self.assertIn("ReportA", downstream_names)
        self.assertIn("ReportB", downstream_names)
        for d in downstream:
            self.assertFalse(d["is_direct"])
            self.assertEqual(d["via_model"], "ReportA_Model")

        gen = WorkspaceDocGenerator(self.config)
        md_index = gen._build_workspace_index_markdown(mock_scan)
        self.assertIn("[ReportA](reports/ReportA/README.md) *(via ReportA_Model)*", md_index)
        self.assertIn("[ReportB](reports/ReportB/README.md) *(via ReportA_Model)*", md_index)

    def test_report_overview_page_visibility_column(self):
        """Issue 5: Report catalog shows Visibility column before Dynamic Visuals."""
        from pbip_doc.report_schema import PBIPReportModel, PageDefinition
        p1 = PageDefinition(page_id="p1", display_name="Page One", page_number=1, is_hidden=False)
        p2 = PageDefinition(page_id="p2", display_name="Page Two", page_number=2, is_hidden=True)
        rep_obj = PBIPReportModel(report_name="SalesViz", format="PBIR", source_path="/workspace/SalesViz.Report", pages=[p1, p2])
        r = DiscoveredReport(
            name="SalesViz",
            path=Path("/workspace/SalesViz.Report"),
            rel_path="SalesViz.Report",
            raw_name="SalesViz.Report",
            report_format="PBIR",
            page_names=["Page One", "Page Two"],
            report_obj=rep_obj,
        )
        mock_scan = WorkspaceScanResult(
            root_path=Path("/workspace"),
            models={},
            reports={r.artifact_id: r},
        )
        gen = WorkspaceDocGenerator(self.config)
        md_out = gen._build_report_overview_markdown(r, mock_scan, None)
        html_out = gen._build_report_overview_html(r, mock_scan, None)

        # Markdown checks
        self.assertIn("| # | Page Name | Referenced Models | Visibility | Dynamic Visuals | Visuals Catalog |", md_out)
        self.assertIn("| 1 | **Page One** | — | Visible | `0` |", md_out)
        self.assertIn("| 2 | **Page Two** | — | Hidden | `0` |", md_out)

        # HTML checks
        self.assertIn("<th>Visibility</th>\n                  <th>Dynamic Visuals</th>", html_out)
        self.assertIn('<span class="badge badge-status-active">Visible</span>', html_out)
        self.assertIn('<span class="badge badge-dim">Hidden</span>', html_out)

    def test_workspace_html_theme_propagation(self):
        for theme, expected_root, expected_svg_cls, unexpected_svg_cls in [
            ("auto", '<html lang="en">', 'class="model-relationship-diagram "', ('class="model-relationship-diagram theme-force-light"', 'class="model-relationship-diagram theme-force-dark"')),
            ("light", '<html lang="en" data-theme="light">', 'class="model-relationship-diagram theme-force-light"', ('class="model-relationship-diagram theme-force-dark"',)),
            ("dark", '<html lang="en" data-theme="dark">', 'class="model-relationship-diagram theme-force-dark"', ('class="model-relationship-diagram theme-force-light"',)),
        ]:
            cfg = DocGenConfig(output_format="html", html_theme=theme)
            gen = WorkspaceDocGenerator(cfg)
            docs = gen.generate_all_html_documents(self.scan_result)

            root_html = docs["index.html"]
            model_html = docs["models/Ecommerce_Sales/index.html"]
            report_html = docs["reports/Ecommerce_Sales/index.html"]

            for page in (root_html, model_html, report_html):
                self.assertIn(expected_root, page)
                if theme == "auto":
                    self.assertNotIn("data-theme=", page.split("<head>", 1)[0])

            self.assertIn(expected_svg_cls, model_html)
            for bad_cls in unexpected_svg_cls:
                self.assertNotIn(bad_cls, model_html)

            self.assertNotIn('@media (prefers-color-scheme: dark) { #page-tab-', model_html)
            self.assertNotIn('@media (prefers-color-scheme: dark) { #sc-tab-', model_html)
            if theme == "dark":
                self.assertIn(':root[data-theme="dark"] #page-tab-', model_html)


if __name__ == "__main__":
    unittest.main()
