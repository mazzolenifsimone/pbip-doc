"""
Documentation Generator Engine.
Coordinates TableDocBuilder, MeasureDocBuilder, IndexDocBuilder, and PageVisualDocBuilder
to emit granular, AI-RAG-ready, human-readable markdown documents.
Vanilla Python implementation.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, Union, Optional

from .config import DocGenConfig
from .table_doc import TableDocBuilder
from .measure_doc import MeasureDocBuilder
from .function_doc import FunctionDocBuilder
from .expression_doc import ExpressionDocBuilder, DataflowDocBuilder
from .index_doc import IndexDocBuilder
from .visual_doc import PageVisualDocBuilder
from .relationship_diagram import RelationshipSvgGenerator
from .utils import sanitize_filename, clean_project_name, resolve_model_index_filename
from ..report_parser import ReportParser
from ..report_schema import PBIPReportModel


class MarkdownDocGenerator:
    """
    Main entry point for generating modular documentation from semantic model JSON
    and associated Power BI report presentation metadata.
    """

    def __init__(self, config: Optional[DocGenConfig] = None):
        self.config = config or DocGenConfig()

    def generate_all_documents(self, model_data: Union[Dict[str, Any], str, Path]) -> Dict[str, str]:
        """
        Generates in-memory dictionary of all markdown documents:
        {
          "<project_name>.md": content,
          "tables/FactInternetSales.md": content,
          "measures/Sales/Total_Sales.md": content,
          "expressions/Staging_Orders.md": content,
          "visuals/Executive_Overview.md": content,
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

        # 1. Master Catalog (<project_name>.md)
        if self.config.generate_index_file and self.config.include_models:
            index_builder = IndexDocBuilder(data, self.config, report_model=report_model, project_name=project_name)
            index_filename = resolve_model_index_filename(self.config, project_name)
            documents[index_filename] = index_builder.build_markdown()

        # 2. Dataflow Documents (Dataflow Overview + Ingested Tables + Shared Queries)
        if self.config.include_dataflow and self.config.include_expression_docs:
            expressions_sub = self.config.expressions_subdir.strip("/\\")

            # 2a. Dataflow Overview (expressions/README.md)
            df_doc_builder = DataflowDocBuilder(data, self.config, project_name=project_name)
            df_doc_path = f"{expressions_sub}/README.md" if expressions_sub else "README_dataflow.md"
            documents[df_doc_path] = df_doc_builder.build_markdown()

            # 2b. Loaded Model Tables (under expressions/<Table>.md)
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
                expr_builder = ExpressionDocBuilder(expr_data, data, self.config, project_name=project_name)
                expr_filename = f"{clean_name}.md"
                doc_path = f"{expressions_sub}/{expr_filename}" if expressions_sub else expr_filename
                documents[doc_path] = expr_builder.build_markdown()

            # 2c. Shared Staging Queries, Parameters, Functions
            expr_list = data.get("expressions") or data.get("shared_queries") or []
            existing_tbl_names = {t.get("name") for t in dataflow_tables}
            for expr in expr_list:
                q_name = expr.get("query_name") or "expression"
                if q_name in existing_tbl_names:
                    continue
                expr_builder = ExpressionDocBuilder(expr, data, self.config, project_name=project_name)
                clean_name = sanitize_filename(q_name)
                expr_filename = f"{clean_name}.md"
                doc_path = f"{expressions_sub}/{expr_filename}" if expressions_sub else expr_filename
                documents[doc_path] = expr_builder.build_markdown()

        # 3. Table Documents (Model - one markdown per table)
        if self.config.include_models:
            tables_sub = self.config.tables_subdir.strip("/\\")
            for table in data.get("tables", []):
                if not self.config.is_table_published(table):
                    continue
                tbl_name = table.get("name")
                tbl_builder = TableDocBuilder(table, data, self.config, project_name=project_name)
                clean_tbl_name = sanitize_filename(tbl_name)
                tbl_filename = f"{clean_tbl_name}.md"
                doc_path = f"{tables_sub}/{tbl_filename}" if tables_sub else tbl_filename
                documents[doc_path] = tbl_builder.build_markdown()

        # 4. Measure Documents (Model - one markdown per measure grouped by clean host table folder)
        if self.config.include_models:
            measures_sub = self.config.measures_subdir.strip("/\\")
            for measure in data.get("measures", []):
                if not self.config.is_measure_published(measure):
                    continue
                meas_tbl = measure.get("table", "Model")
                meas_builder = MeasureDocBuilder(measure, data, self.config, project_name=project_name)
                clean_tbl_name = sanitize_filename(meas_tbl)
                clean_name = sanitize_filename(measure.get("name", "measure"))
                meas_filename = f"{clean_name}.md"
                if measures_sub:
                    doc_path = f"{measures_sub}/{clean_tbl_name}/{meas_filename}"
                else:
                    doc_path = f"{clean_tbl_name}/{meas_filename}"
                documents[doc_path] = meas_builder.build_markdown()

        # 5. Function Documents (Model - one markdown per UDF function)
        if self.config.include_models:
            functions_sub = self.config.functions_subdir.strip("/\\")
            for fn in data.get("functions", []):
                fn_builder = FunctionDocBuilder(fn, data, self.config, project_name=project_name)
                clean_name = sanitize_filename(fn.get("name", "function"))
                fn_filename = f"{clean_name}.md"
                doc_path = f"{functions_sub}/{fn_filename}" if functions_sub else fn_filename
                documents[doc_path] = fn_builder.build_markdown()

        # 6. Report & Visual Documents (Report - one markdown per page)
        if self.config.include_reports and self.config.include_visual_docs and report_model:
            visuals_sub = self.config.visuals_subdir.strip("/\\")
            known_measure_keys = {
                (m.get("table"), m.get("name")) for m in data.get("measures", [])
            } | {
                f"{m.get('table')}[{m.get('name')}]" for m in data.get("measures", [])
            }
            known_table_names = {t.get("name") for t in data.get("tables", [])}

            for page in report_model.pages:
                page_builder = PageVisualDocBuilder(
                    page=page,
                    report_model=report_model,
                    config=self.config,
                    known_measure_keys=known_measure_keys,
                    known_table_names=known_table_names,
                    project_name=project_name,
                    model_tables=data.get("tables", []),
                    model_measures=data.get("measures", []),
                )
                clean_page_name = sanitize_filename(page.display_name)
                page_filename = f"{clean_page_name}.md"
                doc_path = f"{visuals_sub}/{page_filename}" if visuals_sub else page_filename
                documents[doc_path] = page_builder.build_markdown()

                # Generate and collect scaled SVG canvas mini-maps
                if self.config.include_visual_svg_maps:
                    svg_assets = page_builder.build_svg_assets()
                    for asset_rel_path, svg_content in svg_assets.items():
                        asset_doc_path = f"{visuals_sub}/{asset_rel_path}" if visuals_sub else asset_rel_path
                        documents[asset_doc_path] = svg_content

        # 7. Relationship Diagram SVG Assets
        if self.config.include_relationship_diagrams and (data.get("relationships") or data.get("tables") or data.get("upstream_models")):
            svg_gen = RelationshipSvgGenerator(data, config=self.config)
            diagram_assets = svg_gen.build_diagram_assets(self.config.diagrams_subdir)
            for diag_rel_path, diag_content in diagram_assets.items():
                documents[diag_rel_path] = diag_content

        return documents

    def write_to_directory(self, model_data: Union[Dict[str, Any], str, Path], target_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Generates and writes all markdown files to target directory.
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
        """Attempts to locate and parse the associated PBIP *.Report component."""
        if not self.config.include_visual_docs:
            return None

        # 1. Explicit report path from config
        if self.config.report_path:
            rp = Path(self.config.report_path)
            if rp.exists():
                try:
                    parser = ReportParser()
                    return parser.parse(str(rp))
                except Exception:
                    return None

        # 2. Auto-discovery from model_input
        if isinstance(model_input, (str, Path)):
            p = Path(model_input)
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
            elif p.is_file():
                if p.name == "report_documentation.json" or "report" in p.name.lower():
                    candidates.append(p)
                candidates.append(p.parent / "report_documentation.json")
                candidates.extend(list(p.parent.glob("*.Report")))
                candidates.extend(list(p.parent.parent.glob("*.Report")))

            for cand in candidates:
                if cand.exists():
                    try:
                        parser = ReportParser()
                        return parser.parse(str(cand))
                    except Exception:
                        continue

        return None

    def _load_model_dict(self, model_input: Union[Dict[str, Any], str, Path]) -> Dict[str, Any]:
        """Ensures input is converted to standard dictionary."""
        if hasattr(model_input, "to_dict"):
            return model_input.to_dict()
        if isinstance(model_input, dict):
            return model_input
        
        path = Path(model_input)
        if path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and ("model_name" in data or "source_format" in data) and "tables" in data:
                    return data
            except Exception:
                pass
        
        # If passed a PBIP directory, definition folder, or model.bim, parse it directly via PBIPParser
        from ..parser import PBIPParser
        parser = PBIPParser(config=self.config)
        model_obj = parser.parse(str(path), config=self.config)
        return model_obj.to_dict()

    def _resolve_project_name(
        self,
        model_input: Union[Dict[str, Any], str, Path],
        data: Dict[str, Any],
        report_model: Optional[PBIPReportModel],
    ) -> str:
        """
        Resolves the PBIP project name from explicit config, input path,
        report metadata, or semantic model data.
        """
        if self.config.project_name:
            return clean_project_name(self.config.project_name)

        # 1. From model_input path if provided as string or Path
        if isinstance(model_input, (str, Path)):
            p = Path(model_input)
            stem = p.stem
            cleaned = clean_project_name(stem)
            if cleaned and cleaned not in ("model", "definition", "PBIP"):
                return cleaned

            parent_cleaned = clean_project_name(p.parent.name)
            if parent_cleaned and parent_cleaned not in ("definition", ".", "PBIP"):
                return parent_cleaned

        # 2. From report_model
        if report_model and getattr(report_model, "report_name", None):
            cleaned = clean_project_name(report_model.report_name)
            if cleaned and cleaned != "PBIP":
                return cleaned

        # 3. From semantic model data
        m_name = data.get("model_name")
        if m_name:
            cleaned = clean_project_name(m_name)
            if cleaned and cleaned != "PBIP":
                return cleaned

        return "PBIP"
