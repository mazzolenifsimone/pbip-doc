"""
Modular Markdown Document Generator for Power Query (M) Expressions and Shared ETL Queries.
Supports Staging Queries, Parameters, Custom Functions, and Inline Tables (#table).
Optimized for dual consumption: human readability + AI RAG semantic search.
Vanilla Python implementation.
"""

from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .utils import format_yaml_frontmatter, sanitize_filename, join_doc_path, clean_project_name, resolve_model_index_url
from .section_engine import DocSection, assemble_markdown_document
from .layout_engine import render_document_markdown
from ..model_schema import resolve_expression_type_and_inline
from ..m_formatter import format_m


class ExpressionDocBuilder:
    """
    Builds modular markdown documentation for a single Power Query expression / shared staging query.
    """

    def __init__(
        self,
        expr_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        project_name: Optional[str] = None,
    ):
        self.expr = expr_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.project_name = clean_project_name(
            project_name or self.config.project_name or full_model.get("project_name") or full_model.get("model_name")
        )
        self.name = expr_data.get("query_name", "UnnamedExpression")
        self.is_staging = expr_data.get("is_staging", True)
        self.target_table = expr_data.get("target_table")
        self.full_m = expr_data.get("full_m_expression", "")
        self.steps = expr_data.get("steps", [])
        self.direct_deps = expr_data.get("direct_dependencies", [])
        self.upstream_queries = expr_data.get("all_upstream_queries", [])
        self.downstream_queries = expr_data.get("downstream_queries", [])
        self.downstream_tables = [
            t for t in expr_data.get("downstream_tables", [])
            if not self.config.is_table_excluded(t)
        ]
        self.root_sources = expr_data.get("root_sources", [])
        self.description = expr_data.get("description")
        self.query_group = expr_data.get("query_group")
        self.lineage_tag = expr_data.get("lineage_tag")

        # Read pre-calculated expression category & inline table metadata
        resolved_meta = resolve_expression_type_and_inline(expr_data)
        self.expression_type = resolved_meta["expression_type"]
        self.is_inline_table = resolved_meta["is_inline_table"]
        self.inline_cols = resolved_meta["inline_table_columns"]
        self.inline_types = resolved_meta["inline_table_column_types"]
        self.inline_rows = resolved_meta["inline_table_rows"]
        self.inline_md = resolved_meta["inline_table_markdown"]

    def _classify_expression_type(self) -> str:
        """Returns the pre-resolved canonical expression type."""
        return resolve_expression_type_and_inline(self.expr)["expression_type"]

    def build_markdown(self) -> str:
        """Assembles all enabled modular chapters into a complete Markdown document according to document layout."""
        fm_str: Optional[str] = None
        if self.config.include_expression_yaml_frontmatter:
            fm_str = self._build_frontmatter()

        header_block = self._build_header_block()

        registry = {
            "description": self._section_description,
            "function_parameters": self._section_function_parameters,
            "inline_definition": self._section_inline_table,
            "lineage_steps": self._section_steps,
            "power_query_m": self._section_m_code,
            "calculated_columns": self._section_calculated_columns,
            "unused_steps": self._section_unused_steps,
            "upstream_dependencies": self._section_upstream,
            "upstream": self._section_upstream,
            "downstream_dependents": self._section_downstream,
            "downstream": self._section_downstream,
            "details": self._section_technical_specs,
            "technical_specs": self._section_technical_specs,
            "rag": self._section_rag_hints,
        }
        return render_document_markdown(
            doc_type="expression",
            frontmatter_str=fm_str,
            header_block=header_block,
            registry=registry,
            config=self.config,

        )

    def _legacy_build_markdown(self) -> str:
        """Assembles all enabled modular chapters into a complete Markdown document."""
        fm_str: Optional[str] = None
        if self.config.include_expression_yaml_frontmatter:
            fm_str = self._build_frontmatter()

        header_block = self._build_header_block()

        sections: List[Optional[DocSection]] = [
            self._section_description(),
            self._section_function_parameters(),
            self._section_inline_table(),
            self._section_m_code(),
            self._section_steps(),
            self._section_calculated_columns(),
            self._section_unused_steps(),
            self._section_upstream(),
            self._section_downstream(),
            self._section_technical_specs(),
            self._section_rag_hints(),
        ]

        return assemble_markdown_document(fm_str, header_block, sections)

    def _build_frontmatter(self) -> str:
        """Constructs YAML frontmatter for RAG vector indexing."""
        tags = ["power_query", "expression", "etl", self.expression_type.lower(), sanitize_filename(self.name)]
        if self.project_name:
            tags.append(sanitize_filename(self.project_name))
        if self.is_inline_table:
            tags.extend(["inline_table", "table_literal", "static_lookup"])
        elif self.expression_type == "PARAMETER":
            tags.extend(["parameter", "configuration"])
        elif self.expression_type == "CUSTOM_FUNCTION":
            tags.extend(["custom_function", "m_function"])
        else:
            tags.extend(["staging_query", "data_transformation"])

        root_source_strings = [
            str(s.get("connection_string", s.get("source_type", ""))).replace("\\", "/")
            for s in self.root_sources
            if s.get("connection_string") or s.get("source_type")
        ]

        frontmatter_data = {
            "title": f"Expression: {self.name}",
            "pbip_project": self.project_name,
            "entity_name": self.name,
            "doc_type": "power_query_expression",
            "expression_type": self.expression_type,
            "is_inline_table": self.is_inline_table,
            "is_staging": self.is_staging,
            "parameter_value": self.expr.get("parameter_value"),
            "parameter_type": self.expr.get("parameter_type"),
            "parameter_required": self.expr.get("parameter_required", False),
            "steps_count": len(self.steps),
            "direct_dependencies": self.direct_deps,
            "upstream_queries": self.upstream_queries,
            "downstream_queries": self.downstream_queries,
            "downstream_tables": self.downstream_tables,
            "root_sources": root_source_strings,
            "query_group": self.query_group,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_header_block(self) -> str:
        model_url = resolve_model_index_url(self.config, self.project_name, self.config.expressions_subdir)
        model_link = f"[{self.project_name}]({model_url})" if self.config.include_markdown_links else f"`{self.project_name}`"
        if self.expression_type == "PARAMETER":
            p_val = self.expr.get("parameter_value") or "—"
            p_type = self.expr.get("parameter_type") or "Any"
            p_req = "Yes" if self.expr.get("parameter_required") else "No"
            downstream_cnt = len(self.downstream_tables) + len(self.downstream_queries)
            lines = [
                f"# Expression: `{self.name}`",
                "",
                f"**Model**: {model_link} | **Role**: `Query Parameter M` | **Current Value**: `{p_val}` | **Type**: `{p_type}` | **Required**: `{p_req}` | **Impacted Items**: `{downstream_cnt}`",
            ]
        elif self.expression_type == "LOADED_TABLE":
            target = self.target_table or self.name
            clean_t = sanitize_filename(target)
            tbl_link = f"[{target}](../tables/{clean_t}.md)" if self.config.include_markdown_links else f"`{target}`"
            lines = [
                f"# Expression: `{self.name}`",
                "",
                f"**Model**: {model_link} | **Pipeline Role**: `Loaded Model Table` | **Target Table**: {tbl_link} | **Dependencies**: `{len(self.direct_deps)}`",
            ]
        else:
            role_label = 'Custom Function' if self.expression_type == "CUSTOM_FUNCTION" else ('Inline Table' if self.is_inline_table else ('Staging' if self.is_staging else 'Model Table'))
            lines = [
                f"# Expression: `{self.name}`",
                "",
                f"**Model**: {model_link} | **Pipeline Role**: `{role_label}` | **Dependencies**: `{len(self.direct_deps)}` | **Downstream Tables**: `{len(self.downstream_tables)}`",
            ]
        return "\n".join(lines)

    def _section_description(self) -> Optional[DocSection]:
        if not self.config.include_expression_overview_section:
            return None

        lines = ["## Description", ""]
        if self.description:
            lines.append(f"> {self.description}")
        else:
            lines.append("*No description provided.*")
        lines.append("")

        if self.expression_type == "INLINE_TABLE":
            col_count = len(self.inline_cols)
            row_count = len(self.inline_rows)
            lines.append(
                f"The expression **`{self.name}`** defines an in-memory, static **Inline Table (`#table`)** "
                f"containing **{col_count} columns** and **{row_count} rows**. "
                "It serves as a hardcoded reference dataset, lookup table, or static mapping matrix within the semantic model."
            )
        elif self.expression_type == "PARAMETER":
            lines.append(
                f"The expression **`{self.name}`** is an ETL **Parameter**. "
                "It parameterizes connection endpoints, environment settings, or query filters, "
                "enabling dynamic deployment across environments (Dev, Test, Prod)."
            )
        elif self.expression_type == "CUSTOM_FUNCTION":
            lines.append(
                f"The expression **`{self.name}`** is a reusable **Power Query Custom Function**. "
                "It encapsulates transformation logic invoked across multiple queries or row-level operations."
            )
        elif self.expression_type == "LOADED_TABLE":
            target = self.target_table or self.name
            clean_t = sanitize_filename(target)
            tbl_link = f"[{target}](../tables/{clean_t}.md)" if self.config.include_markdown_links else f"`{target}`"
            lines.append(
                f"The expression **`{self.name}`** defines the primary Power Query data ingestion pipeline "
                f"for the semantic model table {tbl_link}. "
                "It extracts, cleanses, transforms, and loads data from physical sources into the in-memory semantic model."
            )
        else:
            lines.append(
                f"The expression **`{self.name}`** is a Power Query **Staging / Intermediate ETL Query**. "
                "It extracts, cleanses, and reshapes data from physical sources or upstream queries before loading into destination tables."
            )

        if self.query_group:
            lines.append(f"- **Query Folder / Group**: `{self.query_group}`")

        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content="\n".join(lines),
        )

    def _section_function_parameters(self) -> Optional[DocSection]:
        params = self.expr.get("m_function_parameters", [])
        ret_type = self.expr.get("m_function_return_type")
        if self.expression_type != "CUSTOM_FUNCTION" and not params:
            return None
        lines = ["## Function Signature & Parameters", ""]
        if ret_type:
            lines.append(f"- **Return Type**: `{ret_type}`")
            lines.append("")
        if params:
            lines.append("| Parameter | Type | Optional | Description |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for p in params:
                p_name = p.name if hasattr(p, "name") else p.get("name", "")
                p_type = (p.data_type if hasattr(p, "data_type") else p.get("data_type")) or "any"
                p_opt = "Yes" if (p.is_optional if hasattr(p, "is_optional") else p.get("is_optional")) else "No"
                p_desc = (p.description if hasattr(p, "description") else p.get("description")) or "—"
                lines.append(f"| `{p_name}` | `{p_type}` | {p_opt} | {p_desc} |")
        return DocSection(
            section_id="tab-params",
            title="Function Signature & Parameters",
            nav_label="Parameters",
            content="\n".join(lines),
        )

    def _section_unused_steps(self) -> Optional[DocSection]:
        unused = self.expr.get("unused_steps", [])
        if not (self.config.include_m_unused_steps and unused):
            return None
        lines = [
            f"## Unused / Dead Steps ({len(unused)} steps)",
            "",
            "> **Note**: These steps are defined in the `let` block but are not referenced in the `in` expression or DAG slice.",
            "",
            "| Step | Operation |",
            "| :--- | :--- |",
        ]
        for st in unused:
            s_name = st.step_name if hasattr(st, "step_name") else st.get("step_name", "")
            op = st.operation if hasattr(st, "operation") else st.get("operation", "")
            lines.append(f"| `{s_name}` | {op} |")
        return DocSection(
            section_id="tab-unused",
            title=f"Unused / Dead Steps ({len(unused)})",
            nav_label=f"Unused Steps ({len(unused)})",
            content="\n".join(lines),
        )

    def _section_inline_table(self) -> Optional[DocSection]:
        if not (self.config.include_expression_inline_table and self.is_inline_table and self.inline_md):
            return None
        lines = [
            "## Inline Table Definition (`#table`)",
            "",
            f"This expression contains a static in-memory table defined via `#table` with **{len(self.inline_cols)} columns** and **{len(self.inline_rows)} rows**:",
            "",
        ]
        if self.inline_types:
            type_items = [f"`{col}`: *{t}*" for col, t in self.inline_types.items()]
            lines.append(f"- **Column Types**: {', '.join(type_items)}")
            lines.append("")
        lines.append(self.inline_md)
        return DocSection(
            section_id="tab-inline",
            title="Inline Table Definition (`#table`)",
            nav_label="Inline Table",
            content="\n".join(lines),
        )

    def _section_m_code(self) -> Optional[DocSection]:
        if not (self.config.include_expression_m_code and self.full_m):
            return None
        formatted_m = format_m(self.full_m) if self.full_m else ""
        lines = [
            "## Full Power Query M Expression",
            "",
            "```powerquery",
            formatted_m,
            "```",
        ]
        return DocSection(
            section_id="tab-m",
            title="Full Power Query M Expression",
            nav_label="Power Query (M) Script",
            content="\n".join(lines),
        )

    def _section_steps(self) -> Optional[DocSection]:
        if not (self.config.include_expression_steps_section and self.steps):
            return None
        lines = [
            f"## Transformation Steps ({len(self.steps)} steps)",
            "",
            "Step-by-step transformations executed within the `let ... in` block:",
            "",
            "| # & Step Name | Operation | Transformed Column / Scope | Expression Preview / Details | Referenced Queries |",
            "| :--- | :--- | :--- | :--- | :--- |",
        ]
        for idx, st in enumerate(self.steps, 1):
            s_name = st.get("step_name", f"Step_{idx}") if isinstance(st, dict) else getattr(st, "step_name", f"Step_{idx}")
            op = st.get("operation", "Transform") if isinstance(st, dict) else getattr(st, "operation", "Transform")
            col_scope = st.get("transformed_column") if isinstance(st, dict) else getattr(st, "transformed_column", None)
            raw_code = st.get("raw_m_code") if isinstance(st, dict) else getattr(st, "raw_m_code", None)
            details = st.get("details") if isinstance(st, dict) else getattr(st, "details", None)
            s_expr = details or raw_code or (st.get("raw_expression", "") if isinstance(st, dict) else getattr(st, "raw_expression", ""))
            if len(s_expr) > 120:
                s_expr = s_expr[:117] + "..."
            s_expr_clean = s_expr.replace("\n", " ").replace("|", "\\|")

            refs_raw = st.get("referenced_queries", []) if isinstance(st, dict) else getattr(st, "referenced_queries", [])
            ref_links = []
            for r in refs_raw:
                clean_r = sanitize_filename(r)
                if self.config.include_markdown_links:
                    ref_links.append(f"[{r}]({clean_r}.md)")
                else:
                    ref_links.append(f"`{r}`")
            refs_display = ", ".join(ref_links) if ref_links else "—"
            col_display = f"`{col_scope}`" if col_scope else "—"

            lines.append(f"| `#{idx} {s_name}` | {op} | {col_display} | `{s_expr_clean}` | {refs_display} |")

        return DocSection(
            section_id="tab-steps",
            title=f"Transformation Steps ({len(self.steps)} steps)",
            nav_label=f"Transformation Steps ({len(self.steps)})",
            content="\n".join(lines),
        )

    def _get_calculated_columns(self) -> List[Dict[str, Any]]:
        """Extracts Power Query calculated and transformed columns for this expression."""
        cols: List[Dict[str, Any]] = []
        target = self.expr.get("target_table") or self.name
        tables = self.model.get("tables", [])
        matched_table = next((t for t in tables if t.get("name") == target), None)
        if matched_table:
            for c in matched_table.get("columns", []):
                origin = c.get("origin")
                is_pq = origin == "power_query" or bool(c.get("m_expression")) or bool(c.get("m_operation"))
                if is_pq:
                    cols.append(c)
        if not cols:
            for s in self.steps:
                s_op = s.get("operation") if isinstance(s, dict) else getattr(s, "operation", "")
                t_col = s.get("transformed_column") if isinstance(s, dict) else getattr(s, "transformed_column", None)
                if t_col and (s_op in ("Calculated Column", "Add Column", "Custom Column", "Added Custom", "Added Column") or "Column" in str(s_op)):
                    cols.append({
                        "name": t_col,
                        "data_type": "Any",
                        "m_operation": s_op,
                        "m_step_name": s.get("step_name") if isinstance(s, dict) else getattr(s, "step_name", ""),
                        "m_expression": s.get("raw_m_code") or s.get("details") if isinstance(s, dict) else getattr(s, "raw_m_code", ""),
                    })
        return cols

    def _section_calculated_columns(self) -> Optional[DocSection]:
        pq_cols = self._get_calculated_columns()
        if not pq_cols:
            return None
        lines = [
            f"## Calculated & Transformed Columns ({len(pq_cols)})\n",
            "Columns derived or computed in Power Query (M) before loading into the model:\n",
            "| Column | Operation | Step Name | Source / Details |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for pqc in pq_cols:
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
        return DocSection(
            section_id="tab-calc-cols",
            title=f"Calculated Columns ({len(pq_cols)})",
            nav_label=f"Calculated Columns ({len(pq_cols)})",
            content="\n".join(lines),
        )

    def _section_upstream(self) -> Optional[DocSection]:
        if not self.config.include_expression_lineage_section:
            return None
        lines = [
            "## Upstream Dependencies",
            "",
            "This section maps upstream physical data sources and referenced queries feeding this expression.",
        ]

        if self.root_sources:
            lines.append("")
            lines.append("### Physical Data Sources of Origin:")
            lines.append("")
            lines.append("| Source Type | Connection / Details | Server | Database | Schema | Table / Object |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
            for s in self.root_sources:
                stype = f"`{s.get('source_type', 'GENERIC')}`"
                raw_conn = str(s.get("connection_string", "—")).replace("\\\\", "/")
                conn = f"`{raw_conn}`" if s.get("connection_string") else "—"
                server = f"`{s.get('server')}`" if s.get("server") and s.get("server") != "—" else "—"
                db = f"`{s.get('database')}`" if s.get("database") and s.get("database") != "—" else "—"
                sch = f"`{s.get('schema')}`" if s.get("schema") and s.get("schema") != "—" else "—"
                itm = f"`{s.get('item') or s.get('endpoint_or_path')}`" if (s.get("item") or s.get("endpoint_or_path")) and (s.get("item") or s.get("endpoint_or_path")) != "—" else "—"
                lines.append(f"| {stype} | {conn} | {server} | {db} | {sch} | {itm} |")

        if self.direct_deps:
            lines.append("")
            lines.append("### Directly Referenced Queries:")
            for dep in self.direct_deps:
                clean_dep = sanitize_filename(dep)
                if self.config.base_doc_url:
                    expr_sub = self.config.expressions_subdir.strip("/\\")
                    q_url = join_doc_path(self.config.base_doc_url, expr_sub, f"{clean_dep}.md") if expr_sub else join_doc_path(self.config.base_doc_url, f"{clean_dep}.md")
                else:
                    q_url = f"{clean_dep}.md"
                link = f"[{dep}]({q_url})" if self.config.include_markdown_links else f"`{dep}`"
                lines.append(f"- {link}")
        elif not self.root_sources:
            lines.append("")
            lines.append("- *No upstream Power Query dependencies detected.*")

        return DocSection(
            section_id="tab-upstream",
            title="Upstream Dependencies",
            nav_label=f"Upstream ({len(self.direct_deps)})",
            content="\n".join(lines),
        )

    def _section_downstream(self) -> Optional[DocSection]:
        if not self.config.include_expression_lineage_section:
            return None
        lines = [
            "## Downstream Dependencies",
            "",
        ]
        if self.downstream_queries:
            lines.append("### Downstream Queries Consuming this Expression:")
            for dq in self.downstream_queries:
                clean_dq = sanitize_filename(dq)
                if self.config.base_doc_url:
                    expr_sub = self.config.expressions_subdir.strip("/\\")
                    q_url = join_doc_path(self.config.base_doc_url, expr_sub, f"{clean_dq}.md") if expr_sub else join_doc_path(self.config.base_doc_url, f"{clean_dq}.md")
                else:
                    q_url = f"{clean_dq}.md"
                link = f"[{dq}]({q_url})" if self.config.include_markdown_links else f"`{dq}`"
                lines.append(f"- {link}")
            lines.append("")

        if self.downstream_tables:
            lines.append("### Final Model Tables Loaded from this Pipeline:")
            tables_sub = self.config.tables_subdir.strip("/\\")
            for tbl in self.downstream_tables:
                clean_tbl = sanitize_filename(tbl)
                target_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == tbl), None)
                tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
                if tbl_pub and self.config.include_markdown_links:
                    if self.config.base_doc_url:
                        tbl_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
                    else:
                        rel_prefix = f"../{tables_sub}/" if tables_sub else "../"
                        tbl_url = f"{rel_prefix}{clean_tbl}.md"
                    link = f"[{tbl}]({tbl_url})"
                elif not tbl_pub:
                    ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        link = f"[{tbl}]({ext_url}) *(Inherited Entity)*"
                    else:
                        link = f"`{tbl}` *(Inherited Entity)*" if (target_tbl and target_tbl.get("is_inherited")) else f"`{tbl}`"
                else:
                    link = f"`{tbl}`"
                lines.append(f"- {link}")
        else:
            lines.append("> ℹ️ **Unloaded / Utility Query**: This expression is not loaded directly into a model table. It serves as an intermediate staging query or configuration parameter.")

        total_down = len(self.downstream_queries) + len(self.downstream_tables)
        return DocSection(
            section_id="tab-downstream",
            title="Downstream Dependencies",
            nav_label=f"Downstream ({total_down})",
            content="\n".join(lines),
        )

    def _section_technical_specs(self) -> Optional[DocSection]:
        if self.expression_type == "PARAMETER":
            role_label = "Query Parameter M"
            target_tbl = "— (Parameter)"
        elif self.expression_type == "CUSTOM_FUNCTION":
            role_label = "Custom Function M"
            target_tbl = "— (Function)"
        elif self.expression_type == "INLINE_TABLE":
            role_label = "Inline Table"
            target_tbl = self.target_table or "— (Inline Table)"
        elif self.expression_type == "LOADED_TABLE":
            role_label = "Loaded Model Table"
            target_tbl = self.target_table or self.name
        else:
            role_label = "Staging" if self.is_staging else "Model Table"
            target_tbl = self.target_table or "None (Staging Query)"

        lines = [
            "## Technical Specifications",
            "",
            "| Property | Value |",
            "| :--- | :--- |",
            f"| **Query Name** | `{self.name}` |",
            f"| **Expression Type** | `{self.expression_type}` |",
            f"| **Pipeline Role** | `{role_label}` |",
            f"| **Target Table** | `{target_tbl}` |",
            f"| **Query Group** | `{self.query_group or '—'}` |",
            f"| **Steps Count** | `{len(self.steps)}` |",
        ]
        if self.expression_type == "PARAMETER":
            p_val = self.expr.get("parameter_value") or "—"
            p_type = self.expr.get("parameter_type") or "Any"
            p_req = "Yes" if self.expr.get("parameter_required") else "No"
            lines.extend([
                f"| **Parameter Value** | `{p_val}` |",
                f"| **Parameter Type** | `{p_type}` |",
                f"| **Parameter Required** | `{p_req}` |",
            ])
        return DocSection(
            section_id="tab-tech",
            title="Technical Specifications",
            nav_label="Technical Specifications",
            content="\n".join(lines),
        )

    def _section_rag_hints(self) -> Optional[DocSection]:
        if not self.config.include_expression_rag_hints:
            return None
        lines = [
            "## Semantic Context for AI & RAG",
            "",
            "Synthesized context for semantic vector search and AI assistants:",
            "",
            f"- **Entity Type**: Power Query expression of type `{self.expression_type}`.",
            f"- **Primary Responsibility**: {self._synthesize_ai_summary()}",
        ]

        if self.downstream_tables:
            tables_str = ", ".join(f"`{t}`" for t in self.downstream_tables)
            lines.append(f"- **Impacted Data Model Tables**: {tables_str}.")

        lines.extend([
            "- **Resolvable ETL & Business Questions**:",
            "  - How is data ingested and transformed before reaching downstream tables?",
            f"  - What data sources or parameters does `{self.name}` rely on?",
            f"  - What happens if the schema or transformations in `{self.name}` are modified?",
        ])

        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content="\n".join(lines),
        )

    def _synthesize_ai_summary(self) -> str:
        """Generates a concise 1-sentence summary of what this expression does."""
        if self.is_inline_table:
            return f"Provides an in-memory static lookup table with columns {', '.join(f'`{c}`' for c in self.inline_cols[:5])}."
        if self.expression_type == "PARAMETER":
            return f"Configures environment or connection parameter `{self.name}`."
        if self.expression_type == "CUSTOM_FUNCTION":
            return f"Encapsulates reusable Power Query M transformation function `{self.name}`."
        if self.expression_type == "LOADED_TABLE":
            return f"Primary data ingestion pipeline for model table `{self.target_table or self.name}`."
        if self.downstream_tables:
            return f"Staging transformation pipeline feeding model table(s) {', '.join(f'`{t}`' for t in self.downstream_tables)}."
        return "Intermediate data transformation pipeline in Power Query."


class DataflowDocBuilder:
    """
    Builds the Dataflow & Power Query Overview document (expressions/README.md).
    Provides central inventory of ingested tables, staging queries, parameters, and functions.
    Follows unified Section-Driven modular architecture.
    """

    def __init__(
        self,
        model_data: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        project_name: Optional[str] = None,
    ):
        self.model = model_data
        self.config = config or DocGenConfig()
        self.project_name = clean_project_name(
            project_name or self.config.project_name or model_data.get("project_name") or model_data.get("model_name") or "PBIP"
        )
        self.tables = [t for t in self.model.get("tables", []) if not self.config.is_table_excluded(t.get("name"))]
        self.exprs = self.model.get("expressions") or self.model.get("shared_queries") or []

        self.dataflow_tables = [
            t for t in self.tables
            if (
                t.get("source_type", "PowerQuery") == "PowerQuery"
                or bool(t.get("power_query_lineage") and t.get("power_query_lineage", {}).get("full_m_expression"))
            )
            and t.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (t.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
        ]

        self.params = [
            e for e in self.exprs
            if resolve_expression_type_and_inline(e)["expression_type"] == "PARAMETER"
        ]
        self.functions = [
            e for e in self.exprs
            if resolve_expression_type_and_inline(e)["expression_type"] == "CUSTOM_FUNCTION"
        ]
        self.staging = [
            e for e in self.exprs
            if e not in self.params and e not in self.functions
        ]

    def build_markdown(self) -> str:
        """Assembles dataflow overview markdown using declarative layout."""
        fm_str = self._build_frontmatter()
        header_block = self._build_header_block()

        registry = {
            "description": self._section_overview,
            "data_source_summary": self._section_data_source_summary,
            "sources": self._section_data_source_summary,
            "loaded_tables": self._section_loaded_tables,
            "staging_queries": self._section_staging_queries,
            "parameters_and_functions": self._section_parameters_and_functions,
            "parameters": self._section_parameters_and_functions,
            "topology": self._section_lineage,
            "lineage": self._section_lineage,
        }
        return render_document_markdown(
            doc_type="dataflow_overview",
            frontmatter_str=fm_str,
            header_block=header_block,
            registry=registry,
            config=self.config,
        )

    def _section_data_source_summary(self) -> Optional[DocSection]:
        sources_map = {}
        for t in self.tables:
            for s in t.get("root_data_sources", []):
                s_dict = s if isinstance(s, dict) else s.__dict__
                key = (s_dict.get("source_type"), s_dict.get("server"), s_dict.get("database"), s_dict.get("schema"), s_dict.get("item") or s_dict.get("endpoint_or_path"))
                t_name = t.get("name")
                if key not in sources_map:
                    sources_map[key] = {
                        "source": s_dict,
                        "targets": [t_name] if t_name else []
                    }
                else:
                    if t_name and t_name not in sources_map[key]["targets"]:
                        sources_map[key]["targets"].append(t_name)

        for e in self.exprs:
            for s in e.get("root_sources", []):
                s_dict = s if isinstance(s, dict) else s.__dict__
                key = (s_dict.get("source_type"), s_dict.get("server"), s_dict.get("database"), s_dict.get("schema"), s_dict.get("item") or s_dict.get("endpoint_or_path"))
                q_name = e.get("query_name", e.get("name"))
                if key not in sources_map:
                    sources_map[key] = {
                        "source": s_dict,
                        "targets": [q_name] if q_name else []
                    }
                else:
                    if q_name and q_name not in sources_map[key]["targets"]:
                        sources_map[key]["targets"].append(q_name)

        if not sources_map:
            return None

        lines = [
            "## Data Source Summary",
            "",
            "Consolidated physical data sources feeding the Power Query ETL pipelines:",
            "",
            "| Source Type | Connection / Details | Server | Database | Schema | Table / Object | Feeding Pipelines |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for key, info in sorted(sources_map.items(), key=lambda x: (str(x[0][0]), str(x[0][1]), str(x[0][2]))):
            s = info["source"]
            stype = f"`{s.get('source_type', 'GENERIC')}`"
            conn = f"`{s.get('connection_string', '—')}`" if s.get("connection_string") and s.get("connection_string") != "—" else "—"
            srv = f"`{s.get('server', '—')}`" if s.get("server") and s.get("server") != "—" else "—"
            db = f"`{s.get('database', '—')}`" if s.get("database") and s.get("database") != "—" else "—"
            sch = f"`{s.get('schema', '—')}`" if s.get("schema") and s.get("schema") != "—" else "—"
            itm = f"`{s.get('item', '—')}`" if s.get("item") and s.get("item") != "—" else "—"
            targets = ", ".join(f"`{tgt}`" for tgt in info["targets"] if tgt) or "—"
            lines.append(f"| {stype} | {conn} | {srv} | {db} | {sch} | {itm} | {targets} |")

        return DocSection(
            section_id="tab-sources",
            title="Data Source Summary",
            nav_label="Data Sources",
            content="\n".join(lines),
        )

    def _build_frontmatter(self) -> str:
        data = {
            "title": f"Dataflow Overview - {self.project_name}",
            "pbip_project": self.project_name,
            "doc_type": "dataflow_overview",
            "loaded_tables_count": len(self.dataflow_tables),
            "staging_queries_count": len(self.staging),
            "parameters_count": len(self.params),
            "functions_count": len(self.functions),
            "tags": ["dataflow", "power_query", "overview", sanitize_filename(self.project_name)],
        }
        return format_yaml_frontmatter(data)

    def _build_header_block(self) -> str:
        model_url = resolve_model_index_url(self.config, self.project_name, self.config.expressions_subdir)
        model_link = f"[{self.project_name}]({model_url})" if self.config.include_markdown_links else f"`{self.project_name}`"
        lines = [
            f"# Dataflow & Power Query Overview: `{self.project_name}`",
            "",
            f"**Semantic Model**: {model_link} | **Ingested Tables**: `{len(self.dataflow_tables)}` | **Staging Queries**: `{len(self.staging)}` | **Parameters**: `{len(self.params)}` | **Functions**: `{len(self.functions)}`",
        ]
        return "\n".join(lines)

    def _section_overview(self) -> Optional[DocSection]:
        lines = [
            "## Architecture Overview",
            "",
            f"This chapter documents the end-to-end Power Query Dataflow pipelines for **`{self.project_name}`**. "
            "It captures physical source connectivity, intermediate data preparation and cleansing, query parameters, "
            "reusable functions, and table ingestion definitions.",
        ]
        return DocSection(
            section_id="tab-overview",
            title="Architecture Overview",
            nav_label="Overview",
            content="\n".join(lines),
        )

    def _section_loaded_tables(self) -> Optional[DocSection]:
        if not self.dataflow_tables:
            return None
        lines = [
            f"## Loaded ({len(self.dataflow_tables)})",
            "",
            "Power Query pipelines feeding tables directly into the in-memory semantic model:",
            "",
            "| Ingested Table | Star Schema Role | Steps | Direct Upstream Queries | Physical Data Sources | Destination Table |",
            "| :--- | :--- | :---: | :--- | :--- | :--- |",
        ]
        for t in sorted(self.dataflow_tables, key=lambda x: x.get("name", "")):
            t_name = t.get("name", "Table")
            clean_t = sanitize_filename(t_name)
            role = t.get("role", "DIM")
            lineage = t.get("power_query_lineage") or {}
            steps_cnt = len(lineage.get("steps", []))
            deps = lineage.get("direct_dependencies", [])
            dep_links = []
            for d in deps:
                clean_d = sanitize_filename(d)
                dep_links.append(f"[`{d}`]({clean_d}.md)" if self.config.include_markdown_links else f"`{d}`")
            deps_str = ", ".join(dep_links) or "— *(Direct Source)*"

            sources = t.get("root_data_sources", [])
            src_types = list({s.get("source_type", "Source") for s in sources if s.get("source_type")})
            src_str = ", ".join(f"`{st}`" for st in src_types) or "—"

            ingested_link = f"[**{t_name}**]({clean_t}.md)" if self.config.include_markdown_links else f"**{t_name}**"
            dest_link = f"[{t_name}](../tables/{clean_t}.md)" if self.config.include_markdown_links else f"`{t_name}`"

            lines.append(f"| {ingested_link} | `{role}` | {steps_cnt} | {deps_str} | {src_str} | {dest_link} |")

        return DocSection(
            section_id="tab-loaded",
            title=f"Loaded ({len(self.dataflow_tables)})",
            nav_label=f"Loaded ({len(self.dataflow_tables)})",
            content="\n".join(lines),
        )

    def _section_staging_queries(self) -> Optional[DocSection]:
        if not self.staging:
            return None
        lines = [
            f"## Staging & Intermediate Queries ({len(self.staging)})",
            "",
            "Intermediate transformations, base staging queries, and static inline reference tables:",
            "",
            "| Query Name | Category | Steps | Direct Dependencies | Downstream Dependents |",
            "| :--- | :--- | :---: | :--- | :--- |",
        ]
        for s in sorted(self.staging, key=lambda x: x.get("query_name", "")):
            q_name = s.get("query_name", "Query")
            clean_q = sanitize_filename(q_name)
            is_inline = resolve_expression_type_and_inline(s)["is_inline_table"]
            kind = "Inline Table" if is_inline else "Staging Query"
            steps_cnt = len(s.get("steps", []))
            deps = s.get("direct_dependencies", [])
            dep_links = [f"[`{d}`]({sanitize_filename(d)}.md)" if self.config.include_markdown_links else f"`{d}`" for d in deps]
            deps_str = ", ".join(dep_links) or "—"

            downs = s.get("downstream_tables", []) + s.get("downstream_queries", [])
            down_links = [f"[`{d}`]({sanitize_filename(d)}.md)" if self.config.include_markdown_links else f"`{d}`" for d in downs]
            downs_str = ", ".join(down_links) or "—"

            q_link = f"[**{q_name}**]({clean_q}.md)" if self.config.include_markdown_links else f"**{q_name}**"
            lines.append(f"| {q_link} | `{kind}` | {steps_cnt} | {deps_str} | {downs_str} |")

        return DocSection(
            section_id="tab-staging",
            title=f"Staging Queries ({len(self.staging)})",
            nav_label=f"Staging Queries ({len(self.staging)})",
            content="\n".join(lines),
        )

    def _section_parameters_and_functions(self) -> Optional[DocSection]:
        items = self.params + self.functions
        if not items:
            return None
        lines = [
            f"## Parameters & Custom Functions ({len(items)})",
            "",
            "Configurable environment parameters and reusable M functions:",
            "",
            "| Item Name | Category | Current Value / Signature | Required | Consuming Items |",
            "| :--- | :--- | :--- | :---: | :--- |",
        ]
        for it in sorted(items, key=lambda x: x.get("query_name", "")):
            name = it.get("query_name", "Item")
            clean_n = sanitize_filename(name)
            is_param = it in self.params
            cat = "Parameter" if is_param else "Custom Function"
            val = it.get("parameter_value", "—") if is_param else (it.get("m_function_return_type") or "λ function")
            req = ("Yes" if it.get("parameter_required") else "No") if is_param else "—"

            downs = it.get("downstream_tables", []) + it.get("downstream_queries", [])
            down_str = f"{len(downs)} items" if downs else "—"

            it_link = f"[**{name}**]({clean_n}.md)" if self.config.include_markdown_links else f"**{name}**"
            lines.append(f"| {it_link} | `{cat}` | `{val}` | {req} | {down_str} |")

        return DocSection(
            section_id="tab-params",
            title=f"Parameters & Functions ({len(items)})",
            nav_label=f"Parameters & Functions ({len(items)})",
            content="\n".join(lines),
        )

    def _section_lineage(self) -> Optional[DocSection]:
        lines = [
            "## Dataflow Pipeline Topology",
            "",
            "The dataflow execution topology organizes data movement from raw physical data sources "
            "through staging transformations into the final semantic model tables.",
        ]
        return DocSection(
            section_id="tab-topology",
            title="Dataflow Pipeline Topology",
            nav_label="Topology",
            content="\n".join(lines),
        )
