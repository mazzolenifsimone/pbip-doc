"""
PBIP Relationship Diagram SVG Generator.
Renders topological Star, Snowflake, and Bridge relationship diagrams in standalone or inline SVG.
Pure Python standard library implementation with zero external dependencies and zero JavaScript.
"""

import html
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from .utils import (
    sanitize_filename,
    get_model_upstream_summaries,
    is_table_remote,
    filter_local_scope_relationships,
)
from .relationship_config import (
    ROLE_CONFIG,
    normalize_role_key,
    get_table_role_short,
    get_table_role_badge_class,
)


def _safe_id(text: Any) -> str:
    """Produces a CSS-safe ID token containing only alphanumeric, underscores, and hyphens."""
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", str(text or ""))


def _get_entity_prop(obj: Any, prop: str, default: Any = None) -> Any:
    """Safely reads a property whether obj is a class instance or a dictionary."""
    if hasattr(obj, prop):
        val = getattr(obj, prop)
        return val if val is not None else default
    if isinstance(obj, dict):
        return obj.get(prop, default)
    return default


# ==============================================================================
# SVG RELATIONSHIP DIAGRAM GENERATOR
# ==============================================================================
class RelationshipSvgGenerator:
    """
    Renders topological Star, Snowflake, and Bridge schema relationship diagrams in SVG.
    Fully aligned with pbip-doc design tokens, themes, and badges.
    Supports both PBIPSemanticModel objects and extracted JSON/dictionary representations.
    """

    def __init__(self, model_or_dict: Any, config: Any = None):
        self.model = model_or_dict
        self.config = config
        raw_tables = _get_entity_prop(self.model, "tables", []) or []
        raw_relationships = _get_entity_prop(self.model, "relationships", []) or []
        raw_measures = _get_entity_prop(self.model, "measures", []) or []

        self.tables = list(raw_tables)
        self.relationships = filter_local_scope_relationships(raw_relationships, self.tables, config=self.config)
        self.measures = list(raw_measures)
        self._table_map: Dict[str, Any] = {
            _get_entity_prop(t, "name"): t for t in self.tables if _get_entity_prop(t, "name")
        }

    def _is_table_remote(self, table_name: str) -> bool:
        """Returns True if table is an inherited entity from an external / remote data model."""
        return is_table_remote(self._table_map.get(table_name))

    def get_upstream_models(self) -> List[Dict[str, Any]]:
        """
        Returns structured list of upstream semantic models from pre-computed model data
        (with deterministic fallback for raw test dictionaries).
        """
        summaries = get_model_upstream_summaries(self.model)
        result = []
        for s in summaries:
            t_set = set(s.get("tables", []))
            result.append({
                "name": s["name"],
                "tables_count": s.get("tables_count", len(t_set)),
                "measures_count": s.get("measures_count", len(s.get("measures", []))),
                "tables": t_set,
                "mode": s.get("mode", "DirectQuery"),
                "is_in_workspace": s.get("is_in_workspace", False),
                "target_model_slug": s.get("target_model_slug"),
            })
        return result

    def get_inherited_metrics(self) -> Tuple[int, int, str]:
        """
        Calculates exact count of inherited tables and measures in local report scope.
        X = len([t for t in model.tables if t.is_inherited or t.source_type == 'InheritedEntity'])
        Y = len([m for m in model.measures if m.is_inherited or m.is_external_measure])
        """
        up_models = self.get_upstream_models()
        if not up_models:
            return (0, 0, "Remote Semantic Model")
        total_t = sum(m["tables_count"] for m in up_models)
        total_m = sum(m["measures_count"] for m in up_models)
        primary_name = up_models[0]["name"]
        return (total_t, total_m, primary_name)

    def get_utility_tables(self) -> List[str]:
        """
        Returns table names representing utility tables, parameter tables,
        or calculation groups disconnected from the relational star flow.
        Remote / inherited tables are strictly excluded.
        """
        connected_tables = set()
        for r in self.relationships:
            f_t = _get_entity_prop(r, "from_table")
            t_t = _get_entity_prop(r, "to_table")
            if f_t:
                connected_tables.add(f_t)
            if t_t:
                connected_tables.add(t_t)

        util = []
        for t_name, tbl in self._table_map.items():
            if self._is_table_remote(t_name):
                continue
            if self.config is not None and self.config.is_table_excluded(t_name):
                continue
            role = self._get_role_key(t_name)
            if role in ("PARAMETER_UTILITY", "CALCULATION_GROUP"):
                util.append(t_name)
            elif t_name not in connected_tables and len(self.tables) > 1:
                util.append(t_name)
        return sorted(util)

    @staticmethod
    def _render_semantic_model_icon(x: float, y: float, size: float = 20) -> str:
        """Renders the official pbip-doc Semantic Model vector SVG icon."""
        scale = size / 100.0
        return f"""<g class="icon-semantic-model" transform="translate({x}, {y}) scale({scale})">
      <rect x="10" y="10" width="80" height="80" rx="12" fill="none" stroke="var(--g-upstream-border)" stroke-width="7" />
      <circle cx="29" cy="39" r="7" fill="var(--g-upstream-border)" />
      <circle cx="50" cy="39" r="7" fill="var(--g-upstream-border)" />
      <circle cx="71" cy="39" r="7" fill="var(--g-upstream-border)" />
      <circle cx="29" cy="61" r="7" fill="var(--g-upstream-border)" />
      <circle cx="50" cy="61" r="7" fill="var(--g-upstream-border)" />
    </g>"""

    def _get_role_key(self, table_name: str) -> str:
        tbl = self._table_map.get(table_name)
        if not tbl:
            return "UNKNOWN"
        raw_role = _get_entity_prop(tbl, "role", "UNKNOWN")
        return normalize_role_key(raw_role)

    def _is_bidirectional(self, rel: Any) -> bool:
        c_dir = str(_get_entity_prop(rel, "cross_filtering_behavior", "Single") or "").lower()
        return "both" in c_dir or "bidirectional" in c_dir

    def _is_active(self, rel: Any) -> bool:
        val = _get_entity_prop(rel, "is_active", True)
        return bool(val) if val is not None else True

    def _get_cardinality_labels(self, rel: Any) -> Tuple[str, str, str]:
        """
        Determines the cardinality badges for a relationship connector:
        Returns (from_label, to_label, canonical_type).
        - 1:1 -> ('1', '1', '1:1')
        - Many-to-Many -> ('*', '*', '*:*')
        - 1:N / N:1 -> ('*', '1', '1:N')
        """
        raw_card = str(_get_entity_prop(rel, "cardinality", "1:N") or "").strip().upper()
        if raw_card in ("1:1", "ONETOONE", "ONE_TO_ONE", "1 TO 1"):
            return ("1", "1", "1:1")
        elif raw_card in ("N:N", "M:M", "*:*", "MANYTOMANY", "MANY_TO_MANY", "* TO *", "N TO N"):
            return ("*", "*", "*:*")
        elif raw_card in ("N:1", "MANYTOONE", "MANY_TO_ONE"):
            return ("*", "1", "1:N")
        elif raw_card in ("1:N", "ONETOMANY", "ONE_TO_MANY"):
            return ("*", "1", "1:N")
        return ("*", "1", "1:N")

    def get_fact_tables(self) -> List[str]:
        """Returns sorted list of all Fact table names in the model, strictly excluding remote tables."""
        facts = [
            t_name for t_name in self._table_map
            if self._get_role_key(t_name) == "FACT"
            and not self._is_table_remote(t_name)
            and not (self.config is not None and self.config.is_table_excluded(t_name))
        ]
        if not facts:
            many_sides = set()
            one_sides = set()
            for r in self.relationships:
                f_t = _get_entity_prop(r, "from_table")
                t_t = _get_entity_prop(r, "to_table")
                if f_t and not self._is_table_remote(f_t):
                    many_sides.add(f_t)
                if t_t and not self._is_table_remote(t_t):
                    one_sides.add(t_t)
            candidate_facts = [t for t in many_sides if t not in one_sides and not self._is_table_remote(t)]
            if candidate_facts:
                facts = candidate_facts
        return sorted(facts)

    def extract_star_cluster(self, fact_table_name: str) -> Dict[str, Any]:
        """
        Extracts the 4-tier Star Cluster reachable from a focal Fact table:
        1. Direct 1-hop connections to fact_table_name (Dimensions, Bridges, Outriggers).
        2. Upstream Dimensions connected to reached Bridges.
        3. Upstream Outriggers/Lookups connected to reached Dimensions (recursive snowflake traversal).
        """
        fact_table_name = fact_table_name.strip()
        focal_rels = [
            r for r in self.relationships
            if _get_entity_prop(r, "from_table") == fact_table_name or _get_entity_prop(r, "to_table") == fact_table_name
        ]

        if not focal_rels:
            return {
                "fact_table": fact_table_name,
                "columns": [],
                "outriggers": [],
                "dimensions": [],
                "bridges": [],
                "facts": [fact_table_name],
                "tables": {fact_table_name},
                "relationships": [],
            }

        col_bridges: Set[str] = set()
        col_dimensions: Set[str] = set()
        col_outriggers: Set[str] = set()

        # Step 1: Direct 1-hop neighbors from Fact
        for r in focal_rels:
            from_t = _get_entity_prop(r, "from_table")
            to_t = _get_entity_prop(r, "to_table")
            partner = to_t if from_t == fact_table_name else from_t
            if not partner or partner == fact_table_name:
                continue

            role = self._get_role_key(partner)
            if role == "BRIDGE":
                col_bridges.add(partner)
            elif role == "LOOKUP_OUTRIGGER":
                col_outriggers.add(partner)
            elif role in ("DIMENSION", "DATE_DIMENSION"):
                col_dimensions.add(partner)
            else:
                col_dimensions.add(partner)

        # Step 2: Bidirectional Bridge & Dimension traversal
        # 2a. Bridges connected to reached Dimensions
        for dim in list(col_dimensions):
            for r in self.relationships:
                from_t = _get_entity_prop(r, "from_table")
                to_t = _get_entity_prop(r, "to_table")
                if from_t == dim or to_t == dim:
                    partner = to_t if from_t == dim else from_t
                    if partner and partner != fact_table_name and self._get_role_key(partner) == "BRIDGE":
                        col_bridges.add(partner)

        # 2b. Dimensions connected to reached Bridges
        for bridge in list(col_bridges):
            for r in self.relationships:
                from_t = _get_entity_prop(r, "from_table")
                to_t = _get_entity_prop(r, "to_table")
                if from_t == bridge or to_t == bridge:
                    partner = to_t if from_t == bridge else from_t
                    if not partner or partner == fact_table_name or partner in col_bridges:
                        continue
                    role = self._get_role_key(partner)
                    if role == "LOOKUP_OUTRIGGER":
                        col_outriggers.add(partner)
                    elif role != "FACT":
                        col_dimensions.add(partner)

        # Step 3: Outriggers/Lookups connected upstream to Dimensions (BFS for snowflake chains)
        queue = list(col_dimensions)
        while queue:
            curr = queue.pop(0)
            for r in self.relationships:
                from_t = _get_entity_prop(r, "from_table")
                to_t = _get_entity_prop(r, "to_table")
                if from_t == curr or to_t == curr:
                    partner = to_t if from_t == curr else from_t
                    if not partner or partner == fact_table_name or partner in col_bridges:
                        continue
                    role = self._get_role_key(partner)
                    if role == "LOOKUP_OUTRIGGER" and partner not in col_outriggers:
                        col_outriggers.add(partner)
                        queue.append(partner)

        # Collect all active cluster tables
        cluster_tables = set(col_outriggers) | set(col_dimensions) | set(col_bridges) | {fact_table_name}

        # Collect all relationships between tables in the cluster
        cluster_rels = [
            r for r in self.relationships
            if _get_entity_prop(r, "from_table") in cluster_tables and _get_entity_prop(r, "to_table") in cluster_tables
        ]

        outriggers_list = sorted(col_outriggers)
        dimensions_list = sorted(col_dimensions)
        bridges_list = sorted(col_bridges)
        facts_list = [fact_table_name]

        columns: List[List[str]] = []
        if outriggers_list:
            columns.append(outriggers_list)
        if dimensions_list:
            columns.append(dimensions_list)
        if bridges_list:
            columns.append(bridges_list)
        if facts_list:
            columns.append(facts_list)

        return {
            "fact_table": fact_table_name,
            "columns": columns,
            "outriggers": outriggers_list,
            "dimensions": dimensions_list,
            "bridges": bridges_list,
            "facts": facts_list,
            "tables": cluster_tables,
            "relationships": cluster_rels,
        }

    def get_dimension_fact_usage(self) -> Dict[str, Set[str]]:
        """
        Maps each non-fact table (dimensions, bridges, outriggers) to the set
        of fact tables that consume or reach it.
        """
        fact_tables = self.get_fact_tables()
        usage: Dict[str, Set[str]] = {t: set() for t in self._table_map if t not in fact_tables}

        for f_name in fact_tables:
            cluster = self.extract_star_cluster(f_name)
            for t_name in cluster.get("tables", set()):
                if t_name != f_name:
                    usage.setdefault(t_name, set()).add(f_name)

        return usage

    def _partition_into_columns(
        self,
        active_tables: Set[str],
        relationships: Optional[List[Any]] = None,
        focal_table: Optional[str] = None,
    ) -> List[List[str]]:
        """
        Partitions active tables into 4 standard topological columns:
        Outriggers (Left) -> Dimensions -> Bridges -> Facts (Right).
        Guarantees that directly interrelated tables are never assigned to the same column.
        """
        col_outriggers = []
        col_dimensions = []
        col_bridges = []
        col_facts = []

        for t_name in sorted(active_tables):
            role = self._get_role_key(t_name)
            if role == "LOOKUP_OUTRIGGER":
                col_outriggers.append(t_name)
            elif role in ("DIMENSION", "DATE_DIMENSION"):
                col_dimensions.append(t_name)
            elif role == "BRIDGE":
                col_bridges.append(t_name)
            elif role == "FACT":
                col_facts.append(t_name)
            else:
                col_dimensions.append(t_name)

        # Fallback for circular or unclassified topologies
        if not col_facts and not col_dimensions:
            for r in (relationships or []):
                from_t = _get_entity_prop(r, "from_table")
                to_t = _get_entity_prop(r, "to_table")
                if from_t and from_t in active_tables and from_t not in col_facts:
                    col_facts.append(from_t)
                if to_t and to_t in active_tables and to_t not in col_dimensions and to_t not in col_facts:
                    col_dimensions.append(to_t)

        # Ensure directly related tables in active_tables are not placed in the same column
        if relationships:
            for r in relationships:
                f_t = _get_entity_prop(r, "from_table")
                t_t = _get_entity_prop(r, "to_table")
                if f_t in active_tables and t_t in active_tables:
                    # If both are in col_dimensions:
                    if f_t in col_dimensions and t_t in col_dimensions:
                        # t_t is the One-side (lookup/parent), move to outriggers
                        col_dimensions.remove(t_t)
                        if t_t not in col_outriggers:
                            col_outriggers.append(t_t)
                    # If both are in col_facts:
                    elif f_t in col_facts and t_t in col_facts:
                        # t_t is header/parent Fact, move to bridges
                        col_facts.remove(t_t)
                        if t_t not in col_bridges:
                            col_bridges.append(t_t)

        columns: List[List[str]] = []
        if col_outriggers:
            columns.append(col_outriggers)
        if col_dimensions:
            columns.append(col_dimensions)
        if col_bridges:
            columns.append(col_bridges)
        if col_facts:
            columns.append(col_facts)

        if not columns and active_tables:
            columns.append(sorted(active_tables))

        return columns

    def extract_1hop_cluster(self, target_table_name: str) -> Dict[str, Any]:
        """
        Extracts direct 1-hop relational neighborhood for target_table_name:
        - Active tables: target_table_name and all directly connected partner tables.
        - Relationships: all active relationships where from_table == target or to_table == target.
        - Columns: partitioned into standard 4 topological columns (Outrigger -> Dim -> Bridge -> Fact).
        """
        target_table_name = target_table_name.strip()
        focal_rels = [
            r for r in self.relationships
            if _get_entity_prop(r, "from_table") == target_table_name or _get_entity_prop(r, "to_table") == target_table_name
        ]

        if not focal_rels:
            return {
                "target_table": target_table_name,
                "columns": [],
                "tables": {target_table_name},
                "relationships": [],
            }

        active_tables = {target_table_name}
        for r in focal_rels:
            f_t = _get_entity_prop(r, "from_table")
            t_t = _get_entity_prop(r, "to_table")
            if f_t:
                active_tables.add(f_t)
            if t_t:
                active_tables.add(t_t)

        columns = self._partition_into_columns(active_tables, focal_rels, focal_table=target_table_name)

        return {
            "target_table": target_table_name,
            "columns": columns,
            "tables": active_tables,
            "relationships": focal_rels,
        }

    def generate_diagram(
        self,
        scope: str = "model",  # "model" | "star_cluster" | "1hop"
        target_table: Optional[str] = None,
        theme_mode: Optional[str] = None,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
    ) -> str:
        """
        Unified SVG relationship diagram generator across all scopes:
        - scope='model': renders full model schema.
        - scope='star_cluster': renders 4-tier Star Cluster centered on a Fact table.
        - scope='1hop': renders direct 1-hop relational neighborhood for Dim/Bridge/Lookup.
        Differences are strictly governed by parameterization of data extraction.
        """
        target_table = target_table.strip() if target_table else None

        if scope == "star_cluster":
            if not target_table:
                raise ValueError("target_table is required when scope='star_cluster'")
            cluster = self.extract_star_cluster(target_table)
            columns = cluster.get("columns", [])
            relationships = cluster.get("relationships", [])
            active_tables = cluster.get("tables", set())
            focal_table = target_table
            if not columns or not relationships:
                if target_table in self._table_map and not self._is_table_remote(target_table):
                    columns = [[target_table]]
                    relationships = []
                    active_tables = {target_table}
                else:
                    return self._generate_empty_svg(f"No active table relationships connected to Fact table '{target_table}'.")
            clean_slug = sanitize_filename(target_table).lower().replace("_", "-")
            prefix = svg_id_prefix or f"star-{clean_slug}"

        elif scope == "1hop":
            if not target_table:
                raise ValueError("target_table is required when scope='1hop'")
            cluster = self.extract_1hop_cluster(target_table)
            columns = cluster.get("columns", [])
            relationships = cluster.get("relationships", [])
            active_tables = cluster.get("tables", set())
            focal_table = target_table
            if not columns or not relationships:
                return self._generate_empty_svg(f"No direct relationships connected to table '{target_table}'.")
            prefix = svg_id_prefix

        else:  # scope == "model"
            active_tables = set()
            for r in self.relationships:
                from_t = _get_entity_prop(r, "from_table")
                to_t = _get_entity_prop(r, "to_table")
                if from_t:
                    active_tables.add(from_t)
                if to_t:
                    active_tables.add(to_t)

            if not active_tables:
                up_models = self.get_upstream_models()
                if up_models:
                    return self._render_diagram_layout(
                        columns=[],
                        relationships=[],
                        active_tables=set(),
                        theme_mode=theme_mode,
                        svg_id_prefix=svg_id_prefix,
                        focal_table=target_table,
                        interactive=interactive,
                    )
                return self._generate_empty_svg("No active table relationships defined in semantic model.")

            columns = self._partition_into_columns(active_tables, self.relationships)
            relationships = self.relationships
            focal_table = target_table
            prefix = svg_id_prefix

        return self._render_diagram_layout(
            columns=columns,
            relationships=relationships,
            active_tables=active_tables,
            theme_mode=theme_mode,
            svg_id_prefix=prefix,
            focal_table=focal_table,
            interactive=interactive,
        )

    def generate_star_cluster_svg(
        self,
        fact_table_name: str,
        theme_mode: Optional[str] = None,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
    ) -> str:
        """
        Renders an isolated 4-tier Star Cluster diagram centered on a Fact table:
        Lookup / Outrigger -> Dimension -> Bridge -> Fact.
        """
        return self.generate_diagram(
            scope="star_cluster",
            target_table=fact_table_name,
            interactive=interactive,
            theme_mode=theme_mode,
            svg_id_prefix=svg_id_prefix,
        )

    def generate_model_svg(
        self,
        theme_mode: Optional[str] = None,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
        focal_table: Optional[str] = None,
    ) -> str:
        """
        Renders the full model Star & Snowflake schema diagram.
        Topology: Outriggers (Left) -> Dimensions -> Bridge (conditional) -> Facts (Right).
        """
        return self.generate_diagram(
            scope="model",
            target_table=focal_table,
            interactive=interactive,
            theme_mode=theme_mode,
            svg_id_prefix=svg_id_prefix,
        )

    def _render_diagram_layout(
        self,
        columns: List[List[str]],
        relationships: List[Any],
        active_tables: Set[str],
        theme_mode: Optional[str] = None,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
        focal_table: Optional[str] = None,
    ) -> str:
        # Minimal Layout Geometry
        card_width = 215
        header_height = 28
        row_height = 20
        col_gap = 130
        padding_y = 20
        start_y = 50

        # Collect relationship keys per table to display inside card
        table_keys: Dict[str, List[Tuple[str, str]]] = {t: [] for t in active_tables}
        for r in relationships:
            from_t = _get_entity_prop(r, "from_table")
            from_c = _get_entity_prop(r, "from_column")
            to_t = _get_entity_prop(r, "to_table")
            to_c = _get_entity_prop(r, "to_column")

            if from_t in table_keys and from_c and (from_c, "FK") not in table_keys[from_t]:
                table_keys[from_t].append((from_c, "FK"))
            if to_t in table_keys and to_c and (to_c, "PK") not in table_keys[to_t]:
                table_keys[to_t].append((to_c, "PK"))

        # Detect Border Tables and Cross-Model Relationships
        border_tables: Set[str] = set()
        cross_rel_indices: Set[int] = set()
        for r_idx, r in enumerate(relationships):
            f_t = _get_entity_prop(r, "from_table")
            t_t = _get_entity_prop(r, "to_table")
            f_rem = self._is_table_remote(f_t)
            t_rem = self._is_table_remote(t_t)
            if f_rem and not t_rem:
                border_tables.add(f_t)
                cross_rel_indices.add(r_idx)
            elif t_rem and not f_rem:
                border_tables.add(t_t)
                cross_rel_indices.add(r_idx)

        # Detect Upstream Semantic Models
        raw_upstream_models = self.get_upstream_models()
        if focal_table and not border_tables:
            upstream_models = []
        else:
            upstream_models = [dict(m) for m in raw_upstream_models]
        has_remote = len(upstream_models) > 0

        # Partition border tables across upstream models
        if upstream_models:
            all_assigned_border = set()
            for m in upstream_models:
                m_border = [t for t in sorted(border_tables) if t in m.get("tables", set())]
                m["border_tables"] = m_border
                all_assigned_border.update(m_border)
            unassigned = [t for t in sorted(border_tables) if t not in all_assigned_border]
            if unassigned:
                upstream_models[0]["border_tables"].extend(unassigned)

        # Local active tables: strictly exclude remote tables, border tables, and utility tables
        util_tables_set = set(self.get_utility_tables())
        local_active = [t for t in active_tables if t not in border_tables and not self._is_table_remote(t) and t not in util_tables_set]
        local_columns = self._partition_into_columns(set(local_active), relationships) if local_active else []

        min_canvas_w = 1040 if (has_remote or bool(border_tables)) else 840
        card_positions: Dict[str, Dict[str, Any]] = {}
        max_height = 0

        content_width = len(local_columns) * card_width + max(0, len(local_columns) - 1) * col_gap if local_columns else 0

        max_border_in_any_model = max((len(m.get("border_tables", [])) for m in upstream_models), default=0) if upstream_models else 0
        min_box_w = max_border_in_any_model * (card_width + 40) + 60 if max_border_in_any_model else 0
        svg_width = max(content_width + 80 if content_width else 0, min_box_w + 60, min_canvas_w)

        box_x = 30.0
        box_w = svg_width - 60.0
        curr_box_y = 20.0
        upstream_containers_svg = []

        if upstream_models:
            for m in upstream_models:
                m_name = m["name"]
                m_border = m.get("border_tables", [])
                num_b = len(m_border)

                if num_b > 0:
                    max_b_h = max(header_height + max(1, len(table_keys.get(t_name, []))) * row_height + 8 for t_name in m_border)
                    box_h = 46.0 + max_b_h + 16.0

                    if num_b == 1:
                        bx = box_x + (box_w - card_width) / 2.0
                        t_name = m_border[0]
                        b_keys = table_keys.get(t_name, [])
                        ports = {k_name.lower(): (curr_box_y + 46.0) + header_height + 2 + k_idx * row_height + row_height / 2 for k_idx, (k_name, _) in enumerate(b_keys)}
                        card_positions[t_name] = {"x": bx, "y": curr_box_y + 46.0, "w": card_width, "h": max_b_h, "ports": ports, "col_idx": 0, "is_remote": True}
                    else:
                        margin_bx = 50.0
                        gap_bx = (box_w - 2 * margin_bx - num_b * card_width) / max(1, num_b - 1)
                        for b_idx, t_name in enumerate(m_border):
                            bx = box_x + margin_bx + b_idx * (card_width + gap_bx)
                            by = curr_box_y + 46.0
                            b_keys = table_keys.get(t_name, [])
                            b_card_h = header_height + max(1, len(b_keys)) * row_height + 8
                            ports = {k_name.lower(): by + header_height + 2 + k_idx * row_height + row_height / 2 for k_idx, (k_name, _) in enumerate(b_keys)}
                            card_positions[t_name] = {"x": bx, "y": by, "w": card_width, "h": b_card_h, "ports": ports, "col_idx": b_idx, "is_remote": True}
                else:
                    box_h = 56.0

                tag_w = 75
                tag_x = box_w - tag_w - 35
                stat_msr_w = 110
                stat_msr_x = tag_x - stat_msr_w - 12
                stat_tbl_w = 100
                stat_tbl_x = stat_msr_x - stat_tbl_w - 12

                upstream_containers_svg.append(f"""
  <!-- UPSTREAM SUPER-NODE CONTAINER: {html.escape(m_name)} -->
  <g class="upstream-group" transform="translate({box_x}, {curr_box_y})">
    <rect x="0" y="0" width="{box_w}" height="{box_h}" class="upstream-box" />
    <g transform="translate(20, 12)">
      {self._render_semantic_model_icon(x=0, y=2, size=20)}
      <text x="28" y="17" class="upstream-header-title">{html.escape(m_name)}</text>
      <!-- Stat Card 1: Tables -->
      <g transform="translate({stat_tbl_x}, 0)">
        <rect x="0" y="0" width="{stat_tbl_w}" height="24" rx="4" class="upstream-stat-box" />
        <text x="10" y="16.5" class="upstream-stat-label">Tables:</text>
        <text x="56" y="16.5" class="upstream-stat-val">{m['tables_count']}</text>
      </g>
      <!-- Stat Card 2: Measures -->
      <g transform="translate({stat_msr_x}, 0)">
        <rect x="0" y="0" width="{stat_msr_w}" height="24" rx="4" class="upstream-stat-box" />
        <text x="10" y="16.5" class="upstream-stat-label">Measures:</text>
        <text x="68" y="16.5" class="upstream-stat-val">{m['measures_count']}</text>
      </g>
      <!-- DirectQuery Mode Tag -->
      <g transform="translate({tag_x}, 0)">
        <rect x="0" y="0" width="{tag_w}" height="24" rx="4" class="upstream-stat-box" />
        <text x="{tag_w / 2}" y="16.5" class="upstream-stat-label" text-anchor="middle" font-weight="700">{html.escape(m.get('mode', 'DirectQuery'))}</text>
      </g>
    </g>
  </g>""")
                curr_box_y += box_h + 20.0

            if local_columns:
                local_start_y = curr_box_y + 40.0
                local_start_x = (svg_width - content_width) / 2.0
                max_height = local_start_y

                for col_idx, col_tables in enumerate(local_columns):
                    curr_x = local_start_x + col_idx * (card_width + col_gap)
                    curr_y = local_start_y
                    for t_name in col_tables:
                        keys = table_keys.get(t_name, [])
                        card_h = header_height + max(1, len(keys)) * row_height + 8
                        ports = {k_name.lower(): curr_y + header_height + 2 + k_idx * row_height + row_height / 2 for k_idx, (k_name, _) in enumerate(keys)}
                        card_positions[t_name] = {"x": curr_x, "y": curr_y, "w": card_width, "h": card_h, "ports": ports, "col_idx": col_idx, "is_remote": False}
                        curr_y += card_h + padding_y
                    max_height = max(max_height, curr_y)
            else:
                max_height = curr_box_y
        else:
            # Standalone local model layout
            content_width = len(columns) * card_width + max(0, len(columns) - 1) * col_gap
            svg_width = max(content_width + 80, min_canvas_w)
            start_x = (svg_width - content_width) / 2.0

            for col_idx, col_tables in enumerate(columns):
                curr_y = start_y
                curr_x = start_x + col_idx * (card_width + col_gap)
                for t_name in col_tables:
                    keys = table_keys.get(t_name, [])
                    card_h = header_height + max(1, len(keys)) * row_height + 8
                    ports = {k_name.lower(): curr_y + header_height + 2 + k_idx * row_height + row_height / 2 for k_idx, (k_name, _) in enumerate(keys)}
                    card_positions[t_name] = {"x": curr_x, "y": curr_y, "w": card_width, "h": card_h, "ports": ports, "col_idx": col_idx, "is_remote": False}
                    curr_y += card_h + padding_y
                max_height = max(max_height, curr_y)

        canvas_id = f"canvas-{svg_id_prefix}" if svg_id_prefix else "canvas"
        canvas_tabindex = ' tabindex="0"' if interactive else ""

        # Bézier multi-port fan-out offset calculation
        endpoint_from = defaultdict(list)
        endpoint_to = defaultdict(list)

        for r_idx, r in enumerate(relationships):
            from_t = _get_entity_prop(r, "from_table")
            to_t = _get_entity_prop(r, "to_table")
            from_c = _get_entity_prop(r, "from_column")
            to_c = _get_entity_prop(r, "to_column")
            from_pos = card_positions.get(from_t)
            to_pos = card_positions.get(to_t)
            if not from_pos or not to_pos:
                continue
            y_to = to_pos["y"]
            y_from = from_pos["y"]
            k_from = (from_t, from_c.lower()) if from_c else (from_t, "")
            k_to = (to_t, to_c.lower()) if to_c else (to_t, "")
            endpoint_from[k_from].append((y_to, r_idx))
            endpoint_to[k_to].append((y_from, r_idx))

        rel_offsets_from: Dict[int, float] = {}
        rel_offsets_to: Dict[int, float] = {}

        for _, items in endpoint_from.items():
            sorted_items = sorted(items, key=lambda x: x[0])
            n = len(sorted_items)
            if n > 1:
                step = min(3.5, 15.0 / n)
                for rank, (_, r_id) in enumerate(sorted_items):
                    rel_offsets_from[r_id] = (rank - (n - 1) / 2.0) * step
            else:
                for _, r_id in sorted_items:
                    rel_offsets_from[r_id] = 0.0

        for _, items in endpoint_to.items():
            sorted_items = sorted(items, key=lambda x: x[0])
            n = len(sorted_items)
            if n > 1:
                step = min(3.5, 15.0 / n)
                for rank, (_, r_id) in enumerate(sorted_items):
                    rel_offsets_to[r_id] = (rank - (n - 1) / 2.0) * step
            else:
                for _, r_id in sorted_items:
                    rel_offsets_to[r_id] = 0.0

        # Build dynamic CSS rules for relationships and cards
        dynamic_css_rules: List[str] = []

        def _scoped_sel(triggers: List[str], target: str) -> str:
            return ", ".join(f"{trig} {target}" for trig in triggers)

        # 1. Rules for each Relationship
        for r_idx, r in enumerate(relationships):
            from_t = _get_entity_prop(r, "from_table")
            to_t = _get_entity_prop(r, "to_table")
            from_c = _get_entity_prop(r, "from_column")
            to_c = _get_entity_prop(r, "to_column")

            rel_id = f"rel-{svg_id_prefix}-{r_idx}" if svg_id_prefix else f"rel-{r_idx}"
            from_card_id = f"card-{svg_id_prefix}-{_safe_id(from_t)}" if svg_id_prefix else f"card-{_safe_id(from_t)}"
            to_card_id = f"card-{svg_id_prefix}-{_safe_id(to_t)}" if svg_id_prefix else f"card-{_safe_id(to_t)}"

            from_row_id = f"row-{svg_id_prefix}-{_safe_id(from_t)}-{_safe_id(from_c)}" if (svg_id_prefix and from_c) else (f"row-{_safe_id(from_t)}-{_safe_id(from_c)}" if from_c else "")
            to_row_id = f"row-{svg_id_prefix}-{_safe_id(to_t)}-{_safe_id(to_c)}" if (svg_id_prefix and to_c) else (f"row-{_safe_id(to_t)}-{_safe_id(to_c)}" if to_c else "")

            triggers = [
                f".model-relationship-diagram:has(#{rel_id}:focus)",
                f".model-relationship-diagram:has(#{rel_id}:focus-within)",
                f".model-relationship-diagram:has(#{rel_id}:target)",
            ]

            sel_path = _scoped_sel(triggers, f"#{rel_id} .rel-path") + ", " + _scoped_sel(triggers, f"#{rel_id} .rel-path-bridge")
            sel_dots = _scoped_sel(triggers, f"#{rel_id} .port-dot") + ", " + _scoped_sel(triggers, f"#{rel_id} .port-dot-bridge")
            sel_card_badges = _scoped_sel(triggers, f"#{rel_id} .cardinality-badge")
            sel_bidi_group = _scoped_sel(triggers, f"#{rel_id} .bidi-glyph-group")
            sel_bidi_bg = _scoped_sel(triggers, f"#{rel_id} .bidi-badge-bg")
            sel_bidi_text = _scoped_sel(triggers, f"#{rel_id} .bidi-badge-text")
            sel_cards = _scoped_sel(triggers, f"#{from_card_id}") + ", " + _scoped_sel(triggers, f"#{to_card_id}")

            row_targets = []
            text_targets = []
            if from_row_id:
                row_targets.append(_scoped_sel(triggers, f"#{from_row_id}"))
                text_targets.append(_scoped_sel(triggers, f"#{from_row_id} .column-name"))
            if to_row_id:
                row_targets.append(_scoped_sel(triggers, f"#{to_row_id}"))
                text_targets.append(_scoped_sel(triggers, f"#{to_row_id} .column-name"))

            sel_rows = ", ".join(row_targets) if row_targets else ""
            sel_text = ", ".join(text_targets) if text_targets else ""

            rel_block = f"""
    {sel_path} {{ stroke: var(--g-path-active) !important; opacity: 1 !important; }}
    {sel_dots} {{ fill: var(--g-path-active) !important; opacity: 1 !important; }}
    {sel_card_badges} {{ fill: var(--g-path-active) !important; opacity: 1 !important; font-weight: 700 !important; }}
    {sel_bidi_group} {{ opacity: 1 !important; }}
    {sel_bidi_bg} {{ stroke: var(--g-path-active) !important; }}
    {sel_bidi_text} {{ fill: var(--g-path-active) !important; font-weight: 700 !important; }}
    {sel_cards} {{ opacity: 1 !important; }}
    #{rel_id}:focus .rel-path, #{rel_id}:focus-within .rel-path, #{rel_id}:target .rel-path, #{rel_id}:focus .rel-path-bridge, #{rel_id}:focus-within .rel-path-bridge, #{rel_id}:target .rel-path-bridge {{ stroke: var(--g-path-active) !important; opacity: 1 !important; }}
    #{rel_id}:focus .port-dot, #{rel_id}:focus-within .port-dot, #{rel_id}:target .port-dot, #{rel_id}:focus .port-dot-bridge, #{rel_id}:focus-within .port-dot-bridge, #{rel_id}:target .port-dot-bridge {{ fill: var(--g-path-active) !important; opacity: 1 !important; }}
    #{rel_id}:focus .cardinality-badge, #{rel_id}:focus-within .cardinality-badge, #{rel_id}:target .cardinality-badge {{ fill: var(--g-path-active) !important; opacity: 1 !important; font-weight: 700 !important; }}
    #{rel_id}:focus .bidi-glyph-group, #{rel_id}:focus-within .bidi-glyph-group, #{rel_id}:target .bidi-glyph-group {{ opacity: 1 !important; }}
    #{rel_id}:focus .bidi-badge-bg, #{rel_id}:focus-within .bidi-badge-bg, #{rel_id}:target .bidi-badge-bg {{ stroke: var(--g-path-active) !important; }}
    #{rel_id}:focus .bidi-badge-text, #{rel_id}:focus-within .bidi-badge-text, #{rel_id}:target .bidi-badge-text {{ fill: var(--g-path-active) !important; font-weight: 700 !important; }}
"""
            if sel_rows:
                rel_block += f"    {sel_rows} {{ opacity: 1 !important; }}\n"
            if sel_text:
                rel_block += f"    {sel_text} {{ fill: var(--g-key-active) !important; font-weight: 700 !important; }}\n"

            dynamic_css_rules.append(rel_block)

        # 2. Rules for each Table
        for t_name in active_tables:
            incident_rel_ids = []
            partner_card_ids = set()
            active_row_ids = set()

            for r_idx, r in enumerate(relationships):
                f_t = _get_entity_prop(r, "from_table")
                t_t = _get_entity_prop(r, "to_table")
                f_c = _get_entity_prop(r, "from_column")
                t_c = _get_entity_prop(r, "to_column")

                if f_t == t_name or t_t == t_name:
                    r_id = f"rel-{svg_id_prefix}-{r_idx}" if svg_id_prefix else f"rel-{r_idx}"
                    incident_rel_ids.append(r_id)
                    if f_t != t_name:
                        p_c = f"card-{svg_id_prefix}-{_safe_id(f_t)}" if svg_id_prefix else f"card-{_safe_id(f_t)}"
                        partner_card_ids.add(p_c)
                    if t_t != t_name:
                        p_c = f"card-{svg_id_prefix}-{_safe_id(t_t)}" if svg_id_prefix else f"card-{_safe_id(t_t)}"
                        partner_card_ids.add(p_c)

                    if f_c:
                        rw = f"row-{svg_id_prefix}-{_safe_id(f_t)}-{_safe_id(f_c)}" if svg_id_prefix else f"row-{_safe_id(f_t)}-{_safe_id(f_c)}"
                        active_row_ids.add(rw)
                    if t_c:
                        rw = f"row-{svg_id_prefix}-{_safe_id(t_t)}-{_safe_id(t_c)}" if svg_id_prefix else f"row-{_safe_id(t_t)}-{_safe_id(t_c)}"
                        active_row_ids.add(rw)

            if not incident_rel_ids:
                continue

            card_id = f"card-{svg_id_prefix}-{_safe_id(t_name)}" if svg_id_prefix else f"card-{_safe_id(t_name)}"
            triggers = [
                f".model-relationship-diagram:has(#{card_id}:focus)",
                f".model-relationship-diagram:has(#{card_id}:focus-within)",
                f".model-relationship-diagram:has(#{card_id}:target)",
            ]

            focal_card_bg = _scoped_sel(triggers, f"#{card_id} .card-bg")
            focal_card = _scoped_sel(triggers, f"#{card_id}")

            rel_paths_list = [_scoped_sel(triggers, f"#{r_id} .rel-path") for r_id in incident_rel_ids] + [_scoped_sel(triggers, f"#{r_id} .rel-path-bridge") for r_id in incident_rel_ids]
            rel_paths = ", ".join(p for p in rel_paths_list if p)

            rel_dots_list = [_scoped_sel(triggers, f"#{r_id} .port-dot") for r_id in incident_rel_ids] + [_scoped_sel(triggers, f"#{r_id} .port-dot-bridge") for r_id in incident_rel_ids]
            rel_dots = ", ".join(d for d in rel_dots_list if d)

            rel_card_badges = ", ".join(_scoped_sel(triggers, f"#{r_id} .cardinality-badge") for r_id in incident_rel_ids)
            rel_bidi_groups = ", ".join(_scoped_sel(triggers, f"#{r_id} .bidi-glyph-group") for r_id in incident_rel_ids)
            rel_bidi_bgs = ", ".join(_scoped_sel(triggers, f"#{r_id} .bidi-badge-bg") for r_id in incident_rel_ids)
            rel_bidi_texts = ", ".join(_scoped_sel(triggers, f"#{r_id} .bidi-badge-text") for r_id in incident_rel_ids)

            partner_cards = ", ".join(_scoped_sel(triggers, f"#{c_id}") for c_id in partner_card_ids) if partner_card_ids else ""
            row_sel = ", ".join(_scoped_sel(triggers, f"#{rw_id}") for rw_id in active_row_ids) if active_row_ids else ""
            text_sel = ", ".join(_scoped_sel(triggers, f"#{rw_id} .column-name") for rw_id in active_row_ids) if active_row_ids else ""

            tbl_block = f"""
    {focal_card_bg} {{ stroke: var(--g-focal-border) !important; stroke-width: 2.2px !important; opacity: 1 !important; }}
    {focal_card} {{ opacity: 1 !important; }}
    #{card_id}:focus .card-bg, #{card_id}:focus-within .card-bg, #{card_id}:target .card-bg {{ stroke: var(--g-focal-border) !important; stroke-width: 2.2px !important; opacity: 1 !important; }}
    #{card_id}:focus, #{card_id}:focus-within, #{card_id}:target {{ opacity: 1 !important; }}
    {rel_paths} {{ stroke: var(--g-path-active) !important; opacity: 1 !important; }}
    {rel_dots} {{ fill: var(--g-path-active) !important; opacity: 1 !important; }}
    {rel_card_badges} {{ fill: var(--g-path-active) !important; opacity: 1 !important; font-weight: 700 !important; }}
    {rel_bidi_groups} {{ opacity: 1 !important; }}
    {rel_bidi_bgs} {{ stroke: var(--g-path-active) !important; }}
    {rel_bidi_texts} {{ fill: var(--g-path-active) !important; font-weight: 700 !important; }}
"""
            if partner_cards:
                tbl_block += f"    {partner_cards} {{ opacity: 1 !important; }}\n"
            if row_sel:
                tbl_block += f"    {row_sel} {{ opacity: 1 !important; }}\n"
            if text_sel:
                tbl_block += f"    {text_sel} {{ fill: var(--g-key-active) !important; font-weight: 700 !important; }}\n"

            dynamic_css_rules.append(tbl_block)

        legend_height = 56
        svg_height = max_height + legend_height + 24

        theme_class = ""
        if theme_mode == "light":
            theme_class = "theme-force-light"
        elif theme_mode == "dark":
            theme_class = "theme-force-dark"

        if not interactive:
            dynamic_css_rules = []
        extra_css_combined = "\n".join(dynamic_css_rules)
        canvas_tabindex = ' tabindex="0"' if interactive else ""
        svg_parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="{svg_width}" height="{svg_height}" style="max-width: 100%; height: auto;" class="model-relationship-diagram {theme_class}">',
            self._generate_defs_and_styles(svg_id_prefix=svg_id_prefix, extra_css=extra_css_combined, interactive=interactive),
            f'  <rect width="{svg_width}" height="{svg_height}" id="{canvas_id}" rx="4" class="canvas-bg"{canvas_tabindex} />',
        ]

        # Draw Upstream Super-Node Containers
        if upstream_containers_svg:
            svg_parts.extend(upstream_containers_svg)

        # Draw Relationship Connector Edges
        svg_parts.append('<g class="relationship-edges">')
        for r_idx, r in enumerate(relationships):
            from_t = _get_entity_prop(r, "from_table")
            to_t = _get_entity_prop(r, "to_table")
            from_c = _get_entity_prop(r, "from_column")
            to_c = _get_entity_prop(r, "to_column")

            from_pos = card_positions.get(from_t)
            to_pos = card_positions.get(to_t)
            if not from_pos or not to_pos:
                continue

            rel_id = f"rel-{svg_id_prefix}-{r_idx}" if svg_id_prefix else f"rel-{r_idx}"
            from_card_label, to_card_label, card_canonical = self._get_cardinality_labels(r)

            offset_1 = rel_offsets_from.get(r_idx, 0.0)
            offset_2 = rel_offsets_to.get(r_idx, 0.0)

            base_y1 = from_pos["ports"].get(from_c.lower(), from_pos["y"] + from_pos["h"] / 2) if from_c else from_pos["y"] + from_pos["h"] / 2
            base_y2 = to_pos["ports"].get(to_c.lower(), to_pos["y"] + to_pos["h"] / 2) if to_c else to_pos["y"] + to_pos["h"] / 2

            y1 = round(base_y1 + offset_1, 1)
            y2 = round(base_y2 + offset_2, 1)

            from_center_x = from_pos["x"] + from_pos["w"] * 0.5
            to_center_x = to_pos["x"] + to_pos["w"] * 0.5

            if from_center_x > to_center_x:
                x1 = from_pos["x"]
                x2 = to_pos["x"] + to_pos["w"]
                col_dist = x1 - x2
                dy = abs(y2 - y1)
                dx_base = min(max(col_dist * 0.45, 45.0), max(45.0, col_dist * 0.25 + dy * 0.035))
                c1_x = round(x1 - (dx_base + offset_1 * 1.5), 1)
                c2_x = round(x2 + (dx_base + offset_2 * 1.5), 1)
                card_label_x1 = x1 - 12
                card_label_x2 = x2 + 12
            elif from_center_x < to_center_x:
                x1 = from_pos["x"] + from_pos["w"]
                x2 = to_pos["x"]
                col_dist = x2 - x1
                dy = abs(y2 - y1)
                dx_base = min(max(col_dist * 0.45, 45.0), max(45.0, col_dist * 0.25 + dy * 0.035))
                c1_x = round(x1 + (dx_base + offset_1 * 1.5), 1)
                c2_x = round(x2 - (dx_base + offset_2 * 1.5), 1)
                card_label_x1 = x1 + 12
                card_label_x2 = x2 - 12
            else:
                x1 = from_pos["x"] + from_pos["w"]
                x2 = to_pos["x"] + to_pos["w"]
                c1_x = x1 + 50
                c2_x = x2 + 50
                card_label_x1 = x1 + 12
                card_label_x2 = x2 + 12

            path_d = f"M {x1} {y1} C {c1_x} {y1}, {c2_x} {y2}, {x2} {y2}"
            rel_tabindex = ' tabindex="0"' if interactive else ""
            rel_hitbox_tag = f'<path d="{path_d}" class="rel-hitbox" />\n              ' if interactive else ""

            is_cross = r_idx in cross_rel_indices
            if is_cross:
                path_class = "rel-path-bridge"
                dot_class = "port-dot-bridge"
                dash_attr = ""
                title_text = f"{from_t}[{from_c or ''}] → {to_t}[{to_c or ''}] (Cross-Model Rel, {card_canonical})"
                bidi_glyph = ""
            else:
                is_active = self._is_active(r)
                is_bidi = self._is_bidirectional(r)
                bidi_class = "rel-bidirectional" if is_bidi else ""
                active_class = "active-rel" if is_active else "inactive-rel"
                path_class = f"rel-path {bidi_class} {active_class}"
                dot_class = f"port-dot {'port-bidi' if is_bidi else ''}"
                dash_attr = '' if is_active else 'stroke-dasharray="5,4" opacity="0.65"'
                arrow = "⇄" if is_bidi else "→"
                cross_label = "Both" if is_bidi else "Single"
                title_text = f"{from_t}[{from_c or ''}] {arrow} {to_t}[{to_c or ''}] ({card_canonical}, {cross_label})"

                x_mid = round(0.5 * (x1 + x2), 1)
                y_mid = round(0.5 * (y1 + y2), 1)
                bidi_glyph = ""
                if is_bidi:
                    bidi_glyph = f"""
              <g class="bidi-glyph-group">
                <rect x="{x_mid - 12}" y="{y_mid - 8}" width="24" height="16" rx="2" class="bidi-badge-bg" />
                <text x="{x_mid}" y="{y_mid + 4}" class="bidi-badge-text" text-anchor="middle">⇄</text>
              </g>"""

            svg_parts.append(f"""
            <g class="rel-group" id="{rel_id}"{rel_tabindex} title="{html.escape(title_text)}" data-from="{html.escape(str(from_t))}" data-to="{html.escape(str(to_t))}">
              {rel_hitbox_tag.strip()}
              <path d="{path_d}" class="{path_class}" {dash_attr} />
              <circle cx="{x1}" cy="{y1}" r="3" class="{dot_class}" />
              <circle cx="{x2}" cy="{y2}" r="3" class="{dot_class}" />
              <text x="{card_label_x1}" y="{y1 + 4}" class="cardinality-badge" text-anchor="middle">{from_card_label}</text>
              <text x="{card_label_x2}" y="{y2 + 4}" class="cardinality-badge" text-anchor="middle">{to_card_label}</text>
              {bidi_glyph}
            </g>""")
        svg_parts.append('</g>')

        # Draw Cards
        svg_parts.append('<g class="relationship-tables">')
        for t_name, pos in card_positions.items():
            role_key = self._get_role_key(t_name)
            keys = table_keys.get(t_name, [])
            is_focal = bool(focal_table and t_name == focal_table)
            is_rem = pos.get("is_remote", False)
            svg_parts.append(self._render_table_card(
                t_name, role_key, pos["x"], pos["y"], pos["w"], pos["h"], keys,
                is_focal=is_focal, svg_id_prefix=svg_id_prefix, is_remote=is_rem,
                enable_card_toggle=interactive, interactive=interactive,
            ))
        svg_parts.append('</g>')

        # Integrated Legend Bar
        svg_parts.append(self._render_legend(svg_width, max_height + 14, has_bridge=bool(border_tables), has_remote=has_remote))

        svg_parts.append('</svg>')
        return "\n".join(svg_parts)

    def generate_table_svg(
        self,
        target_table_name: str,
        theme_mode: Optional[str] = None,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
    ) -> str:
        """
        Renders a relationship diagram centered on target_table_name:
        - If target_table_name is a FACT table, delegates to scope='star_cluster'.
        - Otherwise, delegates to scope='1hop'.
        Shared unified pipeline ensures identical geometry, styling, and click-to-focus behavior.
        """
        target_table_name = target_table_name.strip()
        scope = "star_cluster" if self._get_role_key(target_table_name) == "FACT" else "1hop"
        return self.generate_diagram(
            scope=scope,
            target_table=target_table_name,
            interactive=interactive,
            theme_mode=theme_mode,
            svg_id_prefix=svg_id_prefix,
        )

    def build_diagram_assets(self, diagrams_subdir: str = "diagrams") -> Dict[str, str]:
        """
        Generates standalone SVG relationship diagrams for the model and all interrelated tables.
        Returns a dictionary mapping relative asset path (e.g. 'diagrams/model_relationships.svg')
        to SVG XML content.
        """
        assets: Dict[str, str] = {}
        diag_sub = diagrams_subdir.strip("/\\")

        # 1. Model Overview Diagram
        model_svg = self.generate_model_svg(interactive=False)

        # Utility Diagram
        util_tables = self.get_utility_tables()
        if util_tables:
            util_svg = self.generate_utility_svg(interactive=False)
            if util_svg:
                util_path = f"{diag_sub}/utility_relationships.svg" if diag_sub else "utility_relationships.svg"
                assets[util_path] = util_svg
        if model_svg:
            model_path = f"{diag_sub}/model_relationships.svg" if diag_sub else "model_relationships.svg"
            assets[model_path] = model_svg

        # 2. 1-Hop Focal Diagrams for every interrelated table
        related_tables: Set[str] = set()
        for r in self.relationships:
            from_t = _get_entity_prop(r, "from_table")
            to_t = _get_entity_prop(r, "to_table")
            if from_t:
                related_tables.add(from_t)
            if to_t:
                related_tables.add(to_t)

        for f_name in self.get_fact_tables():
            if f_name:
                related_tables.add(f_name)

        for tbl_name in sorted(related_tables):
            table_svg = self.generate_table_svg(tbl_name, interactive=False)
            if table_svg:
                clean_name = sanitize_filename(tbl_name)
                table_path = f"{diag_sub}/{clean_name}_relationships.svg" if diag_sub else f"{clean_name}_relationships.svg"
                assets[table_path] = table_svg

        return assets

    def _render_table_card(
        self,
        table_name: str,
        role_key: str,
        x: float,
        y: float,
        w: float,
        h: float,
        keys: List[Tuple[str, str]],
        is_focal: bool = False,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
        enable_card_toggle: bool = True,
        is_remote: bool = False,
    ) -> str:
        role_cfg = ROLE_CONFIG.get(role_key, ROLE_CONFIG["UNKNOWN"])
        role_label = role_cfg["short"]
        role_class = role_cfg["diagram_class"]

        card_shadow_id = f"card-shadow-{svg_id_prefix}" if svg_id_prefix else "card-shadow"
        focal_shadow_id = f"focal-shadow-{svg_id_prefix}" if svg_id_prefix else "focal-shadow"

        card_border_class = "card-border-focal" if is_focal else f"card-border card-border-{role_class}"
        extra_stroke = 'stroke="var(--g-focal-border)" stroke-width="2.2"' if is_focal else 'stroke="var(--g-card-border)" stroke-width="1"'
        focal_shadow = f'filter="url(#{focal_shadow_id})"' if is_focal else f'filter="url(#{card_shadow_id})"'

        safe_t = _safe_id(table_name)
        card_id = f"card-{svg_id_prefix}-{safe_t}" if svg_id_prefix else f"card-{safe_t}"
        card_tabindex = ' tabindex="0"' if interactive else ""
        svg = [f'<g class="table-card" id="{card_id}"{card_tabindex} {focal_shadow}>']
        svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" class="card-bg {card_border_class}" {extra_stroke} />')

        # Header Bar (28px height)
        header_height = 28
        svg.append(f'<path d="M {x} {y+4} A 4 4 0 0 1 {x+4} {y} H {x+w-4} A 4 4 0 0 1 {x+w} {y+4} V {y+header_height} H {x} Z" class="card-header-bg header-{role_class}" />')
        svg.append(f'<line x1="{x}" y1="{y+header_height}" x2="{x+w}" y2="{y+header_height}" class="card-header-divider divider-{role_class}" />')

        # Table Name
        display_name = table_name if len(table_name) <= 16 else table_name[:14] + "…"
        svg.append(f'<text x="{x+10}" y="{y+18}" class="table-title">{html.escape(display_name)}</text>')

        # Role Badge
        badge_w = max(38, len(role_label) * 7 + 10)
        badge_x = x + w - badge_w - 8
        svg.append(f'<rect x="{badge_x}" y="{y+6}" width="{badge_w}" height="16" rx="2" class="badge-bg badge-bg-{role_class}" />')
        svg.append(f'<text x="{badge_x + badge_w/2}" y="{y+17.5}" class="role-badge-text badge-text-{role_class}" text-anchor="middle">{html.escape(role_label)}</text>')

        # Remote Tag (if border table)
        if is_remote:
            rem_x = badge_x - 48
            svg.append(f'<rect x="{rem_x}" y="{y+6}" width="44" height="16" rx="2" class="remote-tag-bg" />')
            svg.append(f'<text x="{rem_x + 22}" y="{y+17.5}" class="remote-tag-text" text-anchor="middle">REMOTE</text>')

        # Column Rows (Minimal: soft pill badges, no horizontal row separators)
        start_cols_y = y + header_height + 2
        for idx, (col_name, col_type) in enumerate(keys):
            row_y = start_cols_y + idx * 20
            row_id = f"row-{svg_id_prefix}-{_safe_id(table_name)}-{_safe_id(col_name)}" if svg_id_prefix else f"row-{_safe_id(table_name)}-{_safe_id(col_name)}"

            svg.append(f'<g class="card-column-row" id="{row_id}">')
            if col_type == "MORE":
                svg.append(f'<text x="{x+14}" y="{row_y+14}" class="column-name" style="opacity: 0.65; font-style: italic;">{html.escape(col_name)}</text>')
            else:
                if col_type == "PK":
                    badge_class = "pk"
                    b_w = 20
                elif col_type in ("FK", "COL"):
                    badge_class = "fk"
                    b_w = 24 if col_type == "COL" else 20
                elif col_type == "CALC":
                    badge_class = "calc"
                    b_w = 28
                else:
                    badge_class = "msr"
                    b_w = 26

                text_x = x + 10 + b_w / 2
                svg.append(f'<rect x="{x+10}" y="{row_y+3}" width="{b_w}" height="14" rx="2" class="col-badge-bg col-badge-bg-{badge_class}" />')
                svg.append(f'<text x="{text_x}" y="{row_y+13.5}" class="col-type-badge col-badge-text-{badge_class}" text-anchor="middle">{col_type}</text>')

                disp_col = col_name if len(col_name) <= 20 else col_name[:18] + "…"
                svg.append(f'<text x="{x+16+b_w}" y="{row_y+14}" class="column-name">{html.escape(disp_col)}</text>')
            svg.append('</g>')

        # Hitbox for direct click/focus (No <a> tag, zero scroll jump)
        if enable_card_toggle and interactive:
            svg.append(f'  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" class="card-hitbox" />')

        svg.append('</g>')
        return "\n".join(svg)

    def _render_legend(
        self,
        svg_width: float,
        y_legend: float,
        has_bridge: bool = False,
        has_remote: bool = False,
    ) -> str:
        if not (has_bridge or has_remote):
            bar_w = 790
            bar_x = (svg_width - bar_w) / 2
            return f"""
  <g class="diagram-legend" transform="translate({bar_x}, {y_legend})">
    <rect x="0" y="0" width="{bar_w}" height="36" rx="3" class="legend-card-bg" />
    
    <!-- Active Relationship -->
    <line x1="20" y1="18" x2="48" y2="18" class="rel-path legend-rel-path" />
    <circle cx="20" cy="18" r="3" class="port-dot" />
    <circle cx="48" cy="18" r="3" class="port-dot" />
    <text x="56" y="22" class="legend-text">Active Rel</text>

    <!-- Inactive Relationship -->
    <line x1="126" y1="18" x2="154" y2="18" class="rel-path legend-rel-path" style="stroke-dasharray: 4,4; opacity: 0.7;" />
    <text x="162" y="22" class="legend-text">Inactive Rel</text>

    <!-- Bidirectional Relationship -->
    <line x1="242" y1="18" x2="278" y2="18" class="rel-path rel-bidirectional legend-rel-path" />
    <rect x="253" y="10" width="16" height="16" rx="2" class="bidi-badge-bg" />
    <text x="261" y="21.5" class="bidi-badge-text" style="font-size: 9px;" text-anchor="middle">⇄</text>
    <text x="286" y="22" class="legend-text">Bidirectional (Both)</text>

    <!-- Cardinality -->
    <text x="412" y="22" class="cardinality-badge" style="font-size: 11px;">1 : *</text>
    <text x="436" y="22" class="legend-text">Cardinality (1:*, 1:1, *:*)</text>

    <!-- Keys -->
    <rect x="585" y="10" width="20" height="14" rx="2" class="col-badge-bg col-badge-bg-pk" />
    <text x="595" y="20.5" class="col-type-badge col-badge-text-pk" text-anchor="middle">PK</text>
    <rect x="612" y="10" width="20" height="14" rx="2" class="col-badge-bg col-badge-bg-fk" />
    <text x="622" y="20.5" class="col-type-badge col-badge-text-fk" text-anchor="middle">FK</text>
    <text x="642" y="22" class="legend-text">Primary / Foreign Key</text>
  </g>"""

        bar_w = 980
        bar_x = (svg_width - bar_w) / 2
        return f"""
  <g class="diagram-legend" transform="translate({bar_x}, {y_legend})">
    <rect x="0" y="0" width="{bar_w}" height="36" rx="3" class="legend-card-bg" />
    
    <!-- Active Relationship -->
    <line x1="20" y1="18" x2="48" y2="18" class="rel-path legend-rel-path" />
    <circle cx="20" cy="18" r="3" class="port-dot" />
    <circle cx="48" cy="18" r="3" class="port-dot" />
    <text x="56" y="22" class="legend-text">Active Rel</text>

    <!-- Remote Relationship -->
    <line x1="130" y1="18" x2="158" y2="18" class="rel-path-bridge" />
    <circle cx="130" cy="18" r="3" class="port-dot-bridge" />
    <circle cx="158" cy="18" r="3" class="port-dot-bridge" />
    <text x="166" y="22" class="legend-text">Remote Rel</text>

    <!-- Inactive Relationship -->
    <line x1="250" y1="18" x2="278" y2="18" class="rel-path legend-rel-path" style="stroke-dasharray: 4,4; opacity: 0.7;" />
    <text x="286" y="22" class="legend-text">Inactive Rel</text>

    <!-- Bidirectional Relationship -->
    <line x1="365" y1="18" x2="401" y2="18" class="rel-path rel-bidirectional legend-rel-path" />
    <rect x="376" y="10" width="16" height="16" rx="2" class="bidi-badge-bg" />
    <text x="384" y="21.5" class="bidi-badge-text" style="font-size: 9px;" text-anchor="middle">⇄</text>
    <text x="409" y="22" class="legend-text">Bidirectional (Both)</text>

    <!-- Cardinality -->
    <text x="535" y="22" class="cardinality-badge" style="font-size: 11px;">1 : *</text>
    <text x="559" y="22" class="legend-text">Cardinality (1:*, 1:1, *:*)</text>

    <!-- Remote Entity -->
    <rect x="715" y="10" width="44" height="16" rx="2" class="remote-tag-bg" />
    <text x="737" y="21.5" class="remote-tag-text" text-anchor="middle">REMOTE</text>
    <text x="765" y="22" class="legend-text">Remote Entity</text>

    <!-- Keys -->
    <rect x="858" y="10" width="20" height="14" rx="2" class="col-badge-bg col-badge-bg-pk" />
    <text x="868" y="20.5" class="col-type-badge col-badge-text-pk" text-anchor="middle">PK</text>
    <rect x="884" y="10" width="20" height="14" rx="2" class="col-badge-bg col-badge-bg-fk" />
    <text x="894" y="20.5" class="col-type-badge col-badge-text-fk" text-anchor="middle">FK</text>
    <text x="912" y="22" class="legend-text">PK / FK</text>
  </g>"""

    def generate_utility_svg(
        self,
        theme_mode: Optional[str] = None,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
    ) -> str:
        """
        Renders the dedicated [Utility & Parameters] SVG tab:
        - 3-column grid of minimal cards for disconnected utility tables, parameter tables, and calc groups.
        """
        util_tables = self.get_utility_tables()
        if not util_tables:
            return ""

        svg_width = 880
        card_w = 215
        cols = min(3, len(util_tables))
        col_gap = 30
        margin_x = max(30.0, (svg_width - (cols * card_w + (cols - 1) * col_gap)) / 2.0)
        start_y = 75.0

        canvas_id = f"canvas-{svg_id_prefix}" if svg_id_prefix else "canvas"
        canvas_tabindex = ' tabindex="0"' if interactive else ""
        theme_class = ""
        if theme_mode == "light":
            theme_class = "theme-force-light"
        elif theme_mode == "dark":
            theme_class = "theme-force-dark"

        cards_svg = []
        max_y = start_y
        row_max_h = 0
        curr_row = 0

        for idx, t_name in enumerate(util_tables):
            col_idx = idx % cols
            row_idx = idx // cols
            if row_idx > curr_row:
                curr_row = row_idx
                start_y += row_max_h + 20
                row_max_h = 0

            cx = margin_x + col_idx * (card_w + col_gap)
            cy = start_y

            role_key = self._get_role_key(t_name)
            # Find measures or columns for this utility table
            tbl_msrs = [
                m for m in self.measures
                if (_get_entity_prop(m, "table") == t_name or _get_entity_prop(m, "host_table") == t_name)
            ]
            keys = []
            if tbl_msrs:
                total_items = len(tbl_msrs)
                for m in tbl_msrs[:4]:
                    keys.append((_get_entity_prop(m, "name") or "Measure", "MSR"))
                if total_items > 4:
                    keys.append((f"+ {total_items - 4} more...", "MORE"))
            else:
                tbl_obj = self._table_map.get(t_name)
                t_cols = _get_entity_prop(tbl_obj, "columns", []) or []
                total_items = len(t_cols)
                for c in t_cols[:4]:
                    is_calc = bool(role_key == "CALC_GROUP" or _get_entity_prop(c, "is_calculation_item"))
                    k_type = "CALC" if is_calc else "COL"
                    keys.append((_get_entity_prop(c, "name") or "Column", k_type))
                if total_items > 4:
                    keys.append((f"+ {total_items - 4} more...", "MORE"))

            if not keys:
                keys = [("Utility Item", "COL")]

            card_h = 28 + len(keys) * 20 + 8
            row_max_h = max(row_max_h, card_h)
            max_y = max(max_y, cy + card_h)

            cards_svg.append(self._render_table_card(
                t_name, role_key, cx, cy, card_w, card_h, keys,
                svg_id_prefix=svg_id_prefix, enable_card_toggle=interactive, interactive=interactive,
            ))

        # Check if CALC items exist across utility tables
        has_calc = any(self._get_role_key(t) == "CALC_GROUP" for t in util_tables)

        legend_items = []
        # MSR
        legend_items.append((120.0, lambda x: f"""    <!-- Measure Tag -->
    <rect x="{x}" y="10" width="28" height="14" rx="2" class="col-badge-bg col-badge-bg-msr" />
    <text x="{x+14}" y="20.5" class="col-type-badge col-badge-text-msr" text-anchor="middle">MSR</text>
    <text x="{x+36}" y="22" class="legend-text">DAX Measure</text>"""))

        # COL
        legend_items.append((195.0, lambda x: f"""    <!-- Column Tag -->
    <rect x="{x}" y="10" width="24" height="14" rx="2" class="col-badge-bg col-badge-bg-fk" />
    <text x="{x+12}" y="20.5" class="col-type-badge col-badge-text-fk" text-anchor="middle">COL</text>
    <text x="{x+32}" y="22" class="legend-text">Column / Parameter Attribute</text>"""))

        # CALC (if present)
        if has_calc:
            legend_items.append((130.0, lambda x: f"""    <!-- Calculation Item Tag -->
    <rect x="{x}" y="10" width="28" height="14" rx="2" class="col-badge-bg col-badge-bg-calc" />
    <text x="{x+14}" y="20.5" class="col-type-badge col-badge-text-calc" text-anchor="middle">CALC</text>
    <text x="{x+36}" y="22" class="legend-text">Calculation Item</text>"""))

        # CalcGroup Role (if present)
        if has_calc:
            legend_items.append((115.0, lambda x: f"""    <!-- CalcGroup Role -->
    <rect x="{x}" y="9" width="56" height="16" rx="2" class="badge-bg badge-bg-calcgroup" />
    <text x="{x+28}" y="20.5" class="role-badge-text badge-text-calcgroup" text-anchor="middle">CalcGroup</text>
    <text x="{x+64}" y="22" class="legend-text">Calc Group</text>"""))

        u_gap = 16.0
        u_pad = 20.0
        u_bar_w = sum(w for w, _ in legend_items) + u_gap * (len(legend_items) - 1) + u_pad * 2
        u_bar_x = (svg_width - u_bar_w) / 2.0
        y_legend = max_y + 24.0

        rendered_u_items = []
        c_x = u_pad
        for w, render_fn in legend_items:
            rendered_u_items.append(render_fn(c_x))
            c_x += w + u_gap

        rendered_u_items_str = "\n\n".join(rendered_u_items)
        utility_legend_svg = f"""
  <!-- Utility Tab Dedicated Legend -->
  <g class="diagram-legend" transform="translate({u_bar_x}, {y_legend})">
    <rect x="0" y="0" width="{u_bar_w}" height="36" rx="3" class="legend-card-bg" />
{rendered_u_items_str}
  </g>"""

        svg_height = y_legend + 36 + 24

        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_width} {svg_height}" width="{svg_width}" height="{svg_height}" style="max-width: 100%; height: auto;" class="model-relationship-diagram {theme_class}">
{self._generate_defs_and_styles(svg_id_prefix=svg_id_prefix, interactive=interactive)}
  <rect width="{svg_width}" height="{svg_height}" id="{canvas_id}" rx="4" class="canvas-bg"{canvas_tabindex} />

  <!-- Header Banner -->
  <g transform="translate(30, 24)">
    <text x="0" y="14" class="util-section-hdr">Utility Entities, Calculation Groups &amp; Dynamic Parameters</text>
    <text x="0" y="32" class="util-section-sub">Disconnected metadata containers and calculation engines isolated from the core Star Schema topology</text>
  </g>

  <!-- Utility Cards Grid -->
  <g class="relationship-tables">
    {"".join(cards_svg)}
  </g>
{utility_legend_svg}
</svg>"""

    def _generate_empty_svg(self, message: str) -> str:
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 120" width="600" height="120" style="max-width: 100%; height: auto;">
  <rect width="600" height="120" rx="8" fill="#f8fafc" stroke="#e2e8f0" />
  <text x="300" y="65" text-anchor="middle" font-family="system-ui, sans-serif" font-size="14" fill="#64748b">{html.escape(message)}</text>
</svg>"""

    def _generate_defs_and_styles(
        self,
        svg_id_prefix: Optional[str] = None,
        interactive: bool = True,
        extra_css: str = "",
    ) -> str:
        """Dynamically generates clean, minimal geometric SVG styles from ROLE_CONFIG."""
        card_shadow_id = f"card-shadow-{svg_id_prefix}" if svg_id_prefix else "card-shadow"
        focal_shadow_id = f"focal-shadow-{svg_id_prefix}" if svg_id_prefix else "focal-shadow"

        light_card_borders = []
        light_headers = []
        light_dividers = []
        light_badges = []

        def _dark_media_rule(sel: str, body: str) -> str:
            return (
                f'      :root.model-relationship-diagram:not([data-theme="light"]):not(.theme-force-light) {sel},\n'
                f'      :root:not([data-theme="light"]) .model-relationship-diagram:not(.theme-force-light) {sel} {{ {body} }}'
            )

        def _forced_theme_rule(theme: str, sel: str, body: str) -> str:
            return (
                f'    .theme-force-{theme} {sel},\n'
                f'    :root[data-theme="{theme}"] .model-relationship-diagram {sel},\n'
                f'    [data-theme="{theme}"] .model-relationship-diagram {sel} {{ {body} }}'
            )

        dark_card_borders = []
        dark_headers = []
        dark_dividers = []
        dark_badges = []

        force_light_rules = []
        force_dark_rules = []

        for role_key, cfg in ROLE_CONFIG.items():
            if role_key == "UNKNOWN":
                continue
            d_class = cfg["diagram_class"]
            l_tok = cfg["light"]
            d_tok = cfg["dark"]

            # Light Mode (Base)
            light_card_borders.append(f"    .card-border-{d_class} {{ stroke: {l_tok['card_border']}; }}")
            light_headers.append(f"    .header-{d_class} {{ fill: {l_tok['header_bg']}; }}")
            light_dividers.append(f"    .divider-{d_class} {{ stroke: {l_tok['divider']}; }}")
            light_badges.append(
                f"    .badge-bg-{d_class} {{ fill: transparent; stroke: {l_tok['badge_fg']}; stroke-width: 1px; }}\n"
                f"    .badge-text-{d_class} {{ fill: {l_tok['badge_fg']}; font-weight: 700; }}"
            )

            # Dark Mode (@media prefers-color-scheme: dark, scoped against forced light)
            dark_card_borders.append(_dark_media_rule(f".card-border-{d_class}", f"stroke: {d_tok['card_border']};"))
            dark_headers.append(_dark_media_rule(f".header-{d_class}", f"fill: {d_tok['header_bg']};"))
            dark_dividers.append(_dark_media_rule(f".divider-{d_class}", f"stroke: {d_tok['divider']};"))
            dark_badges.append(
                _dark_media_rule(f".badge-bg-{d_class}", f"fill: transparent; stroke: {d_tok['badge_fg']}; stroke-width: 1px;")
                + "\n"
                + _dark_media_rule(f".badge-text-{d_class}", f"fill: {d_tok['badge_fg']}; font-weight: 700;")
            )

            # Forced Dark Themes (Both CSS class and HTML portal [data-theme="dark"])
            force_dark_rules.append(
                _forced_theme_rule("dark", f".card-border-{d_class}", f"stroke: {d_tok['card_border']} !important;") + "\n"
                + _forced_theme_rule("dark", f".header-{d_class}", f"fill: {d_tok['header_bg']} !important;") + "\n"
                + _forced_theme_rule("dark", f".divider-{d_class}", f"stroke: {d_tok['divider']} !important;") + "\n"
                + _forced_theme_rule("dark", f".badge-bg-{d_class}", f"fill: transparent !important; stroke: {d_tok['badge_fg']} !important; stroke-width: 1px !important;") + "\n"
                + _forced_theme_rule("dark", f".badge-text-{d_class}", f"fill: {d_tok['badge_fg']} !important; font-weight: 700 !important;")
            )

            # Forced Light Themes (Both CSS class and HTML portal [data-theme="light"])
            force_light_rules.append(
                _forced_theme_rule("light", f".card-border-{d_class}", f"stroke: {l_tok['card_border']} !important;") + "\n"
                + _forced_theme_rule("light", f".header-{d_class}", f"fill: {l_tok['header_bg']} !important;") + "\n"
                + _forced_theme_rule("light", f".divider-{d_class}", f"stroke: {l_tok['divider']} !important;") + "\n"
                + _forced_theme_rule("light", f".badge-bg-{d_class}", f"fill: transparent !important; stroke: {l_tok['badge_fg']} !important; stroke-width: 1px !important;") + "\n"
                + _forced_theme_rule("light", f".badge-text-{d_class}", f"fill: {l_tok['badge_fg']} !important; font-weight: 700 !important;")
            )

        dark_media_rules = "\n".join(
            _dark_media_rule(sel, body)
            for sel, body in [
                (".canvas-bg", "fill: #16181d;"),
                (".card-bg", "fill: #21252d;"),
                (".card-border-focal", "stroke: var(--g-focal-border) !important; stroke-width: 2.2px !important;"),
                (".table-title", "fill: #f0f3f6;"),
                (".column-name", "fill: #d0d7de;"),
                (".cardinality-badge", "fill: var(--g-path-normal);"),
                (".legend-text", "fill: #9da7b3;"),
                (".legend-card-bg", "fill: #21252d; stroke: #343a46;"),
                (".diagram-legend .legend-text", "fill: #e2e8f0 !important;"),
                (".diagram-legend .cardinality-badge", "fill: #f0f3f6 !important;"),
                (".diagram-legend .bidi-badge-text", "fill: #f0f3f6 !important;"),
                (".diagram-legend .bidi-badge-bg", "fill: #21252d !important; stroke: #9ca3af !important;"),
                (".diagram-legend .rel-path", "stroke: #9ca3af !important;"),
                (".diagram-legend .port-dot", "fill: #9ca3af !important; stroke: #21252d !important;"),
                (".row-separator", "stroke: #272c35;"),
                (".rel-path", "stroke: var(--g-path-normal);"),
                (".rel-path.rel-bidirectional", "stroke: var(--g-path-normal);"),
                (".port-dot", "fill: var(--g-path-normal); stroke: #21252d;"),
                (".port-dot.port-bidi", "fill: var(--g-path-normal);"),
                (".bidi-badge-bg", "fill: #21252d; stroke: var(--g-path-normal);"),
                (".bidi-badge-text", "fill: var(--g-path-normal);"),
            ]
        )

        dark_media_badge_rules = "\n".join(
            _dark_media_rule(sel, body)
            for sel, body in [
                (".col-badge-bg-pk", "fill: transparent; stroke: #93c5fd; stroke-width: 0.8px;"),
                (".col-badge-text-pk", "fill: #93c5fd; font-weight: 700;"),
                (".col-badge-bg-fk", "fill: transparent; stroke: #cbd5e1; stroke-width: 0.8px;"),
                (".col-badge-text-fk", "fill: #cbd5e1; font-weight: 700;"),
                (".col-badge-bg-calc", "fill: transparent; stroke: #d8b4fe; stroke-width: 0.8px;"),
                (".col-badge-text-calc", "fill: #d8b4fe; font-weight: 700;"),
            ]
        )

        forced_dark_legend_rules = "\n".join(
            _forced_theme_rule("dark", sel, body)
            for sel, body in [
                (".diagram-legend .legend-text", "fill: #e2e8f0 !important;"),
                (".diagram-legend .cardinality-badge", "fill: #f0f3f6 !important;"),
                (".diagram-legend .bidi-badge-text", "fill: #f0f3f6 !important;"),
                (".diagram-legend .bidi-badge-bg", "fill: #21252d !important; stroke: #9ca3af !important;"),
                (".diagram-legend .rel-path", "stroke: #9ca3af !important;"),
                (".diagram-legend .port-dot", "fill: #9ca3af !important; stroke: #21252d !important;"),
            ]
        )

        forced_light_legend_rules = "\n".join(
            _forced_theme_rule("light", sel, body)
            for sel, body in [
                (".diagram-legend .legend-text", "fill: #1e293b !important;"),
                (".diagram-legend .cardinality-badge", "fill: #0f172a !important;"),
                (".diagram-legend .bidi-badge-text", "fill: #0f172a !important;"),
                (".diagram-legend .bidi-badge-bg", "fill: #ffffff !important; stroke: #64748b !important;"),
                (".diagram-legend .rel-path", "stroke: #64748b !important;"),
                (".diagram-legend .port-dot", "fill: #64748b !important; stroke: #ffffff !important;"),
            ]
        )

        extra_css_block = f"\n    /* Diagram-Specific Click-to-Focus Rules */\n{extra_css}" if (extra_css and interactive) else ""
        cursor_stat_link = " cursor: pointer;" if interactive else ""
        if interactive:
            hitbox_and_outline_css = """    /* Pure Static Click-to-Focus: Instantaneous response */
    .card-hitbox { fill: transparent; cursor: pointer; outline: none; }
    .rel-hitbox { fill: none; stroke: transparent; stroke-width: 16; cursor: pointer; outline: none; pointer-events: stroke; }
    .canvas-bg { fill: var(--g-bg-canvas); cursor: default; outline: none; }
    .rel-group, .table-card { outline: none; cursor: pointer; }"""
            dimming_rules_css = """    /* Focus and Target Dimming Rules (Interactive Only) */
    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .relationship-edges .rel-path,
    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .relationship-edges .rel-path-bridge,
    svg.model-relationship-diagram:has(:target) .relationship-edges .rel-path,
    svg.model-relationship-diagram:has(:target) .relationship-edges .rel-path-bridge,
    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .relationship-edges .port-dot,
    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .relationship-edges .port-dot-bridge,
    svg.model-relationship-diagram:has(:target) .relationship-edges .port-dot,
    svg.model-relationship-diagram:has(:target) .relationship-edges .port-dot-bridge,
    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .relationship-edges .cardinality-badge,
    svg.model-relationship-diagram:has(:target) .relationship-edges .cardinality-badge,
    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .relationship-edges .bidi-glyph-group,
    svg.model-relationship-diagram:has(:target) .relationship-edges .bidi-glyph-group {
      opacity: var(--g-dim-opacity);
    }

    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .relationship-tables .table-card,
    svg.model-relationship-diagram:has(:target) .relationship-tables .table-card {
      opacity: var(--g-dim-opacity);
    }

    svg.model-relationship-diagram:has(:focus):not(:has(.canvas-bg:focus)) .card-column-row,
    svg.model-relationship-diagram:has(:target) .card-column-row {
      opacity: var(--g-dim-keys);
    }

    .diagram-legend, .upstream-group { opacity: 1 !important; }
    .diagram-legend *, .upstream-group * { opacity: 1 !important; }"""
        else:
            hitbox_and_outline_css = """    /* Static Mode: Outline and Cursor Normalization */
    .canvas-bg { fill: var(--g-bg-canvas); cursor: default; outline: none; }
    .rel-group, .table-card { outline: none; }"""
            dimming_rules_css = ""

        return f"""<defs>
    <filter id="{card_shadow_id}" x="-5%" y="-5%" width="110%" height="115%" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.04" />
    </filter>
    <filter id="{focal_shadow_id}" x="-10%" y="-10%" width="120%" height="125%" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="2" stdDeviation="4" flood-opacity="0.08" />
    </filter>
    <marker id="feed-arrow-{svg_id_prefix}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="var(--g-upstream-border)" />
    </marker>
    <marker id="feed-arrow" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 10 5 L 0 8.5 z" fill="var(--g-upstream-border)" />
    </marker>
  </defs>
  <style>
    /* CSS Variables for Dynamic Dark/Light Theme */
    :root, .model-relationship-diagram {{
      --g-bg-canvas: #f8fafc;
      --g-card-bg: #ffffff;
      --g-card-border: #cbd5e1;
      --g-card-hdr: #f8fafc;
      --g-title: #0f172a;
      --g-text-col: #475569;
      --g-text-key: #334155;
      --g-key-active: #1e293b;
      --g-path-normal: #cbd5e1;
      --g-path-active: #475569;
      --g-path-bridge: #2c4a6f;
      --g-focal-border: #475569;
      --g-upstream-border: #94a3b8;
      --g-upstream-bg: rgba(148, 163, 184, 0.08);
      --g-upstream-stat-bg: #ffffff;
      --g-upstream-stat-border: #e2e8f0;
      --g-upstream-stat-num: #1e293b;
      --g-upstream-stat-label: #64748b;
      --g-upstream-pill-bg: #f1f5f9;
      --g-upstream-pill-text: #334155;
      --g-pk-fg: #0284c7;
      --g-pk-bg: rgba(2, 132, 199, 0.08);
      --g-fk-fg: #64748b;
      --g-fk-bg: rgba(100, 116, 139, 0.08);
      --g-msr-fg: #2c4a6f;
      --g-msr-bg: rgba(44, 74, 111, 0.08);
      --g-badge-bg: rgba(0, 0, 0, 0.03);
      --g-badge-border: rgba(0, 0, 0, 0.08);
      --g-dim-opacity: 0.14;
      --g-dim-keys: 0.20;
    }}

    /* Base Typography & Geometry (Light Defaults First) */
    .canvas-bg {{ fill: var(--g-bg-canvas); cursor: default; outline: none; }}
    .card-bg {{ fill: var(--g-card-bg); stroke-width: 1; stroke: var(--g-card-border); }}
    .card-border-focal {{ stroke: var(--g-focal-border) !important; stroke-width: 2.2px !important; }}
    .table-title {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; font-weight: 700; fill: var(--g-title); }}
    .role-badge-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 9px; font-weight: 700; }}
    .column-name {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 11px; fill: var(--g-text-col); font-weight: 500; }}
    .col-type-badge {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 9px; font-weight: 700; }}
    .cardinality-badge {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 11px; font-weight: 700; fill: var(--g-path-normal); }}
    .legend-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 11px; font-weight: 600; fill: var(--g-text-col); }}
    .legend-card-bg {{ fill: var(--g-card-bg); stroke: var(--g-card-border); stroke-width: 1; }}
    .diagram-legend .legend-text {{ fill: #1e293b; font-weight: 600; }}
    .diagram-legend .cardinality-badge {{ fill: #0f172a; font-weight: 700; }}
    .diagram-legend .bidi-badge-text {{ fill: #0f172a; font-weight: 700; }}
    .diagram-legend .bidi-badge-bg {{ fill: #ffffff; stroke: #64748b; stroke-width: 1.2px; }}
    .diagram-legend .rel-path {{ stroke: #64748b !important; stroke-width: 1.5px !important; }}
    .diagram-legend .port-dot {{ fill: #64748b !important; stroke: #ffffff !important; }}
    .row-separator {{ stroke: var(--g-card-border); stroke-opacity: 0.4; stroke-width: 1; }}

{hitbox_and_outline_css}

    /* Constant Stroke-Width Relationship Connectors (Luminance shift only, No neon) */
    .rel-path {{ fill: none; stroke: var(--g-path-normal); stroke-width: 1.3px; }}
    .rel-path.rel-bidirectional {{ stroke: var(--g-path-normal); stroke-width: 1.3px; }}
    .rel-path.inactive-rel {{ stroke-dasharray: 4, 4; opacity: 0.6; }}
    .rel-path-bridge {{ fill: none; stroke: var(--g-path-bridge); stroke-width: 1.6px; stroke-dasharray: 6, 3; }}
    .rel-path-feed {{ fill: none; stroke: var(--g-upstream-border); stroke-width: 1.4px; stroke-dasharray: 4, 3; }}
    .port-dot {{ fill: var(--g-path-normal); stroke: var(--g-card-bg); stroke-width: 1.1; }}
    .port-dot.port-bidi {{ fill: var(--g-path-normal); }}
    .port-dot-bridge {{ fill: var(--g-path-bridge); stroke: var(--g-card-bg); stroke-width: 1.2px; }}
    .badge-cardinality-bg {{ fill: var(--g-card-bg); stroke: var(--g-path-bridge); stroke-width: 1px; rx: 3px; }}
    .bidi-badge-bg {{ fill: var(--g-card-bg); stroke: var(--g-path-normal); stroke-width: 1; }}
    .bidi-badge-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 9.5px; font-weight: 700; fill: var(--g-path-normal); }}

    /* Card Borders (Light Mode Defaults) */
{chr(10).join(light_card_borders)}

    /* Card Header Tints (Light Mode Defaults) */
{chr(10).join(light_headers)}

    /* Header Dividers (Light Mode Defaults) */
{chr(10).join(light_dividers)}

    /* Role Badges (Light Mode Defaults) */
{chr(10).join(light_badges)}

    /* Key Badges (Transparent Squared Border, Aligned with HTML Legend & Forced Themes) */
    .col-badge-bg-pk {{ fill: transparent; stroke: #1e3a8a; stroke-width: 0.8px; rx: 2px; }}
    .col-badge-text-pk {{ fill: #1e3a8a; font-weight: 700; }}
    .col-badge-bg-fk {{ fill: transparent; stroke: #475569; stroke-width: 0.8px; rx: 2px; }}
    .col-badge-text-fk {{ fill: #475569; font-weight: 700; }}
    .col-badge-bg-msr {{ fill: var(--g-msr-bg); rx: 2px; }}
    .col-badge-text-msr {{ fill: var(--g-msr-fg); font-weight: 700; }}
    .col-badge-bg-calc {{ fill: transparent; stroke: #6b21a8; stroke-width: 0.8px; rx: 2px; }}
    .col-badge-text-calc {{ fill: #6b21a8; font-weight: 700; }}

    /* Upstream Container Elements */
    .upstream-box {{ fill: var(--g-upstream-bg); stroke: var(--g-upstream-border); stroke-width: 1.2px; stroke-dasharray: 6, 4; rx: 6px; }}
    .upstream-header-title {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; font-weight: 700; fill: var(--g-title); }}
    .upstream-stat-box {{ fill: var(--g-upstream-stat-bg); stroke: var(--g-upstream-stat-border); stroke-width: 1px; rx: 4px; }}
    .upstream-stat-link {{ fill: var(--g-upstream-pill-bg); stroke: var(--g-upstream-border); stroke-width: 1px; rx: 4px;{cursor_stat_link} }}
    .upstream-stat-label {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 10px; font-weight: 600; fill: var(--g-upstream-stat-label); }}
    .upstream-stat-val {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 10.5px; font-weight: 700; fill: var(--g-upstream-stat-num); }}
    .upstream-link-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 10px; font-weight: 700; fill: var(--g-upstream-pill-text); }}
    .upstream-stat-card-lg {{ fill: var(--g-upstream-stat-bg); stroke: var(--g-upstream-stat-border); stroke-width: 1px; rx: 5px; }}
    .upstream-stat-lg-num {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; font-weight: 800; fill: var(--g-upstream-stat-num); }}
    .upstream-stat-lg-title {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 11px; font-weight: 700; fill: var(--g-title); }}
    .upstream-stat-lg-sub {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 9.5px; fill: var(--g-text-col); }}
    .remote-tag-bg {{ fill: var(--g-upstream-pill-bg); stroke: var(--g-upstream-border); stroke-width: 0.8px; rx: 2px; }}
    .remote-tag-text {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 8px; font-weight: 700; fill: var(--g-upstream-pill-text); }}
    .util-section-hdr {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; font-weight: 700; fill: var(--g-title); }}
    .util-section-sub {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 11px; fill: var(--g-text-col); }}

    /* ============================================================= */
    /* DARK THEME STYLES (Overrides Light Defaults)                  */
    /* ============================================================= */
    @media (prefers-color-scheme: dark) {{
      :root.model-relationship-diagram:not([data-theme="light"]):not(.theme-force-light),
      :root:not([data-theme="light"]) .model-relationship-diagram:not(.theme-force-light) {{
        --g-bg-canvas: #16181d;
        --g-card-bg: #21252d;
        --g-card-border: #343a46;
        --g-card-hdr: #1e2229;
        --g-title: #f0f3f6;
        --g-text-col: #8b949e;
        --g-text-key: #c9d1d9;
        --g-key-active: #e2e8f0;
        --g-path-normal: #404752;
        --g-path-active: #9ca3af;
        --g-path-bridge: #8fa8c4;
        --g-focal-border: #9ca3af;
        --g-upstream-border: #64748b;
        --g-upstream-bg: rgba(100, 116, 139, 0.08);
        --g-upstream-stat-bg: #1c2128;
        --g-upstream-stat-border: #30363d;
        --g-upstream-stat-num: #e2e8f0;
        --g-upstream-stat-label: #8b949e;
        --g-upstream-pill-bg: rgba(100, 116, 139, 0.18);
        --g-upstream-pill-text: #cbd5e1;
        --g-pk-fg: #93c5fd;
        --g-pk-bg: rgba(147, 197, 253, 0.12);
        --g-fk-fg: #94a3b8;
        --g-fk-bg: rgba(148, 163, 184, 0.12);
        --g-msr-fg: #8fa8c4;
        --g-msr-bg: rgba(143, 168, 196, 0.12);
        --g-badge-bg: rgba(255, 255, 255, 0.05);
        --g-badge-border: rgba(255, 255, 255, 0.10);
        --g-dim-opacity: 0.15;
        --g-dim-keys: 0.20;
      }}
{dark_media_rules}

{chr(10).join(dark_card_borders)}

{chr(10).join(dark_headers)}

{chr(10).join(dark_dividers)}

{chr(10).join(dark_badges)}

{dark_media_badge_rules}
    }}

    /* Forced Dark Mode Class & HTML data-theme integration */
    .theme-force-dark,
    :root[data-theme="dark"] .model-relationship-diagram,
    [data-theme="dark"] .model-relationship-diagram {{
      --g-bg-canvas: #16181d;
      --g-card-bg: #21252d;
      --g-card-border: #343a46;
      --g-card-hdr: #1e2229;
      --g-title: #f0f3f6;
      --g-text-col: #8b949e;
      --g-text-key: #c9d1d9;
      --g-key-active: #e2e8f0;
      --g-path-normal: #404752;
      --g-path-active: #9ca3af;
      --g-path-bridge: #8fa8c4;
      --g-focal-border: #9ca3af;
      --g-upstream-border: #64748b;
      --g-upstream-bg: rgba(100, 116, 139, 0.08);
      --g-upstream-stat-bg: #1c2128;
      --g-upstream-stat-border: #30363d;
      --g-upstream-stat-num: #e2e8f0;
      --g-upstream-stat-label: #8b949e;
      --g-upstream-pill-bg: rgba(100, 116, 139, 0.18);
      --g-upstream-pill-text: #cbd5e1;
      --g-pk-fg: #93c5fd;
      --g-pk-bg: rgba(147, 197, 253, 0.12);
      --g-fk-fg: #94a3b8;
      --g-fk-bg: rgba(148, 163, 184, 0.12);
      --g-msr-fg: #8fa8c4;
      --g-msr-bg: rgba(143, 168, 196, 0.12);
      --g-badge-bg: rgba(255, 255, 255, 0.05);
      --g-badge-border: rgba(255, 255, 255, 0.10);
      --g-dim-opacity: 0.15;
      --g-dim-keys: 0.20;
    }}
    .theme-force-dark .canvas-bg,
    :root[data-theme="dark"] .model-relationship-diagram .canvas-bg,
    [data-theme="dark"] .model-relationship-diagram .canvas-bg {{ fill: #16181d !important; }}
    .theme-force-dark .card-bg,
    :root[data-theme="dark"] .model-relationship-diagram .card-bg,
    [data-theme="dark"] .model-relationship-diagram .card-bg {{ fill: #21252d !important; }}
    .theme-force-dark .card-border-focal,
    :root[data-theme="dark"] .model-relationship-diagram .card-border-focal,
    [data-theme="dark"] .model-relationship-diagram .card-border-focal {{ stroke: var(--g-focal-border) !important; stroke-width: 2.2px !important; }}
    .theme-force-dark .table-title,
    :root[data-theme="dark"] .model-relationship-diagram .table-title,
    [data-theme="dark"] .model-relationship-diagram .table-title {{ fill: #f0f3f6 !important; }}
    .theme-force-dark .column-name,
    :root[data-theme="dark"] .model-relationship-diagram .column-name,
    [data-theme="dark"] .model-relationship-diagram .column-name {{ fill: #d0d7de !important; }}
    .theme-force-dark .cardinality-badge,
    :root[data-theme="dark"] .model-relationship-diagram .cardinality-badge,
    [data-theme="dark"] .model-relationship-diagram .cardinality-badge {{ fill: var(--g-path-normal) !important; }}
    .theme-force-dark .legend-text,
    :root[data-theme="dark"] .model-relationship-diagram .legend-text,
    [data-theme="dark"] .model-relationship-diagram .legend-text {{ fill: #9da7b3 !important; }}
    .theme-force-dark .legend-card-bg,
    :root[data-theme="dark"] .model-relationship-diagram .legend-card-bg,
    [data-theme="dark"] .model-relationship-diagram .legend-card-bg {{ fill: #21252d !important; stroke: #343a46 !important; }}
    .theme-force-dark .row-separator,
    :root[data-theme="dark"] .model-relationship-diagram .row-separator,
    [data-theme="dark"] .model-relationship-diagram .row-separator {{ stroke: #272c35 !important; }}
    .theme-force-dark .rel-path,
    :root[data-theme="dark"] .model-relationship-diagram .rel-path,
    [data-theme="dark"] .model-relationship-diagram .rel-path {{ stroke: var(--g-path-normal) !important; }}
    .theme-force-dark .rel-path.rel-bidirectional,
    :root[data-theme="dark"] .model-relationship-diagram .rel-path.rel-bidirectional,
    [data-theme="dark"] .model-relationship-diagram .rel-path.rel-bidirectional {{ stroke: var(--g-path-normal) !important; }}
    .theme-force-dark .port-dot,
    :root[data-theme="dark"] .model-relationship-diagram .port-dot,
    [data-theme="dark"] .model-relationship-diagram .port-dot {{ fill: var(--g-path-normal) !important; stroke: #21252d !important; }}
    .theme-force-dark .port-dot.port-bidi,
    :root[data-theme="dark"] .model-relationship-diagram .port-dot.port-bidi,
    [data-theme="dark"] .model-relationship-diagram .port-dot.port-bidi {{ fill: var(--g-path-normal) !important; }}
    .theme-force-dark .bidi-badge-bg,
    :root[data-theme="dark"] .model-relationship-diagram .bidi-badge-bg,
    [data-theme="dark"] .model-relationship-diagram .bidi-badge-bg {{ fill: #21252d !important; stroke: var(--g-path-normal) !important; }}
    .theme-force-dark .bidi-badge-text,
    :root[data-theme="dark"] .model-relationship-diagram .bidi-badge-text,
    [data-theme="dark"] .model-relationship-diagram .bidi-badge-text {{ fill: var(--g-path-normal) !important; }}
{forced_dark_legend_rules}
{chr(10).join(force_dark_rules)}
    .theme-force-dark .col-badge-bg-pk,
    :root[data-theme="dark"] .model-relationship-diagram .col-badge-bg-pk,
    [data-theme="dark"] .model-relationship-diagram .col-badge-bg-pk {{ fill: transparent !important; stroke: #93c5fd !important; }}
    .theme-force-dark .col-badge-text-pk,
    :root[data-theme="dark"] .model-relationship-diagram .col-badge-text-pk,
    [data-theme="dark"] .model-relationship-diagram .col-badge-text-pk {{ fill: #93c5fd !important; }}
    .theme-force-dark .col-badge-bg-fk,
    :root[data-theme="dark"] .model-relationship-diagram .col-badge-bg-fk,
    [data-theme="dark"] .model-relationship-diagram .col-badge-bg-fk {{ fill: transparent !important; stroke: #cbd5e1 !important; }}
    .theme-force-dark .col-badge-text-fk,
    :root[data-theme="dark"] .model-relationship-diagram .col-badge-text-fk,
    [data-theme="dark"] .model-relationship-diagram .col-badge-text-fk {{ fill: #cbd5e1 !important; }}
    .theme-force-dark .col-badge-bg-calc,
    :root[data-theme="dark"] .model-relationship-diagram .col-badge-bg-calc,
    [data-theme="dark"] .model-relationship-diagram .col-badge-bg-calc {{ fill: transparent !important; stroke: #d8b4fe !important; }}
    .theme-force-dark .col-badge-text-calc,
    :root[data-theme="dark"] .model-relationship-diagram .col-badge-text-calc,
    [data-theme="dark"] .model-relationship-diagram .col-badge-text-calc {{ fill: #d8b4fe !important; }}

    /* Forced Light Mode Class & HTML data-theme integration */
    .theme-force-light,
    :root[data-theme="light"] .model-relationship-diagram,
    [data-theme="light"] .model-relationship-diagram {{
      --g-bg-canvas: #f8fafc;
      --g-card-bg: #ffffff;
      --g-card-border: #cbd5e1;
      --g-card-hdr: #f8fafc;
      --g-title: #0f172a;
      --g-text-col: #475569;
      --g-text-key: #334155;
      --g-key-active: #1e293b;
      --g-path-normal: #cbd5e1;
      --g-path-active: #475569;
      --g-path-bridge: #2c4a6f;
      --g-focal-border: #475569;
      --g-upstream-border: #94a3b8;
      --g-upstream-bg: rgba(148, 163, 184, 0.08);
      --g-upstream-stat-bg: #ffffff;
      --g-upstream-stat-border: #e2e8f0;
      --g-upstream-stat-num: #1e293b;
      --g-upstream-stat-label: #64748b;
      --g-upstream-pill-bg: #f1f5f9;
      --g-upstream-pill-text: #334155;
      --g-pk-fg: #0284c7;
      --g-pk-bg: rgba(2, 132, 199, 0.08);
      --g-fk-fg: #64748b;
      --g-fk-bg: rgba(100, 116, 139, 0.08);
      --g-msr-fg: #2c4a6f;
      --g-msr-bg: rgba(44, 74, 111, 0.08);
      --g-badge-bg: rgba(0, 0, 0, 0.03);
      --g-badge-border: rgba(0, 0, 0, 0.08);
      --g-dim-opacity: 0.14;
      --g-dim-keys: 0.20;
    }}
    .theme-force-light .canvas-bg,
    :root[data-theme="light"] .model-relationship-diagram .canvas-bg,
    [data-theme="light"] .model-relationship-diagram .canvas-bg {{ fill: #f8fafc !important; }}
    .theme-force-light .card-bg,
    :root[data-theme="light"] .model-relationship-diagram .card-bg,
    [data-theme="light"] .model-relationship-diagram .card-bg {{ fill: #ffffff !important; }}
    .theme-force-light .card-border-focal,
    :root[data-theme="light"] .model-relationship-diagram .card-border-focal,
    [data-theme="light"] .model-relationship-diagram .card-border-focal {{ stroke: var(--g-focal-border) !important; stroke-width: 2.2px !important; }}
    .theme-force-light .table-title,
    :root[data-theme="light"] .model-relationship-diagram .table-title,
    [data-theme="light"] .model-relationship-diagram .table-title {{ fill: #0f172a !important; }}
    .theme-force-light .column-name,
    :root[data-theme="light"] .model-relationship-diagram .column-name,
    [data-theme="light"] .model-relationship-diagram .column-name {{ fill: #334155 !important; }}
    .theme-force-light .cardinality-badge,
    :root[data-theme="light"] .model-relationship-diagram .cardinality-badge,
    [data-theme="light"] .model-relationship-diagram .cardinality-badge {{ fill: var(--g-path-normal) !important; }}
    .theme-force-light .legend-text,
    :root[data-theme="light"] .model-relationship-diagram .legend-text,
    [data-theme="light"] .model-relationship-diagram .legend-text {{ fill: #475569 !important; }}
    .theme-force-light .legend-card-bg,
    :root[data-theme="light"] .model-relationship-diagram .legend-card-bg,
    [data-theme="light"] .model-relationship-diagram .legend-card-bg {{ fill: #ffffff !important; stroke: #cbd5e1 !important; }}
    .theme-force-light .row-separator,
    :root[data-theme="light"] .model-relationship-diagram .row-separator,
    [data-theme="light"] .model-relationship-diagram .row-separator {{ stroke: #f1f5f9 !important; }}
    .theme-force-light .rel-path,
    :root[data-theme="light"] .model-relationship-diagram .rel-path,
    [data-theme="light"] .model-relationship-diagram .rel-path {{ stroke: var(--g-path-normal) !important; }}
    .theme-force-light .rel-path.rel-bidirectional,
    :root[data-theme="light"] .model-relationship-diagram .rel-path.rel-bidirectional,
    [data-theme="light"] .model-relationship-diagram .rel-path.rel-bidirectional {{ stroke: var(--g-path-normal) !important; }}
    .theme-force-light .port-dot,
    :root[data-theme="light"] .model-relationship-diagram .port-dot,
    [data-theme="light"] .model-relationship-diagram .port-dot {{ fill: var(--g-path-normal) !important; stroke: #ffffff !important; }}
    .theme-force-light .port-dot.port-bidi,
    :root[data-theme="light"] .model-relationship-diagram .port-dot.port-bidi,
    [data-theme="light"] .model-relationship-diagram .port-dot.port-bidi {{ fill: var(--g-path-normal) !important; }}
    .theme-force-light .bidi-badge-bg,
    :root[data-theme="light"] .model-relationship-diagram .bidi-badge-bg,
    [data-theme="light"] .model-relationship-diagram .bidi-badge-bg {{ fill: #ffffff !important; stroke: var(--g-path-normal) !important; }}
    .theme-force-light .bidi-badge-text,
    :root[data-theme="light"] .model-relationship-diagram .bidi-badge-text,
    [data-theme="light"] .model-relationship-diagram .bidi-badge-text {{ fill: var(--g-path-normal) !important; }}
{forced_light_legend_rules}
{chr(10).join(force_light_rules)}
    .theme-force-light .col-badge-bg-pk,
    :root[data-theme="light"] .model-relationship-diagram .col-badge-bg-pk,
    [data-theme="light"] .model-relationship-diagram .col-badge-bg-pk {{ fill: transparent !important; stroke: #1e3a8a !important; }}
    .theme-force-light .col-badge-text-pk,
    :root[data-theme="light"] .model-relationship-diagram .col-badge-text-pk,
    [data-theme="light"] .model-relationship-diagram .col-badge-text-pk {{ fill: #1e3a8a !important; }}
    .theme-force-light .col-badge-bg-fk,
    :root[data-theme="light"] .model-relationship-diagram .col-badge-bg-fk,
    [data-theme="light"] .model-relationship-diagram .col-badge-bg-fk {{ fill: transparent !important; stroke: #475569 !important; }}
    .theme-force-light .col-badge-text-fk,
    :root[data-theme="light"] .model-relationship-diagram .col-badge-text-fk,
    [data-theme="light"] .model-relationship-diagram .col-badge-text-fk {{ fill: #475569 !important; }}
    .theme-force-light .col-badge-bg-calc,
    :root[data-theme="light"] .model-relationship-diagram .col-badge-bg-calc,
    [data-theme="light"] .model-relationship-diagram .col-badge-bg-calc {{ fill: transparent !important; stroke: #6b21a8 !important; }}
    .theme-force-light .col-badge-text-calc,
    :root[data-theme="light"] .model-relationship-diagram .col-badge-text-calc,
    [data-theme="light"] .model-relationship-diagram .col-badge-text-calc {{ fill: #6b21a8 !important; }}

{dimming_rules_css}
{extra_css_block}
  </style>"""
