"""
HTML Documentation Generator Engine.
Coordinates HtmlLayoutBuilder, HtmlIndexBuilder, HtmlTableBuilder, HtmlMeasureBuilder,
and HtmlVisualBuilder to produce a complete, interactive, self-contained enterprise wiki portal.
100% Vanilla Python standard library.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Union, Optional

from .config import DocGenConfig
from .html_layout import HtmlLayoutBuilder, get_relative_root
from .html_builders import (
    HtmlIndexBuilder,
    HtmlTableBuilder,
    HtmlMeasureBuilder,
    HtmlVisualBuilder,
    HtmlExpressionBuilder,
    HtmlFunctionBuilder,
    HtmlDataflowOverviewBuilder,
)
from .html_assets import STYLE_CSS
from .visual_doc import PageVisualDocBuilder
from .relationship_diagram import RelationshipSvgGenerator
from .utils import sanitize_filename, clean_project_name
from ..report_parser import ReportParser
from ..report_schema import PBIPReportModel


class HtmlDocGenerator:
    """
    Main entry point for generating native, interactive HTML wiki documentation
    from PBIP semantic model metadata and report visual presentations.
    """

    def __init__(self, config: Optional[DocGenConfig] = None):
        self.config = config or DocGenConfig()

    def generate_all_documents(
        self,
        model_data: Union[Dict[str, Any], str, Path],
        layout_override: Optional[Any] = None,
        base_prefix: str = "",
    ) -> Dict[str, str]:
        """
        Generates in-memory dictionary of all HTML documents and static assets:
        {
          "index.html": content,
          "assets/style.css": content,
          "tables/FactInternetSales.html": content,
          "measures/Sales/Total_Sales.html": content,
          ...
        }
        """
        data = self._load_model_dict(model_data)
        report_model = self._resolve_report(model_data)
        project_name = self._resolve_project_name(model_data, data, report_model)
        data["project_name"] = project_name
        if hasattr(model_data, "workspace_models"):
            data["workspace_models"] = getattr(model_data, "workspace_models")
        elif hasattr(self.config, "workspace_models"):
            data["workspace_models"] = getattr(self.config, "workspace_models")

        if hasattr(model_data, "bound_reports_info"):
            data["bound_reports_info"] = getattr(model_data, "bound_reports_info")
        if hasattr(model_data, "bound_reports_count"):
            data["bound_reports_count"] = getattr(model_data, "bound_reports_count")
        documents: Dict[str, str] = {}

        # 1. Static Assets (CSS only - 100% Zero-JS) - only if standalone root
        if not layout_override:
            documents["assets/style.css"] = STYLE_CSS

        # Layout wrapper
        layout = layout_override or HtmlLayoutBuilder(
            project_name=project_name,
            data=data,
            config=self.config,
            report_model=report_model,
        )

        bp = f"{base_prefix.strip('/')}/" if base_prefix.strip('/') else ""

        # 2. Master Catalog (index page)
        if self.config.generate_index_file and self.config.include_models:
            idx_builder = HtmlIndexBuilder(data, self.config, report_model=report_model, project_name=project_name)
            idx_content = idx_builder.build_content()
            doc_path = f"{bp}index{self.config.html_ext_suffix}"
            rel_root = get_relative_root(doc_path)
            breadcrumbs = [("Workspace", f"{rel_root}/index{self.config.html_ext_suffix}"), (project_name, None)] if base_prefix else [("Home", None)]
            idx_html = layout.wrap_page(
                current_path=doc_path,
                page_title="Model Overview",
                breadcrumbs=breadcrumbs,
                content_html=idx_content,
            )
            documents[doc_path] = idx_html

        # 3. Dataflow Documents (Dataflow Overview + Ingested Tables + Shared Queries)
        if self.config.include_dataflow and self.config.include_expression_docs:
            expressions_sub = self.config.expressions_subdir.strip("/\\")

            # 3a. ETL Overview (etl/index page)
            df_builder = HtmlDataflowOverviewBuilder(data, self.config, project_name=project_name)
            df_content = df_builder.build_content()
            df_doc_path = f"{bp}{expressions_sub}/index{self.config.html_ext_suffix}" if expressions_sub else f"{bp}index_dataflow{self.config.html_ext_suffix}"
            df_rel_root = get_relative_root(df_doc_path)
            if base_prefix:
                df_breadcrumbs = [
                    ("Workspace", f"{df_rel_root}/index{self.config.html_ext_suffix}"),
                    (project_name, f"{df_rel_root}/{base_prefix}/index{self.config.html_ext_suffix}"),
                    ("ETL", None),
                ]
            else:
                df_breadcrumbs = [("Home", f"{df_rel_root}/index{self.config.html_ext_suffix}"), ("ETL", None)]

            df_html = layout.wrap_page(
                current_path=df_doc_path,
                page_title="ETL Overview",
                breadcrumbs=df_breadcrumbs,
                content_html=df_content,
            )
            documents[df_doc_path] = df_html

            # 3b. Loaded Model Tables (under expressions/<Table>.html)
            tables_list = [t for t in data.get("tables", []) if self.config.is_table_published(t)]
            dataflow_tables = [
                t for t in tables_list
                if (
                    t.get("source_type", "PowerQuery") == "PowerQuery"
                    or bool(t.get("power_query_lineage") and t.get("power_query_lineage", {}).get("full_m_expression"))
                )
                and t.get("source_type") not in ("CalculatedTable", "CalculationGroup")
                and (t.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
            ]
            for tbl in dataflow_tables:
                t_name = tbl.get("name")
                clean_name = sanitize_filename(t_name)
                lineage = tbl.get("power_query_lineage") or {}
                raw_m = lineage.get("full_m_expression") or tbl.get("power_query_expression") or tbl.get("m_code") or ""
                expr_data = {
                    "query_name": t_name,
                    "name": t_name,
                    "description": tbl.get("description"),
                    "target_table": t_name,
                    "is_staging": False,
                    "is_loaded_table": True,
                    "expression_kind": "table",
                    "source_type": tbl.get("source_type", "PowerQuery"),
                    "full_m_expression": raw_m,
                    "steps": lineage.get("steps", []),
                    "merges": lineage.get("merges", []),
                    "unused_steps": lineage.get("unused_steps", []),
                    "direct_dependencies": lineage.get("direct_dependencies", []),
                    "all_upstream_queries": lineage.get("all_upstream_queries") or tbl.get("upstream_queries_chain", []),
                    "downstream_queries": lineage.get("downstream_queries", []),
                    "downstream_tables": [t_name],
                    "root_sources": lineage.get("root_sources") or tbl.get("root_data_sources", []),
                    "is_inline_table": lineage.get("is_inline_table", False),
                    "inline_table_columns": lineage.get("inline_table_columns", []),
                    "inline_table_column_types": lineage.get("inline_table_column_types", {}),
                    "inline_table_rows": lineage.get("inline_table_rows", []),
                    "inline_table_markdown": lineage.get("inline_table_markdown"),
                    "query_group": tbl.get("query_group"),
                    "lineage_tag": tbl.get("lineage_tag"),
                }
                expr_builder = HtmlExpressionBuilder(expr_data, data, self.config, project_name=project_name)
                expr_filename = f"{clean_name}{self.config.html_ext_suffix}"
                rel_doc = f"{expressions_sub}/{expr_filename}" if expressions_sub else expr_filename
                doc_path = f"{bp}{rel_doc}"
                rel_root = get_relative_root(doc_path)
                expr_content = expr_builder.build_content()

                overview_url = f"{rel_root}/{base_prefix}/{expressions_sub}/index{self.config.html_ext_suffix}" if base_prefix else f"{rel_root}/{expressions_sub}/index{self.config.html_ext_suffix}"
                if base_prefix:
                    breadcrumbs = [
                        ("Workspace", f"{rel_root}/index{self.config.html_ext_suffix}"),
                        (project_name, f"{rel_root}/{base_prefix}/index{self.config.html_ext_suffix}"),
                        ("ETL", overview_url),
                        (t_name, None),
                    ]
                else:
                    breadcrumbs = [("Home", f"{rel_root}/index{self.config.html_ext_suffix}"), ("ETL", overview_url), (t_name, None)]

                expr_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"ETL: {t_name}",
                    breadcrumbs=breadcrumbs,
                    content_html=expr_content,
                )
                documents[doc_path] = expr_html

            # 3c. Shared Staging Queries, Parameters, Functions
            expr_list = data.get("expressions") or data.get("shared_queries") or []
            existing_tbl_names = {t.get("name") for t in dataflow_tables}
            for expr in expr_list:
                q_name = expr.get("query_name") or "expression"
                if q_name in existing_tbl_names:
                    continue  # already rendered as loaded table
                clean_name = sanitize_filename(q_name)
                expr_builder = HtmlExpressionBuilder(expr, data, self.config, project_name=project_name)
                expr_filename = f"{clean_name}{self.config.html_ext_suffix}"
                rel_doc = f"{expressions_sub}/{expr_filename}" if expressions_sub else expr_filename
                doc_path = f"{bp}{rel_doc}"
                rel_root = get_relative_root(doc_path)

                expr_content = expr_builder.build_content()
                overview_url = f"{rel_root}/{base_prefix}/{expressions_sub}/index{self.config.html_ext_suffix}" if base_prefix else f"{rel_root}/{expressions_sub}/index{self.config.html_ext_suffix}"
                if base_prefix:
                    breadcrumbs = [
                        ("Workspace", f"{rel_root}/index{self.config.html_ext_suffix}"),
                        (project_name, f"{rel_root}/{base_prefix}/index{self.config.html_ext_suffix}"),
                        ("ETL", overview_url),
                        (q_name, None),
                    ]
                else:
                    breadcrumbs = [("Home", f"{rel_root}/index{self.config.html_ext_suffix}"), ("ETL", overview_url), (q_name, None)]

                expr_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"ETL: {q_name}",
                    breadcrumbs=breadcrumbs,
                    content_html=expr_content,
                )
                documents[doc_path] = expr_html

        # 4. Table Documents (Model - tables/<Table>.<ext>)
        if self.config.include_models:
            tables_sub = self.config.tables_subdir.strip("/\\")
            for table in data.get("tables", []):
                if not self.config.is_table_published(table):
                    continue
                tbl_name = table.get("name")
                clean_tbl_name = sanitize_filename(tbl_name)
                tbl_builder = HtmlTableBuilder(table, data, self.config, project_name=project_name)
                tbl_filename = f"{clean_tbl_name}{self.config.html_ext_suffix}"
                rel_doc = f"{tables_sub}/{tbl_filename}" if tables_sub else tbl_filename
                doc_path = f"{bp}{rel_doc}"
                rel_root = get_relative_root(doc_path)

                tbl_content = tbl_builder.build_content()
                if base_prefix:
                    breadcrumbs = [
                        ("Workspace", f"{rel_root}/index{self.config.html_ext_suffix}"),
                        (project_name, f"{rel_root}/{base_prefix}/index{self.config.html_ext_suffix}"),
                        ("Tables", None),
                        (tbl_name, None),
                    ]
                else:
                    breadcrumbs = [("Home", f"{rel_root}/index{self.config.html_ext_suffix}"), ("Tables", None), (tbl_name, None)]

                tbl_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"Table: {tbl_name}",
                    breadcrumbs=breadcrumbs,
                    content_html=tbl_content,
                )
                documents[doc_path] = tbl_html

        # 5. Measure Documents (Model - measures/<Table>/<Measure>.<ext>)
        if self.config.include_models:
            measures_sub = self.config.measures_subdir.strip("/\\")
            for measure in data.get("measures", []):
                if not self.config.is_measure_published(measure):
                    continue
                meas_tbl = measure.get("table", "Model")
                meas_name = measure.get("name", "Measure")
                clean_tbl_name = sanitize_filename(meas_tbl)
                clean_name = sanitize_filename(meas_name)
                meas_builder = HtmlMeasureBuilder(measure, data, self.config, project_name=project_name)
                meas_filename = f"{clean_name}{self.config.html_ext_suffix}"
                if measures_sub:
                    rel_doc = f"{measures_sub}/{clean_tbl_name}/{meas_filename}"
                else:
                    rel_doc = f"{clean_tbl_name}/{meas_filename}"
                doc_path = f"{bp}{rel_doc}"
                rel_root = get_relative_root(doc_path)

                meas_content = meas_builder.build_content()
                tbl_doc_url = f"{rel_root}/{bp}{tables_sub}/{clean_tbl_name}{self.config.html_ext_suffix}" if tables_sub else f"{rel_root}/{bp}{clean_tbl_name}{self.config.html_ext_suffix}"
                if base_prefix:
                    breadcrumbs = [
                        ("Workspace", f"{rel_root}/index{self.config.html_ext_suffix}"),
                        (project_name, f"{rel_root}/{base_prefix}/index{self.config.html_ext_suffix}"),
                        ("Measures", None),
                        (meas_tbl, tbl_doc_url),
                        (meas_name, None),
                    ]
                else:
                    breadcrumbs = [
                        ("Home", f"{rel_root}/index{self.config.html_ext_suffix}"),
                        ("Measures", None),
                        (meas_tbl, tbl_doc_url),
                        (meas_name, None),
                    ]

                meas_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"Measure: [{meas_name}]",
                    breadcrumbs=breadcrumbs,
                    content_html=meas_content,
                )
                documents[doc_path] = meas_html

        # 6. Functions Documents (Model - functions/<Function>.<ext>)
        if self.config.include_models:
            functions_sub = self.config.functions_subdir.strip("/\\")
            for fn in data.get("functions", []):
                fn_name = fn.get("name", "function")
                clean_name = sanitize_filename(fn_name)
                fn_builder = HtmlFunctionBuilder(fn, data, self.config, project_name=project_name)
                fn_filename = f"{clean_name}{self.config.html_ext_suffix}"
                rel_doc = f"{functions_sub}/{fn_filename}" if functions_sub else fn_filename
                doc_path = f"{bp}{rel_doc}"
                rel_root = get_relative_root(doc_path)

                fn_content = fn_builder.build_content()
                if base_prefix:
                    breadcrumbs = [
                        ("Workspace", f"{rel_root}/index{self.config.html_ext_suffix}"),
                        (project_name, f"{rel_root}/{base_prefix}/index{self.config.html_ext_suffix}"),
                        ("Functions", None),
                        (fn_name, None),
                    ]
                else:
                    breadcrumbs = [("Home", f"{rel_root}/index{self.config.html_ext_suffix}"), ("Functions", None), (fn_name, None)]

                fn_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"Function: {fn_name}",
                    breadcrumbs=breadcrumbs,
                    content_html=fn_content,
                )
                documents[doc_path] = fn_html

        # 7. Report & Visual Pages (Report - visuals/<Page>.<ext>)
        if self.config.include_reports and self.config.include_visual_docs and report_model:
            visuals_sub = self.config.visuals_subdir.strip("/\\")
            for page in report_model.pages:
                clean_page_name = sanitize_filename(page.display_name)
                page_filename = f"{clean_page_name}{self.config.html_ext_suffix}"
                rel_doc = f"{visuals_sub}/{page_filename}" if visuals_sub else page_filename
                doc_path = f"{bp}{rel_doc}"
                rel_root = get_relative_root(doc_path)

                vis_builder = HtmlVisualBuilder(
                    page=page,
                    report_model=report_model,
                    config=self.config,
                    project_name=project_name,
                    model_tables=data.get("tables", []),
                    model_measures=data.get("measures", []),
                )
                vis_content = vis_builder.build_content()
                if base_prefix:
                    breadcrumbs = [
                        ("Workspace", f"{rel_root}/index{self.config.html_ext_suffix}"),
                        (project_name, f"{rel_root}/{base_prefix}/index{self.config.html_ext_suffix}"),
                        ("Report Pages", None),
                        (page.display_name, None),
                    ]
                else:
                    breadcrumbs = [("Home", f"{rel_root}/index{self.config.html_ext_suffix}"), ("Report Pages", None), (page.display_name, None)]

                vis_html = layout.wrap_page(
                    current_path=doc_path,
                    page_title=f"Report Page: {page.display_name}",
                    breadcrumbs=breadcrumbs,
                    content_html=vis_content,
                )
                documents[doc_path] = vis_html

                # Scaled SVG canvas mini-maps (reusing PageVisualDocBuilder SVG generator)
                if self.config.include_visual_svg_maps:
                    page_svg_builder = PageVisualDocBuilder(
                        page=page,
                        report_model=report_model,
                        config=self.config,
                        project_name=project_name,
                    )
                    svg_assets = page_svg_builder.build_svg_assets()
                    for asset_rel_path, svg_content in svg_assets.items():
                        asset_doc_path = f"{visuals_sub}/{asset_rel_path}" if visuals_sub else asset_rel_path
                        documents[asset_doc_path] = svg_content

        # 7. Relationship Diagram SVG Assets
        if self.config.include_models and self.config.include_relationship_diagrams and data.get("relationships"):
            svg_gen = RelationshipSvgGenerator(data, config=self.config)
            diagram_assets = svg_gen.build_diagram_assets(self.config.diagrams_subdir)
            for diag_rel_path, diag_content in diagram_assets.items():
                asset_doc_path = f"{bp}{diag_rel_path}"
                documents[asset_doc_path] = diag_content

        return documents

    def write_to_directory(self, model_data: Union[Dict[str, Any], str, Path], target_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Generates and writes all HTML files and assets to target directory.
        Returns the dictionary of generated relative file paths and contents.
        """
        out_path = Path(target_dir or self.config.output_dir)
        docs = self.generate_all_documents(model_data)

        for rel_path, content in docs.items():
            dest_file = out_path / rel_path
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_file, "w", encoding="utf-8") as f:
                f.write(content)

        return docs

    def _resolve_report(self, model_input: Union[Dict[str, Any], str, Path]) -> Optional[PBIPReportModel]:
        if not self.config.include_visual_docs:
            return None
        if self.config.report_path:
            rp = Path(self.config.report_path)
            if rp.exists():
                try:
                    parser = ReportParser()
                    return parser.parse(str(rp))
                except Exception:
                    return None
        input_path = None
        if isinstance(model_input, (str, Path)):
            input_path = Path(model_input)
        elif hasattr(model_input, "source_path") and getattr(model_input, "source_path"):
            input_path = Path(model_input.source_path)

        if input_path:
            p = input_path
            candidates = []
            if p.suffix.lower() == ".report":
                candidates.append(p)
            elif p.suffix.lower() == ".semanticmodel":
                candidates.append(p.parent / f"{p.stem}.Report")
                candidates.extend(list(p.parent.glob("*.Report")))
            elif p.suffix.lower() == ".pbip":
                candidates.append(p.parent / f"{p.stem}.Report")
                candidates.extend(list(p.parent.glob("*.Report")))
            elif p.is_dir():
                candidates.append(p / f"{p.name}.Report")
                candidates.extend(list(p.glob("*.Report")))
                candidates.extend(list(p.parent.glob("*.Report")))
                if p.name == "definition" and p.parent.suffix.lower() == ".semanticmodel":
                    candidates.append(p.parent.parent / f"{p.parent.stem}.Report")
                    candidates.extend(list(p.parent.parent.glob("*.Report")))
            for c in candidates:
                if c.exists() and c.is_dir():
                    try:
                        parser = ReportParser()
                        return parser.parse(str(c))
                    except Exception:
                        continue
        return None

    def _resolve_project_name(
        self,
        model_input: Union[Dict[str, Any], str, Path],
        model_data: Dict[str, Any],
        report_model: Optional[PBIPReportModel] = None,
    ) -> str:
        if self.config.project_name:
            return clean_project_name(self.config.project_name)
        if isinstance(model_data, dict):
            if model_data.get("project_name"):
                return clean_project_name(model_data["project_name"])
            if model_data.get("model_name"):
                return clean_project_name(model_data["model_name"])
        if report_model and report_model.report_name:
            return clean_project_name(report_model.report_name)
        if isinstance(model_input, (str, Path)):
            p = Path(model_input)
            if p.suffix.lower() in (".pbip", ".semanticmodel", ".report"):
                return clean_project_name(p.stem)
            if p.name == "definition" and p.parent.suffix.lower() == ".semanticmodel":
                return clean_project_name(p.parent.stem)
            if p.name == "definition" and p.parent.suffix.lower() == ".report":
                return clean_project_name(p.parent.stem)
            return clean_project_name(p.stem)
        return "PBIP"

    def _load_model_dict(self, model_data: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
        if hasattr(model_data, "to_dict"):
            return model_data.to_dict()
        if isinstance(model_data, dict):
            return model_data
        if isinstance(model_data, (str, Path)):
            path = Path(model_data)
            if path.is_file() and path.suffix.lower() == ".json":
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and ("model_name" in data or "source_format" in data) and "tables" in data:
                        return data
                except Exception:
                    pass

            from ..parser import PBIPParser
            parser = PBIPParser(config=self.config)
            model_obj = parser.parse(str(path), config=self.config)
            return model_obj.to_dict()
        raise ValueError(f"Unsupported model_data type: {type(model_data)}")
