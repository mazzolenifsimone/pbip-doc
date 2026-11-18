"""
Unit tests for PBIP CodebaseScanner & Workspace Lineage Discovery.
"""

import os
import tempfile
import unittest
from pathlib import Path

from pbip_doc.codebase_scanner import CodebaseScanner, WorkspaceScanResult
from pbip_doc.docgen.config import DocGenConfig


class TestCodebaseScanner(unittest.TestCase):

    def setUp(self):
        self.samples_dir = Path(__file__).resolve().parent.parent / "samples"

    def test_scan_samples_workspace(self):
        scanner = CodebaseScanner(self.samples_dir)
        result = scanner.scan(populate_symbols=True)

        # Check models discovered
        # Expected in pbip-doc-gen/samples: Ecommerce Sales (TMDL), retail_sales_bim (BIM)
        self.assertEqual(len(result.models), 2)
        ecom_model = result.get_model("Ecommerce_Sales")
        self.assertIsNotNone(ecom_model, "Ecommerce_Sales model should be discovered")
        bim_model = result.get_model("retail_sales_bim")
        self.assertIsNotNone(bim_model, "retail_sales_bim standalone model should be discovered")

        # Check reports discovered
        self.assertEqual(len(result.reports), 1)
        ecom_report = result.get_report("Ecommerce_Sales")
        self.assertIsNotNone(ecom_report, "Ecommerce_Sales report should be discovered")

        # Check lineage bindings
        self.assertFalse(ecom_report.is_external_model)
        self.assertEqual(ecom_report.bound_model_name, ecom_model.name)
        self.assertIn(ecom_report.artifact_id, ecom_model.bound_reports)

        # Check symbol lookup
        margin_matches = result.find_measure("Gross Margin %")
        self.assertGreaterEqual(len(margin_matches), 1)
        found_ecom = any(m[0].name == ecom_model.name for m in margin_matches)
        self.assertTrue(found_ecom, "Should find Gross Margin % in Ecommerce_Sales model")

        # Check measure in retail_sales_bim
        bim_matches = result.find_measure("Total Revenue")
        self.assertGreaterEqual(len(bim_matches), 1)
        found_bim = any(m[0].name == bim_model.name for m in bim_matches)
        self.assertTrue(found_bim, "Should find Total Revenue in retail_sales_bim model")

        # Check table lookup
        tbl_matches = result.find_table("Customers")
        self.assertGreaterEqual(len(tbl_matches), 1)

    def test_scan_single_artifact_direct_target(self):
        # Scan just the Ecommerce SemanticModel folder directly
        ecom_model_dir = self.samples_dir / "Ecommerce_Sales" / "Ecommerce Sales.SemanticModel"
        scanner = CodebaseScanner(ecom_model_dir)
        result = scanner.scan(populate_symbols=True)

        self.assertEqual(len(result.models), 1)
        self.assertTrue(result.is_single_artifact())

    def test_external_dataset_thin_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            report_dir = tmp_path / "Finance.Report"
            report_dir.mkdir()
            def_dir = report_dir / "definition"
            def_dir.mkdir()

            # definition.pbir with byConnection to remote Fabric dataset
            pbir_content = """{
  "version": "4.0",
  "datasetReference": {
    "byConnection": {
      "connectionString": "Data Source=powerbi://api.powerbi.com/v1.0/myorg/CorpWorkspace;Initial Catalog=EnterpriseGL;Integrated Security=ClaimsToken",
      "pbiModelDatabaseName": "EnterpriseGL"
    }
  }
}"""
            (def_dir / "definition.pbir").write_text(pbir_content, encoding="utf-8")
            (def_dir / "report.json").write_text('{"sections": []}', encoding="utf-8")

            scanner = CodebaseScanner(tmp_path)
            result = scanner.scan(populate_symbols=False)

            self.assertEqual(len(result.reports), 1)
            report = result.get_report("Finance")
            self.assertIsNotNone(report)
            self.assertTrue(report.is_external_model)
            self.assertEqual(report.bound_model_name, "EnterpriseGL")

    def test_scanner_respects_configuration_exclusions(self):
        """
        Verifies that CodebaseScanner dynamically excludes tables and their measures
        strictly based on what is declared in configuration (excluded_tables or patterns),
        without hardcoding specific table names.
        """
        custom_cfg = DocGenConfig(
            excluded_tables=["Customers", "Products"],
            excluded_table_patterns=["^Channels$"],
        )
        scanner = CodebaseScanner(self.samples_dir, config=custom_cfg)
        result = scanner.scan(populate_symbols=True)

        ecom_model = result.get_model("Ecommerce_Sales")
        self.assertIsNotNone(ecom_model)

        # Configured exclusions must not be in model.tables
        self.assertNotIn("Customers", ecom_model.tables)
        self.assertNotIn("Channels", ecom_model.tables)

        # Non-excluded tables must be present
        self.assertIn("Orders", ecom_model.tables)
        self.assertIn("Date", ecom_model.tables)

        # find_table should not find excluded tables
        self.assertEqual(len(result.find_table("Customers")), 0)
        self.assertGreater(len(result.find_table("Orders")), 0)


if __name__ == "__main__":
    unittest.main()
