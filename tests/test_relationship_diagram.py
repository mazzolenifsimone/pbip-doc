"""
Unit Tests for Relationship Diagram SVG Generator and HTML Portal Integration.
Verifies single source of truth for design tokens, SVG generation, and configurable options.
100% Python standard library.
"""

import sys
import unittest
from pathlib import Path
from typing import Dict, Any

# Ensure pbip-doc-gen is on sys.path
TEST_DIR = Path(__file__).resolve().parent
GEN_DIR = TEST_DIR.parent
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))

from pbip_doc.docgen.config import DocGenConfig
from pbip_doc.docgen.relationship_diagram import (
    ROLE_CONFIG,
    RelationshipSvgGenerator,
    normalize_role_key,
    get_table_role_short,
    get_table_role_badge_class,
)
from pbip_doc.docgen.html_builders import HtmlIndexBuilder, HtmlTableBuilder
from pbip_doc.docgen.index_doc import IndexDocBuilder
from pbip_doc.docgen.table_doc import TableDocBuilder
from pbip_doc.docgen.engine import MarkdownDocGenerator
from pbip_doc.cli import _load_cli_config


class TestRelationshipDiagram(unittest.TestCase):
    def setUp(self):
        self.sample_model_dict: Dict[str, Any] = {
            "model_name": "Sales Model",
            "project_name": "Sales Model",
            "tables": [
                {
                    "name": "Fact_Sales",
                    "role": "FACT",
                    "storage_mode": "Import",
                    "columns": [
                        {"name": "SalesKey", "data_type": "Int64", "is_key": True},
                        {"name": "DateKey", "data_type": "Int64"},
                        {"name": "CustomerKey", "data_type": "Int64"},
                        {"name": "Amount", "data_type": "Decimal"},
                    ],
                    "measures": [],
                },
                {
                    "name": "Dim_Customer",
                    "role": "DIMENSION",
                    "storage_mode": "Import",
                    "columns": [
                        {"name": "CustomerKey", "data_type": "Int64", "is_key": True},
                        {"name": "CustomerName", "data_type": "String"},
                        {"name": "GeographyKey", "data_type": "Int64"},
                    ],
                    "measures": [],
                },
                {
                    "name": "Dim_Geography",
                    "role": "LOOKUP_OUTRIGGER",
                    "storage_mode": "Import",
                    "columns": [
                        {"name": "GeographyKey", "data_type": "Int64", "is_key": True},
                        {"name": "City", "data_type": "String"},
                        {"name": "Country", "data_type": "String"},
                    ],
                    "measures": [],
                },
                {
                    "name": "Dim_Date",
                    "role": "DATE_DIMENSION",
                    "storage_mode": "Import",
                    "columns": [
                        {"name": "DateKey", "data_type": "Int64", "is_key": True},
                        {"name": "Date", "data_type": "DateTime"},
                    ],
                    "measures": [],
                },
            ],
            "relationships": [
                {
                    "from_table": "Fact_Sales",
                    "from_column": "CustomerKey",
                    "to_table": "Dim_Customer",
                    "to_column": "CustomerKey",
                    "cardinality": "ManyToOne",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
                {
                    "from_table": "Fact_Sales",
                    "from_column": "DateKey",
                    "to_table": "Dim_Date",
                    "to_column": "DateKey",
                    "cardinality": "ManyToOne",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
                {
                    "from_table": "Dim_Customer",
                    "from_column": "GeographyKey",
                    "to_table": "Dim_Geography",
                    "to_column": "GeographyKey",
                    "cardinality": "ManyToOne",
                    "cross_filtering_behavior": "Both",
                    "is_active": True,
                },
            ],
        }

    def test_role_config_single_source_of_truth(self):
        """Verifies design tokens and structure in ROLE_CONFIG."""
        expected_roles = [
            "FACT",
            "DIMENSION",
            "LOOKUP_OUTRIGGER",
            "BRIDGE",
            "DATE_DIMENSION",
            "CALCULATION_GROUP",
            "PARAMETER_UTILITY",
            "UNKNOWN",
        ]
        for role_key in expected_roles:
            self.assertIn(role_key, ROLE_CONFIG)
            cfg = ROLE_CONFIG[role_key]
            self.assertIn("short", cfg)
            self.assertIn("badge_class", cfg)
            self.assertIn("diagram_class", cfg)
            self.assertIn("light", cfg)
            self.assertIn("dark", cfg)

            for token_theme in ("light", "dark"):
                tokens = cfg[token_theme]
                for req_key in ("badge_bg", "badge_fg", "badge_border", "header_bg", "card_border", "divider"):
                    self.assertIn(req_key, tokens)

        # Canonical helpers
        self.assertEqual(get_table_role_short("FACT"), "Fact")
        self.assertEqual(get_table_role_short("DIMENSION"), "Dim")
        self.assertEqual(get_table_role_short("LOOKUP_OUTRIGGER"), "Snow")
        self.assertEqual(get_table_role_badge_class("FACT"), "badge-role-fact")
        self.assertEqual(get_table_role_badge_class("DIMENSION"), "badge-role-dim")
        self.assertEqual(get_table_role_badge_class("LOOKUP_OUTRIGGER"), "badge-role-snowflake")

    def test_model_svg_generation(self):
        """Verifies full model SVG rendering with cards, paths, and legend."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)
        svg = gen.generate_model_svg()

        self.assertIn("<svg", svg)
        self.assertIn('class="model-relationship-diagram', svg)
        self.assertIn('id="card-Fact_Sales"', svg)
        self.assertIn('id="card-Dim_Customer"', svg)
        self.assertIn('id="card-Dim_Geography"', svg)
        self.assertIn('id="card-Dim_Date"', svg)
        self.assertIn('class="relationship-edges"', svg)
        self.assertIn('class="diagram-legend"', svg)

        # Bidirectional glyph
        self.assertIn("bidi-glyph-group", svg)

        # Light / Dark theme override tests
        svg_light = gen.generate_model_svg(theme_mode="light")
        self.assertIn("theme-force-light", svg_light)

        svg_dark = gen.generate_model_svg(theme_mode="dark")
        self.assertIn("theme-force-dark", svg_dark)
        self.assertIn(".canvas-bg { fill: #16181d; }", svg_dark)
        self.assertIn(".card-bg { fill: #21252d; }", svg_dark)
        self.assertNotIn(".canvas-bg { fill: #0f172a; }", svg_dark)

    def test_table_focal_svg_generation(self):
        """Verifies 1-hop focal diagram for a single table."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)

        # Focal on Dim_Customer: has upstream Dim_Geography and downstream Fact_Sales
        svg = gen.generate_table_svg("Dim_Customer")
        self.assertIn("<svg", svg)
        self.assertIn('id="card-Dim_Customer"', svg)
        self.assertIn('id="card-Fact_Sales"', svg)
        self.assertIn('id="card-Dim_Geography"', svg)
        self.assertIn('card-border-focal', svg)
        self.assertIn('class="diagram-legend"', svg)

        # Table with no relationships produces empty SVG message
        empty_svg = gen.generate_table_svg("NonExistentTable")
        self.assertIn("No direct relationships", empty_svg)

    def test_html_index_builder_with_and_without_diagram(self):
        """Verifies HtmlIndexBuilder respects include_relationship_diagrams config."""
        # 1. Enabled
        config_enabled = DocGenConfig(include_relationship_diagrams=True)
        builder_enabled = HtmlIndexBuilder(self.sample_model_dict, config_enabled)
        html_enabled = builder_enabled.build_content()
        self.assertIn("Star Schema Relationship Diagram", html_enabled)
        self.assertIn('class="model-relationship-diagram', html_enabled)
        # Diagram in Summary tab precedes Relationship details table in Relationships tab
        self.assertLess(
            html_enabled.find("Star Schema Relationship Diagram"),
            html_enabled.find("From (Many Side)"),
        )

        # 2. Disabled
        config_disabled = DocGenConfig(include_relationship_diagrams=False)
        builder_disabled = HtmlIndexBuilder(self.sample_model_dict, config_disabled)
        html_disabled = builder_disabled.build_content()
        self.assertNotIn("Star Schema Relationship Diagram", html_disabled)
        self.assertNotIn('class="model-relationship-diagram', html_disabled)

    def test_html_table_builder_with_and_without_diagram(self):
        """Verifies HtmlTableBuilder respects include_relationship_diagrams config."""
        table_data = self.sample_model_dict["tables"][1]  # Dim_Customer

        # 1. Enabled
        config_enabled = DocGenConfig(include_relationship_diagrams=True)
        builder_enabled = HtmlTableBuilder(table_data, self.sample_model_dict, config_enabled)
        html_enabled = builder_enabled.build_content()
        self.assertIn("1-Hop Relationship Diagram", html_enabled)
        self.assertIn('class="model-relationship-diagram', html_enabled)

        # 2. Disabled
        config_disabled = DocGenConfig(include_relationship_diagrams=False)
        builder_disabled = HtmlTableBuilder(table_data, self.sample_model_dict, config_disabled)
        html_disabled = builder_disabled.build_content()
        self.assertNotIn("1-Hop Relationship Diagram", html_disabled)

    def test_cli_config_no_diagrams_flags(self):
        """Verifies CLI flag --no-diagrams turns off diagram generation in config."""
        class MockArgs:
            no_diagrams = True

        cfg = _load_cli_config(MockArgs())
        self.assertFalse(cfg.include_relationship_diagrams)

    def test_build_diagram_assets(self):
        """Verifies build_diagram_assets produces full model and 1-hop table SVG assets."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)
        assets = gen.build_diagram_assets("diagrams")

        self.assertIn("diagrams/model_relationships.svg", assets)
        self.assertIn("diagrams/Fact_Sales_relationships.svg", assets)
        self.assertIn("diagrams/Dim_Customer_relationships.svg", assets)
        self.assertIn("diagrams/Dim_Geography_relationships.svg", assets)
        self.assertIn("diagrams/Dim_Date_relationships.svg", assets)

        for path, svg_code in assets.items():
            self.assertTrue(svg_code.strip().startswith("<svg"), f"{path} should start with <svg")
            self.assertTrue(svg_code.strip().endswith("</svg>"), f"{path} should end with </svg>")

    def test_markdown_index_builder_with_and_without_diagram(self):
        """Verifies IndexDocBuilder includes diagram link and relationships matrix when enabled."""
        # 1. Enabled
        config_enabled = DocGenConfig(include_relationship_diagrams=True)
        builder_enabled = IndexDocBuilder(self.sample_model_dict, config_enabled)
        md_enabled = builder_enabled.build_markdown()
        self.assertIn("## Star Schema Relationship Diagram", md_enabled)
        self.assertIn("## Model Relationships", md_enabled)
        self.assertIn("![Star Schema Relationship Diagram](diagrams/model_relationships.svg)", md_enabled)
        self.assertIn("### Active Relationships Matrix", md_enabled)
        self.assertIn("[`Fact_Sales`](tables/Fact_Sales.md)", md_enabled)
        # Diagram in Summary tab must precede Relationships Matrix in Relationships tab
        self.assertLess(
            md_enabled.find("![Star Schema Relationship Diagram]"),
            md_enabled.find("### Active Relationships Matrix"),
        )

        # 2. Disabled
        config_disabled = DocGenConfig(include_relationship_diagrams=False)
        builder_disabled = IndexDocBuilder(self.sample_model_dict, config_disabled)
        md_disabled = builder_disabled.build_markdown()
        self.assertNotIn("![Star Schema Relationship Diagram]", md_disabled)

    def test_markdown_table_builder_with_and_without_diagram(self):
        """Verifies TableDocBuilder includes diagram link when enabled (Star Cluster for Fact, 1-Hop for Dim)."""
        table_data = self.sample_model_dict["tables"][0]  # Fact_Sales

        # 1. Enabled (Fact table -> Star Cluster Diagram)
        config_enabled = DocGenConfig(include_relationship_diagrams=True)
        builder_enabled = TableDocBuilder(table_data, self.sample_model_dict, config_enabled)
        md_enabled = builder_enabled.build_markdown()
        self.assertIn("![Fact_Sales - Star Cluster Relationship Diagram](../diagrams/Fact_Sales_relationships.svg)", md_enabled)
        self.assertIn("### Active Direct Relationships:", md_enabled)
        # Diagram in Summary tab must precede Relationships Table in Relationships tab
        self.assertLess(
            md_enabled.find("![Fact_Sales - Star Cluster Relationship Diagram]"),
            md_enabled.find("### Active Direct Relationships:"),
        )

        # 1b. Enabled (Dimension table -> 1-Hop Diagram)
        dim_table_data = self.sample_model_dict["tables"][1]  # Dim_Customer
        dim_builder = TableDocBuilder(dim_table_data, self.sample_model_dict, config_enabled)
        dim_md = dim_builder.build_markdown()
        self.assertIn("![Dim_Customer - 1-Hop Relationship Diagram](../diagrams/Dim_Customer_relationships.svg)", dim_md)

        # 2. Disabled
        config_disabled = DocGenConfig(include_relationship_diagrams=False)
        builder_disabled = TableDocBuilder(table_data, self.sample_model_dict, config_disabled)
        md_disabled = builder_disabled.build_markdown()
        self.assertNotIn("Star Cluster Relationship Diagram", md_disabled)
        self.assertNotIn("1-Hop Relationship Diagram", md_disabled)

    def test_markdown_doc_generator_diagram_assets(self):
        """Verifies MarkdownDocGenerator collects standalone SVG diagram assets."""
        config = DocGenConfig(include_relationship_diagrams=True)
        generator = MarkdownDocGenerator(config)
        docs = generator.generate_all_documents(self.sample_model_dict)

        self.assertIn("diagrams/model_relationships.svg", docs)
        self.assertIn("diagrams/Fact_Sales_relationships.svg", docs)
        self.assertIn("diagrams/Dim_Customer_relationships.svg", docs)

    def test_model_svg_two_column_legend_clamping(self):
        """Verifies that model diagrams with only 2 columns (e.g. pure Star Dim+Fact) enforce min_canvas_w >= 840 so the 780px legend is never cut off."""
        two_col_model = {
            "model_name": "Two Col Model",
            "tables": [
                {
                    "name": "Fact_Orders",
                    "role": "FACT",
                    "columns": [{"name": "CustKey", "data_type": "Int64", "is_key": True}],
                },
                {
                    "name": "Dim_Customer",
                    "role": "DIMENSION",
                    "columns": [{"name": "CustKey", "data_type": "Int64", "is_key": True}],
                },
            ],
            "relationships": [
                {
                    "from_table": "Fact_Orders",
                    "from_column": "CustKey",
                    "to_table": "Dim_Customer",
                    "to_column": "CustKey",
                    "cardinality": "ManyToOne",
                    "is_active": True,
                }
            ],
        }
        gen = RelationshipSvgGenerator(two_col_model)
        svg = gen.generate_model_svg()

        # Canvas must be clamped to at least min_canvas_w = 840
        self.assertIn('viewBox="0 0 840', svg)
        # Legend translation must be positive (25.0 px with 790px legend), never negative (-40.0 px)
        self.assertIn('transform="translate(25.0,', svg)
        self.assertNotIn('transform="translate(-', svg)

    def test_star_cluster_multi_fact_svg_and_dual_engine_parity(self):
        """
        Comprehensive test for Star Cluster Dual-Engine Architecture:
        1. Topology 4-tier extraction (extract_star_cluster).
        2. Dimension fact usage (get_dimension_fact_usage).
        3. SVG generation with scoped filter IDs (preventing browser <filter> collisions).
        4. Fact table delegation in generate_table_svg.
        5. Zero-JS Pure CSS Radio Tabs in HtmlIndexBuilder.
        6. Markdown table and links in IndexDocBuilder (Dual-Engine Parity - Opzione A).
        """
        multi_fact_model = {
            "model_name": "Galaxy Enterprise Model",
            "tables": [
                {"name": "Fact_Sales", "role": "FACT", "columns": [{"name": "CustKey", "data_type": "Int64"}, {"name": "DateKey", "data_type": "Int64"}, {"name": "ProductPromoKey", "data_type": "Int64"}]},
                {"name": "Fact_Orders", "role": "FACT", "columns": [{"name": "CustKey", "data_type": "Int64"}, {"name": "DateKey", "data_type": "Int64"}]},
                {"name": "Dim_Customer", "role": "DIMENSION", "columns": [{"name": "CustKey", "data_type": "Int64", "is_key": True}, {"name": "GeoKey", "data_type": "Int64"}]},
                {"name": "Dim_Date", "role": "DATE_DIMENSION", "columns": [{"name": "DateKey", "data_type": "Int64", "is_key": True}]},
                {"name": "Dim_Promotion", "role": "DIMENSION", "columns": [{"name": "PromoKey", "data_type": "Int64", "is_key": True}]},
                {"name": "Bridge_ProductPromo", "role": "BRIDGE", "columns": [{"name": "ProductPromoKey", "data_type": "Int64", "is_key": True}, {"name": "PromoKey", "data_type": "Int64"}]},
                {"name": "Lookup_Geography", "role": "LOOKUP_OUTRIGGER", "columns": [{"name": "GeoKey", "data_type": "Int64", "is_key": True}]},
            ],
            "relationships": [
                {"from_table": "Fact_Sales", "from_column": "CustKey", "to_table": "Dim_Customer", "to_column": "CustKey", "cardinality": "ManyToOne", "is_active": True},
                {"from_table": "Fact_Sales", "from_column": "DateKey", "to_table": "Dim_Date", "to_column": "DateKey", "cardinality": "ManyToOne", "is_active": True},
                {"from_table": "Fact_Sales", "from_column": "ProductPromoKey", "to_table": "Bridge_ProductPromo", "to_column": "ProductPromoKey", "cardinality": "ManyToOne", "is_active": True},
                {"from_table": "Bridge_ProductPromo", "from_column": "PromoKey", "to_table": "Dim_Promotion", "to_column": "PromoKey", "cardinality": "ManyToOne", "is_active": True},
                {"from_table": "Dim_Customer", "from_column": "GeoKey", "to_table": "Lookup_Geography", "to_column": "GeoKey", "cardinality": "ManyToOne", "is_active": True},
                {"from_table": "Fact_Orders", "from_column": "CustKey", "to_table": "Dim_Customer", "to_column": "CustKey", "cardinality": "ManyToOne", "is_active": True},
                {"from_table": "Fact_Orders", "from_column": "DateKey", "to_table": "Dim_Date", "to_column": "DateKey", "cardinality": "ManyToOne", "is_active": True},
            ],
        }

        gen = RelationshipSvgGenerator(multi_fact_model)

        # 1. get_fact_tables
        fact_tables = gen.get_fact_tables()
        self.assertEqual(fact_tables, ["Fact_Orders", "Fact_Sales"])

        # 2. extract_star_cluster for Fact_Sales
        cluster_sales = gen.extract_star_cluster("Fact_Sales")
        self.assertEqual(cluster_sales["fact_table"], "Fact_Sales")
        self.assertIn("Lookup_Geography", cluster_sales["outriggers"])
        self.assertIn("Dim_Customer", cluster_sales["dimensions"])
        self.assertIn("Dim_Date", cluster_sales["dimensions"])
        self.assertIn("Dim_Promotion", cluster_sales["dimensions"])
        self.assertIn("Bridge_ProductPromo", cluster_sales["bridges"])
        self.assertEqual(cluster_sales["facts"], ["Fact_Sales"])

        # 3. get_dimension_fact_usage
        usage = gen.get_dimension_fact_usage()
        # Dim_Customer and Dim_Date are conformed across both facts
        self.assertEqual(usage["Dim_Customer"], {"Fact_Sales", "Fact_Orders"})
        self.assertEqual(usage["Dim_Date"], {"Fact_Sales", "Fact_Orders"})
        # Dim_Promotion is only used in Fact_Sales
        self.assertEqual(usage["Dim_Promotion"], {"Fact_Sales"})

        # 4. generate_star_cluster_svg with unique scoped filter IDs
        svg_sales = gen.generate_star_cluster_svg("Fact_Sales")
        self.assertIn('filter id="card-shadow-star-fact-sales"', svg_sales)
        self.assertIn('filter id="focal-shadow-star-fact-sales"', svg_sales)
        self.assertIn('id="card-star-fact-sales-Fact_Sales"', svg_sales)
        self.assertIn('card-border-focal', svg_sales)

        # 5. generate_table_svg delegates to star cluster when target is FACT
        table_svg_fact = gen.generate_table_svg("Fact_Sales")
        self.assertIn("card-shadow-star-fact-sales", table_svg_fact)
        # but 1-hop for dimensions
        table_svg_dim = gen.generate_table_svg("Dim_Customer")
        self.assertIn('filter id="card-shadow"', table_svg_dim)

        # 6. HtmlIndexBuilder renders Zero-JS Pure CSS Radio Tabs when len(facts) >= 2
        config = DocGenConfig(include_relationship_diagrams=True)
        html_builder = HtmlIndexBuilder(multi_fact_model, config=config)
        content_section = html_builder._section_star_schema_and_diagram(
            multi_fact_model["tables"], multi_fact_model["relationships"]
        )
        self.assertIsNotNone(content_section)
        html = content_section.content
        self.assertIn("starcluster-container", html)
        self.assertIn('id="sc-tab-galaxy"', html)
        self.assertIn('id="sc-tab-fact-sales"', html)
        self.assertIn('id="sc-tab-fact-orders"', html)
        self.assertIn("Full Galaxy Schema", html)
        self.assertIn("Fact_Sales", html)
        self.assertIn("svg-icon-star", html)
        self.assertIn("panel-fact-sales", html)
        self.assertIn('card-shadow-galaxy', html)
        self.assertIn('card-shadow-sc-fact-sales', html)

        # 7. IndexDocBuilder renders Markdown Star Clusters summary table
        index_builder = IndexDocBuilder(multi_fact_model, config=config)
        md = index_builder.build_markdown()
        self.assertIn("### Star Clusters by Fact Table (Multi-Fact Galaxy Topology)", md)
        self.assertIn("| [`Fact_Sales`](tables/Fact_Sales.md) | `FACT` | 3 | 1 | 1 | [📊 View Star Cluster](diagrams/Fact_Sales_relationships.svg) |", md)
        self.assertIn("| [`Fact_Orders`](tables/Fact_Orders.md) | `FACT` | 2 | 0 | 1 | [📊 View Star Cluster](diagrams/Fact_Orders_relationships.svg) |", md)

    def test_click_to_focus_toggle_and_reset_structure(self):
        """Verifies Click-to-Focus zero-scroll jump architecture with tabindex, :focus, :focus-within, and :target."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)
        svg = gen.generate_model_svg(svg_id_prefix="main")

        # 1. Canvas background has tabindex="0" and no <a href> (Zero scroll jump)
        self.assertIn('id="canvas-main"', svg)
        self.assertIn('class="canvas-bg"', svg)
        self.assertIn('tabindex="0"', svg)
        self.assertNotIn('href="#canvas-main"', svg)

        # 2. Table cards have tabindex="0" and card-hitbox (No <a> tag)
        self.assertIn('class="card-hitbox"', svg)
        self.assertIn('id="card-main-Fact_Sales" tabindex="0"', svg)
        self.assertNotIn('href="#card-main-Fact_Sales"', svg)

        # 3. Relationship edges have tabindex="0" and rel-hitbox (No <a> tag)
        self.assertIn('class="rel-hitbox"', svg)
        self.assertIn('id="rel-main-0" tabindex="0"', svg)
        self.assertNotIn('href="#rel-main-0"', svg)

        # 4. Pure static click-to-focus: Instantaneous response without transition lag
        self.assertIn("Pure Static Click-to-Focus: Instantaneous response", svg)

        # 5. Outlines are suppressed for zero focus ring flash
        self.assertIn("outline: none;", svg)

    def test_constant_stroke_width_and_luminance_tokens(self):
        """Verifies stroke-width remains constant at 1.3px (luminance-only shift, no neon or thickness changes)."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)
        svg = gen.generate_model_svg()

        # Stroke width constant 1.3px
        self.assertIn("stroke-width: 1.3px;", svg)
        self.assertNotIn("stroke-width: 2.6;", svg)
        self.assertNotIn("stroke-width: 2.6px;", svg)

        # Design tokens: focal border matches active path highlight (no amber)
        self.assertIn("--g-path-normal: #cbd5e1;", svg)  # Light neutral
        self.assertIn("--g-path-active: #475569;", svg)  # Light active
        self.assertIn("--g-focal-border: #475569;", svg) # Light active (identical to path active)
        self.assertIn("--g-path-normal: #404752;", svg)  # Dark neutral
        self.assertIn("--g-path-active: #9ca3af;", svg)  # Dark active
        self.assertIn("--g-focal-border: #9ca3af;", svg) # Dark active (identical to path active)
        self.assertIn("--g-dim-opacity: 0.15;", svg)
        self.assertNotIn("#b48154", svg)  # No amber in Light mode
        self.assertNotIn("#d4a373", svg)  # No amber in Dark mode

    def test_bezier_fan_out_multi_port_staggering(self):
        """Verifies multi-port connections at the same column are vertically staggered without mid-air collision."""
        multi_port_model = {
            "model_name": "Multi Port Model",
            "tables": [
                {"name": "Fact_Sales", "role": "FACT", "columns": [{"name": "CustKey", "data_type": "Int64"}]},
                {"name": "Fact_Returns", "role": "FACT", "columns": [{"name": "CustKey", "data_type": "Int64"}]},
                {"name": "Fact_Shipments", "role": "FACT", "columns": [{"name": "CustKey", "data_type": "Int64"}]},
                {"name": "Dim_Customer", "role": "DIMENSION", "columns": [{"name": "CustKey", "data_type": "Int64", "is_key": True}]},
            ],
            "relationships": [
                {"from_table": "Fact_Sales", "from_column": "CustKey", "to_table": "Dim_Customer", "to_column": "CustKey", "is_active": True},
                {"from_table": "Fact_Returns", "from_column": "CustKey", "to_table": "Dim_Customer", "to_column": "CustKey", "is_active": True},
                {"from_table": "Fact_Shipments", "from_column": "CustKey", "to_table": "Dim_Customer", "to_column": "CustKey", "is_active": True},
            ],
        }
        gen = RelationshipSvgGenerator(multi_port_model)
        svg = gen.generate_model_svg()

        # There are 3 connections to Dim_Customer[CustKey]. Their endpoint Y coordinates at Dim_Customer must differ!
        # Search for path d="M ... C ... y2, x2 y2"
        import re
        paths = re.findall(r'<path d="M\s+[\d\.]+\s+([\d\.]+)\s+C\s+[\d\.]+\s+[\d\.]+,\s+[\d\.]+\s+([\d\.]+),\s+[\d\.]+\s+([\d\.]+)"', svg)
        self.assertEqual(len(paths), 6)  # 3 relations x (1 hitbox + 1 visible path)

        # The endpoints connected to Dim_Customer (x2, y2) must have distinct staggered Y coordinates
        end_y_values = [float(p[2]) for p in paths]
        self.assertEqual(len(set(end_y_values)), 3, f"Expected 3 distinct staggered Y ports, got: {end_y_values}")

    def test_one_hop_relation_focus_behavior(self):
        """Verifies unified click-to-focus architecture and shared pipeline across 1-hop and star cluster."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)
        svg = gen.generate_table_svg("Dim_Customer")

        # 1. Focal table card (Dim_Customer) has full card-hitbox and tabindex="0" for click-to-focus
        dim_cust_card = svg[svg.find('id="card-Dim_Customer"'):svg.find('id="card-Fact_Sales"')]
        self.assertIn('class="card-hitbox"', dim_cust_card)
        self.assertIn('class="card-bg card-border-focal"', dim_cust_card)

        # 2. Relationship lines DO have focusable hitboxes and IDs
        self.assertIn('id="rel-0" tabindex="0"', svg)
        self.assertIn('id="rel-1" tabindex="0"', svg)

        # 3. Dynamic rules exist for both table and relationships (:focus, :focus-within, :target)
        self.assertIn(".model-relationship-diagram:has(#card-Dim_Customer:focus)", svg)
        self.assertIn(".model-relationship-diagram:has(#rel-0:focus) #rel-0 .rel-path", svg)
        self.assertIn(".model-relationship-diagram:has(#rel-0:focus-within) #rel-0 .rel-path", svg)
        self.assertIn(".model-relationship-diagram:has(#rel-0:target) #rel-0 .rel-path", svg)

        # 4. Focal border matches active selection and contains no amber
        self.assertIn('stroke="var(--g-focal-border)"', dim_cust_card)
        self.assertNotIn('#b48154', svg)
        self.assertNotIn('#d4a373', svg)

    def test_direction_cardinality_highlighting_parity(self):
        """Verifies PM Note 3: direction glyphs and cardinality badges dim and highlight cleanly."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)
        svg = gen.generate_model_svg()

        # Scoped dimming includes cardinality-badge and bidi-glyph-group
        self.assertIn(".relationship-edges .cardinality-badge", svg)
        self.assertIn(".relationship-edges .bidi-glyph-group", svg)

        # Active rules tint badges and glyphs with var(--g-path-active)
        self.assertIn(".cardinality-badge { fill: var(--g-path-active) !important;", svg)
        self.assertIn(".bidi-badge-bg { stroke: var(--g-path-active) !important;", svg)
        self.assertIn(".bidi-badge-text { fill: var(--g-path-active) !important;", svg)

    def test_dark_mode_header_colors_and_cascade_order(self):
        """Verifies dark mode table headers are dark (#1e2229) and not overridden by light headers (#f8fafc)."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)
        svg = gen.generate_model_svg()

        # 1. Base light headers defined before dark mode media query
        pos_light_header = svg.find(".header-fact { fill: #f8fafc; }")
        pos_dark_media = svg.find("@media (prefers-color-scheme: dark)")
        self.assertTrue(pos_light_header != -1 and pos_dark_media != -1)
        self.assertLess(pos_light_header, pos_dark_media, "Light headers must precede @media dark in CSS cascade")

        # 2. Dark mode media query contains dark header fill (#1e2229)
        self.assertIn(".header-fact { fill: #1e2229; }", svg)

        # 3. Forced dark and [data-theme="dark"] rules contain dark header fill with !important
        self.assertIn('[data-theme="dark"] .model-relationship-diagram .header-fact { fill: #1e2229 !important; }', svg)

    def test_table_names_with_spaces_and_special_characters(self):
        """Verifies table names with spaces (e.g. 'Sales Order', 'Sales Territory') use _safe_id in DOM IDs and CSS selectors."""
        space_model = {
            "model_name": "Space Model",
            "tables": [
                {"name": "Sales", "role": "FACT", "columns": [{"name": "OrderKey", "data_type": "Int64"}, {"name": "TerritoryKey", "data_type": "Int64"}]},
                {"name": "Sales Order", "role": "DIMENSION", "columns": [{"name": "OrderKey", "data_type": "Int64", "is_key": True}]},
                {"name": "Sales Territory", "role": "DIMENSION", "columns": [{"name": "TerritoryKey", "data_type": "Int64", "is_key": True}]},
            ],
            "relationships": [
                {"from_table": "Sales", "from_column": "OrderKey", "to_table": "Sales Order", "to_column": "OrderKey", "is_active": True},
                {"from_table": "Sales", "from_column": "TerritoryKey", "to_table": "Sales Territory", "to_column": "TerritoryKey", "is_active": True},
            ],
        }
        gen = RelationshipSvgGenerator(space_model)
        svg = gen.generate_model_svg()

        # 1. DOM IDs use _safe_id (underscores instead of spaces)
        self.assertIn('id="card-Sales_Order"', svg)
        self.assertIn('id="card-Sales_Territory"', svg)
        self.assertNotIn('id="card-Sales Order"', svg)
        self.assertNotIn('id="card-Sales Territory"', svg)

        # 2. CSS Selectors do NOT contain broken space-separated tags
        self.assertNotIn('#card-Sales Order', svg)
        self.assertNotIn('#card-Sales Territory', svg)
        self.assertIn('.model-relationship-diagram:has(#card-Sales_Order:focus)', svg)
        self.assertIn('.model-relationship-diagram:has(#card-Sales_Territory:focus)', svg)

        # 3. Partner card rules include sanitized safe IDs
        self.assertIn('#card-Sales_Order', svg)
        self.assertIn('#card-Sales_Territory', svg)

    def test_unified_svg_generation_pipeline_across_scopes(self):
        """Verifies unified generate_diagram across model, star_cluster, and 1hop scopes."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)

        # 1. Full Model Scope
        svg_model = gen.generate_diagram(scope="model")
        self.assertIn('<svg', svg_model)
        self.assertIn('class="model-relationship-diagram', svg_model)
        self.assertIn('id="card-Fact_Sales"', svg_model)
        self.assertIn('id="card-Dim_Customer"', svg_model)
        self.assertNotIn('#b48154', svg_model)
        self.assertNotIn('#d4a373', svg_model)

        # 2. Star Cluster Scope (Fact table)
        svg_star = gen.generate_diagram(scope="star_cluster", target_table="Fact_Sales")
        self.assertIn('<svg', svg_star)
        self.assertIn('class="card-bg card-border-focal"', svg_star)
        self.assertIn('stroke="var(--g-focal-border)"', svg_star)
        self.assertIn('stroke-width="2.2"', svg_star)
        self.assertNotIn('#b48154', svg_star)
        self.assertNotIn('#d4a373', svg_star)

        # 3. 1-Hop Scope (Dimension table)
        svg_1hop = gen.generate_diagram(scope="1hop", target_table="Dim_Customer")
        self.assertIn('<svg', svg_1hop)
        self.assertIn('class="card-bg card-border-focal"', svg_1hop)
        self.assertIn('stroke="var(--g-focal-border)"', svg_1hop)
        self.assertIn('stroke-width="2.2"', svg_1hop)
        self.assertNotIn('#b48154', svg_1hop)
        self.assertNotIn('#d4a373', svg_1hop)

        # 4. Error handling on missing target_table
        with self.assertRaises(ValueError):
            gen.generate_diagram(scope="star_cluster")
        with self.assertRaises(ValueError):
            gen.generate_diagram(scope="1hop")

    def test_cardinality_indicators_one_to_one_and_many_to_many(self):
        """Verifies 1:1, Many-to-Many, and 1:N cardinality visual indicators on SVG connectors."""
        model_with_diverse_cards = {
            "tables": [
                {"name": "Orders", "role": "FACT", "columns": [{"name": "OrderID", "is_key": True}, {"name": "AuditID"}]},
                {"name": "OrderAudit", "role": "DIMENSION", "columns": [{"name": "AuditID", "is_key": True}]},
                {"name": "Tags", "role": "BRIDGE", "columns": [{"name": "TagID", "is_key": True}]},
            ],
            "relationships": [
                # 1:1 relationship
                {
                    "from_table": "Orders",
                    "from_column": "AuditID",
                    "to_table": "OrderAudit",
                    "to_column": "AuditID",
                    "cardinality": "1:1",
                    "cross_filtering_behavior": "Both",
                    "is_active": True,
                },
                # Many-to-Many relationship
                {
                    "from_table": "Orders",
                    "from_column": "OrderID",
                    "to_table": "Tags",
                    "to_column": "TagID",
                    "cardinality": "N:N",
                    "cross_filtering_behavior": "Single",
                    "is_active": True,
                },
            ],
        }
        gen = RelationshipSvgGenerator(model_with_diverse_cards)
        svg = gen.generate_model_svg()

        # 1. 1:1 relationship must show '1' at both ends
        self.assertIn('>1</text>', svg)
        self.assertIn('(1:1, Both)', svg)

        # 2. Many-to-Many relationship must show '*' at both ends
        self.assertIn('>*</text>', svg)
        self.assertIn('(*:*, Single)', svg)

        # 3. Legend bar includes cardinality explanation
        self.assertIn('Cardinality (1:*, 1:1, *:*)', svg)

    def test_svg_interactive_vs_flat_markdown_mode(self):
        """Verifies that interactive=True outputs dynamic CSS, hitboxes and tabindex, while interactive=False outputs flat XML SVG for Markdown."""
        gen = RelationshipSvgGenerator(self.sample_model_dict)

        # 1. Interactive SVG (for HTML portal)
        svg_interactive = gen.generate_model_svg(interactive=True)
        self.assertIn('tabindex="0"', svg_interactive)
        self.assertIn('class="rel-hitbox"', svg_interactive)
        self.assertIn('class="card-hitbox"', svg_interactive)
        self.assertIn(':has(', svg_interactive)
        self.assertIn('cursor: pointer;', svg_interactive)
        self.assertIn('viewBox="', svg_interactive)
        self.assertIn('style="max-width: 100%; height: auto;"', svg_interactive)

        # 2. Flat SVG (for standalone Markdown asset)
        svg_flat = gen.generate_model_svg(interactive=False)
        self.assertNotIn('tabindex="0"', svg_flat)
        self.assertNotIn('class="rel-hitbox"', svg_flat)
        self.assertNotIn('class="card-hitbox"', svg_flat)
        self.assertNotIn(':has(', svg_flat)
        self.assertNotIn('cursor: pointer;', svg_flat)
        self.assertIn('viewBox="', svg_flat)
        self.assertIn('width="', svg_flat)
        self.assertIn('height="', svg_flat)
        self.assertIn('style="max-width: 100%; height: auto;"', svg_flat)
        self.assertIn('.rel-group, .table-card { outline: none; }', svg_flat)

    def test_thin_model_and_utility_markdown_diagram_assets(self):
        """Verifies that thin models or models with disconnected/utility tables generate model and utility SVG diagram assets."""
        thin_model = {
            "model_name": "Thin Model",
            "tables": [
                {"name": "Orders", "role": "FACT", "columns": [{"name": "ID", "is_key": True}]},
                {"name": "DateDim", "role": "DATE_DIMENSION", "columns": [{"name": "DateKey", "is_key": True}]},
                {"name": "Utility_Config", "role": "PARAMETER_UTILITY", "columns": [{"name": "Param", "data_type": "String"}]},
            ],
            "relationships": [
                {"from_table": "Orders", "from_column": "ID", "to_table": "DateDim", "to_column": "DateKey", "is_active": True}
            ],
        }
        gen = RelationshipSvgGenerator(thin_model)
        assets = gen.build_diagram_assets("diagrams")
        self.assertIn("diagrams/model_relationships.svg", assets)
        self.assertIn("diagrams/utility_relationships.svg", assets)
        self.assertTrue(assets["diagrams/utility_relationships.svg"].strip().startswith("<svg"))
        self.assertIn("Utility_Config", assets["diagrams/utility_relationships.svg"])


if __name__ == "__main__":
    unittest.main()
