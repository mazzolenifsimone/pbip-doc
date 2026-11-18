"""
PBIP Semantic Model Parser.
Supports both TMDL (Tabular Model Definition Language) directory structures
and TMSL (model.bim) JSON files.
Vanilla Python implementation.
"""

import json
import os
import re
import textwrap
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

from .model_schema import (
    PBIPSemanticModel,
    TableDefinition,
    ColumnDefinition,
    RelationshipDefinition,
    MeasureDefinition,
    FunctionDefinition,
    FunctionParameter,
    IncrementalRefreshPolicy,
    TableRole,
    TableRoleClassification,
    PowerQuerySource,
    UpstreamModelSummary,
    compute_upstream_models,
)
from .m_lineage import MLineageResolver
from .star_schema import StarSchemaResolver
from .measure_analyzer import MeasureDependencyResolver
from .tmdl_lexer import (
    parse_tmdl,
    find_blocks,
    find_first_block,
    unquote_tmdl_name,
    clean_multiline_code,
    clean_tmdl_description,
    TMDLBlock,
)


def _clean_tmdl_multiline_block(expr: Optional[str]) -> Optional[str]:
    """Strips TMDL triple backticks (``` or ```dax / ```m) from multiline code blocks and dedents."""
    return clean_multiline_code(expr)


def _clean_tmdl_description(desc: Optional[str]) -> Optional[str]:
    """Cleans a TMDL description, stripping quotes, triple backticks, and extra whitespace."""
    return clean_tmdl_description(desc)


def _extract_tmdl_doc_comment(text: Optional[str]) -> Optional[str]:
    """Extracts and joins TMDL /// documentation comments from preceding lines."""
    if not text:
        return None
    doc_lines = []
    has_any = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("///"):
            has_any = True
            c = s[3:]
            if c.startswith(" "):
                c = c[1:]
            doc_lines.append(c)
    if not has_any:
        return None
    res = "\n".join(doc_lines).strip()
    return res if res else None


class PBIPParser:
    """
    Parses a PBIP semantic model from either a directory (TMDL/BIM) or a single BIM file.
    Orchestrates M Lineage, Star Schema, and Measure dependency resolution.
    Supports table exclusion configuration (e.g. LocalDateTable_*, DateTableTemplate_*).
    """

    def __init__(self, config: Optional[Any] = None):
        self.config = config

    def parse(self, target_path: str, config: Optional[Any] = None) -> PBIPSemanticModel:
        """
        Auto-detects format (TMDL directory vs BIM JSON file) and executes extraction.
        Applies table exclusion filters from config (e.g. auto date/time tables).
        """
        active_config = config or self.config
        if active_config is None:
            from .docgen.config import DocGenConfig
            base_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
            active_config = DocGenConfig.find_and_load_default(base_dir)
        self.active_config = active_config

        path = Path(target_path)
        model: PBIPSemanticModel

        if path.is_file() and (path.suffix.lower() == ".json" or path.name.lower() == "model.bim"):
            model = self.parse_bim_file(str(path))
        elif path.is_dir():
            # Check if there is a definition/ subfolder (TMDL standard)
            tmdl_dir = path / "definition"
            if tmdl_dir.exists() and (tmdl_dir / "tables").exists():
                model = self.parse_tmdl_dir(str(tmdl_dir), model_name=path.stem)
            # Check if target_path is itself the definition folder
            elif (path / "tables").exists():
                model = self.parse_tmdl_dir(str(path), model_name=path.parent.stem)
            # Check for model.bim inside directory
            elif (path / "model.bim").exists():
                model = self.parse_bim_file(str(path / "model.bim"))
            else:
                # Recursive search for definition or model.bim
                found = False
                for sub in path.rglob("definition"):
                    if sub.is_dir() and (sub / "tables").exists():
                        model = self.parse_tmdl_dir(str(sub), model_name=path.stem)
                        found = True
                        break
                if not found:
                    for bim in path.rglob("model.bim"):
                        model = self.parse_bim_file(str(bim))
                        found = True
                        break
                if not found:
                    raise FileNotFoundError(
                        f"Could not find valid TMDL directory (with 'tables/' folder) or model.bim in: {target_path}"
                    )
        else:
            raise FileNotFoundError(f"Path not found: {target_path}")

        # Filter out auto-generated or user-excluded tables
        if active_config:
            model.filter_excluded_tables(active_config.is_table_excluded)

        return model

    # =========================================================================
    # BIM / TMSL Parser
    # =========================================================================

    def parse_bim_file(self, bim_path: str) -> PBIPSemanticModel:
        """Parses standard model.bim JSON format."""
        with open(bim_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return self.parse_bim_dict(data, model_name=Path(bim_path).stem)

    def parse_bim_dict(self, data: Dict[str, Any], model_name: str = "SemanticModel") -> PBIPSemanticModel:
        """Parses model.bim JSON dictionary."""
        model_data = data.get("model", data)
        culture = model_data.get("culture", "en-US")
        compat_level = data.get("compatibilityLevel", 1550)

        tables: List[TableDefinition] = []
        relationships: List[RelationshipDefinition] = []
        measures: List[MeasureDefinition] = []
        raw_queries: Dict[str, Dict[str, Any]] = {}

        # 1. Parse Shared Expressions (M staging / parameters)
        for expr in model_data.get("expressions", []):
            q_name = expr.get("name", "")
            raw_m = expr.get("expression", "")
            if isinstance(raw_m, list):
                raw_m = "\n".join(raw_m)
            raw_queries[q_name] = {
                "m_code": raw_m,
                "target_table": None,
                "is_staging": True,
                "description": expr.get("description"),
                "lineage_tag": expr.get("lineageTag"),
                "query_group": expr.get("queryGroup"),
                "kind": expr.get("kind", "m"),
            }

        # 2. Parse Tables, Columns, Measures, and Table Partitions (M)
        for tbl in model_data.get("tables", []):
            t_name = tbl.get("name", "")
            description = tbl.get("description")
            is_hidden = tbl.get("isHidden", False)

            # Columns
            cols: List[ColumnDefinition] = []
            for col in tbl.get("columns", []):
                col_name = col.get("name", "")
                data_type = col.get("dataType", "string")
                is_col_hidden = col.get("isHidden", False)
                is_key = col.get("isKey", False)
                format_string = col.get("formatString")
                col_desc = col.get("description")
                col_expr = col.get("expression")
                if isinstance(col_expr, list):
                    col_expr = "\n".join(col_expr)
                is_calculated = (
                    col.get("type", "").lower() == "calculated"
                    or (col_expr is not None and len(str(col_expr).strip()) > 0)
                )
                display_folder = col.get("displayFolder")
                col_data_cat = col.get("dataCategory")

                source_column = col.get("sourceColumn")
                cols.append(
                    ColumnDefinition(
                        name=col_name,
                        data_type=data_type,
                        is_hidden=is_col_hidden,
                        is_key=is_key,
                        is_calculated=is_calculated,
                        format_string=format_string,
                        data_category=col_data_cat,
                        description=col_desc,
                        expression=col_expr,
                        display_folder=display_folder,
                        source_column=source_column,
                        origin="dax" if is_calculated else "source",
                    )
                )

            # Partitions (Power Query M, Calculated, or Inherited Entity)
            source_type = "PowerQuery"
            table_m_code = ""
            table_expression = None
            is_inherited = False
            inherited_entity_name = None
            inherited_expression_source = None
            for part in tbl.get("partitions", []):
                part_source = part.get("source", {})
                p_type = part_source.get("type", "").lower()
                query_body = part_source.get("query", "")
                if isinstance(query_body, list):
                    query_body = "\n".join(query_body)

                expr_body = part_source.get("expression", "")
                if isinstance(expr_body, list):
                    expr_body = "\n".join(expr_body)

                if p_type == "entity" or "entityName" in part_source:
                    source_type = "InheritedEntity"
                    is_inherited = True
                    inherited_entity_name = part_source.get("entityName", t_name)
                    raw_exp = part_source.get("expressionSource")
                    inherited_expression_source = str(raw_exp).strip().strip("'\"") if raw_exp else None
                elif p_type == "m" or "let" in query_body:
                    source_type = "PowerQuery"
                    table_m_code = query_body
                elif p_type == "calculated" or expr_body:
                    source_type = "CalculatedTable"
                    table_m_code = ""
                    calc_candidate = expr_body or query_body
                    if calc_candidate:
                        table_expression = calc_candidate.strip()

            if tbl.get("calculationGroup"):
                source_type = "CalculationGroup"

            if table_m_code:
                raw_queries[t_name] = {
                    "m_code": table_m_code,
                    "target_table": t_name,
                    "is_staging": False,
                }

            # Measures
            for m in tbl.get("measures", []):
                m_name = m.get("name", "")
                m_expr = m.get("expression", "")
                if isinstance(m_expr, list):
                    m_expr = "\n".join(m_expr)
                m_format = m.get("formatString")
                m_desc = m.get("description")
                m_hidden = m.get("isHidden", False)
                m_folder = m.get("displayFolder")

                is_ext = bool(re.search(r'^\s*EXTERNALMEASURE\s*\(', m_expr, re.IGNORECASE))

                measures.append(
                    MeasureDefinition(
                        name=m_name,
                        table=t_name,
                        dax_expression=m_expr,
                        format_string=m_format,
                        description=m_desc,
                        is_hidden=m_hidden,
                        display_folder=m_folder,
                        is_inherited=is_ext,
                        is_external_measure=is_ext,
                        out_of_scope=is_ext,
                    )
                )

            t_refresh_policy = tbl.get("refreshPolicy")
            inc_policy = None
            if t_refresh_policy and isinstance(t_refresh_policy, dict):
                src_expr = t_refresh_policy.get("sourceExpression")
                if isinstance(src_expr, list):
                    src_expr = "\n".join(src_expr)
                poll_expr = t_refresh_policy.get("pollingExpression")
                if isinstance(poll_expr, list):
                    poll_expr = "\n".join(poll_expr)
                inc_policy = IncrementalRefreshPolicy(
                    is_enabled=True,
                    policy_type=t_refresh_policy.get("policyType", "basic"),
                    mode=t_refresh_policy.get("mode", "import"),
                    rolling_window_periods=t_refresh_policy.get("rollingWindowPeriods"),
                    rolling_window_granularity=t_refresh_policy.get("rollingWindowGranularity"),
                    incremental_periods=t_refresh_policy.get("incrementalPeriods") or t_refresh_policy.get("incrementalWindowPeriods"),
                    incremental_granularity=t_refresh_policy.get("incrementalGranularity") or t_refresh_policy.get("incrementalWindowGranularity"),
                    source_expression=src_expr,
                    polling_expression=poll_expr,
                    raw_policy=t_refresh_policy,
                )

            t_data_cat = tbl.get("dataCategory")
            table_def = TableDefinition(
                name=t_name,
                role=TableRole.UNKNOWN,
                classification_reasoning=TableRoleClassification(TableRole.UNKNOWN, 0.0),
                columns=cols,
                is_hidden=is_hidden,
                description=description,
                data_category=t_data_cat,
                source_type=source_type,
                expression=table_expression,
                incremental_refresh_policy=inc_policy,
                is_inherited=is_inherited,
                inherited_entity_name=inherited_entity_name,
                inherited_expression_source=inherited_expression_source,
                out_of_scope=is_inherited,
            )
            tables.append(table_def)

        # 3. Parse Relationships
        rel_index = 1
        for rel in model_data.get("relationships", []):
            from_t = rel.get("fromTable", "")
            from_c = rel.get("fromColumn", "")
            to_t = rel.get("toTable", "")
            to_c = rel.get("toColumn", "")
            cardinality = rel.get("cardinality", "1:N")
            cross_dir = rel.get("crossFilteringBehavior", "Single")
            is_active = rel.get("isActive", True)
            rel_id = rel.get("name", f"rel_{rel_index}_{from_t}_{to_t}")
            rel_index += 1

            # Standardize cardinality representation
            from_card = (rel.get("fromCardinality") or "").lower()
            to_card = (rel.get("toCardinality") or "").lower()
            if from_card == "one" and to_card == "many":
                from_t, to_t = to_t, from_t
                from_c, to_c = to_c, from_c
                cardinality = "1:N"
            elif from_card == "one" and to_card == "one":
                cardinality = "1:1"
            elif from_card == "many" and to_card == "many":
                cardinality = "N:N"
            elif cardinality in ("OneToMany", "1:N"):
                cardinality = "1:N"
            elif cardinality in ("ManyToOne", "N:1"):
                cardinality = "1:N"
            elif cardinality in ("OneToOne", "1:1"):
                cardinality = "1:1"
            elif cardinality in ("ManyToMany", "N:N"):
                cardinality = "N:N"

            relationships.append(
                RelationshipDefinition(
                    id=rel_id,
                    from_table=from_t,
                    from_column=from_c,
                    to_table=to_t,
                    to_column=to_c,
                    cardinality=cardinality,
                    cross_filtering_behavior=cross_dir,
                    is_active=is_active,
                )
            )

        # 4. Parse Functions (if defined in BIM)
        functions: List[FunctionDefinition] = []
        for fn in model_data.get("functions", []):
            fn_name = fn.get("name", "UnnamedFunction")
            fn_expr = fn.get("expression", "")
            if isinstance(fn_expr, list):
                fn_expr = "\n".join(fn_expr)
            fn_desc = fn.get("description")
            fn_type = fn.get("dataType")
            fn_hidden = fn.get("isHidden", False)
            fn_tag = fn.get("lineageTag")

            params: List[FunctionParameter] = []
            for p in fn.get("parameters", []):
                params.append(
                    FunctionParameter(
                        name=p.get("name", "param"),
                        data_type=p.get("dataType"),
                        is_optional=p.get("isOptional", False),
                        default_value=p.get("defaultValue"),
                        description=p.get("description"),
                    )
                )

            sig = ""
            if params:
                param_strs = []
                for p in params:
                    s = p.name
                    if p.data_type:
                        s += f": {p.data_type}"
                    if p.default_value is not None:
                        s += f" = {p.default_value}"
                    param_strs.append(s)
                sig = f"({', '.join(param_strs)})"

            functions.append(
                FunctionDefinition(
                    name=fn_name,
                    expression=fn_expr,
                    parameters=params,
                    parameters_signature=sig,
                    return_type=fn_type,
                    description=fn_desc,
                    is_hidden=fn_hidden,
                    lineage_tag=fn_tag,
                )
            )

        return self._enrich_and_resolve(
            model_name=model_name,
            source_format="BIM",
            compat_level=compat_level,
            culture=culture,
            tables=tables,
            relationships=relationships,
            measures=measures,
            raw_queries=raw_queries,
            functions=functions,
        )

    # =========================================================================
    # TMDL Parser
    # =========================================================================

    def parse_tmdl_dir(self, definition_dir: str, model_name: str = "SemanticModel") -> PBIPSemanticModel:
        """Parses TMDL definition folder."""
        def_path = Path(definition_dir)
        tables: List[TableDefinition] = []
        relationships: List[RelationshipDefinition] = []
        measures: List[MeasureDefinition] = []
        functions: List[FunctionDefinition] = []
        raw_queries: Dict[str, Dict[str, Any]] = {}

        # 1. Parse expressions from expressions.tmdl or expressions/*.tmdl
        expr_file = def_path / "expressions.tmdl"
        if expr_file.exists():
            with open(expr_file, "r", encoding="utf-8") as f:
                content = f.read()
            self._parse_tmdl_expressions(content, raw_queries)

        expr_dir = def_path / "expressions"
        if expr_dir.is_dir():
            for e_file in expr_dir.glob("*.tmdl"):
                with open(e_file, "r", encoding="utf-8") as f:
                    content = f.read()
                self._parse_tmdl_expressions(content, raw_queries, default_name=e_file.stem)

        # 2. Parse tables from tables/*.tmdl
        tables_dir = def_path / "tables"
        if tables_dir.exists():
            for t_file in tables_dir.glob("*.tmdl"):
                with open(t_file, "r", encoding="utf-8") as f:
                    content = f.read()
                table_def, tbl_measures, tbl_m_code = self._parse_single_table_tmdl(content, t_file.stem)
                tables.append(table_def)
                measures.extend(tbl_measures)
                if tbl_m_code:
                    raw_queries[table_def.name] = {
                        "m_code": tbl_m_code,
                        "target_table": table_def.name,
                        "is_staging": False,
                    }

        # 3. Parse relationships.tmdl
        rel_file = def_path / "relationships.tmdl"
        if rel_file.exists():
            with open(rel_file, "r", encoding="utf-8") as f:
                content = f.read()
            relationships = self._parse_tmdl_relationships(content)

        # 4. Parse functions from functions.tmdl or definition/functions.tmdl
        fn_candidates = [
            def_path / "functions.tmdl",
            def_path.parent / "functions.tmdl",
        ]
        fn_candidates.extend(list(def_path.glob("**/functions.tmdl")))
        if (def_path / "functions").is_dir():
            fn_candidates.extend(list((def_path / "functions").glob("*.tmdl")))

        seen_fn_files = set()
        for fn_file in fn_candidates:
            try:
                resolved = fn_file.resolve()
            except Exception:
                resolved = fn_file
            if fn_file.exists() and resolved not in seen_fn_files:
                seen_fn_files.add(resolved)
                with open(fn_file, "r", encoding="utf-8") as f:
                    f_content = f.read()
                parsed_fns = self._parse_tmdl_functions(f_content)
                functions.extend(parsed_fns)

        return self._enrich_and_resolve(
            model_name=model_name,
            source_format="TMDL",
            compat_level=1600,
            culture="en-US",
            tables=tables,
            relationships=relationships,
            measures=measures,
            raw_queries=raw_queries,
            functions=functions,
        )

    def _parse_tmdl_expressions(self, content: str, raw_queries: Dict[str, Dict[str, Any]], default_name: Optional[str] = None):
        """Extracts shared queries from expressions.tmdl or definition/expressions/*.tmdl using TMDLBlock parser."""
        roots = parse_tmdl(content)
        expr_blocks = find_blocks(roots, "expression", recursive=True)
        if not expr_blocks and roots:
            for r in roots:
                if r.expression or r.properties.get("source"):
                    expr_blocks.append(r)

        for eb in expr_blocks:
            q_name = eb.name or default_name or "Expression"
            m_code = eb.expression or eb.properties.get("source", "")
            description = clean_tmdl_description(eb.properties.get("description")) or eb.doc_comment
            lineage_tag = eb.properties.get("lineageTag")
            query_group = eb.properties.get("queryGroup")

            raw_queries[q_name] = {
                "m_code": m_code.strip() if m_code else "",
                "target_table": None,
                "is_staging": True,
                "description": description,
                "lineage_tag": lineage_tag,
                "query_group": query_group,
            }

    def _parse_single_table_tmdl(self, content: str, default_name: str) -> Tuple[TableDefinition, List[MeasureDefinition], str]:
        """Parses a table .tmdl file into columns, measures, and M code using TMDLBlock parser."""
        roots = parse_tmdl(content)
        tbl_block = find_first_block(roots, "table", recursive=True)

        table_name = default_name
        description = None
        is_hidden = False
        source_type = "PowerQuery"
        table_expression = None
        table_doc = None
        table_data_cat = None

        if tbl_block:
            table_name = tbl_block.name or default_name
            table_doc = tbl_block.doc_comment
            description = clean_tmdl_description(tbl_block.properties.get("description")) or table_doc
            is_hidden = "isHidden" in tbl_block.flags
            table_data_cat = tbl_block.properties.get("dataCategory")
            if tbl_block.expression:
                source_type = "CalculatedTable"
                table_expression = tbl_block.expression

        columns: List[ColumnDefinition] = []
        measures: List[MeasureDefinition] = []
        table_m_code = ""
        is_inherited = False
        inherited_entity_name = None
        inherited_expression_source = None

        children = tbl_block.children if tbl_block else roots

        # 1. Partitions & source detection
        for child in children:
            if child.keyword == "partition":
                p_inline = (child.inline_value or "").lower()

                entity_props = dict(child.properties)
                source_block = next((c for c in child.children if c.keyword == "source"), None)
                if source_block:
                    entity_props.update(source_block.properties)

                # Entity partition (DirectQuery / Fabric inherited)
                if p_inline == "entity" or "entityName" in entity_props:
                    source_type = "InheritedEntity"
                    is_inherited = True
                    inherited_entity_name = entity_props.get("entityName", table_name)
                    raw_exp = entity_props.get("expressionSource")
                    inherited_expression_source = str(raw_exp).strip().strip("'\"") if raw_exp else None
                # M Partition
                elif p_inline == "m" or "let" in child.properties.get("source", ""):
                    source_type = "PowerQuery"
                    table_m_code = child.properties.get("source", "")
                # Calculated partition
                elif p_inline == "calculated" or child.properties.get("source") or child.expression:
                    source_type = "CalculatedTable"
                    calc_expr = child.properties.get("source") or child.expression
                    if calc_expr:
                        table_expression = calc_expr

            elif child.keyword == "calculationGroup":
                source_type = "CalculationGroup"

        if tbl_block and ("calculationGroup" in tbl_block.properties or any(c.keyword == "calculationGroup" for c in children)):
            source_type = "CalculationGroup"

        # 2. Columns
        for child in children:
            if child.keyword == "column":
                c_name = child.name
                if not c_name:
                    continue

                data_type = child.properties.get("dataType", "string")
                format_string = child.properties.get("formatString")
                col_data_cat = child.properties.get("dataCategory")
                is_col_hidden = "isHidden" in child.flags
                is_key = "isKey" in child.flags
                c_desc = clean_tmdl_description(child.properties.get("description")) or child.doc_comment
                c_expr = child.expression or child.properties.get("expression")
                is_calculated = bool(c_expr and c_expr.strip())
                source_col = child.properties.get("sourceColumn")
                if source_col:
                    source_col = unquote_tmdl_name(source_col)
                display_folder = child.properties.get("displayFolder")

                columns.append(
                    ColumnDefinition(
                        name=c_name,
                        data_type=data_type,
                        is_hidden=is_col_hidden,
                        is_key=is_key,
                        is_calculated=is_calculated,
                        format_string=format_string,
                        data_category=col_data_cat,
                        description=c_desc,
                        expression=c_expr,
                        source_column=source_col,
                        display_folder=display_folder,
                        origin="dax" if is_calculated else "source",
                    )
                )

        # 3. Measures
        for child in children:
            if child.keyword == "measure":
                m_name = child.name
                if not m_name:
                    continue

                dax_expr = child.expression or child.inline_value or ""
                is_ext = bool(re.search(r'^\s*EXTERNALMEASURE\s*\(', dax_expr, re.IGNORECASE))
                format_string = child.properties.get("formatString")
                m_desc = clean_tmdl_description(child.properties.get("description")) or child.doc_comment
                m_folder = child.properties.get("displayFolder")
                m_hidden = "isHidden" in child.flags

                measures.append(
                    MeasureDefinition(
                        name=m_name,
                        table=table_name,
                        dax_expression=dax_expr,
                        format_string=format_string,
                        description=m_desc,
                        is_hidden=m_hidden,
                        display_folder=m_folder,
                        is_inherited=is_ext,
                        is_external_measure=is_ext,
                        out_of_scope=is_ext,
                    )
                )

        inc_policy = self._parse_tmdl_refresh_policy(content)

        table_def = TableDefinition(
            name=table_name,
            role=TableRole.UNKNOWN,
            classification_reasoning=TableRoleClassification(TableRole.UNKNOWN, 0.0),
            columns=columns,
            is_hidden=is_hidden,
            description=description,
            data_category=table_data_cat,
            source_type=source_type,
            expression=table_expression,
            incremental_refresh_policy=inc_policy,
            is_inherited=is_inherited,
            inherited_entity_name=inherited_entity_name,
            inherited_expression_source=inherited_expression_source,
            out_of_scope=is_inherited,
        )

        return table_def, measures, table_m_code

    def _parse_tmdl_refresh_policy(self, content: str) -> Optional[IncrementalRefreshPolicy]:
        """Parses TMDL refreshPolicy block or JSON assignment."""
        match = re.search(
            r'^\s{1,4}refreshPolicy(?:\s*=\s*(?P<json_str>\{[\s\S]*?\}))?(?P<rest>[^\r\n]*(?:\n\s{2,}[\s\S]*?)?)(?=^\s{1,4}(?:column|measure|partition|hierarchy)|\s*\Z)',
            content,
            re.MULTILINE
        )
        if not match:
            return None

        json_str = match.group("json_str")
        raw_dict = {}
        if json_str:
            try:
                raw_dict = json.loads(json_str)
            except Exception:
                pass

        if raw_dict:
            src_expr = raw_dict.get("sourceExpression")
            if isinstance(src_expr, list):
                src_expr = "\n".join(src_expr)
            poll_expr = raw_dict.get("pollingExpression")
            if isinstance(poll_expr, list):
                poll_expr = "\n".join(poll_expr)
            return IncrementalRefreshPolicy(
                is_enabled=True,
                policy_type=raw_dict.get("policyType", "basic"),
                mode=raw_dict.get("mode", "import"),
                rolling_window_periods=raw_dict.get("rollingWindowPeriods"),
                rolling_window_granularity=raw_dict.get("rollingWindowGranularity"),
                incremental_periods=raw_dict.get("incrementalPeriods") or raw_dict.get("incrementalWindowPeriods"),
                incremental_granularity=raw_dict.get("incrementalGranularity") or raw_dict.get("incrementalWindowGranularity"),
                source_expression=src_expr,
                polling_expression=poll_expr,
                raw_policy=raw_dict,
            )

        combined_text = match.group("rest") or ""

        policy_type_m = re.search(r'policyType:\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        policy_type = policy_type_m.group(1).strip() if policy_type_m else "basic"

        mode_m = re.search(r'mode:\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        mode = mode_m.group(1).strip() if mode_m else "import"

        roll_per_m = re.search(r'rollingWindowPeriods:\s*(\d+)', combined_text, re.IGNORECASE)
        roll_per = int(roll_per_m.group(1)) if roll_per_m else None

        roll_gran_m = re.search(r'rollingWindowGranularity:\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        roll_gran = roll_gran_m.group(1).strip() if roll_gran_m else None

        inc_per_m = re.search(r'(?:incrementalPeriods|incrementalWindowPeriods):\s*(\d+)', combined_text, re.IGNORECASE)
        inc_per = int(inc_per_m.group(1)) if inc_per_m else None

        inc_gran_m = re.search(r'(?:incrementalGranularity|incrementalWindowGranularity):\s*([^\r\n]+)', combined_text, re.IGNORECASE)
        inc_gran = inc_gran_m.group(1).strip() if inc_gran_m else None

        poll_m = re.search(r'pollingExpression:\s*(.+)', combined_text, re.IGNORECASE)
        poll_expr = poll_m.group(1).strip() if poll_m else None

        src_m = re.search(r'sourceExpression:\s*(.+)', combined_text, re.IGNORECASE)
        src_expr = src_m.group(1).strip() if src_m else None

        return IncrementalRefreshPolicy(
            is_enabled=True,
            policy_type=policy_type,
            mode=mode,
            rolling_window_periods=roll_per,
            rolling_window_granularity=roll_gran,
            incremental_periods=inc_per,
            incremental_granularity=inc_gran,
            source_expression=src_expr,
            polling_expression=poll_expr,
            raw_policy={
                "policyType": policy_type,
                "mode": mode,
                "rollingWindowPeriods": roll_per,
                "rollingWindowGranularity": roll_gran,
                "incrementalPeriods": inc_per,
                "incrementalGranularity": inc_gran,
            },
        )

    def _parse_tmdl_relationships(self, content: str) -> List[RelationshipDefinition]:
        """Parses relationships.tmdl using TMDLBlock parser."""
        relationships: List[RelationshipDefinition] = []
        roots = parse_tmdl(content)
        rel_blocks = find_blocks(roots, "relationship", recursive=True)

        for rb in rel_blocks:
            rel_id = rb.name or "relationship"
            from_raw = rb.properties.get("fromColumn", "")
            to_raw = rb.properties.get("toColumn", "")

            if not from_raw or not to_raw:
                continue

            if "." in from_raw:
                from_t, from_c = from_raw.split(".", 1)
            else:
                from_t, from_c = "", from_raw

            if "." in to_raw:
                to_t, to_c = to_raw.split(".", 1)
            else:
                to_t, to_c = "", to_raw

            from_t = unquote_tmdl_name(from_t)
            from_c = unquote_tmdl_name(from_c)
            to_t = unquote_tmdl_name(to_t)
            to_c = unquote_tmdl_name(to_c)

            is_active = rb.properties.get("isActive", "true").lower() != "false"
            cross_dir = rb.properties.get("crossFilteringBehavior", "Single")

            # Check cardinality
            from_card = rb.properties.get("fromCardinality", "").lower()
            to_card = rb.properties.get("toCardinality", "").lower()

            cardinality = "1:N"
            if from_card == "one" and to_card == "one":
                cardinality = "1:1"
            elif from_card == "many" and to_card == "many":
                cardinality = "N:N"
            elif from_card == "one" and to_card != "one":
                # from_t is the ONE side, to_t is the MANY side!
                # Normalize so that from_table is always Many (child/FK) and to_table is One (parent/PK)
                from_t, to_t = to_t, from_t
                from_c, to_c = to_c, from_c
                cardinality = "1:N"
            elif to_card == "many" and from_card != "many":
                # to_t is the MANY side, from_t is the ONE side
                from_t, to_t = to_t, from_t
                from_c, to_c = to_c, from_c
                cardinality = "1:N"

            relationships.append(
                RelationshipDefinition(
                    id=rel_id,
                    from_table=from_t,
                    from_column=from_c,
                    to_table=to_t,
                    to_column=to_c,
                    cardinality=cardinality,
                    cross_filtering_behavior=cross_dir,
                    is_active=is_active,
                )
            )

        return relationships

    # =========================================================================
    # Enrichment & Resolution Pipeline
    # =========================================================================

    def _parse_tmdl_functions(self, content: str) -> List[FunctionDefinition]:
        """Parses DAX User-Defined Functions from functions.tmdl using TMDLBlock parser."""
        functions: List[FunctionDefinition] = []
        roots = parse_tmdl(content)
        fn_blocks = find_blocks(roots, "function", recursive=True)

        for fb in fn_blocks:
            fn_name = fb.name or "UnnamedFunction"
            fn_doc = fb.doc_comment
            description = clean_tmdl_description(fb.properties.get("description")) or fn_doc
            return_type = fb.properties.get("dataType")
            lineage_tag = fb.properties.get("lineageTag")
            is_hidden = "isHidden" in fb.flags

            code_block = fb.expression or fb.inline_value or ""

            # Parse parameters signature and implementation expression
            # Syntax: (param1: type = default, ...) [: returnType] => expression
            parameters: List[FunctionParameter] = []
            if "=>" in code_block:
                arrow_split = re.split(r'\s*=>\s*', code_block, maxsplit=1)
                sig_raw = arrow_split[0].strip()
                expression = arrow_split[1].strip()
            else:
                sig_raw = ""
                expression = code_block.strip()

            expression = clean_multiline_code(expression) or ""

            # Check for inline return type annotation like (...): double =>
            ret_type_match = re.search(r'\)\s*:\s*([a-zA-Z0-9_]+)\s*$', sig_raw)
            if ret_type_match:
                if not return_type:
                    return_type = ret_type_match.group(1).strip()
                sig_raw = sig_raw[:ret_type_match.start() + 1].strip()

            sig_raw = re.sub(r'^[`\s]+', '', sig_raw)
            sig_raw = re.sub(r'[`\s]+$', '', sig_raw)
            if sig_raw.startswith("(") and sig_raw.endswith(")"):
                clean_sig = sig_raw[1:-1].strip()
            else:
                clean_sig = sig_raw.strip("()").strip()

            parameters = self._parse_function_parameters(clean_sig)

            if parameters:
                param_strs = []
                for p in parameters:
                    s = p.name
                    if p.data_type:
                        s += f": {p.data_type}"
                    if p.default_value is not None:
                        s += f" = {p.default_value}"
                    param_strs.append(s)
                sig_str = f"({', '.join(param_strs)})"
            else:
                sig_str = "()"

            functions.append(
                FunctionDefinition(
                    name=fn_name,
                    expression=expression,
                    parameters=parameters,
                    parameters_signature=sig_str,
                    return_type=return_type,
                    description=description,
                    is_hidden=is_hidden,
                    lineage_tag=lineage_tag,
                )
            )

        return functions

    def _parse_function_parameters(self, sig: str) -> List[FunctionParameter]:
        """Parses parameter string like 'Numerator: double, Denominator: double, Alt: double = 0'."""
        params: List[FunctionParameter] = []
        if not sig or not sig.strip():
            return params

        # Strip any stray leading/trailing backticks or parentheses from the entire signature string
        sig = sig.strip()
        sig = re.sub(r'^[`()]+', '', sig).strip()
        sig = re.sub(r'[`()]+$', '', sig).strip()
        if not sig:
            return params

        # Smart split by commas, respecting quotes and parentheses
        tokens: List[str] = []
        current: List[str] = []
        in_quote = None
        paren_depth = 0
        for ch in sig:
            if in_quote:
                current.append(ch)
                if ch == in_quote:
                    in_quote = None
            elif ch in ('"', "'"):
                in_quote = ch
                current.append(ch)
            elif ch in ('(', '[', '{'):
                paren_depth += 1
                current.append(ch)
            elif ch in (')', ']', '}'):
                paren_depth -= 1
                current.append(ch)
            elif ch == ',' and paren_depth == 0:
                t = "".join(current).strip()
                if t:
                    tokens.append(t)
                current = []
            else:
                current.append(ch)
        last_t = "".join(current).strip()
        if last_t:
            tokens.append(last_t)

        for tok in tokens:
            # Strip comments
            tok = re.sub(r'/\*.*?\*/', '', tok, flags=re.DOTALL)
            tok = re.sub(r'//.*$', '', tok, flags=re.MULTILINE)
            # Strip stray backticks, parentheses, and whitespace
            tok = tok.strip()
            tok = re.sub(r'^[`()]+', '', tok).strip()
            tok = re.sub(r'[`()]+$', '', tok).strip()
            if not tok:
                continue

            default_val = None
            is_opt = False
            if "=" in tok:
                parts = tok.split("=", 1)
                tok_name_part = parts[0].strip()
                default_val = parts[1].strip()
                # Clean stray closing backticks, parentheses
                default_val = re.sub(r'[`()]+$', '', default_val).strip()
                is_opt = True
            else:
                tok_name_part = tok.strip()

            if ":" in tok_name_part:
                p_parts = tok_name_part.split(":", 1)
                p_name = p_parts[0].strip()
                p_type = p_parts[1].strip()
            else:
                p_name = tok_name_part.strip()
                p_type = None

            # Clean name: strip backticks, quotes, brackets, parentheses
            p_name = re.sub(r'^[`\'"()\[\]]+', '', p_name)
            p_name = re.sub(r'[`\'"()\[\]]+$', '', p_name).strip()
            p_name = " ".join(p_name.split())

            if p_type:
                p_type = re.sub(r'^[`\'"()]+', '', p_type)
                p_type = re.sub(r'[`\'"()]+$', '', p_type).strip()
                p_type = " ".join(p_type.split())

            if not p_name:
                continue

            params.append(
                FunctionParameter(
                    name=p_name,
                    data_type=p_type,
                    is_optional=is_opt,
                    default_value=default_val,
                )
            )

        return params

    @staticmethod
    def compute_upstream_models(
        tables: List[TableDefinition],
        measures: List[MeasureDefinition],
    ) -> List[UpstreamModelSummary]:
        """Groups remote/inherited tables and external measures by upstream semantic model."""
        return compute_upstream_models(tables, measures)

    def resolve_semantic_model(
        self,
        model_name: str,
        tables: List[TableDefinition],
        relationships: List[RelationshipDefinition],
        measures: List[MeasureDefinition],
        raw_power_query_expressions: Optional[Dict[str, Dict[str, Any]]] = None,
        source_format: str = "TMDL",
        compat_level: int = 1600,
        culture: str = "en-US",
        functions: Optional[List[FunctionDefinition]] = None,
    ) -> PBIPSemanticModel:
        """Programmatic helper to resolve lineages, star schema, and dependencies for a semantic model."""
        return self._enrich_and_resolve(
            model_name=model_name,
            source_format=source_format,
            compat_level=compat_level,
            culture=culture,
            tables=tables,
            relationships=relationships,
            measures=measures,
            raw_queries=raw_power_query_expressions or {},
            functions=functions,
        )

    def _enrich_and_resolve(
        self,
        model_name: str,
        source_format: str,
        compat_level: int,
        culture: str,
        tables: List[TableDefinition],
        relationships: List[RelationshipDefinition],
        measures: List[MeasureDefinition],
        raw_queries: Dict[str, Dict[str, Any]],
        functions: Optional[List[FunctionDefinition]] = None,
    ) -> PBIPSemanticModel:
        """
        Executes the resolution algorithms:
        1. Power Query M lineage (root data sources & multi-hop chains)
        2. Star Schema & Snowflake outrigger paths (Fact -> Dim -> Lookup)
        3. DAX Measure & UDF Function dependency DAG
        """
        # --- 1. Power Query M Lineage Resolution ---
        m_resolver = MLineageResolver(raw_queries)
        for tbl in tables:
            lineage = m_resolver.get_lineage_for_table(tbl.name)
            if lineage:
                tbl.power_query_lineage = lineage
                tbl.root_data_sources = lineage.root_sources
                tbl.upstream_queries_chain = lineage.all_upstream_queries
            elif tbl.is_inherited:
                entity_label = tbl.inherited_entity_name or tbl.name
                src_expr_name = tbl.inherited_expression_source.strip().strip("'\"") if tbl.inherited_expression_source else ""

                # Try to resolve expression in m_resolver
                expr_node = None
                if src_expr_name:
                    for q_name, node in m_resolver.nodes.items():
                        if q_name.strip().strip("'\"").lower() == src_expr_name.lower():
                            expr_node = node
                            break

                remote_model = None
                matched_source = None

                if expr_node:
                    # Link table downstream to expression node
                    if tbl.name not in expr_node.downstream_tables:
                        expr_node.downstream_tables.append(tbl.name)
                    tbl.upstream_queries_chain = [expr_node.query_name]

                    # Check if expression node has physical sources (e.g. AnalysisServices.Database)
                    if expr_node.root_sources:
                        as_src = next((s for s in expr_node.root_sources if s.source_type in ("ANALYSIS_SERVICES", "POWERBI_SEMANTIC_MODEL") or s.database), None)
                        if as_src:
                            matched_source = as_src
                            if as_src.database:
                                remote_model = as_src.database

                # Fallback: parse model name from expression name if starts with DirectQuery to AS -
                if not remote_model and src_expr_name:
                    dq_match = re.search(r'^(?:DirectQuery\s+to\s+AS\s*-\s*)(.+)$', src_expr_name, re.IGNORECASE)
                    if dq_match:
                        remote_model = dq_match.group(1).strip().strip("'\"")
                    elif src_expr_name and src_expr_name != "DatabaseQuery":
                        remote_model = src_expr_name

                if remote_model:
                    tbl.inherited_model_name = remote_model

                if matched_source:
                    tbl.root_data_sources = [matched_source]
                elif remote_model:
                    stype = "ANALYSIS_SERVICES"
                    if expr_node and any(pbi in expr_node.full_m_expression.lower() for pbi in ("powerbi://", "api.powerbi.com", "pbiazure://")):
                        stype = "POWERBI_SEMANTIC_MODEL"
                    as_source = PowerQuerySource(
                        source_type=stype,
                        connection_string=f"Analysis Services / {remote_model}",
                        database=remote_model,
                        endpoint_or_path=entity_label,
                    )
                    tbl.root_data_sources = [as_source]
                    if expr_node and not expr_node.root_sources:
                        expr_node.root_sources.append(as_source)
                else:
                    conn_str = f"Entity: {entity_label}"
                    if tbl.inherited_expression_source:
                        conn_str += f" (Source: {tbl.inherited_expression_source})"
                    tbl.root_data_sources = [
                        PowerQuerySource(
                            source_type="INHERITED_ENTITY",
                            connection_string=conn_str,
                            endpoint_or_path=entity_label,
                        )
                    ]

            # Resolve Column Lineage & Power Query Transformations
            for col in tbl.columns:
                if col.is_calculated or col.expression:
                    col.origin = "dax"
                elif lineage and lineage.is_inline_table:
                    col.origin = "power_query"
                    col.m_operation = "Inline Table (#table)"
                elif lineage and lineage.column_transformations:
                    tf = lineage.column_transformations.get(col.name)
                    if not tf and col.source_column:
                        tf = lineage.column_transformations.get(col.source_column)
                    if tf:
                        col.origin = "power_query"
                        col.m_expression = tf.get("m_expression")
                        col.m_step_name = tf.get("step_name")
                        col.m_operation = tf.get("operation")
                        col.m_source_table = tf.get("m_source_table")
                        if not col.source_column and tf.get("source_column"):
                            col.source_column = tf.get("source_column")
                    else:
                        col.origin = "source"
                else:
                    col.origin = "source"

        # Resolve inherited_model_name for external measures and inherited tables
        known_inherited_model_names = {
            t.inherited_model_name for t in tables if getattr(t, "inherited_model_name", None)
        }
        dq_query_model_names: List[str] = []
        for q_name, node in m_resolver.nodes.items():
            dq_m = re.search(r'^(?:DirectQuery\s+to\s+AS\s*-\s*)(.+)$', q_name.strip().strip("'\""), re.IGNORECASE)
            if dq_m:
                dq_query_model_names.append(dq_m.group(1).strip().strip("'\""))
            elif node.root_sources:
                for rs in node.root_sources:
                    if rs.source_type in ("ANALYSIS_SERVICES", "POWERBI_SEMANTIC_MODEL") and rs.database:
                        dq_query_model_names.append(rs.database)

        fallback_model_name = (
            next(iter(known_inherited_model_names))
            if len(known_inherited_model_names) == 1
            else (dq_query_model_names[0] if len(set(dq_query_model_names)) == 1 else None)
        )

        for tbl in tables:
            if (tbl.is_inherited or tbl.source_type == "InheritedEntity") and not tbl.inherited_model_name:
                tbl.inherited_model_name = fallback_model_name or "Remote Semantic Model"

        for m in measures:
            if m.is_inherited or m.is_external_measure:
                # Step 1: Inherit from host table if known (and not generic fallback when multiple models exist)
                host_tbl = next((t for t in tables if t.name == m.table), None)
                if host_tbl and host_tbl.inherited_model_name and host_tbl.inherited_model_name != "Remote Semantic Model":
                    m.inherited_model_name = host_tbl.inherited_model_name
                elif host_tbl and getattr(host_tbl, "inherited_expression_source", None):
                    dq_match = re.search(r'^(?:DirectQuery\s+to\s+AS\s*-\s*)(.+)$', str(host_tbl.inherited_expression_source), re.IGNORECASE)
                    if dq_match:
                        m.inherited_model_name = dq_match.group(1).strip().strip("'\"")
                    elif str(host_tbl.inherited_expression_source).strip().strip("'\"") != "DatabaseQuery":
                        m.inherited_model_name = str(host_tbl.inherited_expression_source).strip().strip("'\"")

                # Step 2: Extract from EXTERNALMEASURE 3rd argument
                if not m.inherited_model_name:
                    ext_m = re.search(
                        r'EXTERNALMEASURE\s*\(\s*["\'](?P<mname>.*?)["\']\s*(?:,\s*[^,]+(?:\s*,\s*["\'](?P<sname>.*?)["\'])?)?',
                        m.dax_expression or "",
                        re.IGNORECASE
                    )
                    if ext_m and ext_m.group("sname"):
                        raw_sname = ext_m.group("sname").strip().strip("'\"")
                        matched_node = None
                        for q_name, node in m_resolver.nodes.items():
                            if q_name.strip().strip("'\"").lower() == raw_sname.lower():
                                matched_node = node
                                break
                        if matched_node and matched_node.root_sources:
                            as_src = next((s for s in matched_node.root_sources if s.database), None)
                            if as_src and as_src.database:
                                m.inherited_model_name = as_src.database
                        if not m.inherited_model_name:
                            dq_match = re.search(r'^(?:DirectQuery\s+to\s+AS\s*-\s*)(.+)$', raw_sname, re.IGNORECASE)
                            if dq_match:
                                m.inherited_model_name = dq_match.group(1).strip().strip("'\"")
                            elif raw_sname != "DatabaseQuery":
                                m.inherited_model_name = raw_sname

                # Step 3: Multi-Upstream deterministic binding via referenced inherited tables in DAX formula
                if not m.inherited_model_name and m.dax_expression:
                    dax_text = m.dax_expression
                    for t in tables:
                        if (t.is_inherited or t.source_type == "InheritedEntity") and t.inherited_model_name and t.inherited_model_name != "Remote Semantic Model":
                            t_pat = r"(?:'" + re.escape(t.name) + r"'|\b" + re.escape(t.name) + r"\b)"
                            if re.search(t_pat, dax_text, re.IGNORECASE):
                                m.inherited_model_name = t.inherited_model_name
                                break

                # Step 4: Deterministic fallback (single known model -> DQ query model -> "Remote Semantic Model")
                if not m.inherited_model_name:
                    if fallback_model_name:
                        m.inherited_model_name = fallback_model_name
                    elif dq_query_model_names:
                        m.inherited_model_name = dq_query_model_names[0]
                    elif host_tbl and host_tbl.inherited_model_name:
                        m.inherited_model_name = host_tbl.inherited_model_name
                    else:
                        m.inherited_model_name = "Remote Semantic Model"

        cfg = getattr(self, "active_config", None) or self.config
        if cfg is None:
            from .docgen.config import DocGenConfig
            cfg = DocGenConfig()

        include_inherited = getattr(cfg, "include_inherited_entities", False) if cfg else False
        for tbl in tables:
            if tbl.is_inherited:
                tbl.out_of_scope = not include_inherited
        for m in measures:
            if m.is_inherited or m.is_external_measure:
                m.out_of_scope = not include_inherited

        table_names = {t.name for t in tables}
        shared_queries = [
            node for node in m_resolver.get_all_nodes().values()
            if node.target_table is None or node.is_staging or node.query_name not in table_names or node.expression_kind in ("parameter", "function")
        ]

        # Consolidate all root physical data sources (from queries + inherited tables)
        all_root_sources = m_resolver.get_all_root_sources()
        unique_sources: Dict[str, PowerQuerySource] = {}
        for s in all_root_sources:
            MLineageResolver._merge_source_into_dict(unique_sources, s)

        for tbl in tables:
            for s in tbl.root_data_sources:
                if s.source_type != "INHERITED_ENTITY" or not unique_sources:
                    MLineageResolver._merge_source_into_dict(unique_sources, s)

        all_root_sources = list(unique_sources.values())

        # --- Filter Excluded Tables according to configuration BEFORE Topology Estimation ---
        excluded_names = set()
        if hasattr(cfg, "is_table_excluded"):
            excluded_names = {t.name for t in tables if cfg.is_table_excluded(t.name)}

        if excluded_names:
            tables = [t for t in tables if t.name not in excluded_names]
            relationships = [
                r for r in relationships
                if r.from_table not in excluded_names and r.to_table not in excluded_names
            ]
            measures = [m for m in measures if m.table not in excluded_names]
            for m in measures:
                m.referenced_tables = [t for t in m.referenced_tables if t not in excluded_names]
                m.referenced_columns = [
                    rc for rc in m.referenced_columns if rc.get("table") not in excluded_names
                ]
            for fn in (functions or []):
                fn.referenced_tables = [t for t in fn.referenced_tables if t not in excluded_names]
                fn.referenced_columns = [
                    rc for rc in fn.referenced_columns if rc.get("table") not in excluded_names
                ]

        # --- 2. Star Schema & Snowflake Outrigger Resolution ---
        is_excl_fn = cfg.is_table_excluded if cfg and hasattr(cfg, "is_table_excluded") else None
        star_resolver = StarSchemaResolver(
            tables,
            relationships,
            is_table_excluded_fn=is_excl_fn,
        )
        star_resolver.classify_tables()
        star_topology = star_resolver.resolve_topology_and_snowflakes()

        # --- 3. DAX Measure & Function Dependency Resolution ---
        # Ensure tables defined with DAX (e.g. calculated tables) do not erroneously enter the measures list
        known_table_names = {t.name for t in tables}
        valid_measures = []
        for m in measures:
            if not m.table and m.name in known_table_names:
                # Erroneous table entry placed in measures without host table
                continue
            valid_measures.append(m)
        measures = valid_measures

        func_list = functions or []
        measure_resolver = MeasureDependencyResolver(measures, tables, functions=func_list)
        measure_dag = measure_resolver.analyze()

        # --- 4. Compute Upstream Models Summary & Enrich Physical Data Sources ---
        upstream_models = self.compute_upstream_models(tables, measures)
        up_names = {u.name for u in upstream_models}
        param_map = {
            e.query_name: e for e in shared_queries
            if e.expression_kind == "parameter"
            or "IsParameterQuery" in (e.full_m_expression or "")
            or "IsParameterQueryRequired" in (e.full_m_expression or "")
        }
        for src in all_root_sources:
            if src.connection_string in param_map:
                src.parameter_query_name = src.connection_string
                src.parameter_value = param_map[src.connection_string].parameter_value
            stype_up = (src.source_type or "").upper()
            srv_low = (src.server or "").lower()
            if (
                stype_up in ("ANALYSIS_SERVICES", "ANALYSISSERVICES", "POWERBI_SEMANTIC_MODEL", "POWERBI")
                or "powerbi://" in srv_low
                or bool(src.database and src.database in up_names)
            ):
                src.is_remote_model = True

        # Assemble full model
        model = PBIPSemanticModel(
            model_name=model_name,
            source_format=source_format,
            compatibility_level=compat_level,
            culture=culture,
            tables=tables,
            relationships=relationships,
            measures=measures,
            functions=func_list,
            shared_queries=shared_queries,
            expressions=shared_queries,
            data_sources_summary=all_root_sources,
            star_schema=star_topology,
            measure_dependency_dag=measure_dag,
            excluded_tables_count=len(excluded_names),
            excluded_tables_list=sorted(list(excluded_names)),
            upstream_models=upstream_models,
        )

        return model
