"""
Unit tests for the 3-Level Layout-as-Code Configuration Engine.
Verifies Document -> Radio Tab -> Block [Riquadro] -> Functions hierarchy,
schema normalization, multi-function unified card rendering, and builder integration.
"""

import json
import unittest
from pathlib import Path
from typing import Any, Dict

from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.section_engine import DocSection
from pbip_doc.docgen.layout_engine import (
    BlockLayout,
    TabLayout,
    DocumentLayout,
    DEFAULT_LAYOUT_CONFIG,
    normalize_document_layout,
    get_effective_document_layout,
    render_block,
    render_document_tabs,
    render_document_markdown,
    get_default_layout_json,
    extract_card_content,
)
from pbip_doc.docgen.html_builders import HtmlTableBuilder


class TestLayoutEngine(unittest.TestCase):
    def setUp(self):
        self.sample_table = {
            "name": "Orders",
            "description": "Sales orders fact table.",
            "source_type": "m",
            "role": "FACT",
            "columns": [
                {"name": "OrderID", "data_type": "Int64", "is_key": True},
                {"name": "Amount", "data_type": "Decimal"},
            ],
            "measures": [
                {"name": "OrderCount", "expression": "COUNTROWS('Orders')"}
            ],
            "relationships": [],
        }
        self.sample_model = {
            "tables": [self.sample_table],
            "relationships": [],
            "expressions": [],
            "measures": [
                {"name": "OrderCount", "table": "Orders", "expression": "COUNTROWS('Orders')"}
            ],
        }

    def test_default_layout_integrity(self):
        """Checks that DEFAULT_LAYOUT_CONFIG includes all archetypes and normalizes cleanly."""
        expected_docs = [
            "table", "model", "measure", "expression",
            "visual_page", "function", "dataflow_overview", "report_overview"
        ]
        for doc_type in expected_docs:
            self.assertIn(doc_type, DEFAULT_LAYOUT_CONFIG)
            layout = normalize_document_layout(DEFAULT_LAYOUT_CONFIG[doc_type], doc_type)
            self.assertIsInstance(layout, DocumentLayout)
            self.assertEqual(layout.document_type, doc_type)
            self.assertTrue(len(layout.tabs) > 0)
            for tab in layout.tabs:
                self.assertIsInstance(tab, TabLayout)
                self.assertTrue(tab.id)
                self.assertTrue(tab.label)
                self.assertTrue(len(tab.blocks) > 0)
                for block in tab.blocks:
                    self.assertIsInstance(block, BlockLayout)
                    self.assertTrue(len(block.functions) > 0)

    def test_normalize_canonical_3_level_schema(self):
        """Verifies parsing of the formal canonical 3-level schema."""
        raw = {
            "tabs": [
                {
                    "id": "tab-overview",
                    "label": "General Overview",
                    "blocks": [
                        {
                            "id": "info_block",
                            "title": "General Info",
                            "functions": ["description", "data_source_summary"]
                        }
                    ]
                },
                {
                    "id": "tab-schema",
                    "label": "Schema",
                    "blocks": [
                        {
                            "id": "cols_block",
                            "title": "Columns",
                            "functions": ["data_dictionary"]
                        },
                        {
                            "id": "rels_block",
                            "title": "Relations",
                            "functions": ["relationships"]
                        }
                    ]
                }
            ]
        }
        layout = normalize_document_layout(raw, "table")
        self.assertEqual(len(layout.tabs), 2)
        self.assertEqual(layout.tabs[0].id, "tab-overview")
        self.assertEqual(layout.tabs[0].label, "General Overview")
        self.assertEqual(len(layout.tabs[0].blocks), 1)
        self.assertEqual(layout.tabs[0].blocks[0].id, "info_block")
        self.assertEqual(layout.tabs[0].blocks[0].title, "General Info")
        self.assertEqual(layout.tabs[0].blocks[0].functions, ["description", "data_source_summary"])

        self.assertEqual(layout.tabs[1].id, "tab-schema")
        self.assertEqual(len(layout.tabs[1].blocks), 2)
        self.assertEqual(layout.tabs[1].blocks[0].functions, ["data_dictionary"])
        self.assertEqual(layout.tabs[1].blocks[1].functions, ["relationships"])

    def test_normalize_dict_shorthand_formats(self):
        """Verifies that dict-of-dicts and dict-of-lists shorthand normalizes seamlessly."""
        # Format A: Dict of Dicts
        shorthand_a = {
            "Overview": {
                "General Info": ["description", "data_source_summary"],
                "Upstream": ["upstream_pipeline"]
            },
            "Schema": {
                "Dictionary": ["data_dictionary"]
            }
        }
        layout_a = normalize_document_layout(shorthand_a, "table")
        self.assertEqual(len(layout_a.tabs), 2)
        self.assertEqual(layout_a.tabs[0].label, "Overview")
        self.assertEqual(layout_a.tabs[0].id, "tab-overview")
        self.assertEqual(len(layout_a.tabs[0].blocks), 2)
        self.assertEqual(layout_a.tabs[0].blocks[0].title, "General Info")
        self.assertEqual(layout_a.tabs[0].blocks[0].functions, ["description", "data_source_summary"])

        # Format B: Dict of Lists
        shorthand_b = {
            "Overview": ["description", "data_source_summary"],
            "Lineage": ["power_query_lineage"]
        }
        layout_b = normalize_document_layout(shorthand_b, "table")
        self.assertEqual(len(layout_b.tabs), 2)
        self.assertEqual(layout_b.tabs[0].label, "Overview")
        self.assertEqual(len(layout_b.tabs[0].blocks), 1)
        self.assertEqual(layout_b.tabs[0].blocks[0].functions, ["description", "data_source_summary"])

    def test_multi_function_single_block_card_rendering(self):
        """Verifies that 2+ functions inside 1 block are combined into a SINGLE riquadro (.content-card)."""
        block = BlockLayout(
            id="combined_block",
            title="Combined Information",
            functions=["fn_a", "fn_b"]
        )

        def fn_a():
            return DocSection(
                section_id="sec-a",
                title="Alpha Subtitle",
                content='<div class="content-card"><h3 class="content-card-title">Alpha Subtitle</h3><p>Content A</p></div>'
            )

        def fn_b():
            return DocSection(
                section_id="sec-b",
                title="Beta Subtitle",
                content='<div class="content-card"><h3 class="content-card-title">Beta Subtitle</h3><p>Content B</p></div>'
            )

        registry = {"fn_a": fn_a, "fn_b": fn_b}
        rendered = render_block(block, registry)
        self.assertIsNotNone(rendered)

        # Must have exactly ONE outer .content-card
        self.assertEqual(rendered.count('class="content-card"'), 1)
        self.assertIn('id="block-combined_block"', rendered)
        self.assertIn("Combined Information", rendered)

        # Both functions must be embedded inside with .content-block-section
        self.assertIn('id="fn-fn_a"', rendered)
        self.assertIn('id="fn-fn_b"', rendered)
        self.assertIn("Alpha Subtitle", rendered)
        self.assertIn("Beta Subtitle", rendered)
        self.assertIn("<p>Content A</p>", rendered)
        self.assertIn("<p>Content B</p>", rendered)

    def test_single_function_card_rendering(self):
        """Verifies that 1 function inside a block retains its clean card structure."""
        block = BlockLayout(
            id="single_block",
            functions=["fn_single"]
        )

        def fn_single():
            return DocSection(
                section_id="sec-single",
                title="Single Card",
                content='<div class="content-card"><h3 class="content-card-title">Single Card</h3><p>Single Content</p></div>'
            )

        registry = {"fn_single": fn_single}
        rendered = render_block(block, registry)
        self.assertIsNotNone(rendered)
        self.assertEqual(rendered.count('class="content-card"'), 1)
        self.assertIn("Single Content", rendered)

    def test_custom_layout_in_html_table_builder(self):
        """End-to-end test: HtmlTableBuilder custom layout with grouped tabs and blocks."""
        custom_layout = {
            "table": {
                "tabs": [
                    {
                        "id": "tab-summary",
                        "label": "Summary",
                        "blocks": [
                            {
                                "id": "general_block",
                                "title": "General & Sources",
                                "functions": ["description", "data_source_summary"]
                            }
                        ]
                    },
                    {
                        "id": "tab-structure",
                        "label": "Structure",
                        "blocks": [
                            {
                                "id": "dict_block",
                                "title": "Columns",
                                "functions": ["data_dictionary"]
                            },
                            {
                                "id": "meas_block",
                                "title": "Measures",
                                "functions": ["measures"]
                            }
                        ]
                    }
                ]
            }
        }
        cfg = DocGenConfig(layout_config=custom_layout)
        builder = HtmlTableBuilder(self.sample_table, self.sample_model, cfg)
        html_out = builder.build_content()

        # Should only render the 2 custom configured tabs in the tab bar
        self.assertIn('for="page-tab-tab-summary"', html_out)
        self.assertIn('for="page-tab-tab-structure"', html_out)
        self.assertNotIn('for="page-tab-tab-cols"', html_out)
        self.assertNotIn('for="page-tab-tab-rels"', html_out)

        # Tab summary must contain General & Sources card uniting description and data sources
        self.assertIn('id="block-general_block"', html_out)
        self.assertIn("General &amp; Sources", html_out)
        self.assertIn("Sales orders fact table.", html_out)

        # Tab structure must contain 2 separate blocks (Columns and Measures)
        self.assertIn('id="block-dict_block"', html_out)
        self.assertIn('id="block-meas_block"', html_out)
        self.assertIn("OrderID", html_out)
        self.assertIn("OrderCount", html_out)

    def test_empty_blocks_and_tabs_omitted(self):
        """Verifies that blocks and tabs with no output are omitted cleanly."""
        block = BlockLayout(id="empty_block", functions=["fn_none"])
        registry = {"fn_none": lambda: None}
        self.assertIsNone(render_block(block, registry))

        empty_layout = {
            "table": {
                "tabs": [
                    {
                        "id": "tab-empty",
                        "label": "Empty Tab",
                        "blocks": [{"id": "empty_block", "functions": ["fn_none"]}]
                    }
                ]
            }
        }
        sections = render_document_tabs("table", registry, layout_override=empty_layout)
        self.assertEqual(len(sections), 0)

    def test_dump_default_layout_json(self):
        """Verifies get_default_layout_json produces valid JSON with all document types."""
        json_str = get_default_layout_json(indent=2)
        parsed = json.loads(json_str)
        self.assertIsInstance(parsed, dict)
        self.assertIn("table", parsed)
        self.assertIn("model", parsed)
        self.assertIn("measure", parsed)
        self.assertIn("expression", parsed)

    def test_dual_engine_layout_parity_html_and_markdown(self):
        """
        Verifies that HTML and Markdown rendering engines adhere to the exact same tab and section order
        defined in DEFAULT_LAYOUT_CONFIG and support user-defined custom reordering seamlessly.
        """
        # Mock registry with recognizable section outputs
        mock_registry = {
            "description": lambda: DocSection("tab-summary", "Description", "Description", "## Description Section"),
            "relationship_diagram": lambda: DocSection("tab-summary", "Diagram", "Diagram", "![Diagram](diagrams/rel.svg)"),
            "data_source_summary": lambda: DocSection("tab-summary", "Sources", "Sources", "### Data Sources Section"),
            "upstream_pipeline": lambda: None,
            "data_dictionary": lambda: DocSection("tab-cols", "Columns", "Columns", "## Table Columns Section"),
            "calculated_columns": lambda: DocSection("tab-calc-cols", "Calc Cols", "Calc Cols", "## Calculated Columns Section"),
            "relationship_table": lambda: DocSection("tab-rels", "Relationships", "Relationships", "## Relationships Matrix Section"),
            "measures": lambda: DocSection("tab-meas", "Measures", "Measures", "## Measures Section"),
            "details": lambda: DocSection("tab-details", "Details", "Details", "## Details Section"),
            "badge_legend": lambda: None,
        }

        # 1. Default Layout Parity on 'table'
        md_default = render_document_markdown(
            doc_type="table",
            frontmatter_str="---\ntitle: Orders\n---",
            header_block="# Table: Orders",
            registry=mock_registry,
        )

        # Check section order in Markdown
        pos_desc = md_default.find("## Description Section")
        pos_diag = md_default.find("![Diagram](diagrams/rel.svg)")
        pos_cols = md_default.find("## Table Columns Section")
        pos_calc = md_default.find("## Calculated Columns Section")
        pos_rels = md_default.find("## Relationships Matrix Section")
        pos_meas = md_default.find("## Measures Section")
        pos_details = md_default.find("## Details Section")

        self.assertTrue(0 <= pos_desc < pos_diag < pos_cols < pos_calc < pos_rels < pos_meas < pos_details)

        # Check HTML tab order in HTML
        sections_html = render_document_tabs(doc_type="table", registry=mock_registry)
        tab_ids = [s.section_id for s in sections_html]
        self.assertEqual(tab_ids, ["tab-summary", "tab-cols", "tab-calc-cols", "tab-rels", "tab-meas", "tab-details"])

        # 2. Custom Layout Reordering Parity: Inverting Measures before Columns
        custom_inverted_layout = {
            "table": {
                "tabs": [
                    {
                        "id": "tab-meas",
                        "label": "Measures First",
                        "blocks": [{"id": "meas_block", "functions": ["measures"]}]
                    },
                    {
                        "id": "tab-cols",
                        "label": "Columns Second",
                        "blocks": [{"id": "cols_block", "functions": ["data_dictionary"]}]
                    }
                ]
            }
        }

        md_custom = render_document_markdown(
            doc_type="table",
            frontmatter_str=None,
            header_block=None,
            registry=mock_registry,
            layout_override=custom_inverted_layout,
        )

        pos_meas_custom = md_custom.find("## Measures Section")
        pos_cols_custom = md_custom.find("## Table Columns Section")
        self.assertTrue(0 <= pos_meas_custom < pos_cols_custom)
        self.assertNotIn("## Relationships Matrix Section", md_custom)

        sections_html_custom = render_document_tabs(
            doc_type="table",
            registry=mock_registry,
            layout_override=custom_inverted_layout,
        )
        tab_ids_custom = [s.section_id for s in sections_html_custom]
        self.assertEqual(tab_ids_custom, ["tab-meas", "tab-cols"])


    def test_table_dax_and_rag_opt_in_layout(self):
        """Verifies table calculated DAX block and dynamic RAG opt-in tab injection."""
        cfg_default = DocGenConfig()
        # 1. RAG disabled by default across archetypes
        layout_meas_def = get_effective_document_layout("measure", cfg_default)
        self.assertNotIn("tab-rag", [t.id for t in layout_meas_def.tabs])

        layout_tbl_def = get_effective_document_layout("table", cfg_default)
        self.assertNotIn("tab-rag", [t.id for t in layout_tbl_def.tabs])

        # 2. RAG enabled via opt-in config
        cfg_rag = DocGenConfig(include_measure_rag_hints=True, include_table_rag_hints=True)
        layout_meas_rag = get_effective_document_layout("measure", cfg_rag)
        self.assertIn("tab-rag", [t.id for t in layout_meas_rag.tabs])

        layout_tbl_rag = get_effective_document_layout("table", cfg_rag)
        self.assertIn("tab-rag", [t.id for t in layout_tbl_rag.tabs])

        # 3. Table summary tab includes dax_block with dax_formula and referenced_columns
        summary_tab = next(t for t in layout_tbl_def.tabs if t.id == "tab-summary")
        all_funcs = [fn for b in summary_tab.blocks for fn in b.functions]
        self.assertIn("dax_formula", all_funcs)
        self.assertIn("referenced_columns", all_funcs)

        # 4. Model layout does NOT include tab-dataflow by default (ETL referenced via physical sources)
        layout_model = get_effective_document_layout("model", cfg_default)
        self.assertNotIn("tab-dataflow", [t.id for t in layout_model.tabs])


if __name__ == "__main__":
    unittest.main()
