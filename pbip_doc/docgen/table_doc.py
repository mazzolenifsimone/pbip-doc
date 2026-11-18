"""
Modular Markdown Document Generator for Data Model Tables.
Follows the unified Section-Driven modular architecture.
Optimized for dual consumption: human readability + AI RAG semantic search.
100% Python Standard Library.
"""

from typing import Dict, Any, List, Optional, Set, Tuple
from .config import DocGenConfig
from .section_engine import DocSection, assemble_markdown_document
from .layout_engine import render_document_markdown
from .utils import (
    format_yaml_frontmatter,
    sanitize_filename,
    join_doc_path,
    clean_project_name,
    filter_local_scope_relationships,
    resolve_upstream_model_references,
    resolve_model_index_url,
)
from .relationship_diagram import normalize_role_key
from ..dax_formatter import format_dax
from ..m_formatter import format_m


class TableDocBuilder:
    """
    Builds modular markdown chapters for a single table in the semantic model.
    """

    def __init__(
        self,
        table_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        project_name: Optional[str] = None,
    ):
        self.table = table_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.project_name = clean_project_name(
            project_name or self.config.project_name or full_model.get("project_name") or full_model.get("model_name")
        )
        self.name = table_data.get("name", "UnnamedTable")
        self.role = table_data.get("role", "UNKNOWN")
        self.classification = table_data.get("classification_reasoning", {})
        self.columns = table_data.get("columns", [])
        self.measures = [
            m for m in full_model.get("measures", []) if m.get("table") == self.name
        ]

        self.snowflake_paths = table_data.get("snowflake_paths", [])

        # Pre-filter Calculated Columns and Power Query Columns
        self.calc_cols: List[Dict[str, Any]] = []
        self.pq_cols: List[Dict[str, Any]] = []
        for col in self.columns:
            origin = col.get("origin")
            is_calc = col.get("is_calculated") or bool(col.get("expression")) or origin == "dax"
            is_pq = origin == "power_query" or bool(col.get("m_expression"))
            if is_calc:
                self.calc_cols.append(col)
            elif is_pq:
                self.pq_cols.append(col)

        scoped_rels = filter_local_scope_relationships(
            self.model.get("relationships", []),
            self.model.get("tables", []),
            self.config,
        )
        self.direct_rels = [
            r for r in scoped_rels
            if r.get("from_table") == self.name or r.get("to_table") == self.name
        ]

    def build_markdown(self) -> str:
        """Assembles all enabled modular sections into a pristine Markdown document according to document layout."""
        frontmatter_str = self._build_frontmatter() if self.config.include_table_yaml_frontmatter else None
        header_block = self._build_header_block()

        registry = {
            "description": self._section_description,
            "dax_formula": self._section_dax_formula,
            "referenced_columns": self._section_referenced_columns,
            "relationship_diagram": self._section_relationship_diagram,
            "data_source_summary": self._section_data_sources,
            "sources": self._section_data_sources,
            "upstream_pipeline": self._section_upstream_pipeline_dependencies,
            "data_dictionary": self._section_data_dictionary,
            "columns": self._section_data_dictionary,
            "calculated_columns": self._section_calculated_columns,
            "relationship_table": self._section_relations,
            "relationships": self._section_relations,
            "measures": self._section_measures,
            "details": self._section_details,
            "power_query_lineage": self._section_power_query_lineage,
            "pq_columns": self._section_pq_columns,
            "rag": self._section_rag,
        }

        return render_document_markdown(
            doc_type="table",
            frontmatter_str=frontmatter_str,
            header_block=header_block,
            registry=registry,
            config=self.config,
        )

    def _legacy_build_markdown(self) -> str:
        """Assembles all enabled modular sections into a pristine Markdown document (deterministic section order)."""
        frontmatter_str = self._build_frontmatter() if self.config.include_table_yaml_frontmatter else None
        header_block = self._build_header_block()

        sections = [
            self._section_description(),
            self._section_dax_formula(),
            self._section_referenced_columns(),
            self._section_data_sources(),
            self._section_upstream_pipeline_dependencies(),
            self._section_data_dictionary(),
            self._section_relations(),
            self._section_calculated_columns(),
            self._section_measures(),
            self._section_power_query_lineage(),
            self._section_pq_columns(),
            self._section_details(),
            self._section_rag(),
        ]

        return assemble_markdown_document(frontmatter_str, header_block, sections)

    def _build_frontmatter(self) -> str:
        """Constructs YAML frontmatter for RAG indexing and cataloging."""
        root_sources = [
            str(s.get("connection_string", s.get("source_type", ""))).replace("\\", "/")
            for s in self.table.get("root_data_sources", [])
            if s.get("connection_string") or s.get("source_type")
        ]

        inc_policy = self.table.get("incremental_refresh_policy")
        has_inc_refresh = bool(inc_policy and inc_policy.get("is_enabled"))

        tags = ["semantic_model", "table", self.role.lower(), sanitize_filename(self.name)]
        if self.role == "FACT":
            tags.extend(["fact_table", "metrics"])
        elif self.role == "DIMENSION":
            tags.extend(["dimension", "attributes"])
        elif self.role == "LOOKUP_OUTRIGGER":
            tags.extend(["outrigger", "snowflake", "lookup"])
        elif self.role == "BRIDGE":
            tags.extend(["bridge_table", "mapping", "junction"])
        elif self.role == "DATE_DIMENSION":
            tags.extend(["date_dimension", "calendar", "time_intelligence"])

        if has_inc_refresh:
            tags.append("incremental_refresh")
            if inc_policy.get("mode") == "hybrid":
                tags.append("hybrid_table")

        connected_dims = [
            d for d in self.table.get("connected_dimensions", [])
            if not self.config.is_table_excluded(d)
        ]

        connected_facts = [
            f for f in self.table.get("connected_facts", [])
            if not self.config.is_table_excluded(f)
        ]

        reachable_lookups = [
            l for l in self.table.get("reachable_lookup_tables", [])
            if not self.config.is_table_excluded(l)
        ]

        if self.project_name:
            tags.append(sanitize_filename(self.project_name))

        frontmatter_data = {
            "title": f"Table: {self.name}",
            "pbip_project": self.project_name,
            "entity_name": self.name,
            "doc_type": "data_model_table",
            "role": self.role,
            "description": self.table.get("description"),
            "confidence_score": self.classification.get("confidence_score", 1.0),
            "columns_count": len(self.columns),
            "measures_count": len(self.measures),
            "has_incremental_refresh": has_inc_refresh,
            "is_inherited": self.table.get("is_inherited", False),
            "out_of_scope": self.table.get("out_of_scope", False),
            "source_type": self.table.get("source_type", "PowerQuery"),
            "root_sources": root_sources,
            "upstream_queries": self.table.get("upstream_queries_chain", []),
            "connected_dimensions": connected_dims,
            "connected_facts": connected_facts,
            "reachable_lookups": reachable_lookups,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_header_block(self) -> str:
        model_url = resolve_model_index_url(self.config, self.project_name, self.config.tables_subdir)
        model_link = f"[{self.project_name}]({model_url})" if self.config.include_markdown_links else f"`{self.project_name}`"
        return "\n".join([
            f"# Table: `{self.name}`",
            "",
            f"**Model**: {model_link} | **Architectural Role**: `{self.role}` | **Columns**: `{len(self.columns)}` | **Associated Measures**: `{len(self.measures)}`",
        ])

    # 1. Description
    def _section_description(self) -> DocSection:
        lines = [
            "## Description",
            "",
        ]

        if self.table.get("description"):
            lines.append(f"> {self.table['description']}")
        else:
            lines.append("*No description provided.*")
        lines.append("")

        if self.table.get("is_inherited"):
            ent_label = self.table.get("inherited_entity_name") or self.name
            if self.table.get("inherited_model_name"):
                src_label = f" (Source Model: `{self.table.get('inherited_model_name')}`)"
            elif self.table.get("inherited_expression_source"):
                src_label = f" (Source: `{self.table.get('inherited_expression_source')}`)"
            else:
                src_label = ""
            ext_url = self.config.resolve_external_table_url(self.table)
            if ext_url and self.config.include_markdown_links:
                ent_display = f"[{ent_label}]({ext_url})"
            else:
                ent_display = f"`{ent_label}`"
            lines.append(f"> ℹ️ **Inherited Entity**: This table is inherited from upstream semantic model entity {ent_display}{src_label}.")
            lines.append("")

        if self.table.get("source_type") == "CalculatedTable":
            lines.append("> 🧮 **DAX Calculated Table**: This table is dynamically computed within the data model using a DAX table expression.")
            lines.append("")

        if self.role == "FACT":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Fact Table**. "
                "It stores quantitative numeric measurements, aggregatable metrics, and transactional events. "
                "It serves as the analytical foundation of the model and is filtered by related dimension tables."
            )
        elif self.role == "DIMENSION":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Dimension Table**. "
                "It contains descriptive attributes, master data, or business entities used to slice, dice, group, "
                "and filter transactional facts."
            )
        elif self.role == "LOOKUP_OUTRIGGER":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Lookup / Outrigger (Snowflake Dimension)**. "
                "It represents a normalized secondary dimension that does not directly filter a fact table, "
                "but connects upstream to one or more dimensions to provide detailed attributes and hierarchies."
            )
        elif self.role == "DATE_DIMENSION":
            lines.append(
                f"The table **`{self.name}`** is classified as a **Date / Calendar Dimension**. "
                "It provides the time dimension structure required for Time Intelligence calculations (YTD, Prior Year, MTD, Rolling periods)."
            )
        else:
            lines.append(f"The table **`{self.name}`** is part of the semantic model as a utility or calculated entity.")

        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content="\n".join(lines),
        )

    # 1b. DAX Formula (for Calculated Tables)
    def _section_dax_formula(self) -> Optional[DocSection]:
        is_calc_group = (
            self.table.get("source_type") == "CalculationGroup"
            or (self.table.get("role") or "").upper() in ("CALCULATION_GROUP", "CALC_GROUP")
        )
        if is_calc_group:
            lines = [
                "## Calculation Group & Lineage",
                "",
                "This entity is a Calculation Group defined within the semantic model, applying dynamic DAX calculation items to evaluate measures across the model rather than ingesting external data via Power Query.",
            ]
            calc_items = self.table.get("calculation_items") or []
            if calc_items:
                lines.append("")
                lines.append(f"### Calculation Items ({len(calc_items)}):")
                for ci in calc_items:
                    ci_name = ci.get("name", "Item") if isinstance(ci, dict) else str(ci)
                    lines.append(f"- **`{ci_name}`**")
            return DocSection(
                section_id="tab-cg",
                title="Calculation Group & Lineage",
                nav_label="Calculation Group",
                content="\n".join(lines),
            )

        is_calc = (
            self.table.get("source_type") == "CalculatedTable"
            or bool(self.table.get("is_calculated"))
            or normalize_role_key(self.table.get("role")) == "CALCULATED_TABLE"
        )
        if not is_calc:
            return None
        if not getattr(self.config, "include_table_dax_formula", True):
            return None

        lines = [
            "## DAX Table Expression",
            "",
            "This table is dynamically computed in-memory within the semantic model using DAX, rather than loaded from an external Power Query data source.",
        ]

        calc_expr = self.table.get("expression")
        if calc_expr:
            lines.append("")
            lines.append("### DAX Table Formula:")
            lines.append("```dax")
            formatted_calc_expr = format_dax(
                calc_expr,
                name=self.name,
                entity_type="calculated_table",
            )
            lines.append(formatted_calc_expr)
            lines.append("```")
        else:
            lines.append("")
            lines.append("> ℹ️ *DAX calculation formula defined at partition level.*")

        return DocSection(
            section_id="tab-dax",
            title="DAX Table Expression",
            nav_label="DAX Formula",
            content="\n".join(lines),
        )

    def get_upstream_model_references(self) -> Dict[str, Any]:
        """
        Resolves and deduplicates upstream DAX references (Tables, Columns, Measures)
        for calculated tables. Delegates to shared docgen/utils helper.
        """
        return resolve_upstream_model_references(self.table, self.model)

    def _format_ref_table_md(self, t_name: str, t_obj: Optional[Dict[str, Any]]) -> str:
        if not t_name:
            return "*Current Table*"
        if t_obj is not None and self.config.is_table_published(t_obj):
            if not self.config.include_markdown_links:
                return f"`{t_name}`"
            clean_t = sanitize_filename(t_name)
            if self.config.base_doc_url:
                target_url = join_doc_path(self.config.base_doc_url, self.config.clean_tables_subdir, f"{clean_t}.md")
            else:
                target_url = f"{clean_t}.md"
            return f"[{t_name}]({target_url})"
        ext_url = self.config.resolve_external_table_url(t_obj) if t_obj else None
        if ext_url and self.config.include_markdown_links:
            return f"[{t_name}]({ext_url}) *(External)*"
        return f"`{t_name}`"

    # 1c. Referenced Columns / Upstream Model References (for Calculated Tables)
    def _section_referenced_columns(self) -> Optional[DocSection]:
        is_calc = (
            self.table.get("source_type") == "CalculatedTable"
            or bool(self.table.get("is_calculated"))
            or normalize_role_key(self.table.get("role")) == "CALCULATED_TABLE"
        )
        if not is_calc:
            return None
        if not getattr(self.config, "include_table_referenced_columns", True):
            return None

        refs = self.get_upstream_model_references()
        standalone_tables = refs["standalone_tables"]
        ref_cols = refs["columns"]
        ref_measures = refs["measures"]

        if not (standalone_tables or ref_cols or ref_measures):
            return None

        lines = [
            "## Upstream Model References",
            "",
            "The DAX expression defining this calculated table references the following model entities:",
            "",
            "| Entity Type | Referenced Entity / Table | Column / Scope |",
            "| :--- | :--- | :--- |",
        ]

        for t_entry in standalone_tables:
            t_cell = self._format_ref_table_md(t_entry["name"], t_entry["table_obj"])
            lines.append(f"| Table | {t_cell} | — |")

        for c_entry in ref_cols:
            t_cell = self._format_ref_table_md(c_entry["table"], c_entry["table_obj"])
            c_name = c_entry["column"]
            lines.append(f"| Column | {t_cell} | `[{c_name}]` |")

        meas_sub = self.config.clean_measures_subdir
        model_tables = self.model.get("tables", []) or []
        for m_entry in ref_measures:
            m_name = m_entry["name"]
            m_home_tbl = m_entry["home_table"]
            m_obj = m_entry["measure_obj"]
            home_tbl_obj = m_entry["home_table_obj"]

            if m_obj is not None and m_home_tbl and self.config.is_measure_published(m_obj):
                clean_home_tbl = sanitize_filename(m_home_tbl)
                clean_m = sanitize_filename(m_name)
                if self.config.include_markdown_links:
                    if self.config.base_doc_url:
                        m_url = join_doc_path(self.config.base_doc_url, meas_sub, clean_home_tbl, f"{clean_m}.md") if meas_sub else join_doc_path(self.config.base_doc_url, clean_home_tbl, f"{clean_m}.md")
                    else:
                        m_url = f"../{meas_sub}/{clean_home_tbl}/{clean_m}.md" if meas_sub else f"../{clean_home_tbl}/{clean_m}.md"
                    m_cell = f"[{m_name}]({m_url})"
                else:
                    m_cell = f"`{m_name}`"
                scope_cell = self._format_ref_table_md(m_home_tbl, home_tbl_obj)
            else:
                ext_m_url = self.config.resolve_external_measure_url(m_obj, model_tables) if m_obj else None
                if ext_m_url and self.config.include_markdown_links:
                    m_cell = f"[{m_name}]({ext_m_url}) *(External)*"
                else:
                    m_cell = f"`{m_name}`"
                scope_cell = self._format_ref_table_md(m_home_tbl, home_tbl_obj) if m_home_tbl else "—"

            lines.append(f"| Measure | {m_cell} | {scope_cell} |")

        return DocSection(
            section_id="tab-ref-cols",
            title="Upstream Model References",
            nav_label="Model References",
            content="\n".join(lines),
        )

    def get_data_sources_summary(self) -> List[Dict[str, str]]:
        """
        Extracts normalized summary data for all data sources feeding this table.
        Single source of truth used for both Markdown and HTML generation.
        """
        sources = []
        root_sources = self.table.get("root_data_sources", [])
        upstream = self.table.get("upstream_queries_chain", [])
        pipe_label = " ➔ ".join(upstream + [self.name]) if upstream else "Direct Ingestion"

        if root_sources:
            for s in root_sources:
                if isinstance(s, dict):
                    stype = s.get("source_type") or "GENERIC"
                    conn = str(s.get("connection_string") or s.get("endpoint_or_path") or "—").replace("\\", "/")
                    srv = s.get("server") or "—"
                    db = s.get("database") or "—"
                    sch = s.get("schema") or "—"
                    itm = s.get("item") or s.get("endpoint_or_path") or "—"
                else:
                    stype = getattr(s, "source_type", "GENERIC")
                    conn = str(getattr(s, "connection_string", None) or getattr(s, "endpoint_or_path", None) or "—").replace("\\", "/")
                    srv = getattr(s, "server", None) or "—"
                    db = getattr(s, "database", None) or "—"
                    sch = getattr(s, "schema", None) or "—"
                    itm = getattr(s, "item", None) or getattr(s, "endpoint_or_path", None) or "—"
                sources.append({
                    "source_type": stype,
                    "connection": conn,
                    "server": srv,
                    "database": db,
                    "schema": sch,
                    "item": itm,
                    "pipeline": pipe_label,
                    "upstream_chain": list(upstream),
                })
        elif self.table.get("source_type") == "CalculatedTable":
            ref_t = self.table.get("referenced_tables", [])
            ref_label = f"References: {', '.join(ref_t)}" if ref_t else "—"
            sources.append({
                "source_type": "DAX Calculated Table",
                "connection": "Dynamic in-memory DAX expression",
                "server": "—",
                "database": ref_label,
                "schema": "—",
                "item": self.name,
                "pipeline": "Internal DAX Engine",
                "upstream_chain": [],
            })
        elif self.table.get("source_type") == "CalculationGroup":
            sources.append({
                "source_type": "Calculation Group",
                "connection": "In-memory DAX calculation items",
                "server": "—",
                "database": "—",
                "schema": "—",
                "item": self.name,
                "pipeline": "Internal DAX Engine",
                "upstream_chain": [],
            })
        elif self.table.get("is_inherited"):
            sources.append({
                "source_type": "Inherited Entity",
                "connection": self.table.get("inherited_model_name") or self.table.get("inherited_expression_source") or "Remote Semantic Model",
                "server": "—",
                "database": self.table.get("inherited_model_name") or "—",
                "schema": "—",
                "item": self.table.get("inherited_entity_name") or self.name,
                "pipeline": "Direct Lake / AS Composite",
                "upstream_chain": list(upstream),
            })
        else:
            lineage = self.table.get("power_query_lineage") or {}
            if isinstance(lineage, dict) and lineage.get("is_inline_table"):
                stype = "MANUAL_INLINE"
                conn = "In-Memory Inline Table (#table)"
            else:
                stype = self.table.get("source_type") or "PowerQuery"
                conn = "Power Query M Script / Partition"
            sources.append({
                "source_type": stype,
                "connection": conn,
                "server": "—",
                "database": "—",
                "schema": "—",
                "item": self.name,
                "pipeline": pipe_label,
                "upstream_chain": list(upstream),
            })
        return sources

    def get_upstream_pipeline_dependencies(self) -> List[Dict[str, Any]]:
        """
        Gathers structured metadata for all upstream Power Query M expressions,
        staging queries, and parameters feeding this table.
        """
        lineage_node = self.table.get("power_query_lineage") or {}
        raw_upstream = list(self.table.get("upstream_queries_chain", []))
        if isinstance(lineage_node, dict):
            raw_upstream.extend(lineage_node.get("all_upstream_queries", []))
            raw_upstream.extend(lineage_node.get("direct_dependencies", []))
            for st in lineage_node.get("steps", []):
                refs = st.get("referenced_queries", []) if isinstance(st, dict) else getattr(st, "referenced_queries", [])
                raw_upstream.extend(refs)

        upstream_names = []
        for name in raw_upstream:
            if name and name != self.name and name not in upstream_names:
                upstream_names.append(name)

        if not upstream_names:
            return []

        all_exprs = self.model.get("expressions", []) + self.model.get("shared_queries", [])
        expr_map = {}
        for e in all_exprs:
            q_name = e.get("query_name") or e.get("name")
            if q_name:
                expr_map[q_name] = e

        steps = lineage_node.get("steps", []) if isinstance(lineage_node, dict) else []

        deps_list = []
        for name in sorted(upstream_names):
            clean_name = sanitize_filename(name)
            e_data = expr_map.get(name, {})

            is_param = (
                e_data.get("expression_kind") == "parameter"
                or "IsParameterQuery" in e_data.get("full_m_expression", "")
                or bool(e_data.get("parameter_value"))
            )
            is_func = e_data.get("is_m_function") or e_data.get("expression_kind") == "function"
            is_inline = e_data.get("is_inline_table")

            if is_param:
                role = "Query Parameter M"
                role_badge_class = "badge-accent"
            elif is_func:
                role = "Custom Function M"
                role_badge_class = "badge-primary"
            elif is_inline:
                role = "Inline Table (#table)"
                role_badge_class = "badge-dim"
            elif e_data.get("is_staging", True):
                role = "Staging Query"
                role_badge_class = "badge-dim"
            else:
                role = "Shared Query / Pipeline"
                role_badge_class = "badge-dim"

            if is_param:
                pval = e_data.get("parameter_value") or ""
                ptype = e_data.get("parameter_type") or "Any"
                val_desc = f"`{pval}` ({ptype})" if pval else f"Dynamic / Environment ({ptype})"
            elif e_data.get("root_sources"):
                src = e_data["root_sources"][0]
                val_desc = f"{src.get('source_type', 'Source')}: {src.get('connection_string') or src.get('server') or '—'}"
            elif e_data.get("description"):
                val_desc = e_data.get("description")
            else:
                val_desc = "Transformed Tabular Stream"

            consuming_steps = []
            for idx, st in enumerate(steps, 1):
                s_name = st.get("step_name") if isinstance(st, dict) else getattr(st, "step_name", f"Step_{idx}")
                refs = st.get("referenced_queries", []) if isinstance(st, dict) else getattr(st, "referenced_queries", [])
                if name in refs:
                    consuming_steps.append(f"#{idx} {s_name}")

            consumed_in = ", ".join(consuming_steps) if consuming_steps else "Transitive Dependency (via upstream staging query)"

            deps_list.append({
                "name": name,
                "clean_name": clean_name,
                "role": role,
                "role_badge_class": role_badge_class,
                "value_details": val_desc,
                "consumed_in": consumed_in,
            })

        return deps_list

    # 2. Data Source Summary
    def _section_data_sources(self) -> Optional[DocSection]:
        sources = self.get_data_sources_summary()
        if not sources:
            return None

        md_lines = [
            "## Data Source Summary",
            "",
            "| Source Type | Connection / Details | Server | Database | Schema | Table / Object | Data Pipeline / Staging |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]

        clean_tbl = sanitize_filename(self.name)
        expr_sub = self.config.clean_expressions_subdir
        is_etl_loaded = (
            self.table.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (self.table.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
            and not self.table.get("is_inherited")
            and (
                self.table.get("power_query_expression")
                or self.table.get("power_query_lineage")
                or self.table.get("m_code")
                or self.table.get("source_type") == "PowerQuery"
            )
        )

        for s in sources:
            stype = f"`{s['source_type']}`"
            conn = f"`{s['connection']}`" if s["connection"] != "—" else "—"
            srv = f"`{s['server']}`" if s["server"] != "—" else "—"
            db = f"`{s['database']}`" if s["database"] != "—" else "—"
            sch = f"`{s.get('schema', '—')}`" if s.get("schema") and s["schema"] != "—" else "—"
            itm = f"`{s.get('item', '—')}`" if s.get("item") and s["item"] != "—" else "—"
            target_url = join_doc_path(self.config.base_doc_url, expr_sub, f"{clean_tbl}.md") if self.config.base_doc_url else f"../{expr_sub}/{clean_tbl}.md"
            tbl_pipe_label = (
                f"[`{self.name}`]({target_url})"
                if (is_etl_loaded and getattr(self.config, "include_expression_docs", True) and self.config.include_markdown_links)
                else f"`{self.name}`"
            )

            if self.config.include_markdown_links and s.get("upstream_chain"):
                pipe_parts = []
                for q in s["upstream_chain"]:
                    clean_q = sanitize_filename(q)
                    q_target_url = join_doc_path(self.config.base_doc_url, expr_sub, f"{clean_q}.md") if self.config.base_doc_url else f"../{expr_sub}/{clean_q}.md"
                    pipe_parts.append(f"[{q}]({q_target_url})")
                pipe_parts.append(tbl_pipe_label)
                pipe = " ➔ ".join(pipe_parts)
            elif is_etl_loaded and getattr(self.config, "include_expression_docs", True) and self.config.include_markdown_links:
                pipe_raw = s.get("pipeline") or "Direct Ingestion"
                if pipe_raw == "Direct Ingestion":
                    pipe = f"Direct Ingestion ➔ {tbl_pipe_label}"
                elif f"`{self.name}`" in pipe_raw:
                    pipe = pipe_raw.replace(f"`{self.name}`", tbl_pipe_label)
                else:
                    pipe = tbl_pipe_label
            else:
                pipe = s["pipeline"]
            md_lines.append(f"| {stype} | {conn} | {srv} | {db} | {sch} | {itm} | {pipe} |")

        return DocSection(
            section_id="tab-sources",
            title="Data Source Summary",
            nav_label="Data Source Summary",
            content="\n".join(md_lines),
        )

    # 2b. Upstream Pipeline & Expression Dependencies
    def _section_upstream_pipeline_dependencies(self) -> Optional[DocSection]:
        deps = self.get_upstream_pipeline_dependencies()
        if not deps:
            return None

        md_lines = [
            f"## Upstream Pipeline & Expression Dependencies ({len(deps)})",
            "",
            "The following Power Query expressions, shared staging queries, and parameters feed this table:",
            "",
            "| Upstream Query / Parameter | Pipeline Role | Current Value / Details | Consumed in Step(s) |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for d in deps:
            clean_name = d["clean_name"]
            if self.config.base_doc_url:
                target_url = join_doc_path(self.config.base_doc_url, self.config.clean_expressions_subdir, f"{clean_name}.md")
            else:
                target_url = f"../{self.config.clean_expressions_subdir}/{clean_name}.md"
            q_link = f"[{d['name']}]({target_url})" if self.config.include_markdown_links else f"`{d['name']}`"
            md_lines.append(f"| {q_link} | `{d['role']}` | {d['value_details']} | {d['consumed_in']} |")

        return DocSection(
            section_id="tab-upstream-deps",
            title=f"Upstream Pipeline Dependencies ({len(deps)})",
            nav_label=f"Upstream Pipeline ({len(deps)})",
            content="\n".join(md_lines),
        )

    # 3. Data Dictionary
    def _section_data_dictionary(self) -> Optional[DocSection]:
        if not self.config.include_table_columns_dictionary:
            return None

        lines = [
            f"## Columns Data Dictionary ({len(self.columns)} fields)",
            "",
            "| Column Name | Data Type | Type / Origin | Format | Description |",
            "| :--- | :--- | :---: | :--- | :--- |",
        ]

        def _clean_cell(text: Optional[str]) -> str:
            if not text:
                return "—"
            s = str(text).replace("|", "\\|")
            s = " ".join(s.split())
            return s or "—"

        for col in self.columns:
            name = f"`{col.get('name')}`"
            dtype = f"`{col.get('data_type')}`"
            origin = col.get("origin")
            is_calc = col.get("is_calculated") or bool(col.get("expression")) or origin == "dax"
            is_pq = origin == "power_query" or bool(col.get("m_expression"))

            if is_calc:
                col_type = "🧮 DAX Calc"
            elif is_pq:
                op = col.get("m_operation") or "PQ Calc"
                if "Merged" in op:
                    col_type = "⚡ PQ Merge"
                else:
                    col_type = "⚡ PQ Calc"
            elif col.get("is_key"):
                col_type = "🔑 Key"
            else:
                col_type = "📥 Source"

            fmt = f"`{col.get('format_string')}`" if col.get("format_string") else "—"

            desc_parts = []
            if col.get("description"):
                desc_parts.append(_clean_cell(col.get("description")))
            if is_calc:
                desc_parts.append("*(DAX formula below)*")
            elif is_pq:
                op_lbl = col.get("m_operation") or "Power Query"
                desc_parts.append(f"*(PQ: {op_lbl})*")
            desc = " ".join(desc_parts) or "—"

            lines.append(f"| {name} | {dtype} | {col_type} | {fmt} | {desc} |")

        return DocSection(
            section_id="tab-cols",
            title="Data Dictionary",
            nav_label=f"Data Dictionary ({len(self.columns)})",
            content="\n".join(lines),
        )

    def _section_relationship_diagram(self) -> Optional[DocSection]:
        if not self.config.include_relationship_diagrams:
            return None
        if not self.direct_rels and normalize_role_key(self.table.get("role")) != "FACT":
            return None

        diag_url = self.config.resolve_table_diagram_svg_url(self.name)
        is_fact = (normalize_role_key(self.table.get("role")) == "FACT")
        diagram_title = "Star Cluster Relationship Diagram" if is_fact else "1-Hop Relationship Diagram"
        lines = [
            f"## {diagram_title}",
            "",
            f"![{self.name} - {diagram_title}]({diag_url})",
        ]

        return DocSection(
            section_id="relationship_diagram",
            title=diagram_title,
            nav_label="Diagram",
            content="\n".join(lines),
        )

    # 4. Relations
    def _section_relations(self) -> Optional[DocSection]:
        if not self.config.include_table_topology_section:
            return None

        lines = ["## Model Topology & Relationships"]

        connected_dims = [
            dim for dim in self.table.get("connected_dimensions", [])
            if not self.config.is_table_excluded(dim)
        ]

        if connected_dims:
            lines.append("### Directly Connected Dimensions:")
            for dim in connected_dims:
                dim_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == dim), None)
                is_pub = self.config.is_table_published(dim_tbl) if dim_tbl else True
                if is_pub and self.config.include_markdown_links:
                    clean_dim = sanitize_filename(dim)
                    target_url = join_doc_path(self.config.base_doc_url, self.config.clean_tables_subdir, f"{clean_dim}.md") if self.config.base_doc_url else f"{clean_dim}.md"
                    link = f"[{dim}]({target_url})"
                else:
                    ext_url = self.config.resolve_external_table_url(dim_tbl) if dim_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        link = f"[{dim}]({ext_url}) *(Inherited Entity)*"
                    else:
                        badge = " *(Inherited Entity)*" if (dim_tbl and dim_tbl.get("is_inherited")) else ""
                        link = f"`{dim}`{badge}"
                lines.append(f"- {link} (1:N Relationship)")

        connected_facts = [
            fact for fact in self.table.get("connected_facts", [])
            if not self.config.is_table_excluded(fact)
        ]

        if connected_facts:
            lines.append("### Directly Filtered Fact Tables:")
            for fact in connected_facts:
                fact_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == fact), None)
                is_pub = self.config.is_table_published(fact_tbl) if fact_tbl else True
                if is_pub and self.config.include_markdown_links:
                    clean_fact = sanitize_filename(fact)
                    target_url = join_doc_path(self.config.base_doc_url, self.config.clean_tables_subdir, f"{clean_fact}.md") if self.config.base_doc_url else f"{clean_fact}.md"
                    link = f"[{fact}]({target_url})"
                else:
                    ext_url = self.config.resolve_external_table_url(fact_tbl) if fact_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        link = f"[{fact}]({ext_url}) *(Inherited Entity)*"
                    else:
                        badge = " *(Inherited Entity)*" if (fact_tbl and fact_tbl.get("is_inherited")) else ""
                        link = f"`{fact}`{badge}"
                lines.append(f"- {link} (1:N Relationship)")

        if self.config.include_table_snowflake_paths and self.snowflake_paths:
            valid_paths = [
                p for p in self.snowflake_paths
                if not any(self.config.is_table_excluded(n) for n in p.get("path", []))
            ]

            if valid_paths:
                lines.append("")
                lines.append("### Transitive Snowflake Hierarchy (Reachable Lookups):")
                lines.append(
                    "The following lookup/outrigger tables can reach this Fact table through intermediate dimensions:"
                )
                for path_info in valid_paths:
                    path_nodes = path_info.get("path", [])
                    hops = path_info.get("hops", 1)
                    join_keys = path_info.get("join_keys", [])

                    path_str = " ➔ ".join(f"`{n}`" for n in path_nodes)
                    lines.append(f"- **Path ({hops} hops)**: {path_str}")
                    if join_keys:
                        key_descs = [f"`{jk.get('from')}` ═▶ `{jk.get('to')}`" for jk in join_keys]
                        lines.append(f"  - *Join Keys*: {', '.join(key_descs)}")

        if self.direct_rels:
            lines.append("")
            lines.append("### Active Direct Relationships:")
            lines.append("| Relationship ID | From (Many) | To (One) | Cardinality | Cross-Filtering | State |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for r in self.direct_rels:
                status = "Active" if r.get("is_active", True) else "Inactive"
                from_field = f"`{r.get('from_table')}`[{r.get('from_column')}]"
                to_field = f"`{r.get('to_table')}`[{r.get('to_column')}]"
                lines.append(
                    f"| `{r.get('id')}` | {from_field} | {to_field} | {r.get('cardinality')} | {r.get('cross_filtering_behavior')} | {status} |"
                )

        return DocSection(
            section_id="tab-rels",
            title="Relations",
            nav_label=f"Relations ({len(self.direct_rels)})",
            content="\n".join(lines),
        )

    # 5. Calculated Columns
    def _section_calculated_columns(self) -> Optional[DocSection]:
        if not self.calc_cols:
            return None

        lines = [
            f"## Calculated Columns ({len(self.calc_cols)})",
            "",
            "The following columns are computed via DAX expressions in the model:",
            "",
        ]

        for cc in self.calc_cols:
            c_name = cc.get("name")
            c_type = cc.get("data_type", "string")
            c_fmt = cc.get("format_string") or "Default"
            c_desc = cc.get("description")
            c_expr = cc.get("expression") or ""
            lines.append(f"### Calculated Column: `{c_name}`")
            lines.append(f"- **Data Type**: `{c_type}`")
            lines.append(f"- **Format**: `{c_fmt}`")
            if c_desc:
                lines.append(f"- **Description**: {c_desc}")
            lines.append("- **DAX Formula**:")
            lines.append("```dax")
            formatted_c_expr = format_dax(
                c_expr,
                name=c_name,
                entity_type="calculated_column",
                table_name=self.name,
            )
            lines.append(formatted_c_expr)
            lines.append("```")
            lines.append("")

        return DocSection(
            section_id="tab-calc-cols",
            title="Calculated Columns",
            nav_label=f"Calculated Columns ({len(self.calc_cols)})",
            content="\n".join(lines).strip(),
        )

    # 6. Measures
    def _section_measures(self) -> Optional[DocSection]:
        if not (self.config.include_table_measures_list and self.measures):
            return None

        lines = [
            f"## Associated DAX Measures ({len(self.measures)})",
            "",
            "The following calculated measures are defined within this table:",
            "",
            "| Measure | DAG Depth | Direct Dependencies | Format | Description |",
            "| :--- | :---: | :--- | :--- | :--- |",
        ]

        clean_tbl = sanitize_filename(self.name)
        meas_sub = self.config.clean_measures_subdir
        for m in sorted(self.measures, key=lambda x: (x.get("calculation_depth", 0), x.get("name", ""))):
            m_name = m.get("name")
            sanitized = sanitize_filename(m_name)
            is_m_pub = self.config.is_measure_published(m)
            if is_m_pub and self.config.include_markdown_links:
                if self.config.base_doc_url:
                    meas_path = join_doc_path(self.config.base_doc_url, meas_sub, clean_tbl, f"{sanitized}.md") if meas_sub else join_doc_path(self.config.base_doc_url, clean_tbl, f"{sanitized}.md")
                else:
                    meas_path = f"../{meas_sub}/{clean_tbl}/{sanitized}.md" if meas_sub else f"../{clean_tbl}/{sanitized}.md"
                link = f"[{m_name}]({meas_path})"
            elif is_m_pub:
                link = f"`[{m_name}]`"
            else:
                ext_url = self.config.resolve_external_measure_url(m, self.model.get("tables", []))
                if ext_url and self.config.include_markdown_links:
                    link = f"[{m_name}]({ext_url}) *(External)*"
                else:
                    link = f"`[{m_name}]` *(External)*"
            depth = f"Depth {m.get('calculation_depth', 0)}"
            deps = ", ".join(f"`[{d}]`" for d in m.get("direct_measure_dependencies", [])) or "— (Base Measure)"
            fmt = f"`{m.get('format_string')}`" if m.get("format_string") else "—"
            desc = m.get("description") or "—"

            lines.append(f"| {link} | {depth} | {deps} | {fmt} | {desc} |")

        return DocSection(
            section_id="tab-meas",
            title="Measures",
            nav_label=f"Measures ({len(self.measures)})",
            content="\n".join(lines),
        )

    # 7. Power Query Lineage
    def _section_power_query_lineage(self) -> Optional[DocSection]:
        if not self.config.include_table_lineage_section:
            return None

        if self.table.get("source_type") == "CalculatedTable":
            return self._section_dax_formula()

        if self.table.get("source_type") == "CalculationGroup" or (self.table.get("role") or "").upper() in ("CALCULATION_GROUP", "CALC_GROUP"):
            lines = [
                "## Calculation Group & Lineage",
                "",
                "This entity is a Calculation Group defined within the semantic model, applying dynamic DAX calculation items to evaluate measures across the model rather than ingesting external data via Power Query.",
            ]

            calc_items = self.table.get("calculation_items") or []
            if calc_items:
                lines.append("")
                lines.append(f"### Calculation Items ({len(calc_items)}):")
                for ci in calc_items:
                    ci_name = ci.get("name", "Item") if isinstance(ci, dict) else str(ci)
                    lines.append(f"- **`{ci_name}`**")
            return DocSection(
                section_id="tab-m",
                title="Lineage & Calculation Items",
                nav_label="Lineage",
                content="\n".join(lines),
            )

        lineage_node = self.table.get("power_query_lineage")
        raw_m = (
            (lineage_node.get("full_m_expression") if isinstance(lineage_node, dict) else None)
            or self.table.get("power_query_expression")
            or self.table.get("m_code")
            or ""
        )
        has_m_pipeline = (
            self.table.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (self.table.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
            and bool(raw_m or (isinstance(lineage_node, dict) and (lineage_node.get("steps") or lineage_node.get("full_m_expression"))))
        )

        clean_tbl = sanitize_filename(self.name)
        lines = [
            "## Power Query Lineage & Physical Sources",
            "",
        ]

        if has_m_pipeline and self.config.include_expression_docs:
            df_link = f"[`{self.name}`](../{self.config.clean_expressions_subdir}/{clean_tbl}.md)" if self.config.include_markdown_links else f"`{self.name}`"
            lines.append(f"> 🔄 **ETL Query**: View the complete Power Query M transformation pipeline, step-by-step diagnostics, and parameters in {df_link}.")
            lines.append("")
        elif not has_m_pipeline:
            src_type_desc = self.table.get("source_type") or "internal semantic model engine"
            lines.append(f"> ℹ️ *This entity is defined via {src_type_desc} without a dedicated Power Query M dataflow transformation pipeline.*")
            lines.append("")

        lines.append("This section traces data lineage from the original physical data source to table ingestion.")

        root_sources = self.table.get("root_data_sources", [])
        if root_sources:
            lines.append("")
            lines.append("### Physical Data Sources of Origin:")
            for s in root_sources:
                stype = s.get("source_type", "GENERIC")
                conn = str(s.get("connection_string", "N/A")).replace("\\", "/")
                server = s.get("server")
                db = s.get("database")
                desc = f"- **`[{stype}]`** `{conn}`"
                if server and db:
                    desc += f" (Server: `{server}`, Database: `{db}`)"
                lines.append(desc)

        upstream = self.table.get("upstream_queries_chain", [])
        if upstream:
            lines.append("")
            lines.append("### Staging Query Chain:")
            chain = " ➔ ".join(f"`{q}`" for q in upstream + [self.name])
            lines.append(f"{chain}")

        lineage_node = self.table.get("power_query_lineage")

        if lineage_node and lineage_node.get("is_inline_table") and lineage_node.get("inline_table_markdown"):
            lines.append("")
            lines.append("### In-Memory Inline Table Data (`#table`):")
            lines.append(lineage_node["inline_table_markdown"])

        if lineage_node and lineage_node.get("steps"):
            steps = lineage_node.get("steps", [])
            known_expr_names = {e.get("query_name") for e in self.model.get("expressions", []) + self.model.get("shared_queries", []) if e.get("query_name")}
            lines.append("")
            lines.append(f"### Power Query Transformation Steps ({len(steps)} steps):")
            lines.append("| # & Step Name | Operation | Transformed Column / Scope | Expression Preview / Details | Referenced Queries |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for idx, st in enumerate(steps, 1):
                s_name = st.get("step_name", f"Step_{idx}") if isinstance(st, dict) else getattr(st, "step_name", f"Step_{idx}")
                op = st.get("operation", "Transform") if isinstance(st, dict) else getattr(st, "operation", "Transform")
                col_scope = st.get("transformed_column") if isinstance(st, dict) else getattr(st, "transformed_column", None)
                raw_code = st.get("raw_m_code") if isinstance(st, dict) else getattr(st, "raw_m_code", None)
                details = st.get("details") if isinstance(st, dict) else getattr(st, "details", None)
                expr_preview = details or raw_code or "—"
                if len(expr_preview) > 120:
                    expr_preview = expr_preview[:117] + "..."
                expr_preview_clean = expr_preview.replace("\n", " ").replace("|", "\\|")

                refs_raw = st.get("referenced_queries", []) if isinstance(st, dict) else getattr(st, "referenced_queries", [])
                ref_links = []
                for r in refs_raw:
                    if self.config.include_markdown_links and r in known_expr_names:
                        clean_r = sanitize_filename(r)
                        target_url = join_doc_path(self.config.base_doc_url, self.config.clean_expressions_subdir, f"{clean_r}.md") if self.config.base_doc_url else f"../{self.config.clean_expressions_subdir}/{clean_r}.md"
                        ref_links.append(f"[{r}]({target_url})")
                    else:
                        ref_links.append(f"`{r}`")
                refs_display = ", ".join(ref_links) if ref_links else "—"
                col_display = f"`{col_scope}`" if col_scope else "—"

                lines.append(f"| `#{idx} {s_name}` | {op} | {col_display} | `{expr_preview_clean}` | {refs_display} |")

        if lineage_node and lineage_node.get("merges"):
            merges = lineage_node.get("merges", [])
            known_expr_names = {e.get("query_name") for e in self.model.get("expressions", []) + self.model.get("shared_queries", []) if e.get("query_name")}
            lines.append("")
            lines.append(f"### Power Query Table Merges / Joins ({len(merges)}):")
            lines.append("| Step | Joined Query | Join Type | Join Keys | Expanded Columns |")
            lines.append("| :--- | :--- | :--- | :--- | :--- |")
            for m in merges:
                s_name = m.get("step_name", "Merge") if isinstance(m, dict) else getattr(m, "step_name", "Merge")
                j_query_raw = m.get("joined_query") if isinstance(m, dict) else getattr(m, "joined_query", "")
                if self.config.include_markdown_links and j_query_raw in known_expr_names:
                    clean_j = sanitize_filename(j_query_raw)
                    target_url = join_doc_path(self.config.base_doc_url, self.config.clean_expressions_subdir, f"{clean_j}.md") if self.config.base_doc_url else f"../{self.config.clean_expressions_subdir}/{clean_j}.md"
                    j_query = f"[{j_query_raw}]({target_url})"
                else:
                    j_query = f"`{j_query_raw}`"
                j_kind = m.get("join_kind", "LeftOuter") if isinstance(m, dict) else getattr(m, "join_kind", "LeftOuter")
                l_keys = ", ".join(m.get("left_keys", []) if isinstance(m, dict) else getattr(m, "left_keys", [])) or "—"
                r_keys = ", ".join(m.get("right_keys", []) if isinstance(m, dict) else getattr(m, "right_keys", [])) or "—"
                if j_kind == "CrossJoin":
                    keys_str = "*(Cartesian Product)*"
                else:
                    keys_str = f"`[{l_keys}]` ⟷ `[{r_keys}]`"
                exp_cols = ", ".join(f"`{c}`" for c in (m.get("expanded_columns", []) if isinstance(m, dict) else getattr(m, "expanded_columns", []))) or "—"
                lines.append(f"| `{s_name}` | {j_query} | `{j_kind}` | {keys_str} | {exp_cols} |")

        if self.config.include_table_m_code and lineage_node and lineage_node.get("full_m_expression"):
            raw_m = lineage_node["full_m_expression"]
            formatted_m = format_m(raw_m)
            lines.append("")
            lines.append("### Full Power Query M Expression:")
            lines.append("```powerquery")
            lines.append(formatted_m)
            lines.append("```")

        return DocSection(
            section_id="tab-m",
            title="Power Query Lineage",
            nav_label="Power Query Lineage",
            content="\n".join(lines),
        )

    # 8. Power Query Calculated and Transformed Columns
    def _section_pq_columns(self) -> Optional[DocSection]:
        if not self.pq_cols:
            return None

        lines = [
            f"## Power Query Calculated & Transformed Columns ({len(self.pq_cols)})",
            "",
            "The following columns are derived or computed in Power Query (M) before loading into the model:",
            "",
            "| Column | Operation | Step Name | Source / Details |",
            "| :--- | :--- | :--- | :--- |",
        ]

        for pqc in self.pq_cols:
            c_name = f"`{pqc.get('name')}`"
            c_op = pqc.get("m_operation") or "Transformation"
            c_step = f"`{pqc.get('m_step_name')}`" if pqc.get("m_step_name") else "—"
            c_details = []
            if pqc.get("m_source_table"):
                c_details.append(f"Source: `{pqc.get('m_source_table')}`")
            if pqc.get("source_column") and pqc.get("source_column") != pqc.get("name"):
                c_details.append(f"Original: `{pqc.get('source_column')}`")
            if pqc.get("m_expression"):
                c_details.append(f"Formula: `{pqc.get('m_expression')}`")
            details_str = " | ".join(c_details) if c_details else "—"
            lines.append(f"| {c_name} | {c_op} | {c_step} | {details_str} |")

        custom_m_cols = [c for c in self.pq_cols if c.get("m_expression") and c.get("m_operation") == "Calculated Column"]
        if custom_m_cols:
            lines.append("")
            lines.append("### Power Query Custom Column Expressions:")
            lines.append("")
            for cc in custom_m_cols:
                lines.append(f"#### Column: `{cc.get('name')}`")
                if cc.get("m_step_name"):
                    lines.append(f"- **Step**: `{cc.get('m_step_name')}`")
                lines.append("- **M Expression**:")
                lines.append("```powerquery")
                lines.append(cc.get("m_expression", ""))
                lines.append("```")
                lines.append("")

        return DocSection(
            section_id="tab-pq-cols",
            title="Power Query Calculated and Transformed Columns",
            nav_label=f"Power Query Columns ({len(self.pq_cols)})",
            content="\n".join(lines).strip(),
        )

    # 9. Details (Star Schema Classification Analysis + Incremental Refresh Policy)
    def _section_details(self) -> DocSection:
        lines = [
            "## Details",
            "",
            "### Star Schema Classification Analysis",
            "",
            f"- **Assigned Role**: `{self.role}` (Confidence: `{self.classification.get('confidence_score', 1.0):.0%}`)",
        ]

        reasons = self.classification.get("criteria_matched", [])
        if reasons:
            lines.append("- **Detected Classification Criteria**:")
            for r in reasons:
                lines.append(f"  - {r}")

        if self.config.include_table_incremental_refresh:
            lines.append("")
            lines.append(self._build_incremental_refresh_chapter())

        return DocSection(
            section_id="tab-tech",
            title="Details",
            nav_label="Details",
            content="\n".join(lines),
        )

    def _build_incremental_refresh_chapter(self) -> str:
        """Incremental Refresh Policy configuration and details."""
        policy = self.table.get("incremental_refresh_policy")
        is_enabled = bool(policy and policy.get("is_enabled"))

        lines = ["### Incremental Refresh Policy", ""]

        if not is_enabled:
            if self.table.get("source_type") == "CalculatedTable":
                lines.extend([
                    "> ℹ️ **In-Memory Calculated Table**: This table is computed dynamically in-memory via DAX. "
                    "Incremental refresh policies do not apply to calculated tables."
                ])
            else:
                lines.extend([
                    "> ℹ️ **No Incremental Refresh Configured**: This table is loaded via standard full refresh. "
                    "All data is reprocessed during scheduled dataset refreshes without partition-level rolling windows."
                ])
            return "\n".join(lines)

        mode = policy.get("mode", "import")
        policy_type = policy.get("policy_type", "basic")
        rolling_periods = policy.get("rolling_window_periods")
        rolling_gran = policy.get("rolling_window_granularity")
        inc_periods = policy.get("incremental_periods")
        inc_gran = policy.get("incremental_granularity")
        polling_expr = policy.get("polling_expression")
        source_expr = policy.get("source_expression")

        rolling_desc = f"{rolling_periods} {rolling_gran.capitalize() if rolling_gran else ''}s" if rolling_periods is not None else "Not specified"
        inc_desc = f"{inc_periods} {inc_gran.capitalize() if inc_gran else ''}s" if inc_periods is not None else "Not specified"
        mode_badge = "⚡ Hybrid (Import + DirectQuery)" if mode == "hybrid" else f"`{mode}` (Import)"

        lines.extend([
            f"The table **`{self.name}`** utilizes an **Incremental Refresh Policy** to partition data, "
            "optimizing refresh duration and resource consumption in Power BI / Microsoft Fabric.",
            "",
            "#### Policy Configuration Parameters:",
            "",
            "| Parameter | Configuration | Description |",
            "| :--- | :--- | :--- |",
            f"| **Status** | `Enabled` | Partitioned incremental refresh active. |",
            f"| **Policy Type** | `{policy_type}` | Type of incremental policy applied. |",
            f"| **Storage Mode** | {mode_badge} | Historical partitions mode and real-time handling. |",
            f"| **Historical Window (Store)** | `{rolling_desc}` | Total historical data retained across partitions. |",
            f"| **Refresh Window (Refresh)** | `{inc_desc}` | Rolling period refreshed during scheduled updates. |",
            f"| **Detect Data Changes** | {'`Enabled`' if polling_expr else '`Disabled`'} | Polling expression to refresh only changed partitions. |",
        ])

        if polling_expr:
            lines.extend([
                "",
                "#### Detect Data Changes (Polling Expression):",
                "```powerquery",
                polling_expr.strip(),
                "```",
            ])

        if source_expr:
            lines.extend([
                "",
                "#### Partition Source Filter Expression:",
                "```powerquery",
                source_expr.strip(),
                "```",
            ])

        lines.extend([
            "",
            "#### Architectural & Query Folding Notes:",
            "- **Query Folding Requirement**: Power Query parameters `RangeStart` and `RangeEnd` must fold to the source database to ensure efficient partition filtering.",
            "- **Partition Lifecycle**: Partitions older than the historical window are dropped, while incremental periods are refreshed dynamically.",
        ])

        if mode == "hybrid":
            lines.append(
                "- **Hybrid Real-Time Capabilities**: DirectQuery is enabled for the latest partition, ensuring up-to-the-minute data visibility without waiting for a dataset refresh."
            )

        return "\n".join(lines)

    # 10. Semantic Context for AI & RAG (always after Details)
    def _section_rag(self) -> Optional[DocSection]:
        if not self.config.include_table_rag_hints:
            return None

        col_names = [f"`{c.get('name')}`" for c in self.columns[:10]]
        sample_cols = ", ".join(col_names)
        if len(self.columns) > 10:
            sample_cols += f" and {len(self.columns) - 10} other columns"

        lines = [
            "## Semantic Context for AI & RAG",
            "",
            "Synthesized context for semantic vector retrieval and AI search assistants:",
            "",
            f"- **Entity Represented**: {self.role.lower()} table named `{self.name}`.",
            f"- **Key Attributes**: {sample_cols}.",
        ]

        if self.table.get("source_type") == "CalculatedTable":
            lines.append("- **Computation Type**: In-memory DAX Calculated Table (`partition = calculated`).")

        if self.role == "FACT":
            lines.extend([
                "- **Resolvable Business Questions**:",
                f"  - What are the historical volumes and metrics recorded in `{self.name}`?",
                f"  - How are aggregated measures distributed across dimensions {', '.join(f'`{d}`' for d in self.table.get('connected_dimensions', []))}?",
                f"  - What totals are filtered through lookup tables {', '.join(f'`{l}`' for l in self.table.get('reachable_lookup_tables', []))}?",
            ])
        elif self.role in ("DIMENSION", "LOOKUP_OUTRIGGER"):
            lines.extend([
                "- **Resolvable Business Questions**:",
                f"  - What are the unique values, categories, or entities in `{self.name}`?",
                f"  - How do entities in `{self.name}` filter transactional metrics across connected tables?",
            ])

        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content="\n".join(lines),
        )
