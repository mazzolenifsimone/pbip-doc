"""
Modular Markdown Document Generator for DAX Measures.
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
    get_measure_table_map,
    resolve_model_index_url,
)
from ..dax_formatter import format_dax


class MeasureDocBuilder:
    """
    Builds modular markdown chapters for a single DAX measure in the semantic model.
    """

    def __init__(
        self,
        measure_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: Optional[DocGenConfig] = None,
        project_name: Optional[str] = None,
    ):
        self.measure = measure_data
        self.model = full_model
        self.config = config or DocGenConfig()
        self.project_name = clean_project_name(
            project_name or self.config.project_name or full_model.get("project_name") or full_model.get("model_name")
        )
        self.name = measure_data.get("name", "UnnamedMeasure")
        self.table = measure_data.get("table", "Model")
        self.depth = measure_data.get("calculation_depth", 0)
        self.dax = measure_data.get("dax_expression", "")
        self.format_string = measure_data.get("format_string")
        self.description = measure_data.get("description")
        self.direct_deps = measure_data.get("direct_measure_dependencies", [])
        self.all_upstream = measure_data.get("all_upstream_measures", [])
        self.downstream = measure_data.get("downstream_measures", [])
        self.referenced_functions = measure_data.get("referenced_functions", [])
        norm_cols = []
        for rc in measure_data.get("referenced_columns", []):
            if isinstance(rc, dict):
                t_name = rc.get("table", self.table)
                c_name = rc.get("column", "")
            elif isinstance(rc, (list, tuple)) and len(rc) >= 2:
                t_name, c_name = str(rc[0]), str(rc[1])
            elif isinstance(rc, str) and "[" in rc:
                t_name, c_name = rc.split("[", 1)
                c_name = c_name.rstrip("]")
            else:
                t_name, c_name = self.table, str(rc)
            if not self.config.is_table_excluded(t_name):
                norm_cols.append({"table": t_name, "column": c_name})
        self.referenced_cols = norm_cols
        self.referenced_tables = [
            t for t in measure_data.get("referenced_tables", [])
            if not self.config.is_table_excluded(t)
        ]
        self.measure_lookup = get_measure_lookup_map(full_model)
        self.measure_table_map = get_measure_table_map(full_model)

    def _is_measure_published(self, target_measure_name: str) -> bool:
        """Checks if a target measure is published as a dedicated markdown file."""
        target_m = self.measure_lookup.get(target_measure_name)
        if target_m:
            return self.config.is_measure_published(target_m)
        return True

    def _get_measure_link(self, target_measure_name: str) -> str:
        """Computes the relative or absolute markdown link to another measure file."""
        target_table = self.measure_table_map.get(target_measure_name, self.table)
        clean_target_tbl = sanitize_filename(target_table)
        clean_target_m = sanitize_filename(target_measure_name)
        if self.config.base_doc_url:
            meas_sub = self.config.measures_subdir.strip("/\\")
            if meas_sub:
                return join_doc_path(self.config.base_doc_url, meas_sub, clean_target_tbl, f"{clean_target_m}.md")
            return join_doc_path(self.config.base_doc_url, clean_target_tbl, f"{clean_target_m}.md")
        return f"../{clean_target_tbl}/{clean_target_m}.md"

    def _resolve_host_table_link(self) -> str:
        clean_tbl = sanitize_filename(self.table)
        host_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == self.table), None)
        tbl_published = self.config.is_table_published(host_tbl) if host_tbl else True
        if tbl_published and self.config.include_markdown_links:
            if self.config.base_doc_url:
                tables_sub = self.config.tables_subdir.strip("/\\")
                target_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
            else:
                target_url = f"../../tables/{clean_tbl}.md"
            return f"[{self.table}]({target_url})"
        ext_url = self.config.resolve_external_table_url(host_tbl) if host_tbl else None
        if ext_url and self.config.include_markdown_links:
            return f"[{self.table}]({ext_url}) *(Inherited Entity)*"
        badge = " *(Inherited Entity)*" if (host_tbl and host_tbl.get("is_inherited")) else ""
        return f"`{self.table}`{badge}"

    def build_markdown(self) -> str:
        """Assembles all enabled modular sections into a pristine Markdown document according to document layout."""
        frontmatter_str = self._build_frontmatter() if self.config.include_measure_yaml_frontmatter else None
        header_block = self._build_header_block()

        registry = {
            "description": self._section_description,
            "dax_formula": self._section_dax,
            "dax": self._section_dax,
            "referenced_columns": self._section_referenced_columns,
            "direct_dependencies": self._section_upstream,
            "upstream_dependencies": self._section_upstream,
            "upstream": self._section_upstream,
            "downstream_dependencies": self._section_downstream,
            "downstream": self._section_downstream,
            "details": self._section_tech_specs,
            "tech_specs": self._section_tech_specs,
            "rag": self._section_rag,
        }
        return render_document_markdown(
            doc_type="measure",
            frontmatter_str=frontmatter_str,
            header_block=header_block,
            registry=registry,
            config=self.config,

        )

    def _legacy_build_markdown(self) -> str:
        """Assembles all enabled modular sections into a pristine Markdown document (deterministic section order)."""
        frontmatter_str = self._build_frontmatter() if self.config.include_measure_yaml_frontmatter else None
        header_block = self._build_header_block()

        sections = [
            self._section_description(),
            self._section_dax(),
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
            "dax_measure",
            f"depth_{self.depth}",
            sanitize_filename(self.table),
            sanitize_filename(self.name),
        ]
        if self.project_name:
            tags.append(sanitize_filename(self.project_name))
        if self.depth == 0:
            tags.append("base_measure")
        else:
            tags.append("composite_measure")

        col_refs_str = [f"{rc.get('table')}[{rc.get('column')}]" for rc in self.referenced_cols]

        frontmatter_data = {
            "title": f"Measure: [{self.name}]",
            "pbip_project": self.project_name,
            "entity_name": self.name,
            "doc_type": "dax_measure",
            "table_name": self.table,
            "calculation_depth": self.depth,
            "is_base_measure": self.depth == 0,
            "is_inherited": self.measure.get("is_inherited", False),
            "is_external_measure": self.measure.get("is_external_measure", False),
            "out_of_scope": self.measure.get("out_of_scope", False),
            "description": self.description,
            "format_string": self.format_string or "Standard",
            "direct_dependencies": self.direct_deps,
            "all_upstream_dependencies": self.all_upstream,
            "referenced_functions": self.referenced_functions,
            "downstream_measures_count": len(self.downstream),
            "downstream_measures": self.downstream,
            "referenced_tables": self.referenced_tables,
            "referenced_columns": col_refs_str,
            "tags": tags,
        }
        return format_yaml_frontmatter(frontmatter_data)

    def _build_header_block(self) -> str:
        table_link = self._resolve_host_table_link()
        measures_sub = self.config.measures_subdir.strip("/\\")
        rel_dir = f"{measures_sub}/{sanitize_filename(self.table)}" if measures_sub else sanitize_filename(self.table)
        model_url = resolve_model_index_url(self.config, self.project_name, rel_dir)
        model_link = f"[{self.project_name}]({model_url})" if self.config.include_markdown_links else f"`{self.project_name}`"
        return "\n".join([
            f"# Measure: `[{self.name}]`",
            "",
            f"**Model**: {model_link} | **Home Table**: {table_link} | **Calculation Depth**: `Depth {self.depth}` | **Downstream Impact**: `{len(self.downstream)} Dependent Measures`",
        ])

    # 1. Description
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

        if self.measure.get("is_inherited") or self.measure.get("is_external_measure"):
            ext_url = self.config.resolve_external_measure_url(self.measure, self.model.get("tables", []))
            if ext_url and self.config.include_markdown_links:
                lines.append(f"> ℹ️ **External Measure**: This measure is declared via `EXTERNALMEASURE(...)` pointing to upstream measure [{self.name}]({ext_url}).")
            else:
                lines.append("> ℹ️ **External Measure**: This measure is declared via `EXTERNALMEASURE(...)` pointing to an upstream semantic model.")
            lines.append("")

        if self.depth == 0:
            lines.append(
                f"The measure **`[{self.name}]`** is a base-level metric that directly aggregates records "
                f"from the physical table `{self.table}` without intermediate measures."
            )
        else:
            lines.append(
                f"The measure **`[{self.name}]`** is a derived KPI of level {self.depth}. It combines or alters the evaluation "
                f"context of {len(self.direct_deps)} upstream measures ({', '.join(f'`[{d}]`' for d in self.direct_deps)})."
            )

        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content="\n".join(lines),
        )

    # 2. DAX
    def _section_dax(self) -> Optional[DocSection]:
        if not self.config.include_measure_dax_formula:
            return None

        dax_formatted = format_dax(
            self.dax,
            name=self.name,
            entity_type="measure",
            table_name=self.table,
        )
        content = "\n".join([
            "## DAX Formula",
            "```dax",
            dax_formatted,
            "```",
        ])
        return DocSection(
            section_id="tab-dax",
            title="DAX",
            nav_label="DAX",
            content=content,
        )

    # 3. Referenced Columns
    def _section_referenced_columns(self) -> Optional[DocSection]:
        if not self.config.include_measure_referenced_columns:
            return None

        lines = ["## Referenced Physical Columns & Tables"]

        if self.referenced_cols:
            lines.append("The DAX formula directly accesses the following fields from the data model:")
            lines.append("")
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
                        t_url = f"../../tables/{clean_tbl}.md"
                    table_link = f"[{tbl}]({t_url})"
                elif not tbl_pub:
                    ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        table_link = f"[{tbl}]({ext_url}) *(Inherited Entity)*"
                    else:
                        table_link = f"`{tbl}` *(Inherited Entity)*" if (target_tbl and target_tbl.get("is_inherited")) else f"`{tbl}`"
                else:
                    table_link = f"`{tbl}`"
                lines.append(f"- Table {table_link} ➔ Column `{col}`")
        elif self.referenced_tables:
            lines.append("The DAX formula references the following tables:")
            lines.append("")
            for tbl in self.referenced_tables:
                clean_tbl = sanitize_filename(tbl)
                target_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == tbl), None)
                tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
                if tbl_pub and self.config.include_markdown_links:
                    if self.config.base_doc_url:
                        tables_sub = self.config.tables_subdir.strip("/\\")
                        t_url = join_doc_path(self.config.base_doc_url, tables_sub, f"{clean_tbl}.md") if tables_sub else join_doc_path(self.config.base_doc_url, f"{clean_tbl}.md")
                    else:
                        t_url = f"../../tables/{clean_tbl}.md"
                    table_link = f"[{tbl}]({t_url})"
                elif not tbl_pub:
                    ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                    if ext_url and self.config.include_markdown_links:
                        table_link = f"[{tbl}]({ext_url}) *(Inherited Entity)*"
                    else:
                        table_link = f"`{tbl}` *(Inherited Entity)*" if (target_tbl and target_tbl.get("is_inherited")) else f"`{tbl}`"
                else:
                    table_link = f"`{tbl}`"
                lines.append(f"- Table {table_link}")
        else:
            lines.append("- *No physical or calculated columns directly referenced.*")

        return DocSection(
            section_id="tab-cols",
            title="Referenced Columns",
            nav_label=f"Referenced Columns ({len(self.referenced_cols)})",
            content="\n".join(lines),
        )

    # 4. Upstream Dependency
    def _section_upstream(self) -> Optional[DocSection]:
        if not self.config.include_measure_upstream_deps:
            return None

        lines = ["## Upstream Calculation Tree (Direct and Transitive Dependencies)"]

        if not self.direct_deps:
            lines.append(
                "- **Dependencies on other Measures**: None (Terminal base measure computed directly over physical columns)."
            )
        else:
            lines.append("### Directly Referenced Measures:")
            for dep in self.direct_deps:
                dep_m = self.measure_lookup.get(dep)
                if self._is_measure_published(dep) and self.config.include_markdown_links:
                    meas_link = self._get_measure_link(dep)
                    link = f"[{dep}]({meas_link})"
                else:
                    ext_url = self.config.resolve_external_measure_url(dep_m, self.model.get("tables", [])) if dep_m else None
                    if ext_url and self.config.include_markdown_links:
                        link = f"[{dep}]({ext_url}) *(External Measure)*"
                    else:
                        badge = " *(External Measure)*" if (dep_m and (dep_m.get("is_inherited") or dep_m.get("is_external_measure"))) else ""
                        link = f"`[{dep}]`{badge}"
                lines.append(f"- {link}")

            if len(self.all_upstream) > len(self.direct_deps):
                lines.append("")
                lines.append("### Full Transitive Closure (All recursively upstream measures):")
                for u in self.all_upstream:
                    u_m = self.measure_lookup.get(u)
                    if self._is_measure_published(u) and self.config.include_markdown_links:
                        meas_link = self._get_measure_link(u)
                        link = f"[{u}]({meas_link})"
                    else:
                        ext_url = self.config.resolve_external_measure_url(u_m, self.model.get("tables", [])) if u_m else None
                        if ext_url and self.config.include_markdown_links:
                            link = f"[{u}]({ext_url}) *(External Measure)*"
                        else:
                            badge = " *(External Measure)*" if (u_m and (u_m.get("is_inherited") or u_m.get("is_external_measure"))) else ""
                            link = f"`[{u}]`{badge}"
                    lines.append(f"- {link}")

        if self.referenced_functions:
            lines.append("")
            lines.append("### Referenced User-Defined Functions (UDFs):")
            lines.append("This measure invokes the following custom model functions defined in `functions.tmdl`:")
            for fn_name in self.referenced_functions:
                sanitized_fn = sanitize_filename(fn_name)
                if self.config.base_doc_url:
                    functions_sub = self.config.functions_subdir.strip("/\\")
                    fn_url = join_doc_path(self.config.base_doc_url, functions_sub, f"{sanitized_fn}.md") if functions_sub else join_doc_path(self.config.base_doc_url, f"{sanitized_fn}.md")
                else:
                    fn_url = f"../../functions/{sanitized_fn}.md"
                fn_link = f"[`{fn_name}`]({fn_url})" if self.config.include_markdown_links else f"`{fn_name}`"
                lines.append(f"- {fn_link}")

        total_upstream = len(self.direct_deps) + len(self.referenced_functions)
        return DocSection(
            section_id="tab-upstream",
            title="Upstream Dependency",
            nav_label=f"Upstream ({total_upstream})",
            content="\n".join(lines),
        )

    # 5. Downstream Dependency
    def _section_downstream(self) -> Optional[DocSection]:
        if not self.config.include_measure_downstream_impact:
            return None

        lines = [
            "## Downstream Impact Analysis (Where Used)",
            "",
        ]

        if not self.downstream:
            lines.append(
                "This measure is **not referenced by any other DAX measures**. "
                "It serves as an end-user indicator exposed directly to reports, visual cards, or dashboards."
            )
        else:
            lines.append(
                f"⚠️ **Impact Warning**: Modifying the logic or data type of this measure will directly affect **{len(self.downstream)}** downstream measures:"
            )
            lines.append("")
            for child in sorted(self.downstream):
                child_link = self._get_measure_link(child)
                link = f"[{child}]({child_link})" if self.config.include_markdown_links else f"`[{child}]`"
                lines.append(f"- {link}")

        return DocSection(
            section_id="tab-downstream",
            title="Downstream Dependency",
            nav_label=f"Downstream ({len(self.downstream)})",
            content="\n".join(lines),
        )

    def _get_depth_label(self) -> str:
        return (
            "Base Measure (Depth 0 - direct calculation over physical columns)"
            if self.depth == 0
            else f"Composite Measure (Depth {self.depth} - calculated over other measures)"
        )

    # 6. Technical Specifications
    def _section_tech_specs(self) -> DocSection:
        depth_label = self._get_depth_label()
        model_key = self.measure.get("model_key", f"{self.table}[{self.name}]")
        table_link = self._resolve_host_table_link()
        disp_folder = self.measure.get("display_folder") or self.measure.get("displayFolder") or "—"
        fmt_str = f"`{self.format_string}`" if self.format_string else "—"
        hidden_str = "Yes" if self.measure.get("is_hidden") else "No"
        ext_str = "Yes" if self.measure.get("is_external_measure") else "No"

        lines = [
            "## Technical Specifications",
            "",
            "| Property | Value |",
            "| :--- | :--- |",
            f"| **Model Key** | `{model_key}` |",
            f"| **Host Table** | {table_link} |",
            f"| **Calculation Depth** | `Depth {self.depth}` |",
            f"| **DAG Hierarchy** | `{depth_label}` |",
            f"| **Display Folder** | `{disp_folder}` |",
            f"| **Format String** | {fmt_str} |",
            f"| **Hidden in View Mode** | `{hidden_str}` |",
            f"| **External Bound (Composite)** | `{ext_str}` |",
        ]
        return DocSection(
            section_id="tab-tech",
            title="Technical Specifications",
            nav_label="Technical Specifications",
            content="\n".join(lines),
        )

    # 7. Semantic Context for AI & RAG (always after Technical Specifications)
    def _section_rag(self) -> Optional[DocSection]:
        if not self.config.include_measure_rag_hints:
            return None

        lines = [
            "## Semantic Context for AI & RAG",
            "",
            "Semantic retrieval guidance for AI assistants and Vector Search engines:",
            "",
            f"- **Business Concept**: `{self.name}` within the `{self.table}` domain.",
            f"- **Complexity Level**: Level {self.depth} in the Directed Acyclic Graph (DAG).",
            "- **Common Business Questions Answered by This Measure**:",
            f"  - What is the value or trend of `{self.name}`?",
            f"  - How is `{self.name}` calculated in the semantic model?",
            f"  - Which underlying metrics contribute to `{self.name}`?",
        ]

        if self.downstream:
            lines.append(f"  - If the logic of `{self.name}` changes, which other measures will be affected?")

        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content="\n".join(lines),
        )
