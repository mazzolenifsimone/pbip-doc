"""
Utility functions for markdown formatting and YAML frontmatter serialization.
100% Vanilla Python standard library.
"""

import re
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional, Set, Tuple


def sanitize_filename(name: str) -> str:
    """
    Cleans output file names and reference links by replacing characters
    prohibited in filesystem paths (\\, /, :, *, ?, ", <, >, |, brackets, quotes, spaces, control chars)
    with the '_' character.
    """
    if not name:
        return "unnamed"
    # Replace prohibited path characters and characters unsafe in paths/links with '_'
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f\t\r\n\[\]\'#%&`]', '_', name)
    cleaned = re.sub(r'[^\w\-\.]', '_', cleaned)
    # Collapse consecutive underscores into a single underscore
    cleaned = re.sub(r'_+', '_', cleaned)
    # Strip trailing dots or spaces which are invalid in Windows filesystem paths
    cleaned = cleaned.rstrip('. ')
    return cleaned or "unnamed"


def join_doc_path(base: str, *parts: str) -> str:
    """
    Joins a base URL or file path with one or more path components using forward slashes.
    Preserves http://, https://, file://, Windows drive letters (C:/), and UNC paths (//server/share).
    Avoids duplicate slashes and normalizes paths for Markdown link compatibility.
    """
    if not base:
        sub_parts = [str(p).strip("/\\").replace("\\", "/") for p in parts if str(p).strip("/\\")]
        return "/".join(sub_parts)

    is_network = base.startswith("\\\\") or base.startswith("//")
    clean_base = base.replace("\\", "/").rstrip("/")
    if is_network and not clean_base.startswith("//"):
        clean_base = "/" + clean_base

    sub_parts = [str(p).strip("/\\").replace("\\", "/") for p in parts if str(p).strip("/\\")]
    if not sub_parts:
        return clean_base
    return clean_base + "/" + "/".join(sub_parts)


def clean_project_name(name: Any) -> str:
    """
    Normalizes a PBIP project name by stripping technical suffixes
    such as .SemanticModel, .Report, or .pbip.
    """
    if not name:
        return "PBIP"
    clean = str(name).strip()
    for suffix in [".SemanticModel", ".semanticmodel", ".Report", ".report", ".pbip", ".PBIP"]:
        if clean.endswith(suffix):
            clean = clean[:-len(suffix)]
    return clean or "PBIP"


def resolve_model_index_filename(config: Optional[Any], project_name: str) -> str:
    """
    Resolves the Markdown master catalog filename for a semantic model.
    Uses config.index_filename when explicitly set (e.g. 'README.md' in Workspace Mode
    or a custom override), otherwise defaults to '<SanitizedProjectName>.md'.
    """
    if config is not None and getattr(config, "index_filename", None):
        return str(config.index_filename)
    safe_name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', project_name or "PBIP").strip('. ') or "PBIP"
    return f"{safe_name}.md"


def resolve_model_index_url(config: Optional[Any], project_name: str, current_rel_dir: str = "") -> str:
    """
    Builds the relative (or base_doc_url-prefixed) Markdown URL pointing back
    to the semantic model's master catalog file from `current_rel_dir`.
    """
    index_file = resolve_model_index_filename(config, project_name)
    if config is not None and getattr(config, "base_doc_url", None):
        return join_doc_path(config.base_doc_url, index_file)
    clean_dir = (current_rel_dir or "").strip("/\\").replace("\\", "/")
    if not clean_dir:
        return index_file
    depth = len([seg for seg in clean_dir.split("/") if seg])
    return ("../" * depth) + index_file


def resolve_bound_reports_count(
    model_data: Any,
    bound_reports_info: Optional[List[Dict[str, Any]]] = None,
    report_model: Optional[Any] = None,
    include_reports: bool = True,
) -> int:
    """
    Resolves the bound reports count for a semantic model across Workspace Mode
    (explicit bound_reports_count / bound_reports_info) and Single-Model Mode
    (associated report_model when PBIPSemanticModel.to_dict() defaults bound_reports_count to 0).
    """
    raw_cnt = (
        model_data.get("bound_reports_count")
        if isinstance(model_data, dict)
        else getattr(model_data, "bound_reports_count", None)
    )
    if isinstance(raw_cnt, int) and not isinstance(raw_cnt, bool) and raw_cnt > 0:
        return raw_cnt
    if bound_reports_info:
        return len(bound_reports_info)
    if report_model is not None and include_reports:
        return 1
    if isinstance(raw_cnt, int) and not isinstance(raw_cnt, bool) and raw_cnt >= 0:
        return raw_cnt
    return 0


def extract_by_connection_model_candidates(by_conn: Optional[Dict[str, Any]]) -> List[str]:
    """
    Extracts ordered candidate semantic model names from a PBIR datasetReference.byConnection block.
    Prioritizes `Initial Catalog` from `connectionString` (stripping surrounding quotes/whitespace),
    falling back to `pbiModelDatabaseName` (which in Power BI Service is often a GUID).
    """
    if not isinstance(by_conn, dict):
        return []

    candidates: List[str] = []

    conn_str = by_conn.get("connectionString") or ""
    if isinstance(conn_str, str) and conn_str:
        m = re.search(
            r'Initial\s+Catalog\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^;]+))',
            conn_str,
            re.IGNORECASE,
        )
        if m:
            raw_cat = next((g for g in m.groups() if g is not None), "")
            cat = raw_cat.strip().strip('"').strip("'").strip()
            if cat:
                candidates.append(cat)

    pbi_db = by_conn.get("pbiModelDatabaseName")
    if isinstance(pbi_db, str):
        pbi_db_clean = pbi_db.strip().strip('"').strip("'").strip()
        if pbi_db_clean and pbi_db_clean not in candidates:
            candidates.append(pbi_db_clean)

    return candidates


def format_yaml_frontmatter(data: Dict[str, Any]) -> str:
    """
    Serializes a dictionary into standard clean YAML frontmatter block.
    Uses json.dumps for safe scalar serialization to prevent invalid escape sequences
    (such as Windows paths \\U or \\m) from breaking YAML parsers.
    No PyYAML or external library required.
    """
    import json

    lines = ["---"]
    for key, val in data.items():
        if val is None:
            continue
        if isinstance(val, (int, float, bool)):
            lines.append(f"{key}: {str(val).lower() if isinstance(val, bool) else val}")
        elif isinstance(val, str):
            # If string contains special characters or backslashes, serialize with json.dumps for safe YAML double-quoting
            if any(ch in val for ch in [':', '#', '@', '{', '}', '[', ']', ',', '&', '*', '?', '|', '>', '!', '%', '\n', '\\', '"', '`']):
                lines.append(f"{key}: {json.dumps(val)}")
            else:
                lines.append(f"{key}: {val}")
        elif isinstance(val, list):
            if not val:
                lines.append(f"{key}: []")
            elif all(isinstance(x, (str, int, float, bool)) for x in val) and len(val) <= 5 and not any(isinstance(x, str) and (':' in x or '"' in x or '\\' in x or '\n' in x) for x in val):
                # Simple inline array
                items_str = ", ".join(json.dumps(x) if isinstance(x, str) else str(x) for x in val)
                lines.append(f"{key}: [{items_str}]")
            else:
                lines.append(f"{key}:")
                for item in val:
                    if isinstance(item, dict):
                        # Nested dict inside list
                        first = True
                        for dk, dv in item.items():
                            dv_str = json.dumps(dv) if isinstance(dv, str) and any(ch in dv for ch in [':', '#', '@', '{', '}', '[', ']', ',', '&', '*', '?', '|', '>', '!', '%', '\n', '\\', '"', '`']) else dv
                            if first:
                                lines.append(f"  - {dk}: {dv_str}")
                                first = False
                            else:
                                lines.append(f"    {dk}: {dv_str}")
                    else:
                        item_str = json.dumps(item) if isinstance(item, str) else str(item)
                        lines.append(f"  - {item_str}")
        elif isinstance(val, dict):
            if not val:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                for dk, dv in val.items():
                    if isinstance(dv, list):
                        items_str = ", ".join(json.dumps(x) if isinstance(x, str) else str(x) for x in dv)
                        lines.append(f"  {dk}: [{items_str}]")
                    else:
                        dv_str = json.dumps(dv) if isinstance(dv, str) and any(ch in dv for ch in [':', '#', '@', '{', '}', '[', ']', ',', '&', '*', '?', '|', '>', '!', '%', '\n', '\\', '"', '`']) else dv
                        lines.append(f"  {dk}: {dv_str}")
    lines.append("---")
    return "\n".join(lines)


def _get_prop(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    val = getattr(obj, key, default)
    return default if val is None else val


def is_table_remote(table_obj_or_dict: Any) -> bool:
    """
    Canonical check determining whether a table (dataclass or dict) represents
    a remote / inherited entity from an upstream semantic model.
    """
    if not table_obj_or_dict:
        return False
    return bool(
        _get_prop(table_obj_or_dict, "is_inherited")
        or _get_prop(table_obj_or_dict, "source_type") == "InheritedEntity"
        or _get_prop(table_obj_or_dict, "inherited_model_name")
    )


def filter_local_scope_relationships(
    relationships: Any,
    tables: Any,
    config: Optional[Any] = None,
) -> List[Any]:
    """
    Filters semantic model relationships according to the local documentation perimeter:
    - Local <-> Local: INCLUDED
    - Local <-> Remote: INCLUDED
    - Remote <-> Remote: EXCLUDED
    Also filters out relationships touching excluded tables when config is provided.
    Supports both dataclass objects and dictionaries.
    """
    if not relationships:
        return []

    table_map: Dict[str, Any] = {}
    for t in (tables or []):
        t_name = _get_prop(t, "name")
        if t_name:
            table_map[t_name] = t

    filtered: List[Any] = []
    for rel in relationships:
        from_t = _get_prop(rel, "from_table")
        to_t = _get_prop(rel, "to_table")
        if config is not None:
            if config.is_table_excluded(from_t) or config.is_table_excluded(to_t):
                continue
        if is_table_remote(table_map.get(from_t)) and is_table_remote(table_map.get(to_t)):
            continue
        filtered.append(rel)
    return filtered


def resolve_workspace_model_slug(
    name: Optional[str],
    model_data: Any = None,
    config: Optional[Any] = None,
) -> Optional[str]:
    """
    Centralized resolver for a semantic model slug within the active workspace.
    Checks pre-computed workspace_models dictionary from model_data or config.
    """
    if not name or name == "—":
        return None
    ws_models = (
        (_get_prop(model_data, "workspace_models") if model_data else None)
        or (getattr(config, "workspace_models", None) if config else None)
        or {}
    )
    if not ws_models:
        return None
    if name in ws_models:
        return ws_models[name]
    low = name.lower()
    if low in ws_models:
        return ws_models[low]
    san_low = sanitize_filename(name).lower()
    if san_low in ws_models:
        return ws_models[san_low]
    return None


def get_model_upstream_summaries(
    model_data: Any,
    config: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Reads pre-calculated upstream_models from model_data (or delegates to compute_upstream_models
    for raw test dicts) and ensures target_model_slug and is_in_workspace are populated.
    """
    if not model_data:
        return []

    raw_up = _get_prop(model_data, "upstream_models")
    if not raw_up:
        from ..model_schema import compute_upstream_models
        tables = _get_prop(model_data, "tables", []) or []
        measures = _get_prop(model_data, "measures", []) or []
        raw_up = [
            u.to_dict() if hasattr(u, "to_dict") else asdict(u)
            for u in compute_upstream_models(tables, measures)
        ]

    results: List[Dict[str, Any]] = []
    for item in raw_up:
        d = asdict(item) if is_dataclass(item) else (dict(item) if isinstance(item, dict) else {})
        if not d:
            continue
        t_list = d.get("tables", [])
        m_list = d.get("measures", [])
        d["tables_count"] = d.get("tables_count") if d.get("tables_count") is not None else len(t_list)
        d["measures_count"] = d.get("measures_count") if d.get("measures_count") is not None else len(m_list)
        d["mode"] = d.get("mode", "DirectQuery")
        if not d.get("target_model_slug"):
            slug = resolve_workspace_model_slug(d.get("name"), model_data, config)
            if slug:
                d["target_model_slug"] = slug
                d["is_in_workspace"] = True
        results.append(d)
    return results


def normalize_data_source_entry(
    src: Any,
    model_data: Any = None,
    config: Optional[Any] = None,
    up_names: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    Returns a normalized dict for a PowerQuerySource entry with pre-resolved
    target_model_slug, is_remote_model, and parameter_query_name.
    """
    d = asdict(src) if is_dataclass(src) else (dict(src) if isinstance(src, dict) else {})
    conn = d.get("connection_string") or "—"
    server = d.get("server") or ""
    db = d.get("database") or ""
    stype_upper = (d.get("source_type") or "").upper()

    if not d.get("parameter_query_name") and model_data:
        expr_list = _get_prop(model_data, "expressions") or _get_prop(model_data, "shared_queries") or []
        for e in expr_list:
            q_name = _get_prop(e, "query_name")
            if q_name == conn and (
                _get_prop(e, "expression_kind") == "parameter"
                or "IsParameterQuery" in (_get_prop(e, "full_m_expression") or "")
            ):
                d["parameter_query_name"] = q_name
                d["parameter_value"] = _get_prop(e, "parameter_value")
                break

    if db and db != "—":
        if not d.get("target_model_slug"):
            slug = resolve_workspace_model_slug(db, model_data, config)
            if slug:
                d["target_model_slug"] = slug
                d["is_in_workspace"] = True
        if not d.get("is_remote_model"):
            if (
                d.get("is_in_workspace")
                or d.get("target_model_slug")
                or stype_upper in ("ANALYSIS_SERVICES", "ANALYSISSERVICES", "POWERBI_SEMANTIC_MODEL", "POWERBI")
                or "powerbi://" in server.lower()
                or (up_names is not None and db in up_names)
            ):
                d["is_remote_model"] = True

    return d


_MEASURE_MAP_CACHE: Dict[int, Any] = {}


def _get_cached_measure_maps(model_data: Any):
    measures = _get_prop(model_data, "measures") or []
    cache_key = id(measures)
    cached = _MEASURE_MAP_CACHE.get(cache_key)
    if cached is not None and cached[0] is measures and cached[1] == len(measures):
        return cached[2], cached[3]

    lookup_map: Dict[str, Dict[str, Any]] = {}
    table_map: Dict[str, str] = {}
    for m in measures:
        d = asdict(m) if is_dataclass(m) else (m if isinstance(m, dict) else {})
        m_name = d.get("name")
        if m_name:
            lookup_map[m_name] = d
            table_map[m_name] = d.get("table") or "Model"

    if len(_MEASURE_MAP_CACHE) > 32:
        _MEASURE_MAP_CACHE.clear()
    _MEASURE_MAP_CACHE[cache_key] = (measures, len(measures), lookup_map, table_map)
    return lookup_map, table_map


def get_measure_lookup_map(model_data: Any) -> Dict[str, Dict[str, Any]]:
    """
    Returns an O(1) lookup dictionary mapping measure name to its metadata dictionary,
    cached by the identity and length of model_data['measures'].
    """
    lookup_map, _ = _get_cached_measure_maps(model_data)
    return lookup_map


def get_measure_table_map(model_data: Any) -> Dict[str, str]:
    """
    Returns an O(1) lookup dictionary mapping measure name to its host table name,
    cached by the identity and length of model_data['measures'].
    """
    _, table_map = _get_cached_measure_maps(model_data)
    return table_map


def resolve_upstream_model_references(
    table_data: Dict[str, Any],
    model_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Resolves and deduplicates upstream DAX references (Tables, Columns, Measures)
    for calculated tables. Single source of truth shared by Markdown and HTML builders.
    """
    table_data = table_data or {}
    model_data = model_data or {}

    ref_tables = table_data.get("referenced_tables", []) or []
    ref_cols = table_data.get("referenced_columns", []) or []
    ref_measures = table_data.get("referenced_measures", []) or []

    model_tables = model_data.get("tables", []) or []
    table_lookup: Dict[str, Dict[str, Any]] = {}
    table_lookup_ci: Dict[str, Dict[str, Any]] = {}
    for t in model_tables:
        t_name = t.get("name")
        if t_name:
            table_lookup[t_name] = t
            table_lookup_ci[t_name.lower()] = t

    measure_lookup: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    measure_lookup_ci: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for m in model_data.get("measures", []) or []:
        m_name = m.get("name")
        if m_name:
            home_tbl = m.get("table") or "Model"
            measure_lookup[m_name] = (home_tbl, m)
            measure_lookup_ci[m_name.lower()] = (home_tbl, m)

    # Fallback: inspect nested measures inside tables
    for t in model_tables:
        t_name = t.get("name") or "Model"
        for m in t.get("measures", []) or []:
            m_name = m.get("name")
            if m_name and m_name not in measure_lookup:
                m_dict = dict(m)
                if not m_dict.get("table"):
                    m_dict["table"] = t_name
                home_tbl = m_dict.get("table") or t_name
                measure_lookup[m_name] = (home_tbl, m_dict)
                measure_lookup_ci[m_name.lower()] = (home_tbl, m_dict)

    tables_with_cols: Set[str] = {
        rc.get("table")
        for rc in ref_cols
        if isinstance(rc, dict) and rc.get("table")
    }
    tables_with_cols_ci: Set[str] = {t.lower() for t in tables_with_cols if isinstance(t, str)}

    standalone_tables: List[Dict[str, Any]] = []
    seen_standalone: Set[str] = set()
    for t in ref_tables:
        if not t:
            continue
        t_low = str(t).lower()
        if t in tables_with_cols or t_low in tables_with_cols_ci or t_low in seen_standalone:
            continue
        seen_standalone.add(t_low)
        t_obj = table_lookup.get(t) or table_lookup_ci.get(t_low)
        standalone_tables.append({
            "name": t,
            "table_obj": t_obj,
        })

    columns_list: List[Dict[str, Any]] = []
    for rc in ref_cols:
        if isinstance(rc, dict):
            t_name = rc.get("table", "") or ""
            c_name = rc.get("column", "") or ""
        else:
            t_name = ""
            c_name = str(rc)
        t_obj = (table_lookup.get(t_name) or table_lookup_ci.get(t_name.lower())) if t_name else None
        columns_list.append({
            "table": t_name,
            "column": c_name,
            "table_obj": t_obj,
        })

    measures_list: List[Dict[str, Any]] = []
    for m in ref_measures:
        if not m:
            continue
        resolved = measure_lookup.get(m) or measure_lookup_ci.get(str(m).lower())
        if resolved:
            m_home_tbl, m_obj = resolved
            home_tbl_obj = table_lookup.get(m_home_tbl) or table_lookup_ci.get(m_home_tbl.lower())
        else:
            m_home_tbl, m_obj, home_tbl_obj = None, None, None
        measures_list.append({
            "name": m,
            "home_table": m_home_tbl,
            "measure_obj": m_obj,
            "home_table_obj": home_tbl_obj,
        })

    return {
        "standalone_tables": standalone_tables,
        "columns": columns_list,
        "measures": measures_list,
    }

