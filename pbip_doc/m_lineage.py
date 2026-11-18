"""
Power Query (M) Lineage Resolver.
Analyzes M expressions, detects connector source calls, and resolves
multi-step query dependencies transitively from raw data sources to final model tables.
100% Python Standard Library implementation with zero external runtime dependencies.
Powered by AST recursive-descent parsing (m_parser.py) and step graph analysis (m_step_graph.py).
"""

import re
from typing import Dict, List, Set, Tuple, Optional, Any
from .model_schema import (
    PowerQuerySource,
    PowerQueryLineageNode,
    PowerQueryLineageStep,
    PowerQueryMergeJoin,
    PowerQueryColumnTransformation,
    FunctionParameter,
)
from .m_table_parser import parse_m_inline_table
from .m_parser import parse_m, MMetadataExpr, MRecordExpr, MLiteral, MInvocationExpr, MIdentifier, MSectionDocument, MSectionMember
from .m_step_graph import MStepGraph, _ast_to_raw_snippet


class MLineageResolver:
    """
    Parses Power Query M code, tracks inter-query dependencies,
    and extracts original data sources (SQL, SharePoint, Web, Excel, etc.)
    using AST analysis, backward slicing, and symbolic dataflow.
    """

    CONNECTOR_PATTERNS = [
        # SQL / Relational
        (r'\bSql\.Database\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "SQL_SERVER", "server_db"),
        (r'\bSql\.Databases\s*\(\s*["\']([^"\']+)["\']', "SQL_SERVER", "server_only"),
        (r'\bPostgreSQL\.Database\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "POSTGRESQL", "server_db"),
        (r'\bMySQL\.Database\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "MYSQL", "server_db"),
        (r'\bOracle\.Database\s*\(\s*["\']([^"\']+)["\']', "ORACLE", "server_only"),
        (r'\bSnowflake\.Databases\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "SNOWFLAKE", "server_db"),
        (r'\bGoogleBigQuery\.Database\s*\(', "BIGQUERY", "generic"),
        
        # Analysis Services / Power BI Semantic Models
        (r'\bAnalysisServices\.Database\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']', "ANALYSIS_SERVICES", "server_db"),
        (r'\bAnalysisServices\.Databases\s*\(\s*["\']([^"\']+)["\']\s*\)\s*\{[^}]*\[(?:Name|Item)\s*=\s*["\']([^"\']+)["\']', "ANALYSIS_SERVICES", "server_db"),
        (r'\bAnalysisServices\.Databases\s*\(\s*["\']([^"\']+)["\']', "ANALYSIS_SERVICES", "server_only"),

        # Files & Storage
        (r'\bExcel\.Workbook\s*\(\s*File\.Contents\s*\(\s*["\']([^"\']+)["\']', "EXCEL_FILE", "filepath"),
        (r'\bCsv\.Document\s*\(\s*File\.Contents\s*\(\s*["\']([^"\']+)["\']', "CSV_FILE", "filepath"),
        (r'\bFile\.Contents\s*\(\s*["\']([^"\']+)["\']', "LOCAL_FILE", "filepath"),
        (r'\bFolder\.Files\s*\(\s*["\']([^"\']+)["\']', "FOLDER", "filepath"),
        (r'\bSharePoint\.Files\s*\(\s*["\']([^"\']+)["\']', "SHAREPOINT", "url"),
        (r'\bSharePoint\.Tables\s*\(\s*["\']([^"\']+)["\']', "SHAREPOINT", "url"),
        (r'\bAzureStorage\.BlobContents\s*\(\s*["\']([^"\']+)["\']', "AZURE_BLOB", "url"),
        (r'\bAzureStorage\.DataLake\s*\(\s*["\']([^"\']+)["\']', "AZURE_DATALAKE", "url"),
        (r'\bFabric\.Lakehouse\s*\(\s*["\']([^"\']+)["\']', "FABRIC_LAKEHOUSE", "endpoint"),
        
        # Web & OData APIs & ODBC
        (r'\bOData\.Feed\s*\(\s*["\']([^"\']+)["\']', "ODATA", "url"),
        (r'\bWeb\.Contents\s*\(\s*["\']([^"\']+)["\']', "WEB_API", "url"),
        (r'\bWeb\.BrowserContents\s*\(\s*["\']([^"\']+)["\']', "WEB_BROWSER", "url"),
        (r'\bOdbc\.DataSource\s*\(\s*["\']([^"\']+)["\']', "ODBC", "url"),
        (r'\bOdbc\.Query\s*\(\s*["\']([^"\']+)["\']', "ODBC", "url"),
        (r'\bSalesforce\.Data\s*\(', "SALESFORCE", "generic"),
    ]

    def __init__(self, raw_queries: Dict[str, Dict[str, Any]]):
        """
        raw_queries: dictionary of query_name -> {
            "m_code": str,
            "target_table": Optional[str],
            "is_staging": bool
        }
        """
        self.raw_queries = dict(raw_queries)
        self._unpack_section_queries()
        self.known_query_names = set(self.raw_queries.keys())
        self.known_parameter_names = {
            q_name for q_name, q_info in self.raw_queries.items()
            if q_info.get("kind") == "parameter"
            or q_info.get("expression_kind") == "parameter"
            or "IsParameterQuery" in q_info.get("m_code", "")
            or "IsParameterQuery" in q_info.get("expression", "")
        }
        self.nodes: Dict[str, PowerQueryLineageNode] = {}
        self._build_nodes()
        self._resolve_transitive_lineage()

    def _unpack_section_queries(self):
        """
        If any query in raw_queries defines an M section document
        (e.g. 'section SecName; shared QueryA = ...; shared QueryB = ...;'),
        extracts each shared member into raw_queries as an autonomous entry.
        """
        extra_queries: Dict[str, Dict[str, Any]] = {}
        sections_to_remove: List[str] = []

        for q_name, q_info in list(self.raw_queries.items()):
            code = q_info.get("m_code") or q_info.get("expression") or ""
            if "section" in code:
                try:
                    ast = parse_m(code)
                    if isinstance(ast, MSectionDocument):
                        sections_to_remove.append(q_name)
                        for member in ast.members:
                            if member.is_shared:
                                code_str = getattr(member, "raw_code", "") or _ast_to_raw_snippet(member.expression, max_len=0)
                                extra_queries[member.name] = {
                                    "m_code": code_str,
                                    "expression_ast": member.expression,
                                    "target_table": None,
                                    "is_staging": True,
                                    "section_name": ast.section_name,
                                }
                except Exception:
                    pass

        if extra_queries:
            for s_name in sections_to_remove:
                if s_name not in extra_queries:
                    del self.raw_queries[s_name]
            self.raw_queries.update(extra_queries)

    def _strip_string_literals(self, m_code: str) -> str:
        """Removes regular string literals '\"...\"' while preserving '#\"...\"' identifiers."""
        quoted_identifiers = re.findall(r'#"[^"]+"', m_code)
        placeholder_map = {}
        for i, q in enumerate(quoted_identifiers):
            token = f"___QUOTED_ID_{i}___"
            placeholder_map[token] = q
            m_code = m_code.replace(q, token, 1)

        m_code_no_strings = re.sub(r'"[^"]*"', '""', m_code)

        for token, original in placeholder_map.items():
            m_code_no_strings = m_code_no_strings.replace(token, original)

        return m_code_no_strings

    def _extract_quoted_identifiers(self, m_code: str) -> Set[str]:
        """Extracts #"Query Name" references."""
        matches = re.findall(r'#"[^"]+"', m_code)
        cleaned = {m[2:-1] for m in matches}
        return cleaned

    def _extract_word_identifiers(self, m_code: str, local_steps: Set[str]) -> Set[str]:
        """Extracts unquoted identifiers that match known queries, excluding string literals and local step names."""
        code_clean = self._strip_string_literals(m_code)
        tokens = set(re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code_clean))
        external_tokens = tokens - local_steps
        return external_tokens.intersection(self.known_query_names)

    @staticmethod
    def _endpoint_key(val: str) -> str:
        """Normalizes path/endpoint string for deduplication."""
        return val.strip().lower().replace("/", "\\")

    @classmethod
    def _source_identity_key(cls, s: PowerQuerySource) -> str:
        """Computes resource identity key prioritizing endpoint/connection over generic types."""
        if s.endpoint_or_path:
            return f"path:{cls._endpoint_key(s.endpoint_or_path)}"
        if s.server and s.database:
            return f"server_db:{s.server.strip().lower()} / {s.database.strip().lower()}"
        if s.server:
            return f"server:{s.server.strip().lower()}"
        if s.database:
            return f"db:{s.database.strip().lower()}"
        if s.connection_string:
            return f"conn:{cls._endpoint_key(s.connection_string)}"
        return f"{s.source_type}:{s.raw_snippet or ''}"

    @classmethod
    def _merge_source_into_dict(cls, sources_dict: Dict[str, PowerQuerySource], s: PowerQuerySource):
        """Merges a source into dictionary, allowing specialized source types to supersede generic ones."""
        key = cls._source_identity_key(s)
        if key not in sources_dict:
            sources_dict[key] = s
        else:
            existing = sources_dict[key]
            if existing.source_type == "LOCAL_FILE" and s.source_type in ("EXCEL_FILE", "CSV_FILE"):
                sources_dict[key] = s
            elif existing.source_type == "INHERITED_ENTITY" and s.source_type in ("ANALYSIS_SERVICES", "POWERBI_SEMANTIC_MODEL"):
                sources_dict[key] = s

    def _extract_sources(self, m_code: str) -> List[PowerQuerySource]:
        """Scans M code for connector source calls using AST Step Graph with regex fallback."""
        if not m_code:
            return []
        try:
            ast = parse_m(m_code)
            graph = MStepGraph(ast, raw_code=m_code, known_query_names=self.known_query_names, known_parameter_names=self.known_parameter_names)
            if graph.root_sources:
                return graph.root_sources
        except Exception:
            pass

        # Robust regex fallback
        sources: List[PowerQuerySource] = []
        seen_endpoints: Set[str] = set()

        for pattern, source_type, mode in self.CONNECTOR_PATTERNS:
            for match in re.finditer(pattern, m_code, re.IGNORECASE):
                snippet = match.group(0)
                if mode == "server_db":
                    server = match.group(1)
                    db = match.group(2)
                    stype = source_type
                    if source_type == "ANALYSIS_SERVICES" and any(pbi in server.lower() for pbi in ("powerbi://", "api.powerbi.com", "pbiazure://")):
                        stype = "POWERBI_SEMANTIC_MODEL"
                    ep_key = f"server_db:{server.strip().lower()} / {db.strip().lower()}"
                    if ep_key in seen_endpoints:
                        continue
                    seen_endpoints.add(ep_key)
                    seen_endpoints.add(f"server:{server.strip().lower()}")
                    sources.append(
                        PowerQuerySource(
                            source_type=stype,
                            connection_string=f"{server} / {db}",
                            server=server,
                            database=db,
                            raw_snippet=snippet,
                        )
                    )
                elif mode == "server_only":
                    server = match.group(1)
                    stype = source_type
                    if source_type == "ANALYSIS_SERVICES" and any(pbi in server.lower() for pbi in ("powerbi://", "api.powerbi.com", "pbiazure://")):
                        stype = "POWERBI_SEMANTIC_MODEL"
                    ep_key = f"server:{server.strip().lower()}"
                    if ep_key in seen_endpoints:
                        continue
                    seen_endpoints.add(ep_key)
                    sources.append(
                        PowerQuerySource(
                            source_type=stype,
                            connection_string=server,
                            server=server,
                            raw_snippet=snippet,
                        )
                    )
                elif mode in ("filepath", "url", "endpoint"):
                    val = match.group(1)
                    ep_key = f"path:{self._endpoint_key(val)}"
                    if ep_key in seen_endpoints:
                        continue
                    seen_endpoints.add(ep_key)
                    sources.append(
                        PowerQuerySource(
                            source_type=source_type,
                            connection_string=val,
                            endpoint_or_path=val,
                            raw_snippet=snippet,
                        )
                    )
                else:
                    sources.append(
                        PowerQuerySource(
                            source_type=source_type,
                            connection_string="Cloud Service / API",
                            raw_snippet=snippet,
                        )
                    )

        if not sources:
            if "#table(" in m_code or "Table.FromRows" in m_code or "Table.FromRecords" in m_code:
                sources.append(
                    PowerQuerySource(
                        source_type="MANUAL_INLINE",
                        connection_string="Inline Table.FromRows / Static M Table",
                    )
                )

        # Regex fallback for schema and item/table navigation
        schema_found = None
        item_found = None
        nav_match = re.search(r'\{\[\s*Schema\s*=\s*["\']([^"\']+)["\']\s*,\s*Item\s*=\s*["\']([^"\']+)["\']', m_code, re.IGNORECASE)
        if nav_match:
            schema_found = nav_match.group(1)
            item_found = nav_match.group(2)
        else:
            nav_match_rev = re.search(r'\{\[\s*Item\s*=\s*["\']([^"\']+)["\']\s*,\s*Schema\s*=\s*["\']([^"\']+)["\']', m_code, re.IGNORECASE)
            if nav_match_rev:
                schema_found = nav_match_rev.group(2)
                item_found = nav_match_rev.group(1)
            else:
                name_match = re.search(r'\{\[\s*(?:Item|Name)\s*=\s*["\']([^"\']+)["\']', m_code, re.IGNORECASE)
                if name_match:
                    item_found = name_match.group(1)

        if item_found:
            for s in sources:
                if not s.item:
                    s.schema = schema_found
                    s.item = item_found
                    if not s.endpoint_or_path:
                        full_name = f"{schema_found}.{item_found}" if schema_found else item_found
                        s.endpoint_or_path = full_name
                        if full_name not in s.connection_string:
                            s.connection_string = f"{s.connection_string} ➔ [{full_name}]"
                    break

        return sources

    def _extract_steps(self, m_code: str) -> List[PowerQueryLineageStep]:
        """Extracts individual transformation steps inside a 'let ... in' block via AST."""
        if not m_code:
            return []
        try:
            ast = parse_m(m_code)
            graph = MStepGraph(ast, raw_code=m_code, known_query_names=self.known_query_names, known_parameter_names=self.known_parameter_names)
            return graph.get_lineage_steps()
        except Exception:
            return []

    def _extract_column_transformations_and_merges(
        self, m_code: str
    ) -> Tuple[Dict[str, Any], List[PowerQueryMergeJoin]]:
        """
        Extracts column-level transformations (AddColumn, CombineColumns, DuplicateColumn,
        IndexColumn, SplitColumn, RenameColumns) and detailed table joins (NestedJoin, Join, CrossJoin, ExpandTableColumn).
        """
        if not m_code:
            return {}, []
        try:
            ast = parse_m(m_code)
            graph = MStepGraph(ast, raw_code=m_code, known_query_names=self.known_query_names, known_parameter_names=self.known_parameter_names)
            return graph.column_transformations, graph.merges
        except Exception:
            return {}, []

    def _build_nodes(self):
        """Initial pass: parse dependencies, immediate sources, column transformations, and merges for each query."""
        for query_name, info in self.raw_queries.items():
            m_code = info.get("m_code") or info.get("expression") or ""
            target_table = info.get("target_table")
            is_staging = info.get("is_staging", False)

            # AST and Step Graph analysis
            ast = info.get("expression_ast") or parse_m(m_code)
            graph = MStepGraph(ast, raw_code=m_code, known_query_names=self.known_query_names, known_parameter_names=self.known_parameter_names)

            steps = graph.get_lineage_steps()
            unused_steps = graph.get_unused_steps()
            immediate_sources = graph.root_sources or self._extract_sources(m_code)
            col_transformations = graph.column_transformations
            merges = graph.merges

            # Tag source table on transformations if not set
            for tf in col_transformations.values():
                if not tf.get("m_source_table"):
                    if isinstance(tf, PowerQueryColumnTransformation):
                        tf.m_source_table = query_name
                    elif isinstance(tf, dict):
                        tf["m_source_table"] = query_name

            # Detect direct dependencies
            direct_deps = sorted(list(graph.direct_dependencies - {query_name}))

            # Detect inline table (#table)
            inline_tbl = parse_m_inline_table(m_code)
            is_inline = inline_tbl is not None
            inline_cols = inline_tbl.columns if inline_tbl else []
            inline_types = inline_tbl.column_types if inline_tbl else {}
            inline_rows = inline_tbl.rows if inline_tbl else []
            inline_md = inline_tbl.to_markdown_table() if inline_tbl else None

            description = info.get("description")
            query_group = info.get("query_group")
            lineage_tag = info.get("lineage_tag")
            kind = info.get("kind")

            # Check parameter query
            is_param = graph.is_parameter or ("IsParameterQuery" in m_code or "meta [IsParameterQuery=true" in m_code)
            if is_param:
                kind = "parameter"
                is_staging = False

            # Check M custom function
            is_m_fn = graph.is_custom_function
            fn_params = graph.function_parameters
            fn_ret = graph.function_return_type
            if is_m_fn and not kind:
                kind = "function"

            effective_target_table = target_table or (query_name if (not is_staging and not is_param) else None)
            if is_m_fn or kind == "function" or bool(re.search(r'^\s*(\([^\)]*\)|\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*=>', m_code, re.MULTILINE)):
                expr_type = "CUSTOM_FUNCTION"
            elif is_param or kind == "parameter" or "IsParameterQuery" in m_code or "IsParameterQueryRequired" in m_code:
                expr_type = "PARAMETER"
            elif effective_target_table:
                expr_type = "LOADED_TABLE"
            elif is_inline or "#table" in m_code:
                expr_type = "INLINE_TABLE"
            else:
                expr_type = "STAGING_QUERY"

            self.nodes[query_name] = PowerQueryLineageNode(
                query_name=query_name,
                target_table=effective_target_table,
                is_staging=is_staging,
                direct_dependencies=direct_deps,
                all_upstream_queries=[],
                downstream_queries=[],
                downstream_tables=[],
                root_sources=immediate_sources,
                full_m_expression=m_code,
                steps=steps,
                unused_steps=unused_steps,
                merges=merges,
                column_transformations=col_transformations,
                description=description,
                query_group=query_group,
                lineage_tag=lineage_tag,
                expression_kind=kind,
                is_m_function=is_m_fn,
                m_function_parameters=fn_params,
                m_function_return_type=fn_ret,
                parameter_value=graph.parameter_value,
                parameter_type=graph.parameter_type,
                parameter_required=graph.parameter_required,
                is_inline_table=is_inline,
                inline_table_columns=inline_cols,
                inline_table_column_types=inline_types,
                inline_table_rows=inline_rows,
                inline_table_markdown=inline_md,
                expression_type=expr_type,
            )

    def _resolve_transitive_lineage(self):
        """
        Computes transitive upstream dependencies, propagates root sources,
        inherits upstream column transformations & merges, resolves cross-expression parameters,
        and computes downstream pointers.
        """
        # First compute downstream pointers
        for name, node in self.nodes.items():
            for dep in node.direct_dependencies:
                if dep in self.nodes:
                    if name not in self.nodes[dep].downstream_queries:
                        self.nodes[dep].downstream_queries.append(name)

        # Transitive closure for all_upstream_queries, root_sources, and column_transformations
        for query_name, node in self.nodes.items():
            visited: Set[str] = set()
            all_sources: Dict[str, PowerQuerySource] = {}

            # Add direct sources
            for s in node.root_sources:
                self._merge_source_into_dict(all_sources, s)

            # Breadth-first search for ancestors
            queue = list(node.direct_dependencies)
            while queue:
                curr = queue.pop(0)
                if curr in visited or curr not in self.nodes or curr == query_name:
                    continue
                visited.add(curr)
                parent_node = self.nodes[curr]

                # Inherit root sources from parent
                for s in parent_node.root_sources:
                    self._merge_source_into_dict(all_sources, s)

                # Queue grandparents
                for p_dep in parent_node.direct_dependencies:
                    if p_dep not in visited:
                        queue.append(p_dep)

            node.all_upstream_queries = sorted(list(visited))
            node.root_sources = list(all_sources.values())

            # Inherit column transformations and merges from upstream queries (e.g. Staging queries)
            for u_query in node.all_upstream_queries:
                if u_query in self.nodes:
                    parent_node = self.nodes[u_query]
                    for col_name, tf in parent_node.column_transformations.items():
                        if col_name not in node.column_transformations:
                            node.column_transformations[col_name] = tf
                    for m_join in parent_node.merges:
                        if not any(existing.step_name == m_join.step_name and existing.joined_query == m_join.joined_query for existing in node.merges):
                            node.merges.append(m_join)

        # Parameter resolution: if any root source uses a parameter query name, resolve its value
        parameter_values: Dict[str, str] = {}
        for q_name, q_node in self.nodes.items():
            if q_node.expression_kind == "parameter" or "meta [IsParameterQuery" in q_node.full_m_expression:
                # Extract literal value from expression
                val_match = re.match(r'^\s*("[^"]*"|\d+|true|false)', q_node.full_m_expression)
                if val_match:
                    parameter_values[q_name] = val_match.group(1).strip('"')

        if parameter_values:
            for node in self.nodes.values():
                for src in node.root_sources:
                    if src.server and src.server in parameter_values:
                        src.server = parameter_values[src.server]
                    if src.database and src.database in parameter_values:
                        src.database = parameter_values[src.database]
                    if src.endpoint_or_path and src.endpoint_or_path in parameter_values:
                        src.endpoint_or_path = parameter_values[src.endpoint_or_path]

        # Compute downstream final tables for all queries (especially staging)
        for query_name, node in self.nodes.items():
            downstream_tables: Set[str] = set()
            visited: Set[str] = set()
            queue = list(node.downstream_queries)

            if node.target_table:
                downstream_tables.add(node.target_table)

            while queue:
                curr = queue.pop(0)
                if curr in visited or curr not in self.nodes:
                    continue
                visited.add(curr)
                child_node = self.nodes[curr]
                if child_node.target_table:
                    downstream_tables.add(child_node.target_table)
                queue.extend(child_node.downstream_queries)

            node.downstream_tables = sorted(list(downstream_tables))

    def get_lineage_for_table(self, table_name: str) -> Optional[PowerQueryLineageNode]:
        """Returns the complete lineage node for a specific table."""
        if table_name in self.nodes:
            return self.nodes[table_name]
        for node in self.nodes.values():
            if node.target_table == table_name:
                return node
        return None

    def get_lineage_for_expression(self, expression_name: str) -> Optional[PowerQueryLineageNode]:
        """Returns the complete lineage node for a specific expression or query."""
        return self.nodes.get(expression_name)

    def get_lineage_for_query(self, query_name: str) -> Optional[PowerQueryLineageNode]:
        """Alias for get_lineage_for_expression."""
        return self.nodes.get(query_name)

    def get_all_nodes(self) -> Dict[str, PowerQueryLineageNode]:
        return self.nodes

    def get_all_root_sources(self) -> List[PowerQuerySource]:
        """Returns unique physical sources across the entire semantic model."""
        unique_sources: Dict[str, PowerQuerySource] = {}
        for node in self.nodes.values():
            for s in node.root_sources:
                self._merge_source_into_dict(unique_sources, s)
        return list(unique_sources.values())
