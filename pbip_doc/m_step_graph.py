"""
Power Query (M) Intra-Query Step Graph, Backward Slicing, and Physical Navigation Resolver.
100% Python Standard Library implementation with zero external runtime dependencies.
Constructs step DAG, computes backward slices (isolating active vs dead/unused steps),
extracts physical connectors and navigation items {[Schema=..., Item=...]},
and tracks detailed column lineage (Cross Joins, Nested Joins, Rename Chains, Aggregations).
"""

from typing import List, Dict, Set, Optional, Tuple, Any, Union
from .model_schema import (
    PowerQuerySource,
    PowerQueryLineageStep,
    PowerQueryMergeJoin,
    PowerQueryColumnTransformation,
    FunctionParameter,
)
from .m_parser import (
    MNode,
    MLetExpr,
    MStep,
    MInvocationExpr,
    MItemAccessExpr,
    MFieldAccessExpr,
    MRecordExpr,
    MListExpr,
    MIdentifier,
    MLiteral,
    MFunctionExpr,
    MEachExpr,
    MIfExpr,
    MTryExpr,
    MMetadataExpr,
    MBinaryExpr,
    MUnaryExpr,
    MTypeExpr,
    MUnresolvedExpr,
    parse_m,
)


def _ast_to_raw_snippet(node: MNode, max_len: int = 250) -> str:
    """Produces a clean string representation of an AST node for display in documentation."""
    if node is None:
        return ""
    if isinstance(node, MLiteral):
        res = str(node.raw or node.value)
    elif isinstance(node, MIdentifier):
        res = f'#"{node.name}"' if node.is_quoted else node.name
    elif isinstance(node, MFieldAccessExpr):
        tgt = f"{_ast_to_raw_snippet(node.target)}." if node.target else ""
        res = f"{tgt}[{node.field_name}]"
    elif isinstance(node, MItemAccessExpr):
        res = f"{_ast_to_raw_snippet(node.target)}{{{_ast_to_raw_snippet(node.item)}}}"
    elif isinstance(node, MRecordExpr):
        items = [f"{k} = {_ast_to_raw_snippet(v)}" for k, v in node.fields]
        res = f"[{', '.join(items)}]"
    elif isinstance(node, MListExpr):
        items = [_ast_to_raw_snippet(x) for x in node.items]
        res = f"{{{', '.join(items)}}}"
    elif isinstance(node, MEachExpr):
        res = f"each {_ast_to_raw_snippet(node.body)}"
    elif isinstance(node, MInvocationExpr):
        fn_name = _ast_to_raw_snippet(node.function)
        args = [_ast_to_raw_snippet(a) for a in node.arguments]
        res = f"{fn_name}({', '.join(args)})"
    elif isinstance(node, MBinaryExpr):
        res = f"{_ast_to_raw_snippet(node.left)} {node.operator} {_ast_to_raw_snippet(node.right)}"
    elif isinstance(node, MUnaryExpr):
        res = f"{node.operator} {_ast_to_raw_snippet(node.operand)}"
    elif isinstance(node, MIfExpr):
        res = f"if {_ast_to_raw_snippet(node.condition)} then {_ast_to_raw_snippet(node.then_branch)} else {_ast_to_raw_snippet(node.else_branch)}"
    elif isinstance(node, MFunctionExpr):
        params = [p.name for p in node.parameters]
        res = f"({', '.join(params)}) => {_ast_to_raw_snippet(node.body)}"
    elif isinstance(node, MTryExpr):
        otherwise = f" otherwise {_ast_to_raw_snippet(node.otherwise_branch)}" if node.otherwise_branch else ""
        res = f"try {_ast_to_raw_snippet(node.try_branch)}{otherwise}"
    elif isinstance(node, MTypeExpr):
        res = f"type {node.type_name}"
    elif isinstance(node, MMetadataExpr):
        res = f"{_ast_to_raw_snippet(node.expr)} meta {_ast_to_raw_snippet(node.metadata)}"
    elif isinstance(node, MUnresolvedExpr):
        res = node.raw
    else:
        res = str(node)

    parens = getattr(node, "parenthesized_count", 0)
    if parens > 0:
        res = ("(" * parens) + res + (")" * parens)

    if max_len and len(res) > max_len:
        return res[: max_len - 3] + "..."
    return res


def _find_all_identifiers(node: MNode) -> Set[str]:
    """Recursively collects all identifier names referenced inside an AST node."""
    names: Set[str] = set()

    def visit(n: Optional[MNode]):
        if n is None:
            return
        if isinstance(n, MIdentifier):
            names.add(n.name)
        elif isinstance(n, MInvocationExpr):
            visit(n.function)
            for arg in n.arguments:
                visit(arg)
        elif isinstance(n, MItemAccessExpr):
            visit(n.target)
            visit(n.item)
        elif isinstance(n, MFieldAccessExpr):
            visit(n.target)
        elif isinstance(n, MRecordExpr):
            for _, val in n.fields:
                visit(val)
        elif isinstance(n, MListExpr):
            for item in n.items:
                visit(item)
        elif isinstance(n, MEachExpr):
            visit(n.body)
        elif isinstance(n, MIfExpr):
            visit(n.condition)
            visit(n.then_branch)
            visit(n.else_branch)
        elif isinstance(n, MTryExpr):
            visit(n.try_branch)
            visit(n.otherwise_branch)
        elif isinstance(n, MBinaryExpr):
            visit(n.left)
            visit(n.right)
        elif isinstance(n, MUnaryExpr):
            visit(n.operand)
        elif isinstance(n, MMetadataExpr):
            visit(n.expr)
            visit(n.metadata)
        elif isinstance(n, MFunctionExpr):
            visit(n.body)
        elif isinstance(n, MLetExpr):
            for step in n.steps:
                visit(step.value)
            visit(n.in_expr)

    visit(node)
    return names


class MStepGraph:
    """
    Analyzes the AST of a Power Query M script, builds an intra-query DAG of steps,
    performs backward slicing from the 'in' expression, detects physical data sources,
    resolves navigation {[Schema=..., Item=...]}, and extracts column lineage.
    """

    CONNECTOR_FUNCTIONS = {
        "sql.database": ("SQL_SERVER", "server_db"),
        "sql.databases": ("SQL_SERVER", "server_only"),
        "postgresql.database": ("POSTGRESQL", "server_db"),
        "mysql.database": ("MYSQL", "server_db"),
        "oracle.database": ("ORACLE", "server_only"),
        "snowflake.databases": ("SNOWFLAKE", "server_db"),
        "googlebigquery.database": ("BIGQUERY", "generic"),
        "analysisservices.database": ("ANALYSIS_SERVICES", "server_db"),
        "analysisservices.databases": ("ANALYSIS_SERVICES", "server_only"),
        "excel.workbook": ("EXCEL_FILE", "file"),
        "csv.document": ("CSV_FILE", "file"),
        "file.contents": ("LOCAL_FILE", "path"),
        "folder.files": ("FOLDER", "path"),
        "sharepoint.files": ("SHAREPOINT", "url"),
        "sharepoint.tables": ("SHAREPOINT", "url"),
        "azurestorage.blobcontents": ("AZURE_BLOB", "url"),
        "azurestorage.datalake": ("AZURE_DATALAKE", "url"),
        "fabric.lakehouse": ("FABRIC_LAKEHOUSE", "endpoint"),
        "odata.feed": ("ODATA", "url"),
        "web.contents": ("WEB_API", "url"),
        "web.browsercontents": ("WEB_BROWSER", "url"),
        "odbc.datasource": ("ODBC", "url"),
        "odbc.query": ("ODBC", "url"),
        "salesforce.data": ("SALESFORCE", "generic"),
    }

    def __init__(
        self,
        ast: MNode,
        raw_code: str = "",
        known_query_names: Optional[Set[str]] = None,
        known_parameter_names: Optional[Set[str]] = None,
    ):
        self.ast = ast
        self.raw_code = raw_code
        self.known_query_names = known_query_names or set()
        self.known_parameter_names = known_parameter_names or set()

        # Step lists
        self.all_steps: List[MStep] = []
        self.in_expr: Optional[MNode] = None

        # Slicing results
        self.active_steps: List[MStep] = []
        self.unused_steps: List[MStep] = []

        # Lineage results
        self.root_sources: List[PowerQuerySource] = []
        self.merges: List[PowerQueryMergeJoin] = []
        self.column_transformations: Dict[str, PowerQueryColumnTransformation] = {}
        self.direct_dependencies: Set[str] = set()

        # Custom function metadata
        self.is_custom_function: bool = False
        self.function_parameters: List[FunctionParameter] = []
        self.function_return_type: Optional[str] = None

        # Parameter metadata
        self.is_parameter: bool = False
        self.parameter_value: Optional[str] = None
        self.parameter_type: Optional[str] = None
        self.parameter_required: bool = False

        # Build graph
        self._init_steps()
        self._backward_slice()
        self._extract_parameter_meta()
        self._extract_custom_function_meta()
        self._extract_sources_and_navigation()
        self._extract_transformations_and_merges()

    def _init_steps(self):
        """Unpacks let expressions or wraps standalone expressions into synthetic steps."""
        if isinstance(self.ast, MLetExpr):
            self.all_steps = list(self.ast.steps)
            self.in_expr = self.ast.in_expr
        else:
            # Standalone expression
            synthetic_step = MStep(name="Output", value=self.ast, raw_code=self.raw_code)
            self.all_steps = [synthetic_step]
            self.in_expr = MIdentifier("Output")

    def _backward_slice(self):
        """
        Performs backward slicing starting from the in_expr.
        Isolates active steps (forming the production DAG) from unused/dead steps.
        """
        if not self.all_steps:
            return

        step_map: Dict[str, MStep] = {s.name: s for s in self.all_steps}
        all_step_names = set(step_map.keys())

        # If in_expr is missing, treat all steps as active
        if self.in_expr is None:
            self.active_steps = list(self.all_steps)
            self.unused_steps = []
            return

        # Collect dependencies from in_expr
        in_refs = _find_all_identifiers(self.in_expr)
        visited_steps: Set[str] = set()
        queue: List[str] = [name for name in in_refs if name in step_map]

        # BFS / DFS traversal of local step dependencies
        while queue:
            curr_name = queue.pop(0)
            if curr_name in visited_steps:
                continue
            visited_steps.add(curr_name)
            curr_step = step_map[curr_name]
            step_refs = _find_all_identifiers(curr_step.value)
            for ref in step_refs:
                if ref in step_map and ref not in visited_steps:
                    queue.append(ref)

        # Preserve original definition order for both active and unused steps
        self.active_steps = [s for s in self.all_steps if s.name in visited_steps]
        self.unused_steps = [s for s in self.all_steps if s.name not in visited_steps]

        # External query dependencies referenced by active steps or in_expr
        for step in self.active_steps:
            refs = _find_all_identifiers(step.value)
            for r in refs:
                if r in self.known_query_names and r not in all_step_names:
                    self.direct_dependencies.add(r)

        for r in in_refs:
            if r in self.known_query_names and r not in all_step_names:
                self.direct_dependencies.add(r)

    def _extract_parameter_meta(self):
        """Extracts parameter value, type, and required flag if the query defines an M parameter."""
        param_node = None
        if isinstance(self.ast, MMetadataExpr):
            param_node = self.ast
        elif len(self.all_steps) == 1 and isinstance(self.all_steps[0].value, MMetadataExpr):
            param_node = self.all_steps[0].value

        if param_node:
            if isinstance(param_node.metadata, MRecordExpr):
                rec_dict = {k: _ast_to_raw_snippet(v).strip('"\'') for k, v in param_node.metadata.fields}
                if rec_dict.get("IsParameterQuery") == "true" or "IsParameterQuery" in rec_dict:
                    self.is_parameter = True
                    self.parameter_value = _ast_to_raw_snippet(param_node.expr).strip('"\'')
                    self.parameter_type = rec_dict.get("Type", "Any")
                    self.parameter_required = rec_dict.get("IsParameterQueryRequired") == "true"

        # Regex fallback
        if not self.is_parameter and ("IsParameterQuery" in self.raw_code or "IsParameterQueryRequired" in self.raw_code):
            import re
            self.is_parameter = True
            m_val = re.match(r'^\s*("[^"]*"|\d+(\.\d+)?|true|false)', self.raw_code)
            if m_val:
                self.parameter_value = m_val.group(1).strip('"\'')
            m_type = re.search(r'Type\s*=\s*["\']([^"\']+)["\']', self.raw_code)
            if m_type:
                self.parameter_type = m_type.group(1)
            self.parameter_required = "IsParameterQueryRequired=true" in self.raw_code.replace(" ", "")

    def _extract_custom_function_meta(self):
        """Extracts parameters and signature if the script defines an M custom function."""
        fn_expr: Optional[MFunctionExpr] = None

        if isinstance(self.ast, MFunctionExpr):
            fn_expr = self.ast
        elif len(self.all_steps) == 1 and isinstance(self.all_steps[0].value, MFunctionExpr):
            fn_expr = self.all_steps[0].value

        if fn_expr:
            self.is_custom_function = True
            self.function_return_type = fn_expr.return_type
            for p in fn_expr.parameters:
                self.function_parameters.append(
                    FunctionParameter(
                        name=p.name,
                        data_type=p.type_name,
                        is_optional=p.is_optional,
                        default_value=None,
                        description=None,
                    )
                )

    def _extract_sources_and_navigation(self):
        """
        Traverses active steps, finds connector calls, and associates navigation items
        {[Schema="...", Item="..."]} with physical data sources.
        """
        sources: List[PowerQuerySource] = []
        seen_keys: Set[str] = set()

        def add_source(s: PowerQuerySource):
            key = f"{s.source_type}:{s.server}:{s.database}:{s.endpoint_or_path}"
            if key not in seen_keys:
                seen_keys.add(key)
                sources.append(s)

        # Check for connector calls across all steps
        for step in self.all_steps:
            self._inspect_node_for_connectors(step.value, add_source)

        # Also inspect navigation steps like: Source{[Schema="dbo", Item="FactOrders"]}[Data]
        for step in self.all_steps:
            self._inspect_node_for_navigation(step.value, sources)

        # Check for inline table (#table) if no other sources
        if not sources:
            if "#table" in self.raw_code or "Table.FromRows" in self.raw_code:
                sources.append(
                    PowerQuerySource(
                        source_type="MANUAL_INLINE",
                        connection_string="Inline Table.FromRows / Static M Table",
                    )
                )

        self.root_sources = sources

    def _inspect_node_for_connectors(self, node: MNode, add_source_fn):
        """Recursively searches AST node for connector function invocations."""
        if isinstance(node, MInvocationExpr):
            fn_name = ""
            if isinstance(node.function, MIdentifier):
                fn_name = node.function.name.lower()

            if fn_name in self.CONNECTOR_FUNCTIONS:
                stype, mode = self.CONNECTOR_FUNCTIONS[fn_name]
                args = node.arguments

                if mode == "server_db":
                    server = _ast_to_raw_snippet(args[0]).strip('"\'') if len(args) > 0 else ""
                    db = _ast_to_raw_snippet(args[1]).strip('"\'') if len(args) > 1 else ""
                    if stype == "ANALYSIS_SERVICES" and any(p in server.lower() for p in ("powerbi://", "api.powerbi.com", "pbiazure://")):
                        stype = "POWERBI_SEMANTIC_MODEL"
                    add_source_fn(
                        PowerQuerySource(
                            source_type=stype,
                            connection_string=f"{server} / {db}",
                            server=server,
                            database=db,
                            raw_snippet=_ast_to_raw_snippet(node),
                        )
                    )
                elif mode == "server_only":
                    server = _ast_to_raw_snippet(args[0]).strip('"\'') if len(args) > 0 else ""
                    if stype == "ANALYSIS_SERVICES" and any(p in server.lower() for p in ("powerbi://", "api.powerbi.com", "pbiazure://")):
                        stype = "POWERBI_SEMANTIC_MODEL"
                    add_source_fn(
                        PowerQuerySource(
                            source_type=stype,
                            connection_string=server,
                            server=server,
                            raw_snippet=_ast_to_raw_snippet(node),
                        )
                    )
                elif mode in ("path", "url", "endpoint"):
                    val = _ast_to_raw_snippet(args[0]).strip('"\'') if len(args) > 0 else ""
                    add_source_fn(
                        PowerQuerySource(
                            source_type=stype,
                            connection_string=val,
                            endpoint_or_path=val,
                            raw_snippet=_ast_to_raw_snippet(node),
                        )
                    )
                elif mode == "file":
                    # e.g. Excel.Workbook(File.Contents("path"))
                    inner_path = ""
                    if len(args) > 0 and isinstance(args[0], MInvocationExpr):
                        inner_inv = args[0]
                        if len(inner_inv.arguments) > 0:
                            inner_path = _ast_to_raw_snippet(inner_inv.arguments[0]).strip('"\'')
                    add_source_fn(
                        PowerQuerySource(
                            source_type=stype,
                            connection_string=inner_path or "Workbook/Document",
                            endpoint_or_path=inner_path,
                            raw_snippet=_ast_to_raw_snippet(node),
                        )
                    )
                else:
                    add_source_fn(
                        PowerQuerySource(
                            source_type=stype,
                            connection_string="Cloud Service / API",
                            raw_snippet=_ast_to_raw_snippet(node),
                        )
                    )

            # Check Value.NativeQuery for SQL embedding
            if fn_name == "value.nativequery":
                if len(node.arguments) > 1:
                    query_sql = _ast_to_raw_snippet(node.arguments[1]).strip('"\'')
                    add_source_fn(
                        PowerQuerySource(
                            source_type="SQL_NATIVE_QUERY",
                            connection_string=query_sql[:80] + ("..." if len(query_sql) > 80 else ""),
                            raw_snippet=query_sql,
                        )
                    )

            # Recurse arguments
            for a in node.arguments:
                self._inspect_node_for_connectors(a, add_source_fn)

        elif isinstance(node, MItemAccessExpr):
            self._inspect_node_for_connectors(node.target, add_source_fn)
            self._inspect_node_for_connectors(node.item, add_source_fn)
        elif isinstance(node, MFieldAccessExpr) and node.target:
            self._inspect_node_for_connectors(node.target, add_source_fn)
        elif isinstance(node, MLetExpr):
            for s in node.steps:
                self._inspect_node_for_connectors(s.value, add_source_fn)

    def _inspect_node_for_navigation(self, node: MNode, sources: List[PowerQuerySource]):
        """Detects {[Schema="dbo", Item="FactOrders"]} or {[Name="Orders"]} patterns."""
        if isinstance(node, MFieldAccessExpr) and node.target and node.field_name == "Data":
            # Target should be MItemAccessExpr
            if isinstance(node.target, MItemAccessExpr):
                item_node = node.target.item
                if isinstance(item_node, MRecordExpr):
                    record_dict = {k: _ast_to_raw_snippet(v).strip('"\'') for k, v in item_node.fields}
                    schema_val = record_dict.get("Schema")
                    item_val = record_dict.get("Item") or record_dict.get("Name")

                    # If we have an existing server/db source, tag it
                    for s in sources:
                        if not s.endpoint_or_path and item_val:
                            full_name = f"{schema_val}.{item_val}" if schema_val else item_val
                            s.endpoint_or_path = full_name
                            s.schema = schema_val
                            s.item = item_val
                            s.connection_string = f"{s.connection_string} ➔ [{full_name}]"
                            break

    def _extract_transformations_and_merges(self):
        """
        Analyzes active steps in chronological execution order to track table transformations,
        cross joins via Table.AddColumn, nested joins, rename chains, and aggregate columns.
        """
        merges_by_temp_col: Dict[str, PowerQueryMergeJoin] = {}

        for step in self.active_steps:
            step_name = step.name
            val = step.value

            if not isinstance(val, MInvocationExpr) or not isinstance(val.function, MIdentifier):
                continue

            fn_name = val.function.name.lower()
            args = val.arguments

            # ---------------------------------------------------------------
            # 1. Table.AddColumn(table, newColName, each formula, ...)
            # ---------------------------------------------------------------
            if fn_name == "table.addcolumn" and len(args) > 1:
                col_name = _ast_to_raw_snippet(args[1]).strip('"\'')
                formula_node = args[2] if len(args) > 2 else None
                formula_str = _ast_to_raw_snippet(formula_node) if formula_node else ""

                # Check Cross Join pattern: Table.AddColumn(..., "JoinedTable", each OtherTable)
                is_cross_join = False
                joined_table_name = None

                target_ident = None
                if isinstance(formula_node, MEachExpr) and isinstance(formula_node.body, MIdentifier):
                    target_ident = formula_node.body.name
                elif isinstance(formula_node, MFunctionExpr) and isinstance(formula_node.body, MIdentifier):
                    target_ident = formula_node.body.name
                elif isinstance(formula_node, MIdentifier):
                    target_ident = formula_node.name

                if (
                    target_ident
                    and target_ident not in self.known_parameter_names
                    and (target_ident in self.known_query_names or target_ident in [s.name for s in self.all_steps])
                ):
                    is_cross_join = True
                    joined_table_name = target_ident

                if is_cross_join and joined_table_name:
                    merge_info = PowerQueryMergeJoin(
                        step_name=step_name,
                        joined_query=joined_table_name,
                        left_keys=[],
                        right_keys=[],
                        join_kind="CrossJoin",
                        temp_column=col_name,
                        is_cross_join=True,
                        raw_m_code=_ast_to_raw_snippet(val),
                    )
                    merges_by_temp_col[col_name] = merge_info
                    self.merges.append(merge_info)
                else:
                    self.column_transformations[col_name] = PowerQueryColumnTransformation(
                        name=col_name,
                        operation="Calculated Column",
                        step_name=step_name,
                        m_expression=formula_str,
                        expression=formula_str,
                        source_column=None,
                        source_table=None,
                        m_source_table=None,
                    )

            # ---------------------------------------------------------------
            # 2. Table.NestedJoin(table1, key1, table2, key2, tempCol, joinKind)
            # ---------------------------------------------------------------
            elif fn_name == "table.nestedjoin" and len(args) > 4:
                left_keys = self._parse_arg_list(args[1])
                joined_table = _ast_to_raw_snippet(args[2]).strip('"\'')
                right_keys = self._parse_arg_list(args[3])
                temp_col = _ast_to_raw_snippet(args[4]).strip('"\'')
                raw_kind = _ast_to_raw_snippet(args[5]).replace("JoinKind.", "").strip() if len(args) > 5 else "LeftOuter"

                merge_info = PowerQueryMergeJoin(
                    step_name=step_name,
                    joined_query=joined_table,
                    left_keys=left_keys,
                    right_keys=right_keys,
                    join_kind=raw_kind,
                    temp_column=temp_col,
                    is_cross_join=False,
                    raw_m_code=_ast_to_raw_snippet(val),
                )
                merges_by_temp_col[temp_col] = merge_info
                self.merges.append(merge_info)

            # ---------------------------------------------------------------
            # 3. Table.Join(table1, key1, table2, key2, joinKind)
            # ---------------------------------------------------------------
            elif fn_name == "table.join" and len(args) > 3:
                left_keys = self._parse_arg_list(args[1])
                joined_table = _ast_to_raw_snippet(args[2]).strip('"\'')
                right_keys = self._parse_arg_list(args[3])
                raw_kind = _ast_to_raw_snippet(args[4]).replace("JoinKind.", "").strip() if len(args) > 4 else "Inner"

                merge_info = PowerQueryMergeJoin(
                    step_name=step_name,
                    joined_query=joined_table,
                    left_keys=left_keys,
                    right_keys=right_keys,
                    join_kind=raw_kind,
                    temp_column=None,
                    is_cross_join=False,
                    raw_m_code=_ast_to_raw_snippet(val),
                )
                self.merges.append(merge_info)

            # ---------------------------------------------------------------
            # 4. Table.ExpandTableColumn(table, tableColumn, origCols, newCols)
            # ---------------------------------------------------------------
            elif fn_name == "table.expandtablecolumn" and len(args) > 2:
                temp_col = _ast_to_raw_snippet(args[1]).strip('"\'')
                orig_cols = self._parse_arg_list(args[2])
                new_cols = self._parse_arg_list(args[3]) if len(args) > 3 else orig_cols

                merge_info = merges_by_temp_col.get(temp_col)
                joined_table = merge_info.joined_query if merge_info else temp_col
                is_cross = merge_info.is_cross_join if merge_info else False

                join_desc = ""
                if merge_info:
                    merge_info.expanded_columns.extend(new_cols)
                    if is_cross:
                        join_desc = f"Cross Join with [{joined_table}]"
                    elif merge_info.left_keys and merge_info.right_keys:
                        join_desc = f"{merge_info.join_kind} Join on [{', '.join(merge_info.left_keys)}] = [{', '.join(merge_info.right_keys)}]"

                for orig_col, new_col in zip(orig_cols, new_cols):
                    op_title = f"Cross Joined from {joined_table}" if is_cross else f"Merged from {joined_table}"
                    self.column_transformations[new_col] = PowerQueryColumnTransformation(
                        name=new_col,
                        operation=op_title,
                        step_name=step_name,
                        m_expression=join_desc or f"Expanded from {temp_col}",
                        expression=join_desc or f"Expanded from {temp_col}",
                        source_column=orig_col,
                        source_table=joined_table,
                        m_source_table=joined_table,
                        join_keys_desc=join_desc or None,
                    )

            # ---------------------------------------------------------------
            # 5. Table.AggregateTableColumn(table, tempCol, aggregations)
            # ---------------------------------------------------------------
            elif fn_name == "table.aggregatetablecolumn" and len(args) > 2:
                temp_col = _ast_to_raw_snippet(args[1]).strip('"\'')
                merge_info = merges_by_temp_col.get(temp_col)
                joined_table = merge_info.joined_query if merge_info else temp_col

                agg_list_node = args[2]
                if isinstance(agg_list_node, MListExpr):
                    for agg_spec in agg_list_node.items:
                        if isinstance(agg_spec, MListExpr) and len(agg_spec.items) >= 2:
                            orig_col = _ast_to_raw_snippet(agg_spec.items[0]).strip('"\'')
                            agg_fn_name = _ast_to_raw_snippet(agg_spec.items[1]).strip()
                            new_col = _ast_to_raw_snippet(agg_spec.items[2]).strip('"\'') if len(agg_spec.items) > 2 else f"{agg_fn_name} of {orig_col}"

                            if merge_info:
                                merge_info.expanded_columns.append(new_col)

                            self.column_transformations[new_col] = PowerQueryColumnTransformation(
                                name=new_col,
                                operation=f"Aggregated from {joined_table}",
                                step_name=step_name,
                                m_expression=f"{agg_fn_name}([{orig_col}]) from [{joined_table}]",
                                expression=f"{agg_fn_name}([{orig_col}]) from [{joined_table}]",
                                source_column=orig_col,
                                source_table=joined_table,
                                m_source_table=joined_table,
                            )

            # ---------------------------------------------------------------
            # 6. Table.RenameColumns(table, renames) [Chain Resolution]
            # ---------------------------------------------------------------
            elif fn_name == "table.renamecolumns" and len(args) > 1:
                renames_node = args[1]
                rename_pairs: List[Tuple[str, str]] = []

                if isinstance(renames_node, MListExpr):
                    for item in renames_node.items:
                        if isinstance(item, MListExpr) and len(item.items) >= 2:
                            old_c = _ast_to_raw_snippet(item.items[0]).strip('"\'')
                            new_c = _ast_to_raw_snippet(item.items[1]).strip('"\'')
                            rename_pairs.append((old_c, new_c))

                for old_c, new_c in rename_pairs:
                    if old_c in self.column_transformations:
                        # Backward pointer chain: preserve original formula
                        orig_tf = self.column_transformations.pop(old_c)
                        orig_tf.name = new_c
                        orig_tf.source_column = old_c
                        orig_tf.step_name = step_name
                        orig_tf.m_expression = f"{orig_tf.m_expression} (Renamed from [{old_c}])"
                        self.column_transformations[new_c] = orig_tf
                    else:
                        self.column_transformations[new_c] = PowerQueryColumnTransformation(
                            name=new_c,
                            operation="Renamed Column",
                            step_name=step_name,
                            m_expression=f"Renamed from [{old_c}]",
                            expression=f"Renamed from [{old_c}]",
                            source_column=old_c,
                            source_table=None,
                            m_source_table=None,
                        )

            # ---------------------------------------------------------------
            # 7. Table.CombineColumns, DuplicateColumn, AddIndexColumn, SplitColumn
            # ---------------------------------------------------------------
            elif fn_name == "table.combinecolumns" and len(args) > 3:
                src_cols = self._parse_arg_list(args[1])
                new_col = _ast_to_raw_snippet(args[3]).strip('"\'')
                combiner = _ast_to_raw_snippet(args[2]).strip()
                self.column_transformations[new_col] = PowerQueryColumnTransformation(
                    name=new_col,
                    operation="Combine Columns",
                    step_name=step_name,
                    m_expression=f"Combine({src_cols}, {combiner})" if combiner else f"Combine({src_cols})",
                    expression=f"Combine({src_cols}, {combiner})" if combiner else f"Combine({src_cols})",
                    source_column=", ".join(src_cols),
                )

            elif fn_name == "table.duplicatecolumn" and len(args) > 2:
                src_col = _ast_to_raw_snippet(args[1]).strip('"\'')
                new_col = _ast_to_raw_snippet(args[2]).strip('"\'')
                self.column_transformations[new_col] = PowerQueryColumnTransformation(
                    name=new_col,
                    operation="Duplicate Column",
                    step_name=step_name,
                    m_expression=f"[{src_col}]",
                    expression=f"[{src_col}]",
                    source_column=src_col,
                )

            elif fn_name == "table.addindexcolumn" and len(args) > 1:
                new_col = _ast_to_raw_snippet(args[1]).strip('"\'')
                start = _ast_to_raw_snippet(args[2]).strip() if len(args) > 2 else "0"
                inc = _ast_to_raw_snippet(args[3]).strip() if len(args) > 3 else "1"
                self.column_transformations[new_col] = PowerQueryColumnTransformation(
                    name=new_col,
                    operation="Index Column",
                    step_name=step_name,
                    m_expression=f"Index (start={start}, increment={inc})",
                    expression=f"Index (start={start}, increment={inc})",
                )

            elif fn_name == "table.splitcolumn" and len(args) > 3:
                src_col = _ast_to_raw_snippet(args[1]).strip('"\'')
                splitter = _ast_to_raw_snippet(args[2]).strip()
                parts = self._parse_arg_list(args[3])
                for part in parts:
                    self.column_transformations[part] = PowerQueryColumnTransformation(
                        name=part,
                        operation="Split Column",
                        step_name=step_name,
                        m_expression=f"Split [{src_col}] via {splitter}" if splitter else f"Split [{src_col}]",
                        expression=f"Split [{src_col}] via {splitter}" if splitter else f"Split [{src_col}]",
                        source_column=src_col,
                    )

        # Prune unexpanded cross joins (a cross join in M requires expanding the nested table column; without expansion, rows are not multiplied)
        self.merges = [
            m for m in self.merges
            if not m.is_cross_join or bool(m.expanded_columns)
        ]

    def _parse_arg_list(self, node: MNode) -> List[str]:
        """Extracts list of string items from an MListExpr or single literal."""
        if isinstance(node, MListExpr):
            return [_ast_to_raw_snippet(item).strip('"\'') for item in node.items]
        elif isinstance(node, MLiteral):
            return [str(node.value).strip('"\'')]
        elif isinstance(node, MIdentifier):
            return [node.name]
        return []

    def _resolve_step_scope_and_details(self, step_name: str, step_value: MNode, op: str) -> Tuple[Optional[str], Optional[str]]:
        """Resolves target column/scope and details preview for a step."""
        matching_tf = [tf for tf in self.column_transformations.values() if tf.step_name == step_name]
        if matching_tf:
            cols = [tf.name for tf in matching_tf]
            col_str = ", ".join(cols)
            details = matching_tf[0].m_expression or matching_tf[0].expression
            return col_str, details

        matching_merge = [m for m in self.merges if m.step_name == step_name]
        if matching_merge:
            m = matching_merge[0]
            col_str = m.joined_query
            if m.expanded_columns:
                col_str += f" -> [{', '.join(m.expanded_columns)}]"
            if m.is_cross_join:
                details = f"Cross Join with [{m.joined_query}]"
            else:
                details = f"{m.join_kind} Join on [{', '.join(m.left_keys)}] = [{', '.join(m.right_keys)}]"
            return col_str, details

        if isinstance(step_value, MInvocationExpr):
            fn_name = _ast_to_raw_snippet(step_value.function).lower()
            args = step_value.arguments
            if "selectcolumns" in fn_name and len(args) > 1:
                cols = self._parse_arg_list(args[1])
                return ", ".join(cols), f"Kept {len(cols)} columns: [{', '.join(cols)}]"
            elif "removecolumns" in fn_name and len(args) > 1:
                cols = self._parse_arg_list(args[1])
                return ", ".join(cols), f"Removed columns: [{', '.join(cols)}]"
            elif "renamecolumns" in fn_name and len(args) > 1:
                pairs = self._parse_arg_list(args[1])
                return ", ".join(pairs), f"Renamed: {', '.join(pairs)}"
            elif "transformcolumntypes" in fn_name and len(args) > 1:
                cols = self._parse_arg_list(args[1])
                return ", ".join(cols), f"Transformed types: {', '.join(cols)}"
            elif "sort" in fn_name and len(args) > 1:
                cols = self._parse_arg_list(args[1])
                return ", ".join(cols), f"Sorted by: {', '.join(cols)}"
            elif "selectrows" in fn_name and len(args) > 1:
                cond = _ast_to_raw_snippet(args[1])
                return None, f"Filter: {cond}"
                return ", ".join(cols), f"Sorted by: {', '.join(cols)}"

        return None, _ast_to_raw_snippet(step_value)

    def get_lineage_steps(self) -> List[PowerQueryLineageStep]:
        """Returns structured lineage step records for active steps."""
        steps: List[PowerQueryLineageStep] = []
        for step in self.active_steps:
            op = self._categorize_operation(step.value)
            refs = sorted(list(_find_all_identifiers(step.value).intersection(self.known_query_names)))
            col_scope, details = self._resolve_step_scope_and_details(step.name, step.value, op)
            steps.append(
                PowerQueryLineageStep(
                    step_name=step.name,
                    operation=op,
                    referenced_queries=refs,
                    raw_m_code=_ast_to_raw_snippet(step.value),
                    transformed_column=col_scope,
                    details=details,
                )
            )
        return steps

    def get_unused_steps(self) -> List[PowerQueryLineageStep]:
        """Returns structured lineage step records for unused / dead steps."""
        steps: List[PowerQueryLineageStep] = []
        for step in self.unused_steps:
            op = self._categorize_operation(step.value)
            refs = sorted(list(_find_all_identifiers(step.value).intersection(self.known_query_names)))
            col_scope, details = self._resolve_step_scope_and_details(step.name, step.value, op)
            steps.append(
                PowerQueryLineageStep(
                    step_name=step.name,
                    operation=f"Unused: {op}",
                    referenced_queries=refs,
                    raw_m_code=_ast_to_raw_snippet(step.value),
                    transformed_column=col_scope,
                    details=details,
                )
            )
        return steps

    def _categorize_operation(self, node: MNode) -> str:
        """Categorizes step operation based on invocation or AST node."""
        if isinstance(node, MInvocationExpr) and isinstance(node.function, MIdentifier):
            fn = node.function.name.lower()
            if any(k in fn for k in ["sql.", "postgresql.", "mysql.", "oracle.", "snowflake.", "bigquery.", "analysisservices.", "file.", "excel.", "csv.", "web.", "odata.", "fabric.", "sharepoint."]):
                return "Source Connection"
            if "table.nestedjoin" in fn or "table.join" in fn:
                return "Merge / Nested Join"
            if "table.combine" in fn:
                return "Append Queries"
            if "table.selectrows" in fn:
                return "Filter Rows"
            if "table.selectcolumns" in fn or "table.removecolumns" in fn:
                return "Column Projection"
            if "table.transformcolumntypes" in fn:
                return "Type Casting"
            if "table.addcolumn" in fn:
                return "Calculated Column"
            if "table.group" in fn:
                return "Group By / Aggregation"
            if "table.expandtablecolumn" in fn:
                return "Expand Related Table"
            if "table.aggregatetablecolumn" in fn:
                return "Aggregate Related Table"
        return "Transformation"
