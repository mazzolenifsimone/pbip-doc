"""
Data contracts and schema definitions for the PBIP documentation JSON output.
Fully serializable with Python standard library.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
import re
from typing import List, Dict, Optional, Any
from .m_table_parser import parse_m_inline_table


def _prop(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class TableRole(str, Enum):
    FACT = "FACT"
    DIMENSION = "DIMENSION"
    LOOKUP_OUTRIGGER = "LOOKUP_OUTRIGGER"
    BRIDGE = "BRIDGE"
    CALCULATION_GROUP = "CALCULATION_GROUP"
    DATE_DIMENSION = "DATE_DIMENSION"
    PARAMETER_UTILITY = "PARAMETER_UTILITY"
    UNKNOWN = "UNKNOWN"


class Cardinality(str, Enum):
    ONE_TO_MANY = "1:N"
    MANY_TO_ONE = "N:1"
    ONE_TO_ONE = "1:1"
    MANY_TO_MANY = "N:N"


class CrossFilterDirection(str, Enum):
    SINGLE = "Single"
    BOTH = "Both"


@dataclass
class UpstreamModelSummary:
    name: str
    mode: str = "DirectQuery"  # "DirectQuery" or "Import"
    tables_count: int = 0
    measures_count: int = 0
    tables: List[str] = field(default_factory=list)
    measures: List[str] = field(default_factory=list)
    is_in_workspace: bool = False
    target_model_slug: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_upstream_models(
    tables: List[Any],
    measures: List[Any],
) -> List[UpstreamModelSummary]:
    """
    Groups remote/inherited tables and external measures by upstream semantic model.
    Supports both dataclass instances (TableDefinition/MeasureDefinition) and raw dictionaries.
    """
    models_dict: Dict[str, Dict[str, Any]] = {}
    table_to_model: Dict[str, str] = {}

    for t in (tables or []):
        is_rem = bool(
            _prop(t, "is_inherited", False)
            or _prop(t, "source_type", "") == "InheritedEntity"
            or _prop(t, "inherited_model_name", None)
        )
        if not is_rem:
            continue
        m_name = _prop(t, "inherited_model_name", None)
        if not m_name:
            src_expr = _prop(t, "inherited_expression_source", None)
            if src_expr:
                dq_match = re.search(
                    r'^(?:DirectQuery\s+to\s+AS\s*-\s*)(.+)$',
                    str(src_expr).strip().strip("'\""),
                    re.IGNORECASE,
                )
                if dq_match:
                    m_name = dq_match.group(1).strip().strip("'\"")
                elif str(src_expr).strip().strip("'\"") != "DatabaseQuery":
                    m_name = str(src_expr).strip().strip("'\"")
        if not m_name:
            m_name = "Remote Semantic Model"

        t_name = _prop(t, "name")
        if t_name:
            table_to_model[t_name] = m_name

        t_slug = _prop(t, "target_model_slug", None)
        if m_name not in models_dict:
            models_dict[m_name] = {
                "name": m_name,
                "tables": set(),
                "measures": set(),
                "mode": "DirectQuery",
                "target_model_slug": t_slug,
            }
        if t_name:
            models_dict[m_name]["tables"].add(t_name)
        if not models_dict[m_name].get("target_model_slug") and t_slug:
            models_dict[m_name]["target_model_slug"] = t_slug

    single_known_model = next(iter(models_dict.keys())) if len(models_dict) == 1 else None

    for m in (measures or []):
        is_inh = bool(_prop(m, "is_inherited", False) or _prop(m, "is_external_measure", False))
        if not is_inh:
            continue
        m_name = (
            _prop(m, "inherited_model_name", None)
            or table_to_model.get(_prop(m, "table"))
            or single_known_model
            or "Remote Semantic Model"
        )
        m_slug = _prop(m, "target_model_slug", None)
        if m_name not in models_dict:
            models_dict[m_name] = {
                "name": m_name,
                "tables": set(),
                "measures": set(),
                "mode": "DirectQuery",
                "target_model_slug": m_slug,
            }
        models_dict[m_name]["measures"].add(_prop(m, "name") or "Measure")
        if not models_dict[m_name].get("target_model_slug") and m_slug:
            models_dict[m_name]["target_model_slug"] = m_slug

    summaries: List[UpstreamModelSummary] = []
    for name, data in models_dict.items():
        t_sorted = sorted(data["tables"])
        m_sorted = sorted(data["measures"])
        slug = data.get("target_model_slug")
        summaries.append(
            UpstreamModelSummary(
                name=name,
                mode=data["mode"],
                tables_count=len(t_sorted),
                measures_count=len(m_sorted),
                tables=t_sorted,
                measures=m_sorted,
                is_in_workspace=bool(slug),
                target_model_slug=slug,
            )
        )
    return summaries


@dataclass
class PowerQuerySource:
    source_type: str  # e.g., "SQL_SERVER", "SHAREPOINT", "ODATA", "EXCEL", "CSV", "WEB", "LAKEHOUSE", "MANUAL"
    connection_string: str  # Server/database or URL or file path
    server: Optional[str] = None
    database: Optional[str] = None
    schema: Optional[str] = None
    item: Optional[str] = None
    endpoint_or_path: Optional[str] = None
    authentication_mode: Optional[str] = None
    raw_snippet: Optional[str] = None
    is_remote_model: bool = False
    is_in_workspace: bool = False
    target_model_slug: Optional[str] = None
    parameter_query_name: Optional[str] = None
    parameter_value: Optional[str] = None


@dataclass
class PowerQueryLineageStep:
    step_name: str
    operation: str  # e.g., "Source", "Filter", "Merge", "Append", "SelectColumns"
    referenced_queries: List[str] = field(default_factory=list)
    raw_m_code: Optional[str] = None
    transformed_column: Optional[str] = None
    details: Optional[str] = None


@dataclass
class PowerQueryMergeJoin:
    step_name: str
    joined_query: str
    left_keys: List[str] = field(default_factory=list)
    right_keys: List[str] = field(default_factory=list)
    join_kind: str = "LeftOuter"
    expanded_columns: List[str] = field(default_factory=list)
    raw_m_code: Optional[str] = None
    temp_column: Optional[str] = None
    is_cross_join: bool = False


@dataclass
class PowerQueryColumnTransformation:
    """Represents a column-level transformation in Power Query M with full dict compatibility."""
    name: str
    operation: str
    step_name: str
    m_expression: str = ""
    expression: str = ""
    source_column: Optional[str] = None
    source_table: Optional[str] = None
    m_source_table: Optional[str] = None
    join_keys_desc: Optional[str] = None
    data_type: Optional[str] = None

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def __contains__(self, item: str) -> bool:
        return hasattr(self, item) and getattr(self, item) is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "operation": self.operation,
            "step_name": self.step_name,
            "m_expression": self.m_expression,
            "expression": self.expression,
            "source_column": self.source_column,
            "source_table": self.source_table,
            "m_source_table": self.m_source_table,
            "join_keys_desc": self.join_keys_desc,
            "data_type": self.data_type,
        }


@dataclass
class PowerQueryLineageNode:
    query_name: str
    target_table: Optional[str]  # Name of table loaded into the model, if any
    is_staging: bool  # True if this is an internal/unloaded staging query
    direct_dependencies: List[str] = field(default_factory=list)  # Queries directly referenced
    all_upstream_queries: List[str] = field(default_factory=list)  # Transitive upstream queries
    downstream_queries: List[str] = field(default_factory=list)
    downstream_tables: List[str] = field(default_factory=list)  # Final model tables fed by this query
    root_sources: List[PowerQuerySource] = field(default_factory=list)  # Ultimate physical data sources
    full_m_expression: str = ""
    steps: List[PowerQueryLineageStep] = field(default_factory=list)
    unused_steps: List[PowerQueryLineageStep] = field(default_factory=list)
    merges: List[PowerQueryMergeJoin] = field(default_factory=list)
    column_transformations: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    query_group: Optional[str] = None
    lineage_tag: Optional[str] = None
    expression_kind: Optional[str] = None  # "m", "table", "parameter", etc.
    is_m_function: bool = False
    m_function_parameters: List[Any] = field(default_factory=list)
    m_function_return_type: Optional[str] = None
    parameter_value: Optional[str] = None
    parameter_type: Optional[str] = None
    parameter_required: bool = False
    is_inline_table: bool = False
    inline_table_columns: List[str] = field(default_factory=list)
    inline_table_column_types: Dict[str, str] = field(default_factory=dict)
    inline_table_rows: List[List[Any]] = field(default_factory=list)
    inline_table_markdown: Optional[str] = None
    expression_type: str = "STAGING_QUERY"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def resolve_expression_type_and_inline(expr_or_obj: Any) -> Dict[str, Any]:
    """
    Pure domain helper that returns canonical expression_type and inline table
    attributes for a PowerQueryLineageNode or raw dictionary, without requiring
    documentation builders to import M parsers or execute regex heuristics.
    """
    full_m = _prop(expr_or_obj, "full_m_expression", "") or _prop(expr_or_obj, "expression", "") or ""
    is_inline = bool(_prop(expr_or_obj, "is_inline_table", False))
    inline_cols = list(_prop(expr_or_obj, "inline_table_columns", []) or [])
    inline_types = dict(_prop(expr_or_obj, "inline_table_column_types", {}) or {})
    inline_rows = list(_prop(expr_or_obj, "inline_table_rows", []) or [])
    inline_md = _prop(expr_or_obj, "inline_table_markdown", None)

    if not is_inline and "#table" in full_m:
        parsed = parse_m_inline_table(full_m)
        if parsed:
            is_inline = True
            inline_cols = parsed.columns
            inline_types = parsed.column_types
            inline_rows = parsed.rows
            inline_md = parsed.to_markdown_table()

    kind = _prop(expr_or_obj, "expression_kind", "") or ""
    is_loaded = bool(
        _prop(expr_or_obj, "is_loaded_table", False)
        or kind == "table"
        or (not _prop(expr_or_obj, "is_staging", True) and _prop(expr_or_obj, "target_table") and kind != "parameter")
    )
    pre_type = _prop(expr_or_obj, "expression_type", None)

    if is_loaded:
        exp_type = "LOADED_TABLE"
    elif pre_type and str(pre_type).upper() in ("LOADED_TABLE", "PARAMETER", "CUSTOM_FUNCTION", "INLINE_TABLE"):
        exp_type = str(pre_type).upper()
    elif (
        _prop(expr_or_obj, "is_m_function", False)
        or kind == "function"
        or bool(re.search(r'^\s*(\([^\)]*\)|\b[a-zA-Z_][a-zA-Z0-9_]*\b)\s*=>', full_m, re.MULTILINE))
    ):
        exp_type = "CUSTOM_FUNCTION"
    elif (
        kind == "parameter"
        or "IsParameterQuery" in full_m
        or "IsParameterQueryRequired" in full_m
    ):
        exp_type = "PARAMETER"
    elif is_inline or "#table" in full_m:
        exp_type = "INLINE_TABLE"
    else:
        exp_type = str(pre_type).upper() if pre_type else "STAGING_QUERY"

    return {
        "expression_type": exp_type,
        "is_inline_table": is_inline,
        "inline_table_columns": inline_cols,
        "inline_table_column_types": inline_types,
        "inline_table_rows": inline_rows,
        "inline_table_markdown": inline_md,
    }


@dataclass
class FunctionParameter:
    name: str
    data_type: Optional[str] = None
    is_optional: bool = False
    default_value: Optional[str] = None
    description: Optional[str] = None


@dataclass
class FunctionDefinition:
    name: str
    expression: str
    parameters: List[FunctionParameter] = field(default_factory=list)
    parameters_signature: str = ""
    return_type: str = "Variant"
    description: Optional[str] = None
    is_hidden: bool = False
    lineage_tag: Optional[str] = None
    
    # Dependencies
    referenced_functions: List[str] = field(default_factory=list)  # Other UDFs called by this UDF
    referenced_columns: List[Dict[str, str]] = field(default_factory=list)
    referenced_tables: List[str] = field(default_factory=list)
    downstream_measures: List[str] = field(default_factory=list)  # Measures that call this UDF
    downstream_functions: List[str] = field(default_factory=list) # Other UDFs that call this UDF

    def __post_init__(self):
        self.return_type = (self.return_type or "").strip() or "Variant"


@dataclass
class ColumnDefinition:
    name: str
    data_type: str
    is_hidden: bool = False
    is_key: bool = False
    is_calculated: bool = False  # True if this is a DAX calculated column
    format_string: Optional[str] = None
    data_category: Optional[str] = None
    description: Optional[str] = None
    expression: Optional[str] = None  # DAX formula if calculated
    display_folder: Optional[str] = None

    # Power Query & Source Lineage
    source_column: Optional[str] = None
    origin: str = "source"  # "source", "power_query", "dax"
    m_expression: Optional[str] = None
    m_step_name: Optional[str] = None
    m_operation: Optional[str] = None
    m_source_table: Optional[str] = None


@dataclass
class RelationshipDefinition:
    id: str
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: str  # 1:N, N:1, 1:1, N:N
    cross_filtering_behavior: str  # Single, Both
    is_active: bool = True
    security_filtering_behavior: Optional[str] = "None"


@dataclass
class SnowflakePath:
    """
    Represents a transitive path from a Fact table through a Dimension to an Outrigger/Lookup table.
    e.g. FactSales -> DimCustomer -> DimGeography -> DimCountry
    """
    fact_table: str
    dimension_table: str
    lookup_table: str
    path: List[str]  # e.g., ["FactSales", "DimCustomer", "DimGeography"]
    join_keys: List[Dict[str, str]]  # list of {from: "DimCustomer.GeographyKey", to: "DimGeography.GeographyKey"}
    hops: int = 1


@dataclass
class TableRoleClassification:
    role: TableRole
    confidence_score: float  # 0.0 to 1.0
    criteria_matched: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IncrementalRefreshPolicy:
    is_enabled: bool = False
    policy_type: Optional[str] = "basic"
    mode: Optional[str] = "import"  # "import" or "hybrid"
    rolling_window_periods: Optional[int] = None
    rolling_window_granularity: Optional[str] = None  # "year", "quarter", "month", "day"
    incremental_periods: Optional[int] = None
    incremental_granularity: Optional[str] = None  # "year", "quarter", "month", "day"
    polling_expression: Optional[str] = None  # detect data changes query
    source_expression: Optional[str] = None
    raw_policy: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TableDefinition:
    name: str
    role: TableRole
    classification_reasoning: TableRoleClassification
    columns: List[ColumnDefinition] = field(default_factory=list)
    is_hidden: bool = False
    description: Optional[str] = None
    data_category: Optional[str] = None
    source_type: str = "PowerQuery"  # "PowerQuery", "CalculatedTable", "CalculationGroup", "InheritedEntity"
    expression: Optional[str] = None  # DAX table expression if calculated (partition = calculated)
    
    # DAX Lineage / Dependencies (for CalculatedTable)
    referenced_tables: List[str] = field(default_factory=list)
    referenced_columns: List[Dict[str, str]] = field(default_factory=list)
    referenced_measures: List[str] = field(default_factory=list)
    referenced_functions: List[str] = field(default_factory=list)
    
    # Power Query Lineage
    power_query_lineage: Optional[PowerQueryLineageNode] = None
    root_data_sources: List[PowerQuerySource] = field(default_factory=list)
    upstream_queries_chain: List[str] = field(default_factory=list)
    
    # Incremental Refresh Policy
    incremental_refresh_policy: Optional[IncrementalRefreshPolicy] = None
    
    # Relationships & Star Schema connections
    direct_related_tables: List[str] = field(default_factory=list)
    connected_dimensions: List[str] = field(default_factory=list)  # If this is a Fact
    connected_facts: List[str] = field(default_factory=list)  # If this is a Dim
    reachable_lookup_tables: List[str] = field(default_factory=list)  # For facts: dims of dims
    snowflake_paths: List[SnowflakePath] = field(default_factory=list)

    # Inherited Entity / Composite model flags
    is_inherited: bool = False
    inherited_entity_name: Optional[str] = None
    inherited_expression_source: Optional[str] = None
    inherited_model_name: Optional[str] = None
    target_model_slug: Optional[str] = None
    out_of_scope: bool = False


@dataclass
class MeasureDefinition:
    name: str
    table: str
    dax_expression: str
    format_string: Optional[str] = None
    description: Optional[str] = None
    is_hidden: bool = False
    display_folder: Optional[str] = None
    
    # Measure dependency resolution
    calculation_depth: int = 0  # 0 = base measure depending only on columns/scalars
    direct_measure_dependencies: List[str] = field(default_factory=list)  # Measures directly called
    all_upstream_measures: List[str] = field(default_factory=list)  # Transitive closure of measures
    referenced_functions: List[str] = field(default_factory=list)  # UDF functions directly called
    referenced_columns: List[Dict[str, str]] = field(default_factory=list)  # [{"table": "FactSales", "column": "Amount"}]
    referenced_tables: List[str] = field(default_factory=list)
    downstream_measures: List[str] = field(default_factory=list)  # Measures that call this measure

    # Inherited Measure / Composite model flags
    is_inherited: bool = False
    is_external_measure: bool = False
    inherited_model_name: Optional[str] = None
    target_model_slug: Optional[str] = None
    out_of_scope: bool = False


@dataclass
class StarSchemaTopology:
    fact_tables: List[str] = field(default_factory=list)
    dimension_tables: List[str] = field(default_factory=list)
    lookup_outrigger_tables: List[str] = field(default_factory=list)
    bridge_tables: List[str] = field(default_factory=list)
    date_tables: List[str] = field(default_factory=list)
    utility_tables: List[str] = field(default_factory=list)
    fact_dimension_map: Dict[str, List[str]] = field(default_factory=dict)
    fact_to_outriggers_map: Dict[str, List[str]] = field(default_factory=dict)
    snowflake_paths: List[SnowflakePath] = field(default_factory=list)


@dataclass
class PBIPSemanticModel:
    model_name: str
    source_format: str  # "TMDL" or "BIM"
    compatibility_level: Optional[int] = None
    culture: Optional[str] = "en-US"
    created_timestamp: Optional[str] = None
    
    # Main model elements
    tables: List[TableDefinition] = field(default_factory=list)
    relationships: List[RelationshipDefinition] = field(default_factory=list)
    measures: List[MeasureDefinition] = field(default_factory=list)
    functions: List[FunctionDefinition] = field(default_factory=list)
    
    # Power Query Lineage resolution
    shared_queries: List[PowerQueryLineageNode] = field(default_factory=list)
    expressions: List[PowerQueryLineageNode] = field(default_factory=list)
    data_sources_summary: List[PowerQuerySource] = field(default_factory=list)
    
    # Star schema & Snowflake resolution
    star_schema: Optional[StarSchemaTopology] = None
    
    # Measure dependency graph
    measure_dependency_dag: Dict[str, List[str]] = field(default_factory=dict)
    
    # Excluded tables tracking
    excluded_tables_count: int = 0
    excluded_tables_list: List[str] = field(default_factory=list)
    
    # Bound reports consuming this model
    bound_reports_count: int = 0
    bound_reports_info: List[Dict[str, Any]] = field(default_factory=list)

    # Pre-resolved upstream semantic models (composite / thin lineage)
    upstream_models: List[UpstreamModelSummary] = field(default_factory=list)
    
    def filter_excluded_tables(self, is_excluded_fn) -> None:
        """
        Purges auto-generated or user-excluded tables (e.g. LocalDateTable_*, DateTableTemplate_*)
        across all dimensions of the semantic model: tables list, relationships, star schema,
        snowflake paths, and measure dependency references.
        """
        excluded_names = {t.name for t in self.tables if is_excluded_fn(t.name)}
        if not excluded_names:
            return

        self.excluded_tables_count = len(excluded_names)
        self.excluded_tables_list = sorted(list(excluded_names))

        # 1. Filter Tables
        self.tables = [t for t in self.tables if t.name not in excluded_names]

        # 2. Filter Relationships (both from and to)
        self.relationships = [
            r for r in self.relationships
            if r.from_table not in excluded_names and r.to_table not in excluded_names
        ]

        # 3. Filter Measures belonging to excluded tables
        self.measures = [m for m in self.measures if m.table not in excluded_names]

        # Clean measure dependencies and referenced columns/tables
        for m in self.measures:
            m.referenced_tables = [t for t in m.referenced_tables if t not in excluded_names]
            m.referenced_columns = [
                rc for rc in m.referenced_columns
                if rc.get("table") not in excluded_names
            ]

        # Clean function dependencies
        valid_measure_names = {m.name for m in self.measures}
        for fn in self.functions:
            fn.referenced_tables = [t for t in fn.referenced_tables if t not in excluded_names]
            fn.referenced_columns = [
                rc for rc in fn.referenced_columns
                if rc.get("table") not in excluded_names
            ]
            fn.downstream_measures = [dm for dm in fn.downstream_measures if dm in valid_measure_names]

        # Clean calculated table dependencies
        for t in self.tables:
            if t.source_type == "CalculatedTable":
                t.referenced_tables = [rt for rt in t.referenced_tables if rt not in excluded_names]
                t.referenced_columns = [
                    rc for rc in t.referenced_columns
                    if rc.get("table") not in excluded_names
                ]
                t.referenced_measures = [rm for rm in t.referenced_measures if rm in valid_measure_names]

        # 4. Clean and re-resolve Star Schema topology with remaining in-scope tables & relationships
        # This re-evaluates all surviving tables (e.g. date parameter tables previously linked
        # solely to auto date tables now have 0 relationships and become PARAMETER_UTILITY).
        from .star_schema import StarSchemaResolver
        resolver = StarSchemaResolver(
            self.tables,
            self.relationships,
            is_table_excluded_fn=is_excluded_fn,
        )
        resolver.classify_tables()
        self.star_schema = resolver.resolve_topology_and_snowflakes()

        # 6. Clean M Lineage downstream tables
        for node in self.shared_queries:
            node.downstream_tables = [
                dt for dt in node.downstream_tables if dt not in excluded_names
            ]
        for node in self.expressions:
            node.downstream_tables = [
                dt for dt in node.downstream_tables if dt not in excluded_names
            ]

        # 7. Update upstream_models summary
        if self.upstream_models:
            prev_meta = {u.name: (u.is_in_workspace, u.target_model_slug, u.mode) for u in self.upstream_models}
            new_up = compute_upstream_models(self.tables, self.measures)
            for u in new_up:
                if u.name in prev_meta:
                    u.is_in_workspace, u.target_model_slug, u.mode = prev_meta[u.name]
            self.upstream_models = new_up

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire model to standard Python dictionary ready for JSON dump."""
        return asdict(self)
