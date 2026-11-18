"""
Master Index Document Generator for Semantic Models.
Produces an overarching README / INDEX markdown linking all tables and measures.
Follows the unified Section-Driven modular architecture.
100% Python Standard Library.
"""

import re
from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .section_engine import DocSection, assemble_markdown_document
from .layout_engine import render_document_markdown
from .utils import (
    format_yaml_frontmatter,
    sanitize_filename,
    join_doc_path,
    clean_project_name,
    get_model_upstream_summaries,
    normalize_data_source_entry,
    filter_local_scope_relationships,
    resolve_bound_reports_count,
)
from .relationship_diagram import RelationshipSvgGenerator
from ..dax_formatter import format_dax


class IndexDocBuilder:
    """
    Builds the master catalog INDEX.md linking all generated table and measure documents.
    """

    def __init__(
        self,
        model_data: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        report_model: Optional[Any] = None,
        project_name: Optional[str] = None,
    ):
        self.model = model_data
        self.config = config or DocGenConfig()
        self.report_model = report_model
        rep_name = getattr(report_model, "report_name", None) if report_model else None
        self.project_name = clean_project_name(
            project_name or self.config.project_name or model_data.get("project_name") or model_data.get("model_name") or rep_name
        )

        self.valid_tables = [
            t for t in self.model.get("tables", [])
            if not self.config.is_table_excluded(t.get("name"))
        ]
        self.valid_measures = [
            m for m in self.model.get("measures", [])
            if not self.config.is_table_excluded(m.get("table"))
        ]
        self.valid_functions = self.model.get("functions", [])
        self.expr_list = self.model.get("expressions") or self.model.get("shared_queries") or []
        self.data_sources = self.model.get("data_sources_summary") or []
        self.bound_reports_info = self.model.get("bound_reports_info") or []

    def build_markdown(self) -> str:
        frontmatter_str = self._build_frontmatter()
        header_block = self._build_header_block()

        registry = {
            "description": self._section_description,
            "star_schema_diagram": self._section_star_schema_diagram,
            "architecture": self._section_star_schema_diagram,
            "physical_data_sources": self._section_sources,
            "data_source_summary": self._section_sources,
            "sources": self._section_sources,
            "published_tables": self._section_tables,
            "tables": self._section_tables,
            "relationship_table": self._section_relationship_table,
            "relationships": self._section_relationship_table,
            "udf_functions": self._section_functions,
            "functions": self._section_functions,
            "measures": self._section_measures,
            "consuming_reports": self._section_consuming_reports,
            "reports": self._section_consuming_reports,
            "details": self._section_details,
            "dataflow": self._section_expressions,
            "expressions": self._section_expressions,
            "power_query": self._section_expressions,
        }

        return render_document_markdown(
            doc_type="model",
            frontmatter_str=frontmatter_str,
            header_block=header_block,
            registry=registry,
            config=self.config,
        )

    def _legacy_build_markdown(self) -> str:
        frontmatter_str = self._build_frontmatter()
        header_block = self._build_header_block()

        sections = [
            self._section_description(),
            self._section_sources(),
            self._section_expressions(),
            self._section_tables(),
            self._section_architecture(),
            self._section_functions(),
            self._section_measures(),
            self._section_consuming_reports(),
            self._section_details(),
        ]
        return assemble_markdown_document(frontmatter_str, header_block, sections)

    def _build_frontmatter(self) -> str:
        frontmatter = {
            "title": f"Semantic Model Documentation: {self.model.get('model_name')}",
            "pbip_project": self.project_name,
            "doc_type": "semantic_model_catalog",
            "format": self.model.get("source_format"),
            "tables_count": len(self.valid_tables),
            "measures_count": len(self.valid_measures),
            "functions_count": len(self.valid_functions),
            "expressions_count": len(self.expr_list),
            "data_sources_count": len(self.data_sources),
            "excluded_tables_count": self.model.get("excluded_tables_count", 0),
            "tags": ["semantic_model", "catalog", "pbip", sanitize_filename(self.project_name), self.model.get("model_name", "model")],
        }
        if self.report_model and self.config.include_visual_docs:
            rep_pages = getattr(self.report_model, "pages", []) if hasattr(self.report_model, "pages") else self.report_model.get("pages", [])
            rep_name = getattr(self.report_model, "report_name", "") if hasattr(self.report_model, "report_name") else self.report_model.get("report_name", "")
            frontmatter["report_name"] = rep_name
            frontmatter["report_pages_count"] = len(rep_pages)
            if rep_name:
                frontmatter["tags"].append(sanitize_filename(rep_name))
            frontmatter["tags"].append("report")

        return format_yaml_frontmatter(frontmatter)

    def _build_header_block(self) -> str:
        bound_reports_cnt = resolve_bound_reports_count(
            self.model,
            bound_reports_info=self.bound_reports_info,
            report_model=self.report_model,
            include_reports=self.config.include_reports,
        )

        total_cols = sum(len(t.get("columns", [])) for t in self.valid_tables)

        lines = [
            f"# Semantic Model Documentation: `{self.model.get('model_name')}`",
            "",
            f"**Tables**: `{len(self.valid_tables)}` | **Measures**: `{len(self.valid_measures)}` | **Physical Columns**: `{total_cols}` | **Bound Reports**: `{bound_reports_cnt}`",
        ]
        return "\n".join(lines)

    def _get_upstream_models(self) -> List[Dict[str, Any]]:
        return get_model_upstream_summaries(self.model, self.config)

    # 1. Description
    def _section_description(self) -> DocSection:
        lines = [
            "## Description",
            "",
        ]
        if self.model.get("description"):
            lines.append(f"> {self.model['description']}")
            lines.append("")
        lines.append(
            f"Technical documentation and data dictionary catalog for semantic model **`{self.model.get('model_name')}`**. "
            "Every table, DAX measure, User-Defined Function, and ETL expression features a dedicated Markdown document complete with structured YAML frontmatter for search, retrieval, and technical reference."
        )

        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content="\n".join(lines),
        )

    # 2. Physical Data Sources
    def _section_sources(self) -> DocSection:
        lines = [
            "## Detected Physical Data Sources",
            "",
            "| Connector Type | Connection / Target | Server | Database |",
            "| :--- | :--- | :--- | :--- |",
        ]
        expressions_sub = self.config.expressions_subdir.strip("/\\")
        up_models = self._get_upstream_models()
        up_names = {m.get("name", "") for m in up_models}
        known_expr_names = {
            (e.get("query_name") or e.get("name"))
            for e in self.expr_list
            if (e.get("query_name") or e.get("name"))
        }

        for raw_src in self.data_sources:
            src = normalize_data_source_entry(raw_src, self.model, self.config, up_names)
            stype = f"`{src.get('source_type')}`"
            raw_conn = src.get('connection_string', '—')
            param_q = src.get("parameter_query_name")
            if param_q:
                p_val = src.get("parameter_value") or ""
                clean_p = sanitize_filename(param_q)
                p_url = f"{expressions_sub}/{clean_p}.md" if expressions_sub else f"{clean_p}.md"
                val_note = f" *({p_val})*" if p_val else ""
                conn = f"[`{raw_conn}`]({p_url}){val_note}"
            elif raw_conn in known_expr_names and self.config.include_markdown_links:
                clean_q = sanitize_filename(raw_conn)
                p_url = f"{expressions_sub}/{clean_q}.md" if expressions_sub else f"{clean_q}.md"
                conn = f"[`{raw_conn}`]({p_url})"
            else:
                conn = f"`{raw_conn}`"
            raw_server = src.get("server") or ""
            server = f"`{raw_server}`" if raw_server else "—"
            raw_db = src.get("database") or ""
            if raw_db and raw_db != "—":
                target_model_slug = src.get("target_model_slug")
                is_remote_model = src.get("is_remote_model", False)
                if target_model_slug:
                    db = f"[**{raw_db}**](../../models/{target_model_slug}/README.md)"
                elif is_remote_model:
                    db = f"`{raw_db}` *(External Remote Model)*"
                else:
                    db = f"`{raw_db}`"
            else:
                db = "—"
            lines.append(f"| {stype} | {conn} | {server} | {db} |")

        if self.config.include_dataflow and getattr(self.config, "include_expression_docs", True):
            df_overview_url = f"{expressions_sub}/README.md" if expressions_sub else "README_dataflow.md"
            lines.append("")
            lines.append(f"> 🔄 **Dataflow Overview**: View centralized ingestion pipelines and transformation architecture in [{self.project_name} Dataflow Overview]({df_overview_url}).")

        return DocSection(
            section_id="tab-sources",
            title="Physical Data Sources",
            nav_label=f"Data Sources ({len(self.data_sources)})",
            content="\n".join(lines),
        )

    def _resolve_table_link(self, name: str) -> str:
        if not self.config.include_markdown_links:
            return f"`{name}`"
        tbl = next((t for t in self.model.get("tables", []) if t.get("name") == name), None)
        clean_tbl = sanitize_filename(name)
        if tbl and not self.config.is_table_published(tbl):
            ext_url = self.config.resolve_external_table_url(tbl)
            if ext_url:
                return f"[`{name}`]({ext_url}) *(Inherited Entity)*"
            return f"`{name}` *(Inherited Entity)*"
        tables_sub = self.config.tables_subdir.strip("/\\")
        if self.config.base_doc_url:
            tbl_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
        else:
            tbl_url = f"{tables_sub}/{clean_tbl}.md" if tables_sub else f"{clean_tbl}.md"
        return f"[`{name}`]({tbl_url})"

    # 3. Published Data Model Tables
    def _section_tables(self) -> DocSection:
        content = self._build_tables_catalog(self.valid_tables, self.valid_measures)
        return DocSection(
            section_id="tab-tables",
            title="Published Data Model Tables",
            nav_label=f"Tables ({len(self.valid_tables)})",
            content=content,
        )

    def _build_tables_catalog(self, tables: Optional[List[Dict[str, Any]]] = None, measures: Optional[List[Dict[str, Any]]] = None) -> str:
        lines = [
            "## Published Data Model Tables",
            "",
            "Tables analyzed and classified according to topological and heuristic criteria:",
            "",
            "| Table | Role | Refresh Policy | Columns | Measures |",
            "| :--- | :--- | :---: | :---: | :---: |",
        ]

        if tables is None:
            tables = self.valid_tables
        if measures is None:
            measures = self.valid_measures

        role_order = {"FACT": 0, "DIMENSION": 1, "LOOKUP_OUTRIGGER": 2, "DATE_DIMENSION": 3, "BRIDGE": 4, "PARAMETER_UTILITY": 5}
        sorted_tables = sorted(tables, key=lambda t: (role_order.get(t.get("role"), 99), t.get("name")))

        for t in sorted_tables:
            name = t.get("name")
            role = f"`{t.get('role')}`"
            inc_pol = t.get("incremental_refresh_policy")
            if inc_pol and inc_pol.get("is_enabled"):
                mode = inc_pol.get("mode")
                if mode == "hybrid":
                    refresh_badge = "⚡ Hybrid"
                else:
                    refresh_badge = "🔄 Incremental"
            elif t.get("is_inherited"):
                refresh_badge = "📦 Inherited"
            elif t.get("source_type") == "CalculatedTable":
                refresh_badge = "🧮 DAX Calc"
            else:
                refresh_badge = "Full"
            col_count = len(t.get("columns", []))
            m_count = len([m for m in measures if m.get("table") == name])
            clean_tbl = sanitize_filename(name)
            if self.config.is_table_published(t):
                tables_sub = self.config.tables_subdir.strip("/\\")
                if self.config.base_doc_url:
                    tbl_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
                else:
                    tbl_url = f"{tables_sub}/{clean_tbl}.md" if tables_sub else f"{clean_tbl}.md"
                link = f"[`{name}`]({tbl_url})"
            else:
                ext_url = self.config.resolve_external_table_url(t)
                if ext_url:
                    link = f"[`{name}`]({ext_url}) *(External)*"
                else:
                    link = "— *(Inherited Entity)*"
            lines.append(f"| {link} | {role} | {refresh_badge} | {col_count} | {m_count} |")

        return "\n".join(lines)

    # 4. Star Schema and Diagram
    def _section_star_schema_diagram(self) -> Optional[DocSection]:
        if not self.config.include_relationship_diagrams:
            return None
        relationships = filter_local_scope_relationships(
            self.model.get("relationships", []),
            self.model.get("tables", []),
            self.config,
        )
        up_models = self._get_upstream_models()
        if not relationships and not up_models:
            return None

        diag_url = self.config.resolve_model_diagram_svg_url()
        lines = [
            "## Star Schema Relationship Diagram",
            "",
            f"![Star Schema Relationship Diagram]({diag_url})",
            "",
            "*Visual entity relationship topology and role partitions across the semantic model.*",
        ]

        # Multi-Fact Galaxy: Render Star Clusters summary table
        try:
            svg_gen = RelationshipSvgGenerator(self.model, config=self.config)
            fact_tables = svg_gen.get_fact_tables()
            if len(fact_tables) >= 2:
                lines.extend([
                    "",
                    "### Star Clusters by Fact Table (Multi-Fact Galaxy Topology)",
                    "",
                    "The semantic model contains multiple Fact tables forming distinct dimensional Star Clusters. Each cluster isolates a Fact table with its conformed and dedicated dimensions, bridges, and snowflake outriggers.",
                    "",
                    "| Fact Table | Role | Connected Dimensions | Connected Bridges | Outriggers (Lookups) | Star Cluster Diagram |",
                    "| :--- | :--- | :---: | :---: | :---: | :--- |",
                ])
                for f_name in fact_tables:
                    cluster = svg_gen.extract_star_cluster(f_name)
                    c_dims = len(cluster.get("dimensions", []))
                    c_bridges = len(cluster.get("bridges", []))
                    c_outriggers = len(cluster.get("outriggers", []))
                    f_link = self._resolve_table_link(f_name)
                    diag_table_url = self.config.resolve_index_table_diagram_svg_url(f_name)
                    lines.append(
                        f"| {f_link} | `FACT` | {c_dims} | {c_bridges} | {c_outriggers} | [📊 View Star Cluster]({diag_table_url}) |"
                    )
        except Exception:
            pass

        return DocSection(
            section_id="star_schema_diagram",
            title="Star Schema Diagram",
            nav_label="Diagram",
            content="\n".join(lines),
        )

    def _section_relationship_table(self) -> Optional[DocSection]:
        relationships = filter_local_scope_relationships(
            self.model.get("relationships", []),
            self.model.get("tables", []),
            self.config,
        )
        if not relationships:
            return None

        lines = [
            "## Model Relationships",
            "",
        ]
        up_models = self._get_upstream_models()
        if up_models:
            for up in up_models:
                up_name = up["name"]
                t_cnt = up.get("tables_count", 0)
                m_cnt = up.get("measures_count", 0)
                target_model_slug = up.get("target_model_slug")
                if target_model_slug:
                    l_badge = f"[**{up_name}**](../../models/{target_model_slug}/README.md)"
                else:
                    l_badge = f"`{up_name}` *(External Remote Model)*"
                mode_lbl = up.get("mode", "DirectQuery")
                lines.append(f"> **Upstream Composite Link**: Inherits entities from {l_badge} ({t_cnt} tables, {m_cnt} measures via `{mode_lbl}`).")
            lines.append("")

        lines.extend([
            "### Active Relationships Matrix",
            "",
            "| From Table | From Column | Cardinality | Cross-Filtering | To Table | To Column | Status |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for r in relationships:
            status = "Active" if r.get("is_active", True) else "Inactive"
            from_t = r.get("from_table", "")
            to_t = r.get("to_table", "")
            from_c = r.get("from_column", "")
            to_c = r.get("to_column", "")
            card = r.get("cardinality", "")
            cross = r.get("cross_filtering_behavior", "")

            from_link = self._resolve_table_link(from_t)
            to_link = self._resolve_table_link(to_t)

            lines.append(
                f"| {from_link} | `{from_c}` | {card} | {cross} | {to_link} | `{to_c}` | {status} |"
            )

        return DocSection(
            section_id="relationship_table",
            title="Model Relationships",
            nav_label="Relationships",
            content="\n".join(lines),
        )

    def _section_architecture(self) -> Optional[DocSection]:
        content = self._build_architecture_and_relationships_section()
        if not content:
            return None
        return DocSection(
            section_id="tab-architecture",
            title="Star Schema and Diagram",
            nav_label="Star Schema & Diagram",
            content=content,
        )

    def _build_architecture_and_relationships_section(self) -> Optional[str]:
        """Star Schema Architecture Diagram & Active Relationships Matrix."""
        relationships = filter_local_scope_relationships(
            self.model.get("relationships", []),
            self.model.get("tables", []),
            self.config,
        )
        if not relationships:
            return None

        lines = [
            "## Model Architecture & Relationships",
            "",
        ]
        up_models = self._get_upstream_models()
        if up_models:
            for up in up_models:
                up_name = up["name"]
                t_cnt = up.get("tables_count", 0)
                m_cnt = up.get("measures_count", 0)
                target_model_slug = up.get("target_model_slug")
                if target_model_slug:
                    l_badge = f"[**{up_name}**](../../models/{target_model_slug}/README.md)"
                else:
                    l_badge = f"`{up_name}` *(External Remote Model)*"
                mode_lbl = up.get("mode", "DirectQuery")
                lines.append(f"> **Upstream Composite Link**: Inherits entities from {l_badge} ({t_cnt} tables, {m_cnt} measures via `{mode_lbl}`).")
            lines.append("")

        lines.extend([
            "### Active Relationships Matrix",
            "",
            "| From Table | From Column | Cardinality | Cross-Filtering | To Table | To Column | Status |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for r in relationships:
            status = "Active" if r.get("is_active", True) else "Inactive"
            from_t = r.get("from_table", "")
            to_t = r.get("to_table", "")
            from_c = r.get("from_column", "")
            to_c = r.get("to_column", "")
            card = r.get("cardinality", "")
            cross = r.get("cross_filtering_behavior", "")

            from_link = self._resolve_table_link(from_t)
            to_link = self._resolve_table_link(to_t)

            lines.append(
                f"| {from_link} | `{from_c}` | {card} | {cross} | {to_link} | `{to_c}` | {status} |"
            )

        if self.config.include_relationship_diagrams:
            diag_url = self.config.resolve_model_diagram_svg_url()
            lines.extend([
                "",
                "### Star Schema Relationship Diagram",
                "",
                f"![Star Schema Relationship Diagram]({diag_url})",
                "",
                "*Visual entity relationship topology and role partitions across the semantic model.*",
            ])

            # Multi-Fact Galaxy: Render Star Clusters summary table (Opzione A - RAG Ready)
            try:
                svg_gen = RelationshipSvgGenerator(self.model, config=self.config)
                fact_tables = svg_gen.get_fact_tables()
                if len(fact_tables) >= 2:
                    lines.extend([
                        "",
                        "### Star Clusters by Fact Table (Multi-Fact Galaxy Topology)",
                        "",
                        "The semantic model contains multiple Fact tables forming distinct dimensional Star Clusters. Each cluster isolates a Fact table with its conformed and dedicated dimensions, bridges, and snowflake outriggers.",
                        "",
                        "| Fact Table | Role | Connected Dimensions | Connected Bridges | Outriggers (Lookups) | Star Cluster Diagram |",
                        "| :--- | :--- | :---: | :---: | :---: | :--- |",
                    ])
                    for f_name in fact_tables:
                        cluster = svg_gen.extract_star_cluster(f_name)
                        c_dims = len(cluster.get("dimensions", []))
                        c_bridges = len(cluster.get("bridges", []))
                        c_outriggers = len(cluster.get("outriggers", []))
                        f_link = self._resolve_table_link(f_name)
                        diag_table_url = self.config.resolve_index_table_diagram_svg_url(f_name)
                        lines.append(
                            f"| {f_link} | `FACT` | {c_dims} | {c_bridges} | {c_outriggers} | [📊 View Star Cluster]({diag_table_url}) |"
                        )
            except Exception:
                pass

        return "\n".join(lines)

    # 5. Power Query & Dataflow
    def _section_expressions(self) -> Optional[DocSection]:
        if not self.config.include_expression_docs or not (getattr(self.config, "include_expression_chapter", False) or getattr(self.config, "include_expression_sidebar_chapter", False)):
            return None
        content = self._build_expressions_catalog(self.expr_list)
        if not content:
            return None
        dataflow_tables = [
            t for t in self.valid_tables
            if (
                t.get("source_type", "PowerQuery") == "PowerQuery"
                or bool(t.get("power_query_lineage") and t.get("power_query_lineage", {}).get("full_m_expression"))
            )
            and t.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (t.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
        ]
        total_cnt = len(self.expr_list) + len(dataflow_tables)
        return DocSection(
            section_id="tab-expressions",
            title="Dataflow",
            nav_label=f"Dataflow ({total_cnt})",
            content=content,
        )

    def _build_expressions_catalog(self, expressions: Optional[List[Dict[str, Any]]] = None) -> str:
        exprs = expressions if expressions is not None else self.expr_list
        dataflow_tables = [
            t for t in self.valid_tables
            if (
                t.get("source_type", "PowerQuery") == "PowerQuery"
                or bool(t.get("power_query_lineage") and t.get("power_query_lineage", {}).get("full_m_expression"))
            )
            and t.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (t.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
        ]

        if not exprs and not dataflow_tables:
            return ""

        expressions_sub = self.config.expressions_subdir.strip("/\\")
        tables_sub = self.config.tables_subdir.strip("/\\")

        params = [
            e for e in exprs
            if e.get("expression_kind") == "parameter"
            or "IsParameterQuery" in e.get("full_m_expression", "")
            or "IsParameterQueryRequired" in e.get("full_m_expression", "")
        ]
        etls = [e for e in exprs if e not in params]

        df_overview_url = f"{expressions_sub}/README.md" if expressions_sub else "README_dataflow.md"
        sections_md = [
            "## Power Query Dataflow & Expressions",
            "",
            f"> 🔄 **Dataflow Overview**: View the centralized Power Query ingestion pipelines and transformation architecture in [{self.project_name} Dataflow Overview]({df_overview_url}).",
        ]

        # 1. Block: Loaded Model Tables Ingestion
        if dataflow_tables:
            tbl_lines = [
                f"### Loaded Model Tables Ingestion ({len(dataflow_tables)})",
                "",
                "Power Query M ingestion pipelines feeding data directly into the semantic model:",
                "",
                "| Ingested Table | Star Schema Role | Steps | Power Query Pipeline | Semantic Model Doc |",
                "| :--- | :--- | :---: | :--- | :--- |",
            ]
            for t in sorted(dataflow_tables, key=lambda x: x.get("name", "")):
                t_name = t.get("name", "Table")
                clean_t = sanitize_filename(t_name)
                role = t.get("role", "DIM")
                lineage = t.get("power_query_lineage") or {}
                steps_cnt = len(lineage.get("steps", []))
                expr_url = f"{expressions_sub}/{clean_t}.md" if expressions_sub else f"{clean_t}.md"
                model_url = f"{tables_sub}/{clean_t}.md" if tables_sub else f"{clean_t}.md"
                tbl_lines.append(f"| **`{t_name}`** | `{role}` | {steps_cnt} | [`{t_name}`]({expr_url}) | [`{t_name}`]({model_url}) |")
            sections_md.append("\n".join(tbl_lines))

        # 1. Dedicated Block: Power Query Parameters
        if params:
            param_lines = [
                f"### Query Parameters M ({len(params)})",
                "",
                "Configurable environment and deployment parameters governing connections, endpoints, and filters:",
                "",
                "| Parameter | Current Value | Data Type | Required | Consuming Queries & Tables | Document Link |",
                "| :--- | :--- | :---: | :---: | :--- | :--- |",
            ]
            for p in sorted(params, key=lambda x: x.get("query_name", "")):
                p_name = p.get("query_name") or "parameter"
                clean_p = sanitize_filename(p_name)
                p_val = p.get("parameter_value") or "—"
                p_type = p.get("parameter_type") or "Any"
                p_req = "Yes" if p.get("parameter_required") else "No"

                # Downstream impact
                impacted = []
                for dt in p.get("downstream_tables", []):
                    clean_dt = sanitize_filename(dt)
                    dt_url = f"{tables_sub}/{clean_dt}.md" if tables_sub else f"{clean_dt}.md"
                    impacted.append(f"[`{dt}`]({dt_url})")
                for dq in p.get("downstream_queries", []):
                    clean_dq = sanitize_filename(dq)
                    dq_url = f"{expressions_sub}/{clean_dq}.md" if expressions_sub else f"{clean_dq}.md"
                    impacted.append(f"[`{dq}`]({dq_url})")
                impact_str = ", ".join(impacted) or "— *(Unused)*"

                p_doc_url = f"{expressions_sub}/{clean_p}.md" if expressions_sub else f"{clean_p}.md"
                doc_link = f"[`{p_name}`]({p_doc_url})"
                param_lines.append(f"| `{p_name}` | `{p_val}` | `{p_type}` | {p_req} | {impact_str} | {doc_link} |")

            sections_md.append("\n".join(param_lines))

        # 2. Block: Shared ETL & Staging Queries
        if etls:
            etl_lines = [
                f"### Shared ETL & Staging Queries ({len(etls)})",
                "",
                "Intermediate data transformations, custom M functions, and static lookup tables:",
                "",
                "| Expression | Pipeline Role | Target Table | Downstream Tables | Root Sources | Document Link |",
                "| :--- | :--- | :--- | :--- | :--- | :--- |",
            ]
            for expr in sorted(etls, key=lambda e: e.get("query_name", "")):
                name = expr.get("query_name") or "expression"
                clean_name = sanitize_filename(name)
                is_inline = expr.get("is_inline_table", False)
                full_m = expr.get("full_m_expression", "")

                if is_inline or "#table" in full_m:
                    col_cnt = len(expr.get("inline_table_columns", []))
                    row_cnt = len(expr.get("inline_table_rows", []))
                    type_badge = f"📊 Inline Table (`{row_cnt}r × {col_cnt}c`)" if (col_cnt or row_cnt) else "📊 Inline Table"
                elif expr.get("is_m_function") or re.search(r'^\s*(\([^\)]*\)|\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*=>', full_m, re.MULTILINE):
                    type_badge = "λ Custom Function M"
                elif expr.get("is_staging", True):
                    type_badge = "🔄 Staging Query"
                else:
                    type_badge = "📦 Model Entity"

                target_t = expr.get("target_table") or "—"

                downstream = [
                    t for t in expr.get("downstream_tables", [])
                    if not self.config.is_table_excluded(t)
                ]
                if downstream:
                    t_links = []
                    for dt in downstream:
                        clean_dt = sanitize_filename(dt)
                        dt_url = f"{tables_sub}/{clean_dt}.md" if tables_sub else f"{clean_dt}.md"
                        t_links.append(f"[`{dt}`]({dt_url})")
                    downstream_str = ", ".join(t_links)
                else:
                    downstream_str = "— *(Unloaded)*"

                sources = expr.get("root_sources", [])
                if sources:
                    src_types = sorted(list({s.get("source_type", "GENERIC") for s in sources}))
                    sources_str = ", ".join(f"`{st}`" for st in src_types)
                else:
                    sources_str = "—"

                expr_url = f"{expressions_sub}/{clean_name}.md" if expressions_sub else f"{clean_name}.md"
                doc_link = f"[`{name}`]({expr_url})"
                etl_lines.append(f"| `{name}` | {type_badge} | {target_t} | {downstream_str} | {sources_str} | {doc_link} |")

            sections_md.append("\n".join(etl_lines))

        return "\n\n".join(sections_md)

    # 6. UDF Functions (immediately before Measures)
    def _section_functions(self) -> Optional[DocSection]:
        content = self._build_functions_catalog(self.valid_functions)
        if not content:
            return None
        return DocSection(
            section_id="tab-functions",
            title="UDF Functions",
            nav_label=f"UDF Functions ({len(self.valid_functions)})",
            content=content,
        )

    def _build_functions_catalog(self, functions: Optional[List[Dict[str, Any]]] = None) -> str:
        funcs = self.valid_functions if functions is None else functions
        if not funcs:
            return ""

        lines = [
            f"## User-Defined Functions Catalog (UDFs) ({len(funcs)})",
            "",
            "DAX User-Defined Functions (UDFs) defined at semantic model scope (`functions.tmdl`):",
            "",
            "| Function Name | Return Type | Signature | Downstream Measures | Document Link |",
            "| :--- | :---: | :--- | :---: | :--- |",
        ]

        functions_sub = self.config.functions_subdir.strip("/\\")
        sorted_funcs = sorted(funcs, key=lambda f: f.get("name", ""))

        for fn in sorted_funcs:
            fn_name = fn.get("name")
            ret_type = fn.get("return_type") or "Variant"
            sig = fn.get("parameters_signature") or "()"
            sanitized = sanitize_filename(fn_name)
            down_count = len(fn.get("downstream_measures", []))
            if self.config.base_doc_url:
                fn_url = join_doc_path(self.config.base_doc_url, functions_sub, f"{sanitized}.md") if functions_sub else join_doc_path(self.config.base_doc_url, f"{sanitized}.md")
            else:
                fn_url = f"{functions_sub}/{sanitized}.md" if functions_sub else f"{sanitized}.md"
            link = f"[`{fn_name}`]({fn_url})"
            lines.append(f"| `{fn_name}` | `{ret_type}` | `{sig}` | {down_count} | {link} |")

        # Detailed block per UDF: Description, Parameters List, and DAX
        for fn in sorted_funcs:
            fn_name = fn.get("name")
            ret_type = fn.get("return_type") or "Variant"
            sig = fn.get("parameters_signature") or "()"
            desc = fn.get("description")
            params = fn.get("parameters", [])
            expr = fn.get("expression") or fn.get("body") or ""
            sanitized = sanitize_filename(fn_name)
            if self.config.base_doc_url:
                fn_url = join_doc_path(self.config.base_doc_url, functions_sub, f"{sanitized}.md") if functions_sub else join_doc_path(self.config.base_doc_url, f"{sanitized}.md")
            else:
                fn_url = f"{functions_sub}/{sanitized}.md" if functions_sub else f"{sanitized}.md"

            lines.extend([
                "",
                f"### UDF: [`{fn_name}`]({fn_url})",
                "",
                f"- **Description**: {desc if desc else '*No description provided.*'}",
                f"- **Return Type**: `{ret_type}`",
            ])
            if params:
                lines.extend([
                    "- **Parameters**:",
                    "",
                    "| Parameter | Data Type | Optional | Default Value | Description |",
                    "| :--- | :---: | :---: | :--- | :--- |",
                ])
                for p in params:
                    p_name = f"`{p.get('name')}`"
                    p_type = f"`{p.get('data_type') or 'Variant'}`"
                    p_opt = "Yes" if p.get("is_optional") else "No"
                    p_def = f"`{p.get('default_value')}`" if p.get("default_value") is not None else "—"
                    p_desc = p.get("description") or "—"
                    lines.append(f"| {p_name} | {p_type} | {p_opt} | {p_def} | {p_desc} |")
            else:
                lines.append(f"- **Parameters**: `{sig}`")

            formatted_dax = format_dax(
                expr,
                name=fn_name,
                entity_type="function",
                parameters_signature=sig,
            ) if expr else "-- No DAX formula provided"
            lines.extend([
                "",
                "```dax",
                formatted_dax,
                "```",
            ])

        return "\n".join(lines)

    # 7. Measures
    def _section_measures(self) -> DocSection:
        content = self._build_measures_catalog(self.valid_measures)
        return DocSection(
            section_id="tab-measures",
            title="Measures",
            nav_label=f"Measures ({len(self.valid_measures)})",
            content=content,
        )

    def _build_measures_catalog(self, measures: Optional[List[Dict[str, Any]]] = None) -> str:
        lines = [
            "## DAX Measures Catalog",
            "",
            "DAX measures indexed by calculation hierarchy (Calculation Depth):",
            "",
            "| Measure | Table | DAG Depth | Dependencies |",
            "| :--- | :--- | :---: | :--- |",
        ]

        if measures is None:
            measures = self.valid_measures
        sorted_measures = sorted(measures, key=lambda m: (m.get("calculation_depth", 0), m.get("table", ""), m.get("name", "")))

        for m in sorted_measures:
            m_name = m.get("name")
            tbl = m.get("table") or "Model"
            depth = f"Depth {m.get('calculation_depth', 0)}"
            clean_tbl = sanitize_filename(tbl)
            sanitized = sanitize_filename(m_name)
            if self.config.is_measure_published(m):
                measures_sub = self.config.measures_subdir.strip("/\\")
                if self.config.base_doc_url:
                    meas_url = join_doc_path(self.config.base_doc_url, measures_sub, clean_tbl, f"{sanitized}.md") if measures_sub else join_doc_path(self.config.base_doc_url, clean_tbl, f"{sanitized}.md")
                else:
                    meas_url = f"{measures_sub}/{clean_tbl}/{sanitized}.md" if measures_sub else f"{clean_tbl}/{sanitized}.md"
                link = f"[`[{m_name}]`]({meas_url})"
            else:
                ext_url = self.config.resolve_external_measure_url(m, self.model.get("tables", []))
                if ext_url:
                    link = f"[`[{m_name}]`]({ext_url}) *(External)*"
                else:
                    link = "— *(External Measure)*"
            deps = ", ".join(f"`[{d}]`" for d in m.get("direct_measure_dependencies", [])) or "— (Base Measure)"
            lines.append(f"| {link} | `{tbl}` | {depth} | {deps} |")

        ext_count = len([m for m in sorted_measures if not self.config.is_measure_published(m)])
        if ext_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **External Measures**: {ext_count} measures declared via `EXTERNALMEASURE(...)` "
                "are cataloged in the model index, but their individual documentation pages are not generated."
            )

        return "\n".join(lines)

    # 8. Consuming Reports (immediately before Details)
    def _section_consuming_reports(self) -> Optional[DocSection]:
        blocks: List[str] = []
        count = 0

        if self.bound_reports_info:
            count = len(self.bound_reports_info)
            lines = [
                f"## Consuming Reports ({count})",
                "",
                "Reports bound to and consuming this semantic model:",
                "",
                "| Report Name | Format | Binding | Pages |",
                "| :--- | :---: | :---: | :---: |",
            ]
            for rep in self.bound_reports_info:
                r_name = rep.get("name", "Report")
                r_fmt = rep.get("format", "PBIR")
                r_pages = rep.get("pages_count", 0)
                r_url = rep.get("md_url") or f"../../reports/{sanitize_filename(r_name)}/README.md"
                is_direct = rep.get("is_direct", True)
                via = rep.get("via_model")
                binding_str = "Direct" if is_direct else (f"*via {via}*" if via else "*Indirect*")
                lines.append(f"| [**{r_name}**]({r_url}) | `{r_fmt}` | {binding_str} | {r_pages} |")
            blocks.append("\n".join(lines))

        if self.report_model and self.config.include_visual_docs:
            rep_pages_md = self._build_report_pages_catalog()
            if rep_pages_md:
                blocks.append(rep_pages_md)
                if not count:
                    count = 1

        if not blocks:
            return None

        return DocSection(
            section_id="tab-reports",
            title="Consuming Reports",
            nav_label=f"Consuming Reports ({count})",
            content="\n\n".join(blocks),
        )

    def _build_report_pages_catalog(self) -> str:
        """Catalog of report pages with links to dedicated page documentation."""
        if not self.report_model:
            return ""

        pages = getattr(self.report_model, "pages", [])
        if not pages and isinstance(self.report_model, dict):
            pages = self.report_model.get("pages", [])

        if not pages:
            return ""

        rep_name = getattr(self.report_model, "report_name", "") or (
            self.report_model.get("report_name", "Report") if isinstance(self.report_model, dict) else "Report"
        )
        rep_format = getattr(self.report_model, "format", "") or (
            self.report_model.get("format", "PBIR") if isinstance(self.report_model, dict) else "PBIR"
        )

        lines = [
            f"## Report Presentation & Visuals: `{rep_name}`",
            "",
            f"The presentation layer `{rep_name}.Report` ({rep_format}) is organized into **{len(pages)}** pages. "
            "Each page features a dedicated documentation document detailing canvas coordinates, evaluated metrics, slicing dimensions, and filter context:",
            "",
            "| Page | Role | Canvas Size | Status | Dynamic Visuals | Key Evaluated Metrics |",
            "| :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        vis_sub = self.config.visuals_subdir.strip("/\\")
        meas_sub = self.config.measures_subdir.strip("/\\")

        known_measures = {
            (meas.get("table"), meas.get("name"))
            for meas in self.model.get("measures", [])
        }

        for p in pages:
            p_name = getattr(p, "display_name", "") if hasattr(p, "display_name") else p.get("display_name", "")
            p_type = getattr(p, "page_type", "NORMAL") if hasattr(p, "page_type") else p.get("page_type", "NORMAL")
            w = getattr(p, "width", 1920) if hasattr(p, "width") else p.get("width", 1920)
            h = getattr(p, "height", 1080) if hasattr(p, "height") else p.get("height", 1080)
            is_hidden = getattr(p, "is_hidden", False) if hasattr(p, "is_hidden") else p.get("is_hidden", False)
            visuals = getattr(p, "visuals", []) if hasattr(p, "visuals") else p.get("visuals", [])

            dynamic_v = [v for v in visuals if (getattr(v, "is_dynamic", False) if hasattr(v, "is_dynamic") else True)]

            clean_p = sanitize_filename(p_name)
            if self.config.base_doc_url:
                p_url = join_doc_path(self.config.base_doc_url, vis_sub, f"{clean_p}.md") if vis_sub else join_doc_path(self.config.base_doc_url, f"{clean_p}.md")
            else:
                p_url = f"{vis_sub}/{clean_p}.md" if vis_sub else f"{clean_p}.md"

            p_link = f"[{p_name}]({p_url})"
            status_str = "Hidden" if is_hidden else "Visible"

            metric_links = []
            seen_keys = set()
            for v in dynamic_v:
                calc = getattr(v, "calculation_context", None) if hasattr(v, "calculation_context") else v.get("calculation_context", {})
                v_metrics = (
                    getattr(calc, "evaluated_metrics", [])
                    if hasattr(calc, "evaluated_metrics")
                    else (calc.get("evaluated_metrics", []) if isinstance(calc, dict) else [])
                )
                for m in v_metrics:
                    m_key = getattr(m, "model_key", "") if hasattr(m, "model_key") else m.get("model_key", "")
                    tbl = getattr(m, "table", "") if hasattr(m, "table") else m.get("table", "")
                    fld = getattr(m, "field", "") if hasattr(m, "field") else m.get("field", "")
                    m_type = getattr(m, "field_type", "") if hasattr(m, "field_type") else (m.get("field_type", "") if isinstance(m, dict) else "")
                    tables_sub = self.config.tables_subdir.strip("/\\")
                    if m_key and m_key not in seen_keys:
                        seen_keys.add(m_key)
                        if self.config.include_markdown_links and tbl and fld and tbl != "Unknown":
                            is_meas = (m_type == "MEASURE") or ((tbl, fld) in known_measures)
                            if is_meas:
                                if self.config.base_doc_url:
                                    m_url = join_doc_path(self.config.base_doc_url, meas_sub, sanitize_filename(tbl), f"{sanitize_filename(fld)}.md") if meas_sub else join_doc_path(self.config.base_doc_url, sanitize_filename(tbl), f"{sanitize_filename(fld)}.md")
                                else:
                                    m_url = f"{meas_sub}/{sanitize_filename(tbl)}/{sanitize_filename(fld)}.md" if meas_sub else f"{sanitize_filename(tbl)}/{sanitize_filename(fld)}.md"
                                clean_meas_display = f"[{fld}]" if not fld.startswith("[") else fld
                                metric_links.append(f"[{clean_meas_display}]({m_url})")
                            else:
                                if self.config.base_doc_url:
                                    m_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{sanitize_filename(tbl)}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{sanitize_filename(tbl)}.md")
                                else:
                                    m_url = f"{tables_sub}/{sanitize_filename(tbl)}.md" if tables_sub else f"{sanitize_filename(tbl)}.md"
                                metric_links.append(f"[{m_key}]({m_url})")
                        else:
                            is_meas = (m_type == "MEASURE") or ((tbl, fld) in known_measures)
                            if is_meas:
                                clean_meas_display = f"[{fld}]" if not fld.startswith("[") else fld
                                metric_links.append(f"`{clean_meas_display}`")
                            else:
                                metric_links.append(f"`{m_key}`")
                        if len(metric_links) >= 3:
                            break
                if len(metric_links) >= 3:
                    break

            metrics_display = ", ".join(metric_links) if metric_links else "—"
            lines.append(f"| {p_link} | `{p_type}` | `{w}x{h}` | {status_str} | {len(dynamic_v)} | {metrics_display} |")

        return "\n".join(lines)

    # 9. Details
    def _section_details(self) -> DocSection:
        source_format = self.model.get("source_format") or "TMDL"
        compat_level = self.model.get("compatibility_level") or 1600
        culture = self.model.get("culture") or "en-US"
        calc_count = len([t for t in self.valid_tables if t.get("source_type") == "CalculatedTable"])
        inherited_count = len([t for t in self.valid_tables if t.get("is_inherited") or not self.config.is_table_published(t)])
        excluded_count = self.model.get("excluded_tables_count", 0)

        lines = [
            "## Details",
            "",
            "| Property | Value |",
            "| :--- | :--- |",
            f"| **Source Format** | `{source_format}` |",
            f"| **Compatibility Level** | `{compat_level}` |",
            f"| **Culture** | `{culture}` |",
            f"| **Calculated Tables** | `{calc_count}` |",
            f"| **Inherited Tables** | `{inherited_count}` |",
            f"| **Excluded Tables** | `{excluded_count}` |",
        ]

        if calc_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **Calculated Tables**: {calc_count} tables (`source_type = CalculatedTable`) "
                "are computed dynamically in-memory using DAX table expressions (`partition = calculated`)."
            )

        if inherited_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **Inherited Tables**: {inherited_count} inherited tables (`partition = entity`) "
                "are cataloged in the model index, but their individual documentation pages are not generated."
            )

        if excluded_count > 0:
            lines.append("")
            lines.append(
                f"> ℹ️ **Excluded Tables**: {excluded_count} internal system tables "
                "(e.g., `LocalDateTable_*`, `DateTableTemplate_*`) have been excluded from the documentation scope as per configuration."
            )

        return DocSection(
            section_id="tab-details",
            title="Details",
            nav_label="Details",
            content="\n".join(lines),
        )
