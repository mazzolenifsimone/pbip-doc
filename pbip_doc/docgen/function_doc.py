"""
Modular Markdown Document Generator for DAX User-Defined Functions (UDFs).
Follows the unified Section-Driven modular architecture.
Optimized for dual consumption: human readability + AI RAG semantic search.
100% Python Standard Library.
"""

from typing import Dict, Any, List, Optional
from .config import DocGenConfig
from .section_engine import DocSection, assemble_markdown_document
from .layout_engine import render_document_markdown
from .utils import (
    format_yaml_frontmatter,
    sanitize_filename,
    join_doc_path,
    clean_project_name,
    get_measure_lookup_map,
    resolve_model_index_url,
)
from ..dax_formatter import format_dax


class FunctionDocBuilder:
    """
    Builds modular markdown chapters for a single DAX User-Defined Function (UDF).
    """

    def __init__(
        self,
        function_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        project_name: Optional[str] = None,
    ):
        self.fn = function_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.project_name = clean_project_name(
            project_name or self.config.project_name or full_model.get("project_name") or full_model.get("model_name")
        )
        self.name = function_data.get("name", "UnnamedFunction")
        self.expression = function_data.get("expression", "")
        self.parameters = function_data.get("parameters", [])
        self.signature = function_data.get("parameters_signature", "()")
        self.return_type = (function_data.get("return_type") or "").strip() or "Variant"
        self.description = function_data.get("description")
        self.downstream_measures = function_data.get("downstream_measures", [])
        self.downstream_functions = function_data.get("downstream_functions", [])
        self.referenced_functions = function_data.get("referenced_functions", [])
        self.referenced_cols = [
            rc for rc in function_data.get("referenced_columns", [])
            if not self.config.is_table_excluded(rc.get("table", ""))
        ]
        self.referenced_tables = [
            t for t in function_data.get("referenced_tables", [])
            if not self.config.is_table_excluded(t)
        ]

    def build_markdown(self) -> str:
        """Assembles all enabled modular sections into a pristine Markdown document according to document layout."""
        frontmatter_str = self._build_frontmatter() if self.config.include_function_yaml_frontmatter else None
        header_block = self._build_header_block()

        registry = {
            "description": self._section_description,
            "parameters": self._section_parameters,
            "dax_formula": self._section_dax_formula,
            "referenced_columns": self._section_referenced_columns,
            "upstream_dependency": self._section_upstream,
            "upstream": self._section_upstream,
            "downstream_dependents": self._section_downstream,
            "downstream": self._section_downstream,
            "details": self._section_tech_specs,
            "tech_specs": self._section_tech_specs,
            "rag": self._section_rag,
        }
        return render_document_markdown(
            doc_type="function",
            frontmatter_str=frontmatter_str,
            header_block=header_block,
            registry=registry,
            config=self.config,

        )

    def _legacy_build_markdown(self) -> str:
        """Assembles all enabled modular sections into a pristine Markdown document (deterministic section order)."""
        frontmatter_str = self._build_frontmatter() if self.config.include_function_yaml_frontmatter else None
        header_block = self._build_header_block()

        sections = [
            self._section_udf_definition(),
            self._section_referenced_columns(),
            self._section_upstream(),
            self._section_downstream(),
            self._section_tech_specs(),
            self._section_rag(),
        ]
        return assemble_markdown_document(frontmatter_str, header_block, sections)

    def _build_frontmatter(self) -> str:
        """Constructs YAML frontmatter for RAG indexing and cataloging."""
        tags = [
            "semantic_model",
            "dax_udf_function",
            sanitize_filename(self.name),
        ]
        if self.project_name:
            tags.append(sanitize_filename(self.project_name))
        if not self.downstream_measures:
            tags.append("unused_function")
        else:
            tags.append("active_function")

        param_names = [p.get("name") for p in self.parameters if p.get("name")]

        frontmatter_data = {
            "title": f"Function: {self.name}",
            "pbip_project": self.project_name,
            "entity_name": self.name,
            "doc_type": "dax_udf_function",
            "return_type": self.return_type,
            "parameters_count": len(self.parameters),
            "parameters_signature": self.signature,
            "parameter_names": param_names,
            "downstream_measures_count": len(self.downstream_measures),
            "downstream_measures": self.downstream_measures,
            "downstream_functions": self.downstream_functions,
            "referenced_functions": self.referenced_functions,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_header_block(self) -> str:
        sig_display = f"`{self.name}{self.signature}`"
        model_url = resolve_model_index_url(self.config, self.project_name, self.config.functions_subdir)
        model_link = f"[{self.project_name}]({model_url})" if self.config.include_markdown_links else f"`{self.project_name}`"
        return "\n".join([
            f"# Function: `{self.name}`",
            "",
            f"**Model**: {model_link} | **Signature**: {sig_display} | **Return Type**: `{self.return_type}` | **Downstream Dependent Measures**: `{len(self.downstream_measures)}`",
        ])

    # 1a. Description
    def _section_description(self) -> DocSection:
        lines = [
            "## Description",
            "",
        ]
        if self.description:
            lines.append(f"> {self.description}")
        else:
            lines.append("*No description provided.*")
        lines.append("")

        lines.append(
            f"The User-Defined Function (UDF) **`{self.name}`** provides encapsulated, reusable DAX calculation logic "
            "defined at the semantic model level. It standardizes formulas across measures and enforces uniform evaluation rules."
        )

        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content="\n".join(lines),
        )

    # 1b. Parameters & Arguments
    def _section_parameters(self) -> Optional[DocSection]:
        if not self.config.include_function_parameters_section or not self.parameters:
            return None

        lines = [
            f"## Parameters & Arguments ({len(self.parameters)} parameters)",
            "",
            "| Parameter | Data Type | Optional | Default Value | Description |",
            "| :--- | :---: | :---: | :--- | :--- |",
        ]
        for p in self.parameters:
            raw_p_name = str(p.get("name") or "").strip().strip("`")
            p_name = f"`{raw_p_name}`"
            p_type = f"`{p.get('data_type')}`" if p.get("data_type") else "Variant"
            p_opt = "Yes" if p.get("is_optional") else "No (Required)"
            p_def = f"`{p.get('default_value')}`" if p.get("default_value") is not None else "—"
            p_desc = p.get("description") or "—"
            lines.append(f"| {p_name} | {p_type} | {p_opt} | {p_def} | {p_desc} |")

        return DocSection(
            section_id="tab-params",
            title="Parameters & Arguments",
            nav_label="Parameters",
            content="\n".join(lines),
        )

    # 1c. Implementation Formula
    def _section_dax_formula(self) -> Optional[DocSection]:
        if not self.config.include_function_formula_section:
            return None

        formatted_dax = format_dax(
            self.expression,
            name=self.name,
            entity_type="function",
            parameters_signature=self.signature,
        )
        lines = [
            "## Implementation Formula",
            "```dax",
            formatted_dax,
            "```",
        ]

        return DocSection(
            section_id="tab-dax",
            title="Implementation Formula",
            nav_label="DAX Formula",
            content="\n".join(lines),
        )

    # 1. Unified UDF Definition (Legacy aggregator for _legacy_build_markdown)
    def _section_udf_definition(self) -> DocSection:
        parts = [
            sec.content
            for sec in (self._section_description(), self._section_parameters(), self._section_dax_formula())
            if sec and sec.content
        ]
        return DocSection(
            section_id="tab-desc",
            title="UDF Definition",
            nav_label="UDF Definition",
            content="\n\n".join(parts),
        )

    # 2. Referenced Columns
    def _section_referenced_columns(self) -> DocSection:
        lines = [
            "## Referenced Physical Columns & Tables",
            "",
        ]
        if self.referenced_cols:
            for rc in self.referenced_cols:
                tbl = rc.get("table", "")
                col = rc.get("column", "")
                clean_tbl = sanitize_filename(tbl)
                target_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == tbl), None)
                tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
                if tbl_pub and self.config.include_markdown_links:
                    if self.config.base_doc_url:
                        tables_sub = self.config.tables_subdir.strip("/\\")
                        t_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
                    else:
                        t_url = f"../tables/{clean_tbl}.md"
                    tbl_link = f"[{tbl}]({t_url})"
                elif not tbl_pub:
                    ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        tbl_link = f"[{tbl}]({ext_url}) *(Inherited Entity)*"
                    else:
                        tbl_link = f"`{tbl}` *(Inherited Entity)*" if (target_tbl and target_tbl.get("is_inherited")) else f"`{tbl}`"
                else:
                    tbl_link = f"`{tbl}`"
                lines.append(f"- Table {tbl_link} ➔ Column `{col}`")
        elif self.referenced_tables:
            for tbl in self.referenced_tables:
                clean_tbl = sanitize_filename(tbl)
                target_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == tbl), None)
                tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
                if tbl_pub and self.config.include_markdown_links:
                    if self.config.base_doc_url:
                        tables_sub = self.config.tables_subdir.strip("/\\")
                        t_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
                    else:
                        t_url = f"../tables/{clean_tbl}.md"
                    tbl_link = f"[{tbl}]({t_url})"
                elif not tbl_pub:
                    ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        tbl_link = f"[{tbl}]({ext_url}) *(Inherited Entity)*"
                    else:
                        tbl_link = f"`{tbl}` *(Inherited Entity)*" if (target_tbl and target_tbl.get("is_inherited")) else f"`{tbl}`"
                else:
                    tbl_link = f"`{tbl}`"
                lines.append(f"- Table {tbl_link}")
        else:
            lines.append("- *No physical columns or tables directly referenced.*")

        return DocSection(
            section_id="tab-cols",
            title="Referenced Columns",
            nav_label=f"Referenced Columns ({len(self.referenced_cols)})",
            content="\n".join(lines),
        )

    # 3. Upstream Dependency
    def _section_upstream(self) -> DocSection:
        lines = [
            "## Upstream Dependencies",
            "",
        ]
        if self.referenced_functions:
            lines.append("### Referenced UDF Functions:")
            for fn_dep in self.referenced_functions:
                sanitized = sanitize_filename(fn_dep)
                if self.config.base_doc_url:
                    fn_sub = self.config.functions_subdir.strip("/\\")
                    fn_url = join_doc_path(self.config.base_doc_url, fn_sub, f"{sanitized}.md") if fn_sub else join_doc_path(self.config.base_doc_url, f"{sanitized}.md")
                else:
                    fn_url = f"{sanitized}.md"
                link = f"[{fn_dep}]({fn_url})" if self.config.include_markdown_links else f"`{fn_dep}`"
                lines.append(f"- {link}")
        else:
            lines.append("- *No upstream UDF functions referenced.*")

        return DocSection(
            section_id="tab-upstream",
            title="Upstream Dependency",
            nav_label=f"Upstream ({len(self.referenced_functions)})",
            content="\n".join(lines),
        )

    # 4. Downstream Dependency
    def _section_downstream(self) -> Optional[DocSection]:
        if not self.config.include_function_downstream_section:
            return None

        total_downstream = len(self.downstream_measures) + len(self.downstream_functions)
        lines = [
            "## Downstream Impact Analysis (Where Used)",
            "",
        ]

        if not self.downstream_measures and not self.downstream_functions:
            lines.append(
                "This function is currently **not invoked by any DAX measures or functions** in the semantic model. "
                "It is available in `functions.tmdl` for future measure calculations."
            )
        else:
            lines.append(
                f"⚠️ **Impact Warning**: Modifying the logic, parameter types, or return value of this function will directly "
                f"affect **{total_downstream}** downstream model objects."
            )
            lines.append("")

            if self.downstream_measures:
                lines.append(f"### Directly Dependent Measures ({len(self.downstream_measures)}):")
                lines.append("")
                lines.append("| Measure | Home Table | DAG Depth | Document Link |")
                lines.append("| :--- | :--- | :---: | :--- |")

                measure_lookup = get_measure_lookup_map(self.model)
                for m_name in sorted(self.downstream_measures):
                    m_info = measure_lookup.get(m_name, {})
                    tbl = m_info.get("table", "Model")
                    clean_tbl = sanitize_filename(tbl)
                    depth = f"Depth {m_info.get('calculation_depth', 0)}"
                    sanitized = sanitize_filename(m_name)
                    if self.config.base_doc_url:
                        meas_sub = self.config.measures_subdir.strip("/\\")
                        m_url = join_doc_path(self.config.base_doc_url, meas_sub, clean_tbl, f"{sanitized}.md") if meas_sub else join_doc_path(self.config.base_doc_url, clean_tbl, f"{sanitized}.md")
                    else:
                        m_url = f"../measures/{clean_tbl}/{sanitized}.md"
                    link = f"[`[{m_name}]`]({m_url})" if self.config.include_markdown_links else f"`[{m_name}]`"
                    doc_link = f"[View Measure Document]({m_url})" if self.config.include_markdown_links else "—"
                    lines.append(f"| {link} | `{tbl}` | {depth} | {doc_link} |")

            if self.downstream_functions:
                lines.append("")
                lines.append(f"### Directly Dependent Functions ({len(self.downstream_functions)}):")
                for fn_child in sorted(self.downstream_functions):
                    sanitized = sanitize_filename(fn_child)
                    if self.config.base_doc_url:
                        fn_sub = self.config.functions_subdir.strip("/\\")
                        fn_url = join_doc_path(self.config.base_doc_url, fn_sub, f"{sanitized}.md") if fn_sub else join_doc_path(self.config.base_doc_url, f"{sanitized}.md")
                    else:
                        fn_url = f"{sanitized}.md"
                    fn_link = f"[{fn_child}]({fn_url})" if self.config.include_markdown_links else f"`{fn_child}`"
                    lines.append(f"- {fn_link}")

        return DocSection(
            section_id="tab-downstream",
            title="Downstream Dependency",
            nav_label=f"Downstream ({total_downstream})",
            content="\n".join(lines),
        )

    # 5. Technical Specifications
    def _section_tech_specs(self) -> DocSection:
        lines = [
            "## Technical Specifications",
            "",
            "| Property | Value |",
            "| :--- | :--- |",
            f"| **Function Name** | `{self.name}` |",
            f"| **Signature** | `{self.name}{self.signature}` |",
            f"| **Return Type** | `{self.return_type}` |",
            f"| **Parameters Count** | `{len(self.parameters)}` |",
            f"| **Downstream Dependent Measures** | `{len(self.downstream_measures)}` |",
        ]
        return DocSection(
            section_id="tab-tech",
            title="Technical Specifications",
            nav_label="Technical Specifications",
            content="\n".join(lines),
        )

    # 6. Semantic Context for AI & RAG (always after Technical Specifications)
    def _section_rag(self) -> Optional[DocSection]:
        if not self.config.include_function_rag_hints:
            return None

        param_desc = ", ".join(f"`{p.get('name')}`" for p in self.parameters) or "No parameters"
        lines = [
            "## Semantic Context for AI & RAG",
            "",
            "Semantic retrieval guidance for AI assistants and Vector Search engines:",
            "",
            f"- **Entity Represented**: DAX User-Defined Function (UDF) named `{self.name}`.",
            f"- **Signature & Contract**: Returns `{self.return_type}` given parameters ({param_desc}).",
            "- **Common Business Questions Answered by This Function**:",
            f"  - What does the function `{self.name}` compute in the semantic model?",
            f"  - What input parameters are required to invoke `{self.name}`?",
            f"  - Which measures or KPIs depend on `{self.name}`?",
        ]

        if self.downstream_measures:
            lines.append(
                f"  - If the logic of `{self.name}` is changed, which measures are impacted? ({', '.join(f'`[{m}]`' for m in self.downstream_measures[:5])}{'...' if len(self.downstream_measures) > 5 else ''})"
            )

        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content="\n".join(lines),
        )
