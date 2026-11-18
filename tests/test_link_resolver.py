"""
Unit tests for PublicationScope and LinkResolver (Zero 404 guarantee).
Verifies that when macro-families or entities are excluded, links degrade gracefully
to plain text or styled non-anchor tags in both HTML and Markdown modes.
100% Python Standard Library. Zero external dependencies.
"""

import unittest
from pathlib import Path

from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.link_resolver import PublicationScope, LinkResolver
from pbip_doc.docgen.engine import MarkdownDocGenerator
from pbip_doc.docgen.html_engine import HtmlDocGenerator
from pbip_doc.codebase_scanner import CodebaseScanner


class TestPublicationScopeAndLinkResolver(unittest.TestCase):

    def test_scope_defaults(self):
        scope = PublicationScope()
        self.assertTrue(scope.is_model_published("SalesModel"))
        self.assertTrue(scope.is_report_published("SalesReport"))
        self.assertTrue(scope.is_dataflow_published())
        self.assertTrue(scope.is_table_published("Orders"))
        self.assertTrue(scope.is_measure_published("Orders", "Total Sales"))
        self.assertTrue(scope.is_function_published("MyFunction"))
        self.assertTrue(scope.is_expression_published("Staging_Orders"))
        self.assertTrue(scope.is_report_page_published("SalesReport", "Executive"))

    def test_scope_disabled_macro_families(self):
        scope_no_model = PublicationScope(include_models=False)
        self.assertFalse(scope_no_model.is_model_published("SalesModel"))
        self.assertFalse(scope_no_model.is_table_published("Orders"))
        self.assertFalse(scope_no_model.is_measure_published("Orders", "Total Sales"))
        self.assertFalse(scope_no_model.is_function_published("MyFunction"))
        self.assertTrue(scope_no_model.is_report_published("SalesReport"))
        self.assertTrue(scope_no_model.is_dataflow_published())

        scope_no_report = PublicationScope(include_reports=False)
        self.assertFalse(scope_no_report.is_report_published("SalesReport"))
        self.assertFalse(scope_no_report.is_report_page_published("SalesReport", "Executive"))
        self.assertTrue(scope_no_report.is_model_published())

        scope_no_df = PublicationScope(include_dataflow=False)
        self.assertFalse(scope_no_df.is_dataflow_published())
        self.assertFalse(scope_no_df.is_expression_published("Staging_Orders"))
        self.assertTrue(scope_no_df.is_model_published())

    def test_link_resolver_html_rendering(self):
        # 1. Full scope: emits HTML <a> tags
        scope_full = PublicationScope(include_models=True, include_reports=True, include_dataflow=True)
        resolver_html = LinkResolver(scope=scope_full, rel_root=".", is_html=True)

        tbl_link = resolver_html.link_to_table("Customer")
        self.assertIn('<a href="tables/Customer.html"', tbl_link)
        self.assertIn("Customer", tbl_link)

        meas_link = resolver_html.link_to_measure("Customer", "Customer Count")
        self.assertIn('<a href="measures/Customer/Customer_Count.html"', meas_link)
        self.assertIn("Customer Count", meas_link)

        expr_link = resolver_html.link_to_expression("Staging_Cust")
        self.assertIn('<a href="etl/Staging_Cust.html"', expr_link)

        # 2. Scope without models: links degrade to plain text / code tags
        scope_no_models = PublicationScope(include_models=False, include_reports=True, include_dataflow=True)
        resolver_no_models = LinkResolver(scope=scope_no_models, rel_root=".", is_html=True)

        tbl_nolink = resolver_no_models.link_to_table("Customer")
        self.assertNotIn("<a ", tbl_nolink)
        self.assertIn("Customer", tbl_nolink)

        meas_nolink = resolver_no_models.link_to_measure("Customer", "Customer Count")
        self.assertNotIn("<a ", meas_nolink)
        self.assertIn("Customer Count", meas_nolink)

        # Expressions should still link
        expr_link_still = resolver_no_models.link_to_expression("Staging_Cust")
        self.assertIn('<a href="etl/Staging_Cust.html"', expr_link_still)

    def test_link_resolver_markdown_rendering(self):
        # 1. Full scope: emits Markdown links
        scope_full = PublicationScope(include_models=True, include_reports=True, include_dataflow=True)
        resolver_md = LinkResolver(scope=scope_full, rel_root=".", is_html=False)

        tbl_md = resolver_md.link_to_table("Customer", tag="")
        self.assertEqual(tbl_md, "[Customer](tables/Customer.md)")

        meas_md = resolver_md.link_to_measure("Customer", "Customer Count", tag="")
        self.assertEqual(meas_md, "[Customer Count](measures/Customer/Customer_Count.md)")

        # 2. Disabled models: degrades to plain text
        scope_no_models = PublicationScope(include_models=False, include_reports=True, include_dataflow=True)
        resolver_no_models = LinkResolver(scope=scope_no_models, rel_root=".", is_html=False)

        tbl_plain = resolver_no_models.link_to_table("Customer", tag="")
        self.assertEqual(tbl_plain, "Customer")

        meas_plain = resolver_no_models.link_to_measure("Customer", "Customer Count", tag="")
        self.assertEqual(meas_plain, "Customer Count")


class TestMacroFamilyPublicationSelectiveGeneration(unittest.TestCase):

    def setUp(self):
        self.samples_dir = Path(__file__).resolve().parent.parent / "samples"
        self.scanner = CodebaseScanner(self.samples_dir)
        self.scan_result = self.scanner.scan(populate_symbols=True)

    def test_markdown_no_model_excludes_model_docs(self):
        cfg = DocGenConfig(include_models=False, include_dataflow=True)
        sample_model = next(iter(self.scan_result.models.values())).model_obj
        generator = MarkdownDocGenerator(cfg)
        docs = generator.generate_all_documents(sample_model)

        # Model index, tables, measures, functions must NOT be generated
        table_docs = [p for p in docs if p.startswith("tables/")]
        measure_docs = [p for p in docs if p.startswith("measures/")]
        self.assertEqual(len(table_docs), 0)
        self.assertEqual(len(measure_docs), 0)
        self.assertNotIn(f"{sample_model.model_name}.md", docs)

        # Dataflow docs should still be generated
        expr_docs = [p for p in docs if p.startswith("etl/")]
        self.assertGreater(len(expr_docs), 0)

    def test_html_no_dataflow_excludes_expression_docs(self):
        cfg = DocGenConfig(include_models=True, include_dataflow=False)
        sample_model = next(iter(self.scan_result.models.values())).model_obj
        generator = HtmlDocGenerator(cfg)
        docs = generator.generate_all_documents(sample_model)

        # Expression docs must NOT be generated
        expr_docs = [p for p in docs if "etl/" in p]
        self.assertEqual(len(expr_docs), 0)

        # Table and index docs should still exist
        table_docs = [p for p in docs if "tables/" in p]
        self.assertGreater(len(table_docs), 0)
        self.assertIn("index.html", docs)


if __name__ == "__main__":
    unittest.main()
