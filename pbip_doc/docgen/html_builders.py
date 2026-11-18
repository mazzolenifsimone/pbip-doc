"""
Modular HTML Document Builders for Tables, Measures, Master Index, and Report Visuals.
Renders executive C-level interactive HTML5 components with data dictionary filters,
tabs, copy buttons, KPI metric cards, and responsive layouts.
Follows the unified Section-Driven modular pattern (DocSection + assemble_html_document).
100% Vanilla Python standard library.
"""

from typing import Dict, Any, List, Optional, Tuple, Set, Callable
import html
import re

from .config import DocGenConfig
from .utils import (
    sanitize_filename,
    clean_project_name,
    get_model_upstream_summaries,
    normalize_data_source_entry,
    get_measure_lookup_map,
    get_measure_table_map,
    filter_local_scope_relationships,
    resolve_upstream_model_references,
    resolve_bound_reports_count,
)
from .html_layout import (
    get_relative_root,
    get_table_role_badge_class,
    get_table_role_short,
    get_expression_badge_info,
    resolve_html_theme_mode,
)
from .relationship_diagram import RelationshipSvgGenerator, normalize_role_key
from .section_engine import DocSection
from .layout_engine import render_document_html
from .table_doc import TableDocBuilder
from .measure_doc import MeasureDocBuilder
from .function_doc import FunctionDocBuilder
from .expression_doc import ExpressionDocBuilder
from .index_doc import IndexDocBuilder
from ..model_schema import resolve_expression_type_and_inline
from ..report_schema import PBIPReportModel, VisualDefinition, EvaluatedMetric
from ..dax_formatter import format_dax
from ..m_formatter import format_m


def escape(val: Any) -> str:
    """Safe HTML escaping for strings and values."""
    if val is None:
        return ""
    return html.escape(str(val))


def get_svg_galaxy(width: int = 14, height: int = 14, css_class: str = "") -> str:
    """Returns minimal elegant SVG icon for full galaxy multi-fact schema."""
    cls = f"svg-icon-galaxy {css_class}".strip() if css_class != "svg-icon-galaxy" else "svg-icon-galaxy"
    return (
        f'<svg class="{cls}" width="{width}" height="{height}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -2px;">'
        '<circle cx="12" cy="12" r="2.5"></circle>'
        '<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(-30 12 12)"></ellipse>'
        '<ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(30 12 12)"></ellipse>'
        '</svg>'
    )


def get_svg_star(width: int = 14, height: int = 14, css_class: str = "") -> str:
    """Returns minimal elegant SVG icon for star cluster schema."""
    cls = f"svg-icon-star {css_class}".strip() if css_class != "svg-icon-star" else "svg-icon-star"
    return (
        f'<svg class="{cls}" width="{width}" height="{height}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -2px;">'
        '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>'
        '</svg>'
    )


def get_svg_utility(width: int = 14, height: int = 14, css_class: str = "") -> str:
    """Returns minimal elegant SVG icon for utility tables & parameters."""
    cls = f"svg-icon-utility {css_class}".strip() if css_class != "svg-icon-utility" else "svg-icon-utility"
    return (
        f'<svg class="{cls}" width="{width}" height="{height}" viewBox="0 0 24 24" fill="none" '
        'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -2px;">'
        '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>'
        '<line x1="3" y1="9" x2="21" y2="9"></line>'
        '<line x1="9" y1="21" x2="9" y2="9"></line>'
        '</svg>'
    )


def get_svg_dataflow(width: int = 20, height: int = 20, css_class: str = "") -> str:
    """Returns minimal theme-reactive SVG icon for Power Query ETL / Dataflow."""
    cls = f"svg-icon-dataflow {css_class}".strip() if css_class != "svg-icon-dataflow" else "svg-icon-dataflow"
    return (
        f'<svg class="{cls}" width="{width}" height="{height}" viewBox="0 0 100 100" fill="none" '
        'stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="10" y="10" width="80" height="80" rx="8" fill="none" stroke="currentColor" stroke-width="7" />'
        '<path d="M 38 32 V 68 M 38 50 H 57 A 5 5 0 0 0 62 45 V 32" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />'
        '<circle cx="38" cy="32" r="8" fill="currentColor" stroke="none" />'
        '<circle cx="62" cy="32" r="8" fill="currentColor" stroke="none" />'
        '<circle cx="38" cy="68" r="8" fill="currentColor" stroke="none" />'
        '</svg>'
    )


def get_svg_datamodel(width: int = 20, height: int = 20, css_class: str = "") -> str:
    """Returns minimal theme-reactive SVG icon for Semantic Model."""
    cls = f"svg-icon-datamodel {css_class}".strip() if css_class != "svg-icon-datamodel" else "svg-icon-datamodel"
    return (
        f'<svg class="{cls}" width="{width}" height="{height}" viewBox="0 0 100 100" fill="none" '
        'stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="10" y="10" width="80" height="80" rx="8" fill="none" stroke="currentColor" stroke-width="7" />'
        '<circle cx="29" cy="39" r="7" fill="currentColor" stroke="none" />'
        '<circle cx="50" cy="39" r="7" fill="currentColor" stroke="none" />'
        '<circle cx="71" cy="39" r="7" fill="currentColor" stroke="none" />'
        '<circle cx="29" cy="61" r="7" fill="currentColor" stroke="none" />'
        '<circle cx="50" cy="61" r="7" fill="currentColor" stroke="none" />'
        '</svg>'
    )


def get_svg_report(width: int = 20, height: int = 20, css_class: str = "") -> str:
    """Returns minimal theme-reactive SVG icon for Report."""
    cls = f"svg-icon-report {css_class}".strip() if css_class != "svg-icon-report" else "svg-icon-report"
    return (
        f'<svg class="{cls}" width="{width}" height="{height}" viewBox="0 0 100 100" fill="none" '
        'stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="10" y="10" width="80" height="80" rx="8" fill="none" stroke="currentColor" stroke-width="7" />'
        '<path d="M 33 28 V 72 M 50 41 V 72 M 67 54 V 72" fill="none" stroke="currentColor" stroke-width="7" stroke-linecap="round" />'
        '</svg>'
    )


class HtmlIndexBuilder:
    """Builds the Master Catalog & Model Architecture dashboard (index.html)."""

    def __init__(
        self,
        data: Dict[str, Any],
        config: DocGenConfig,
        report_model: Optional[PBIPReportModel] = None,
        project_name: Optional[str] = None,
    ):
        self.data = data
        self.config = config
        self.report = report_model
        self.project_name = clean_project_name(
            project_name or config.project_name or data.get("project_name") or data.get("model_name") or "PBIP"
        )

    def build_content(self) -> str:
        """Assemble complete HTML content for Model Overview following section-driven modular layout."""
        tables = [t for t in self.data.get("tables", []) if self.config.is_table_published(t)]

        # Robust measure collection: from top-level measures or gathered from tables
        measures = [m for m in self.data.get("measures", []) if self.config.is_measure_published(m)]
        if not measures:
            for t in tables:
                for m in t.get("measures", []):
                    if not m.get("table"):
                        m["table"] = t.get("name")
                    if self.config.is_measure_published(m):
                        measures.append(m)

        total_cols = sum(len(t.get("columns", [])) for t in tables)

        expr_list = self.data.get("expressions") or self.data.get("shared_queries") or []
        funcs = self.data.get("functions", [])
        data_sources = self.data.get("data_sources_summary", [])
        relationships = filter_local_scope_relationships(
            self.data.get("relationships", []),
            self.data.get("tables", []),
            self.config,
        )

        fact_count = len([t for t in tables if (t.get("role") or "").upper() in ("FACT", "FACT_TABLE")])
        dim_count = len([t for t in tables if (t.get("role") or "").upper() in ("DIMENSION", "DIM", "DATE_DIMENSION", "DATE")])

        bound_reports_info = self.data.get("bound_reports_info") or []
        bound_reports_cnt = resolve_bound_reports_count(
            self.data,
            bound_reports_info=bound_reports_info,
            report_model=self.report,
            include_reports=self.config.include_reports,
        )

        header_html = f"""      <div class="page-header">
        <h1 class="page-title">
          <span>{escape(self.project_name)}</span>
          <span class="page-title-icon" title="Semantic Model">{get_svg_datamodel(width=22, height=22, css_class="header-icon-datamodel")}</span>
        </h1>
        <p class="page-subtitle">Centralized technical documentation, data dictionary, and metric dependency catalog.</p>
      </div>"""

        kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Tables</div>
          <div class="kpi-value">{len(tables)}</div>
          <div class="kpi-sub">{fact_count} Fact, {dim_count} Dimension</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Measures</div>
          <div class="kpi-value">{len(measures)}</div>
          <div class="kpi-sub">DAX Business Calculations</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Physical Columns</div>
          <div class="kpi-value">{total_cols}</div>
          <div class="kpi-sub">Data Model Attributes</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Bound Reports</div>
          <div class="kpi-value">{bound_reports_cnt}</div>
          <div class="kpi-sub">{'Consuming Reports' if bound_reports_cnt != 1 else 'Consuming Report'}</div>
        </div>
      </div>"""

        # Exact Section Sequence (ETL -> Model -> Report -> Details):
        # 1. Description
        # 2. Physical Data Sources (ETL)
        # 3. Power Query (ETL)
        # 4. Published Data Model Tables (Model)
        # 5. Star Schema and Diagram (Model)
        # 6. UDF Functions (Model)
        # 7. Measures (Model)
        # 8. Consuming Reports (Report)
        # 9. Details
        registry: Dict[str, Callable[[], Any]] = {
            "description": self._section_description,
            "physical_data_sources": lambda: self._section_physical_data_sources(data_sources),
            "power_query": lambda: self._section_power_query(expr_list),
            "published_tables": lambda: self._section_published_tables(tables, measures),
            "tables": lambda: self._section_published_tables(tables, measures),
            "star_schema_diagram": lambda: self._section_star_schema_diagram(tables, relationships),
            "relationship_table": lambda: self._section_relationship_table(tables, relationships),
            "relationships": lambda: self._section_relationship_table(tables, relationships),
            "udf_functions": lambda: self._section_udf_functions(funcs),
            "measures": lambda: self._section_measures(measures),
            "reports": self._section_consuming_reports,
            "details": lambda: self._section_details(tables),
            "badge_legend": self._section_badge_legend,
        }
        return render_document_html("model", header_html, kpis_html, registry, config=self.config)

    def _get_upstream_models(self) -> List[Dict[str, Any]]:
        return get_model_upstream_summaries(self.data, self.config)

    def _section_description(self) -> Optional[DocSection]:
        desc_html = (
            f'<p class="description-text">{escape(self.data["description"])}</p>'
            if self.data.get("description")
            else f'<p class="description-text">Master catalog and architectural reference for semantic model <strong>{escape(self.project_name)}</strong>, documenting tables, measures, relationships, and lineage.</p>'
        )

        content = f"""        <div class="content-card description-card">
          <h3 class="content-card-title">Description</h3>
          {desc_html}
        </div>"""
        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content=content,
        )

    def _section_physical_data_sources(self, data_sources: List[Dict[str, Any]]) -> Optional[DocSection]:
        source_rows = []
        up_models = self._get_upstream_models()
        up_names = {m.get("name", "") for m in up_models}
        expr_list = self.data.get("expressions") or self.data.get("shared_queries") or []
        known_expr_names = {
            (e.get("query_name") or e.get("name"))
            for e in expr_list
            if (e.get("query_name") or e.get("name"))
        }

        for raw_src in data_sources:
            src = normalize_data_source_entry(raw_src, self.data, self.config, up_names)
            stype = src.get("source_type") or "Connector"
            conn = src.get("connection_string") or "—"
            server = src.get("server") or "—"
            db = src.get("database") or "—"
            conn_display = f"<code>{escape(conn)}</code>"
            param_q = src.get("parameter_query_name")
            if param_q:
                p_val = src.get("parameter_value") or ""
                p_url = f"{self.config.clean_expressions_subdir}/{sanitize_filename(param_q)}{self.config.html_ext_suffix}"
                val_note = f' <span style="font-size: 0.85rem; color: var(--color-text-muted);">(<code>{escape(p_val)}</code>)</span>' if p_val else ""
                conn_display = f'<a href="{p_url}"><strong>{escape(conn)}</strong></a>{val_note}'
            elif conn in known_expr_names:
                p_url = f"{self.config.clean_expressions_subdir}/{sanitize_filename(conn)}{self.config.html_ext_suffix}"
                conn_display = f'<a href="{p_url}"><strong>{escape(conn)}</strong></a>'

            db_display = escape(db)
            if db and db != "—":
                target_model_slug = src.get("target_model_slug")
                is_remote_model = src.get("is_remote_model", False)
                if target_model_slug:
                    db_display = f'<a href="../../models/{target_model_slug}/index{self.config.html_ext_suffix}"><strong>{escape(db)}</strong></a>'
                elif is_remote_model:
                    db_display = f'<code>{escape(db)}</code> <span class="badge badge-dim">External Remote Model</span>'

            source_rows.append(f"""          <tr>
            <td><span class="badge badge-type">{escape(stype)}</span></td>
            <td>{conn_display}</td>
            <td>{escape(server)}</td>
            <td>{db_display}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Physical Data Sources ({len(data_sources)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Connector Type</th>
                  <th>Connection / Endpoint</th>
                  <th>Server</th>
                  <th>Database</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(source_rows) if source_rows else '<tr><td colspan="4"><em>No external physical data sources detected.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-sources",
            title=f"Physical Data Sources ({len(data_sources)})",
            nav_label=f"Data Sources ({len(data_sources)})",
            content=content,
        )

    def _section_published_tables(
        self, tables: List[Dict[str, Any]], measures: List[Dict[str, Any]]
    ) -> Optional[DocSection]:
        tables_rows = []
        for t in sorted(tables, key=lambda x: x.get("name", "")):
            t_name = t.get("name", "Table")
            clean_name = sanitize_filename(t_name)
            t_url = f"{self.config.clean_tables_subdir}/{clean_name}{self.config.html_ext_suffix}"
            role = t.get("role", "DIM")
            role_class = get_table_role_badge_class(role)
            role_label = get_table_role_short(role)

            cols_cnt = len(t.get("columns", []))
            meas_cnt = len([m for m in measures if m.get("table") == t_name])
            storage = t.get("storage_mode", "Import")

            inc = t.get("incremental_refresh_policy")
            has_inc_enabled = bool(inc and inc.get("is_enabled"))
            refresh_badge = "Incremental" if has_inc_enabled else "Full Refresh"
            refresh_badge_class = "badge-status-active" if has_inc_enabled else "badge-dim"

            is_pub = self.config.is_table_published(t)
            if is_pub:
                t_cell = f'<strong><a href="{t_url}">{escape(t_name)}</a></strong>'
            else:
                ext_url = self.config.resolve_external_table_url(t)
                if ext_url:
                    t_cell = f'<strong><a href="{ext_url}">{escape(t_name)}</a></strong> <span class="badge badge-dim">Remote Entity</span>'
                else:
                    t_cell = f'<strong><code>{escape(t_name)}</code></strong> <span class="badge badge-dim">Remote Entity</span>'

            tables_rows.append(f"""          <tr>
            <td>{t_cell}</td>
            <td><span class="badge {role_class}">{escape(role_label)}</span></td>
            <td><code>{escape(storage)}</code></td>
            <td>{cols_cnt}</td>
            <td>{meas_cnt}</td>
            <td><span class="badge {refresh_badge_class}">{refresh_badge}</span></td>
            <td>{escape(t.get('description', '') or '—')}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Published Data Model Tables ({len(tables)})</h3>
          <div class="table-responsive">
            <table class="data-table" id="index-tables-table">
              <thead>
                <tr>
                  <th>Table Name</th>
                  <th>Star Schema Role</th>
                  <th>Storage Mode</th>
                  <th>Columns</th>
                  <th>Measures</th>
                  <th>Refresh Policy</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(tables_rows) if tables_rows else '<tr><td colspan="7"><em>No tables cataloged.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-tables",
            title=f"Published Data Model Tables ({len(tables)})",
            nav_label=f"Tables ({len(tables)})",
            content=content,
        )

    @staticmethod
    def _build_starcluster_tab_rules(tab_id: str, panel_class: str) -> List[str]:
        """Generates theme-aware pure CSS radio tab rules for starcluster topology panels."""
        return [
            f'#{tab_id}:checked ~ .starcluster-nav-bar label[for="{tab_id}"] {{ background-color: var(--accent); color: #ffffff; }}',
            f'@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) #{tab_id}:checked ~ .starcluster-nav-bar label[for="{tab_id}"] {{ color: #0f172a; font-weight: 700; }} }}',
            f':root[data-theme="dark"] #{tab_id}:checked ~ .starcluster-nav-bar label[for="{tab_id}"], .theme-force-dark #{tab_id}:checked ~ .starcluster-nav-bar label[for="{tab_id}"] {{ color: #0f172a !important; font-weight: 700 !important; }}',
            f'#{tab_id}:checked ~ .starcluster-nav-bar label[for="{tab_id}"] .cluster-badge {{ background-color: rgba(0,0,0,0.15); color: inherit; border-color: transparent; }}',
            f'#{tab_id}:checked ~ .{panel_class} {{ display: block; }}',
        ]

    def _build_diagram_html(
        self, tables: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> str:
        diagram_html = ""
        if not self.config.include_relationship_diagrams:
            return ""

        try:
            theme_mode = resolve_html_theme_mode(self.config.html_theme)
            svg_gen = RelationshipSvgGenerator(self.data, config=self.config)
            fact_tables = svg_gen.get_fact_tables()
            util_tables = svg_gen.get_utility_tables()
            util_svg = svg_gen.generate_utility_svg(theme_mode=theme_mode, svg_id_prefix="util") if util_tables else ""

            if len(fact_tables) >= 2 or util_svg:
                # Multi-Tab Topology (Galaxy / Star / Utility) with pure CSS radio selectors (Zero-JS)
                tab_rules = self._build_starcluster_tab_rules("sc-tab-galaxy", "panel-galaxy")
                radio_inputs = [
                    '<input type="radio" name="starcluster-view" id="sc-tab-galaxy" class="starcluster-radio" checked>'
                ]
                primary_label = "Full Galaxy Schema" if len(fact_tables) >= 2 else "Star Schema Topology"
                active_star_tables_cnt = max(1, len(tables) - len(util_tables))
                nav_buttons = [
                    '<label for="sc-tab-galaxy" class="starcluster-nav-btn">'
                    f'<span class="icon">{get_svg_galaxy()}</span> {primary_label}'
                    f'<span class="cluster-badge">{active_star_tables_cnt} tables</span>'
                    '</label>'
                ]

                galaxy_svg = svg_gen.generate_model_svg(theme_mode=theme_mode, svg_id_prefix="galaxy")
                panels = [
                    f"""          <div class="starcluster-panel panel-galaxy">
            <div class="starcluster-meta-bar">
              <span class="starcluster-chip">{get_svg_galaxy(16, 16)} {primary_label}: <strong>{active_star_tables_cnt} tables</strong></span>
              <span class="starcluster-chip"><span class="badge badge-role-fact">FACT</span> <strong>{len(fact_tables)}</strong></span>
              <span class="starcluster-chip"><span class="badge badge-outline">RELATIONSHIPS</span> <strong>{len(relationships)}</strong></span>
            </div>
            <div class="diagram-wrapper" style="overflow-x: auto; padding: 0.5rem 0;">
              {galaxy_svg}
            </div>
          </div>"""
                ]

                if len(fact_tables) >= 2:
                    for f_name in fact_tables:
                        f_slug = sanitize_filename(f_name).lower().replace("_", "-")
                        cluster = svg_gen.extract_star_cluster(f_name)
                        c_dims = len(cluster.get("dimensions", []))
                        c_bridges = len(cluster.get("bridges", []))
                        c_outriggers = len(cluster.get("outriggers", []))
                        c_total = len(cluster.get("tables", set()))

                        tab_rules.extend(
                            self._build_starcluster_tab_rules(f"sc-tab-{f_slug}", f"panel-{f_slug}")
                        )
                        radio_inputs.append(
                            f'<input type="radio" name="starcluster-view" id="sc-tab-{f_slug}" class="starcluster-radio">'
                        )
                        nav_buttons.append(
                            f'<label for="sc-tab-{f_slug}" class="starcluster-nav-btn">'
                            f'<span class="icon">{get_svg_star()}</span> {escape(f_name)}'
                            f'<span class="cluster-badge">{c_total} tables</span>'
                            '</label>'
                        )

                        cluster_svg = svg_gen.generate_star_cluster_svg(
                            f_name, theme_mode=theme_mode, svg_id_prefix=f"sc-{f_slug}"
                        )
                        panels.append(
                            f"""          <div class="starcluster-panel panel-{f_slug}">
            <div class="starcluster-meta-bar">
              <span class="starcluster-chip">{get_svg_star(16, 16)} <span class="badge badge-role-fact">FACT</span> <strong>{escape(f_name)}</strong></span>
              <span class="starcluster-chip"><span class="badge badge-role-dim">DIM</span> <strong>{c_dims}</strong></span>
              <span class="starcluster-chip"><span class="badge badge-role-bridge">BRIDGE</span> <strong>{c_bridges}</strong></span>
              <span class="starcluster-chip"><span class="badge badge-role-snowflake">SNOWFLAKE</span> <strong>{c_outriggers}</strong></span>
              <span class="starcluster-chip"><span class="badge badge-outline">TOTAL</span> <strong>{c_total}</strong></span>
            </div>
            <div class="diagram-wrapper" style="overflow-x: auto; padding: 0.5rem 0;">
              {cluster_svg}
            </div>
          </div>"""
                        )

                if util_svg:
                    tab_rules.extend(
                        self._build_starcluster_tab_rules("sc-tab-utility", "panel-utility")
                    )
                    radio_inputs.append(
                        '<input type="radio" name="starcluster-view" id="sc-tab-utility" class="starcluster-radio">'
                    )
                    nav_buttons.append(
                        '<label for="sc-tab-utility" class="starcluster-nav-btn">'
                        f'<span class="icon">{get_svg_utility()}</span> Utility &amp; Parameters'
                        f'<span class="cluster-badge">{len(util_tables)} tables</span>'
                        '</label>'
                    )
                    panels.append(
                        f"""          <div class="starcluster-panel panel-utility">
            <div class="starcluster-meta-bar">
              <span class="starcluster-chip">{get_svg_utility(16, 16)} Utility Tables &amp; Parameters: <strong>{len(util_tables)} tables</strong></span>
            </div>
            <div class="diagram-wrapper" style="overflow-x: auto; padding: 0.5rem 0;">
              {util_svg}
            </div>
          </div>"""
                    )

                style_block = "<style>\n" + "\n".join(tab_rules) + "\n</style>"
                radios_block = "\n".join(radio_inputs)
                nav_block = '          <div class="starcluster-nav-bar">\n' + "\n".join(f"            {btn}" for btn in nav_buttons) + "\n          </div>"
                panels_block = "\n".join(panels)

                diagram_html = f"""
          <div style="margin-top: 0.5rem;">
            <h4 class="content-card-title">Star Schema Relationship Diagram</h4>
            <p style="color: var(--text-muted); margin-bottom: 1rem;">
              Select a view tab below to inspect dimensional topologies or isolated utility and parameter entities.
            </p>
            {style_block}
            <div class="starcluster-container">
{radios_block}
{nav_block}
{panels_block}
            </div>
          </div>"""
            else:
                svg_code = svg_gen.generate_model_svg(theme_mode=theme_mode)
                if svg_code:
                    diagram_html = f"""
          <div style="margin-top: 0.5rem;">
            <h4 class="content-card-title">Star Schema Relationship Diagram</h4>
            <p style="color: var(--text-muted); margin-bottom: 1rem;">
              Visual entity relationship topology and role partitions across the semantic model.
            </p>
            <div class="diagram-wrapper" style="overflow-x: auto; padding: 0.5rem 0;">
              {svg_code}
            </div>
          </div>"""
        except Exception:
            pass
        return diagram_html

    def _section_star_schema_diagram(
        self, tables: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> Optional[DocSection]:
        if not self.config.include_relationship_diagrams:
            return None
        diagram_html = self._build_diagram_html(tables, relationships)
        if not diagram_html:
            return None
        content = f"""        <div class="content-card">
          {diagram_html}
        </div>"""
        return DocSection(
            section_id="tab-architecture-diagram",
            title="Star Schema Diagram",
            nav_label="Diagram",
            content=content,
        )

    def _section_relationship_table(
        self, tables: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> Optional[DocSection]:
        relationships = filter_local_scope_relationships(
            relationships,
            self.data.get("tables", []) or tables,
            self.config,
        )
        rel_rows = []
        for r in relationships:
            from_str = f"{r.get('from_table')}[{r.get('from_column')}]"
            to_str = f"{r.get('to_table')}[{r.get('to_column')}]"
            card = r.get("cardinality") or "1:N"
            cross_dir = r.get("cross_filtering_behavior") or "Single"
            status = "Active" if r.get("is_active", True) else "Inactive"
            status_class = "badge-status-active" if status == "Active" else "badge-status-inactive"
            rel_rows.append(f"""          <tr>
            <td><code>{escape(from_str)}</code></td>
            <td><code>{escape(to_str)}</code></td>
            <td><span class="badge badge-dim">{escape(card)}</span></td>
            <td>{escape(cross_dir)}</td>
            <td><span class="badge {status_class}">{status}</span></td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Model Relationships ({len(relationships)})</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">
            The semantic model contains <strong>{len(tables)}</strong> tables interconnected via 
            <strong>{len(relationships)}</strong> logical relationships.
          </p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>From (Many Side)</th>
                  <th>To (One Side)</th>
                  <th>Cardinality</th>
                  <th>Cross-Filtering</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rel_rows) if rel_rows else '<tr><td colspan="5"><em>No active relationships defined in model.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-relationships",
            title=f"Relationships ({len(relationships)})",
            nav_label=f"Relationships ({len(relationships)})",
            content=content,
        )

    def _section_star_schema_and_diagram(
        self, tables: List[Dict[str, Any]], relationships: List[Dict[str, Any]]
    ) -> Optional[DocSection]:
        rel_rows = []
        for r in relationships:
            from_str = f"{r.get('from_table')}[{r.get('from_column')}]"
            to_str = f"{r.get('to_table')}[{r.get('to_column')}]"
            card = r.get("cardinality") or "1:N"
            cross_dir = r.get("cross_filtering_behavior") or "Single"
            status = "Active" if r.get("is_active", True) else "Inactive"
            status_class = "badge-status-active" if status == "Active" else "badge-status-inactive"
            rel_rows.append(f"""          <tr>
            <td><code>{escape(from_str)}</code></td>
            <td><code>{escape(to_str)}</code></td>
            <td><span class="badge badge-dim">{escape(card)}</span></td>
            <td>{escape(cross_dir)}</td>
            <td><span class="badge {status_class}">{status}</span></td>
          </tr>""")

        diagram_html = self._build_diagram_html(tables, relationships)

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Star Schema &amp; Topological Summary</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">
            The semantic model contains <strong>{len(tables)}</strong> tables interconnected via 
            <strong>{len(relationships)}</strong> logical relationships.
          </p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>From (Many Side)</th>
                  <th>To (One Side)</th>
                  <th>Cardinality</th>
                  <th>Cross-Filtering</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rel_rows) if rel_rows else '<tr><td colspan="5"><em>No active relationships defined in model.</em></td></tr>'}
              </tbody>
            </table>
          </div>{diagram_html}
        </div>"""
        return DocSection(
            section_id="tab-architecture",
            title="Star Schema and Diagram",
            nav_label="Star Schema & Diagram",
            content=content,
        )

    def _section_power_query(self, expr_list: List[Dict[str, Any]]) -> Optional[DocSection]:
        if not (self.config.include_expression_docs and (getattr(self.config, "include_expression_chapter", False) or getattr(self.config, "include_expression_sidebar_chapter", False)) and expr_list):
            return None

        param_list = [
            e for e in expr_list
            if e.get("expression_kind") == "parameter"
            or "IsParameterQuery" in e.get("full_m_expression", "")
            or "IsParameterQueryRequired" in e.get("full_m_expression", "")
        ]
        etl_list = [e for e in expr_list if e not in param_list]

        content_cards = []

        # 1. Dedicated Block: Power Query Parameters
        if param_list:
            param_rows = []
            for p in sorted(param_list, key=lambda x: x.get("query_name", "")):
                p_name = p.get("query_name") or "Parameter"
                clean_p = sanitize_filename(p_name)
                p_url = f"{self.config.clean_expressions_subdir}/{clean_p}{self.config.html_ext_suffix}"
                p_val = p.get("parameter_value") or ""
                p_type = p.get("parameter_type") or "Any"
                p_req = "Yes" if p.get("parameter_required") else "No"
                req_badge = f'<span class="badge badge-accent">{p_req}</span>' if p_req == "Yes" else f'<span class="badge badge-dim">{p_req}</span>'

                # Downstream impact
                impacted = []
                for dt in p.get("downstream_tables", []):
                    clean_dt = sanitize_filename(dt)
                    if self.config.include_models:
                        impacted.append(f'<a href="{self.config.clean_tables_subdir}/{clean_dt}{self.config.html_ext_suffix}"><code>{escape(dt)}</code></a>')
                    else:
                        impacted.append(f'<code>{escape(dt)}</code>')
                for dq in p.get("downstream_queries", []):
                    clean_dq = sanitize_filename(dq)
                    if self.config.include_dataflow:
                        impacted.append(f'<a href="{self.config.clean_expressions_subdir}/{clean_dq}{self.config.html_ext_suffix}"><code>{escape(dq)}</code></a>')
                    else:
                        impacted.append(f'<code>{escape(dq)}</code>')
                impact_str = ", ".join(impacted) or "<em>None (Unused)</em>"

                val_display = f"<code>{escape(p_val)}</code>" if p_val else "<em>(Dynamic / Secret)</em>"

                param_rows.append(f"""          <tr>
            <td><strong><a href="{p_url}">{escape(p_name)}</a></strong></td>
            <td>{val_display}</td>
            <td><span class="badge badge-dim">{escape(p_type)}</span></td>
            <td>{req_badge}</td>
            <td>{impact_str}</td>
          </tr>""")

            content_cards.append(f"""        <div class="content-card" style="margin-bottom: 1.5rem;">
          <h3 class="content-card-title">Query Parameters M ({len(param_list)})</h3>
          <p style="color: var(--color-text-muted); margin-bottom: 1rem;">
            Configurable environment and deployment parameters governing connections, endpoints, and query filters.
          </p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Parameter Name</th>
                  <th>Current Value</th>
                  <th>Data Type</th>
                  <th>Required</th>
                  <th>Consuming Queries &amp; Tables</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(param_rows)}
              </tbody>
            </table>
          </div>
        </div>""")

        # 2. Block: Shared ETL & Staging Queries
        if etl_list:
            etl_rows = []
            for e in sorted(etl_list, key=lambda x: x.get("query_name", "")):
                q_name = e.get("query_name") or "Expression"
                clean_q = sanitize_filename(q_name)
                e_url = f"{self.config.clean_expressions_subdir}/{clean_q}{self.config.html_ext_suffix}"
                target_t = e.get("target_table") or "—"
                steps_cnt = len(e.get("steps", []))

                b_cls, b_lbl, _ = get_expression_badge_info(e)
                role_badge = f'<span class="badge {b_cls}">{escape(b_lbl)}</span>'

                deps_links = []
                for dep in e.get("direct_dependencies", []):
                    clean_d = sanitize_filename(dep)
                    deps_links.append(f'<a href="{self.config.clean_expressions_subdir}/{clean_d}{self.config.html_ext_suffix}"><code>{escape(dep)}</code></a>')
                deps_str = ", ".join(deps_links) or "—"

                etl_rows.append(f"""          <tr>
            <td><strong><a href="{e_url}">{escape(q_name)}</a></strong></td>
            <td>{role_badge}</td>
            <td>{escape(target_t)}</td>
            <td>{deps_str}</td>
            <td>{steps_cnt}</td>
          </tr>""")

            content_cards.append(f"""        <div class="content-card">
          <h3 class="content-card-title">Dataflow Queries ({len(etl_list)})</h3>
          <p style="color: var(--color-text-muted); margin-bottom: 1rem;">
            Power Query M data transformations, custom functions, and staging pipelines.
          </p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Query Name</th>
                  <th>Pipeline Role</th>
                  <th>Target Table</th>
                  <th>Direct Dependencies</th>
                  <th>Steps</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(etl_rows)}
              </tbody>
            </table>
          </div>
        </div>""")

        total_cnt = len(expr_list)
        return DocSection(
            section_id="tab-expressions",
            title=f"Dataflow ({total_cnt})",
            nav_label=f"Dataflow ({total_cnt})",
            content="\n".join(content_cards),
        )

    def _section_udf_functions(self, funcs: List[Dict[str, Any]]) -> Optional[DocSection]:
        if not funcs:
            return None

        udf_cards = []
        for fn in sorted(funcs, key=lambda x: x.get("name", "")):
            f_name = fn.get("name") or "Function"
            clean_f = sanitize_filename(f_name)
            f_url = f"{self.config.clean_functions_subdir}/{clean_f}{self.config.html_ext_suffix}"
            ret_type = fn.get("return_type") or "Variant"
            params = fn.get("parameters", [])
            desc = (fn.get("description") or "").strip()

            sig_parts = []
            param_rows = []
            for p in params:
                p_name = p.get("name", "param")
                p_type = p.get("data_type", "Variant")
                p_opt = p.get("is_optional", False)
                p_desc = p.get("description", "") or "—"
                opt_str = "Optional" if p_opt else "Required"
                sig_parts.append(f"{p_name}: {p_type}" + ("?" if p_opt else ""))
                param_rows.append(f"""                <tr>
                  <td><code>{escape(p_name)}</code></td>
                  <td><code>{escape(p_type)}</code></td>
                  <td><span class="badge badge-dim">{opt_str}</span></td>
                  <td>{escape(p_desc)}</td>
                </tr>""")

            sig_str = f"({', '.join(sig_parts)})"
            body = fn.get("expression") or fn.get("body") or ""
            formatted_dax = format_dax(
                body,
                name=f_name,
                entity_type="function",
                parameters_signature=sig_str,
            ) if body else "-- No DAX body provided"

            params_html = f"""            <div style="margin-top: 0.75rem; margin-bottom: 0.75rem;">
              <div class="spec-group-title">Parameters ({len(params)})</div>
              <div class="table-responsive">
                <table class="data-table">
                  <thead>
                    <tr>
                      <th>Parameter Name</th>
                      <th>Data Type</th>
                      <th>Requirement</th>
                      <th>Description</th>
                    </tr>
                  </thead>
                  <tbody>
{chr(10).join(param_rows)}
                  </tbody>
                </table>
              </div>
            </div>""" if param_rows else '<p style="color: var(--text-muted); font-size: 0.85rem; margin: 0.5rem 0;"><em>Parameters: No input parameters required.</em></p>'

            udf_cards.append(f"""          <div class="calc-col-card" style="margin-bottom: 1.25rem;">
            <div class="calc-col-header">
              <div class="calc-col-title-group">
                <span class="calc-col-name"><a href="{f_url}"><strong><code>{escape(f_name)}{escape(sig_str)}</code></strong></a></span>
                <span class="badge badge-type">Returns: {escape(ret_type)}</span>
              </div>
            </div>
            {f'<p class="calc-col-desc">{escape(desc)}</p>' if desc else '<p class="calc-col-desc" style="color: var(--text-muted);"><em>No description provided.</em></p>'}
{params_html}
            <div class="code-container">
              <div class="code-header">
                <span>DAX Function Definition</span>
              </div>
              <pre><code>{escape(formatted_dax)}</code></pre>
            </div>
          </div>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">UDF Functions ({len(funcs)})</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">
            User-Defined DAX Functions (UDFs) encapsulating reusable business logic across the semantic model.
          </p>
{chr(10).join(udf_cards)}
        </div>"""
        return DocSection(
            section_id="tab-functions",
            title=f"UDF Functions ({len(funcs)})",
            nav_label=f"UDF Functions ({len(funcs)})",
            content=content,
        )

    def _section_measures(self, measures: List[Dict[str, Any]]) -> Optional[DocSection]:
        measures_rows = []
        for m in sorted(measures, key=lambda x: (x.get("table", ""), x.get("name", ""))):
            m_name = m.get("name", "Measure")
            m_tbl = m.get("table", "Model")
            clean_tbl = sanitize_filename(m_tbl)
            clean_m = sanitize_filename(m_name)
            m_url = f"{self.config.clean_measures_subdir}/{clean_tbl}/{clean_m}{self.config.html_ext_suffix}"
            depth = m.get("calculation_depth", 0)

            is_inh_m = m.get("is_inherited") or m.get("is_external_measure")
            if is_inh_m:
                ext_m_url = self.config.resolve_external_measure_url(m, self.data.get("tables", []))
                if ext_m_url:
                    m_cell = f'<strong><a href="{ext_m_url}">[{escape(m_name)}]</a></strong> <span class="badge badge-dim">Remote Measure</span>'
                else:
                    m_cell = f'<strong>[{escape(m_name)}]</strong> <span class="badge badge-dim">Remote Measure</span>'
            else:
                m_cell = f'<strong><a href="{m_url}">[{escape(m_name)}]</a></strong>'

            target_tbl = next((t for t in self.data.get("tables", []) if t.get("name") == m_tbl), None)
            tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
            if tbl_pub:
                tbl_cell = f'<a href="{self.config.clean_tables_subdir}/{clean_tbl}{self.config.html_ext_suffix}">{escape(m_tbl)}</a>'
            else:
                ext_tbl_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                if ext_tbl_url:
                    tbl_cell = f'<a href="{ext_tbl_url}">{escape(m_tbl)}</a> <span class="badge badge-dim">Remote Entity</span>'
                else:
                    tbl_cell = f'<code>{escape(m_tbl)}</code> <span class="badge badge-dim">Remote Entity</span>'

            measures_rows.append(f"""          <tr>
            <td>{m_cell}</td>
            <td>{tbl_cell}</td>
            <td><span class="badge badge-dim">Depth {depth}</span></td>
            <td>{escape(m.get('display_folder', '') or '—')}</td>
            <td><code>{escape(m.get('format_string', '') or '—')}</code></td>
            <td>{escape(m.get('description', '') or '—')}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Measures ({len(measures)})</h3>
          <div class="table-responsive">
            <table class="data-table" id="index-measures-table">
              <thead>
                <tr>
                  <th>Measure Name</th>
                  <th>Host Table</th>
                  <th>Calculation Depth</th>
                  <th>Display Folder</th>
                  <th>Format String</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(measures_rows) if measures_rows else '<tr><td colspan="6"><em>No measures cataloged.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-measures",
            title=f"Measures ({len(measures)})",
            nav_label=f"Measures ({len(measures)})",
            content=content,
        )

    def _section_consuming_reports(self) -> Optional[DocSection]:
        if not self.config.include_reports:
            return None
        bound_reports_info = self.data.get("bound_reports_info") or []

        if bound_reports_info:
            rep_rows = []
            for rep in bound_reports_info:
                r_name = rep.get("name", "Report")
                r_fmt = rep.get("format", "PBIR")
                r_pages = rep.get("pages_count", 0)
                r_url = rep.get("html_url") or f"../../reports/{sanitize_filename(r_name)}/index{self.config.html_ext_suffix}"
                is_direct = rep.get("is_direct", True)
                via = rep.get("via_model")
                if is_direct:
                    binding_badge = '<span class="badge badge-status-active">Direct</span>'
                else:
                    binding_badge = f'<span class="badge badge-dim" title="Connected via {escape(via)}">via {escape(via)}</span>' if via else '<span class="badge badge-dim">Indirect</span>'
                rep_rows.append(f"""          <tr>
            <td><strong><a href="{r_url}">{escape(r_name)}</a></strong></td>
            <td><span class="badge badge-type">{escape(r_fmt)}</span></td>
            <td>{binding_badge}</td>
            <td>{r_pages} pages</td>
          </tr>""")

            content = f"""        <div class="content-card">
          <h3 class="content-card-title">Consuming Reports ({len(bound_reports_info)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Report Name</th>
                  <th>Format</th>
                  <th>Binding</th>
                  <th>Pages</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rep_rows)}
              </tbody>
            </table>
          </div>
        </div>"""
            return DocSection(
                section_id="tab-reports",
                title=f"Consuming Reports ({len(bound_reports_info)})",
                nav_label=f"Consuming Reports ({len(bound_reports_info)})",
                content=content,
            )

        if self.report and self.report.pages:
            pages_rows = []
            for p in self.report.pages:
                clean_p = sanitize_filename(p.display_name)
                p_url = f"{self.config.clean_visuals_subdir}/{clean_p}{self.config.html_ext_suffix}"
                v_cnt = len([v for v in p.visuals if v.is_dynamic])
                pages_rows.append(f"""          <tr>
            <td><strong><a href="{p_url}">{escape(p.display_name)}</a></strong></td>
            <td>#{p.page_number}</td>
            <td><code>{p.width}x{p.height}</code></td>
            <td>{v_cnt} dynamic visuals</td>
            <td><span class="badge badge-dim">{'Hidden' if p.is_hidden else 'Visible'}</span></td>
          </tr>""")

            content = f"""        <div class="content-card">
          <h3 class="content-card-title">Consuming Reports & Interactive Pages ({len(pages_rows)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Report Page</th>
                  <th>Order</th>
                  <th>Dimensions</th>
                  <th>Visuals</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(pages_rows)}
              </tbody>
            </table>
          </div>
        </div>"""
            return DocSection(
                section_id="tab-reports",
                title=f"Consuming Reports ({len(pages_rows)})",
                nav_label=f"Consuming Reports ({len(pages_rows)})",
                content=content,
            )

        content = """        <div class="content-card">
          <h3 class="content-card-title">Consuming Reports (0)</h3>
          <p style="color: var(--text-muted);"><em>No consuming reports bound to this semantic model in the scanned workspace.</em></p>
        </div>"""
        return DocSection(
            section_id="tab-reports",
            title="Consuming Reports (0)",
            nav_label="Consuming Reports (0)",
            content=content,
        )

    def _section_details(self, tables: List[Dict[str, Any]]) -> Optional[DocSection]:
        source_format = self.data.get("source_format", "TMDL")
        compat_level = self.data.get("compatibility_level", 1600)
        culture = self.data.get("culture", "en-US")
        calc_tables = [t for t in tables if t.get("is_calculated")]
        inherited_tables = [t for t in tables if t.get("is_inherited")]
        excluded_cnt = self.data.get("excluded_tables_count", 0)

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Details</h3>
          <table class="data-table">
            <tbody>
              <tr><td><strong>Source Format</strong></td><td><code>{escape(source_format)}</code></td></tr>
              <tr><td><strong>Compatibility Level</strong></td><td><code>{escape(compat_level)}</code></td></tr>
              <tr><td><strong>Culture</strong></td><td><code>{escape(culture)}</code></td></tr>
              <tr><td><strong>Calculated Tables (DAX)</strong></td><td>{len(calc_tables)}</td></tr>
              <tr><td><strong>Inherited Tables (Composite/DirectQuery)</strong></td><td>{len(inherited_tables)}</td></tr>
              <tr><td><strong>Excluded Technical/AutoDate Tables</strong></td><td>{excluded_cnt}</td></tr>
            </tbody>
          </table>
        </div>"""
        return DocSection(
            section_id="tab-details",
            title="Details",
            nav_label="Details",
            content=content,
        )

    def _section_badge_legend(self) -> DocSection:
        content = """        <div class="content-card">
          <h3 class="content-card-title">Semantic Model Badges &amp; Tags Legend</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">Reference guide explaining model architecture tiers, relationship states, and dataset indicators.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Tag / Badge</th>
                  <th style="width: 180px;">Category</th>
                  <th>Functional Meaning &amp; Architectural Role</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge badge-role-fact">Fact</span></td>
                  <td>Star Schema Tier</td>
                  <td>Central business entity containing quantitative metrics, transactional events, or numeric performance measures.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-dim">Dim</span></td>
                  <td>Star Schema Tier</td>
                  <td>Conformed analytical dimension providing contextual slicing, filtering attributes, and business hierarchies.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-snowflake">Snow</span></td>
                  <td>Star Schema Tier</td>
                  <td>Snowflaked secondary dimension (outrigger) extending another dimension via normalized reference keys.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-bridge">Bridge</span></td>
                  <td>Star Schema Tier</td>
                  <td>Intermediate junction table resolving Many-to-Many relationships or complex multi-parent hierarchies.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-date">Date</span></td>
                  <td>Star Schema Tier</td>
                  <td>Dedicated calendar / date dimension supporting time intelligence calculations and period-over-period comparisons.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-calcgroup">CalcGroup</span></td>
                  <td>Star Schema Tier</td>
                  <td>Calculation Group table dynamically altering measure evaluation context through DAX calculation items.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-utility">Utility</span></td>
                  <td>Star Schema Tier</td>
                  <td>Disconnected parameter, DAX calculation helper, or configuration table with no active data model relationships.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-legend",
            title="Tags &amp; Badges Legend",
            nav_label="Legend",
            content=content,
        )


class HtmlTableBuilder:
    """Builds individual Table documentation page (tables/<TableName>.html)."""

    def __init__(
        self,
        table_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.doc_builder = TableDocBuilder(table_data, full_model, config, project_name=project_name)
        self.table = self.doc_builder.table
        self.model = self.doc_builder.model
        self.config = self.doc_builder.config
        self.project_name = self.doc_builder.project_name
        self.name = self.doc_builder.name
        self.role = self.doc_builder.role
        self.classification = self.doc_builder.classification
        self.columns = self.doc_builder.columns
        self.measures = self.doc_builder.measures
        self.snowflake_paths = self.doc_builder.snowflake_paths
        self.direct_rels = self.doc_builder.direct_rels

    def build_content(self) -> str:
        """Assemble complete HTML content for a Table following section-driven modular layout."""
        rel_root = ".."
        role_class = get_table_role_badge_class(self.role)
        role_label = get_table_role_short(self.role)

        # Pre-compute column classifications
        calc_cols: List[Dict[str, Any]] = []
        pq_cols: List[Dict[str, Any]] = []
        col_rows: List[str] = []
        for col in self.columns:
            c_name = col.get("name", "col")
            c_type = col.get("data_type", "String")
            c_fmt = col.get("format_string") or "—"
            c_desc = col.get("description") or "—"
            origin = col.get("origin")

            is_calc = col.get("is_calculated") or bool(col.get("expression")) or origin == "dax"
            is_pq = origin == "power_query" or bool(col.get("m_expression"))

            if is_calc:
                calc_cols.append(col)
                slug = sanitize_filename(c_name)
                origin_badge = f'<label for="page-tab-tab-calc-cols" class="badge badge-calc" title="Click to view DAX formula in Calculated Columns tab">DAX Calc</label>'
            elif is_pq:
                pq_cols.append(col)
                slug = sanitize_filename(c_name)
                op_lbl = col.get("m_operation") or "Power Query"
                clean_tbl = sanitize_filename(self.name)
                expr_sub = self.config.clean_expressions_subdir
                etl_target = f"../{expr_sub}/{clean_tbl}{self.config.html_ext_suffix}"
                origin_badge = f'<a href="{etl_target}" class="badge badge-pq" title="Open dedicated ETL documentation for {escape(self.name)} ({escape(op_lbl)})">ETL Doc ➔</a>'
            elif col.get("is_key"):
                origin_badge = '<span class="badge badge-key">Key</span> <span class="badge badge-imported">Source</span>'
            else:
                origin_badge = '<span class="badge badge-imported">Source</span>'

            col_rows.append(f"""          <tr>
            <td><strong>`{escape(c_name)}`</strong></td>
            <td><span class="badge badge-type">{escape(c_type)}</span></td>
            <td>{origin_badge}</td>
            <td><code>{escape(c_fmt)}</code></td>
            <td>{escape(c_desc)}</td>
          </tr>""")

        direct_rels = self.direct_rels

        source_count = len(self.columns) - len(calc_cols) - len(pq_cols)
        if pq_cols:
            col_kpi_sub = f"{len(calc_cols)} DAX, {len(pq_cols)} ETL, {source_count} Source"
        else:
            col_kpi_sub = f"{len(calc_cols)} Calculated, {len(self.columns) - len(calc_cols)} Imported"

        header_html = f"""      <div class="page-header">
        <h1 class="page-title">
          <span>Table: {escape(self.name)}</span>
          <span class="badge {role_class}">{escape(role_label)}</span>
        </h1>
        <p class="page-subtitle">Table schema definition, column data dictionary, and relational dependencies.</p>
      </div>"""

        kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Model</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><a href="{rel_root}/index{self.config.html_ext_suffix}">{escape(self.project_name)}</a></div>
          <div class="kpi-sub">Parent Semantic Model</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Role</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><span class="badge {role_class}">{escape(role_label)}</span></div>
          <div class="kpi-sub">Star Schema Role</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Columns</div>
          <div class="kpi-value">{len(self.columns)}</div>
          <div class="kpi-sub">{col_kpi_sub}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Host Measures</div>
          <div class="kpi-value">{len(self.measures)}</div>
          <div class="kpi-sub">Formulas Hosted</div>
        </div>
      </div>"""

        # Exact Table Section Sequence:
        # 1. Description
        # 2. Data Source Summary
        # 3. Data Dictionary
        # 4. Relations
        # 5. Calculated Columns
        # 6. Measures
        # 7. Power Query Lineage
        # 8. Power Query Calculated and Transformed Columns
        # 9. Details
        # 10. Semantic Context for AI & RAG
        registry: Dict[str, Callable[[], Any]] = {
            "description": self._section_description,
            "data_source_summary": self._section_data_source_summary,
            "upstream_pipeline": self._section_upstream_pipeline_dependencies,
            "data_dictionary": lambda: self._section_data_dictionary(col_rows),
            "relationship_diagram": lambda: self._section_relationship_diagram(direct_rels),
            "relationship_table": lambda: self._section_relationship_table(direct_rels),
            "relationships": lambda: self._section_relationship_table(direct_rels),
            "calculated_columns": lambda: self._section_calculated_columns(calc_cols),
            "measures": lambda: self._section_measures(rel_root),
            "power_query_lineage": self._section_power_query_lineage,
            "dax_formula": self._section_dax_formula,
            "referenced_columns": self._section_referenced_columns,
            "rag": self._section_rag_context,
            "pq_columns": lambda: self._section_power_query_columns(pq_cols),
            "details": lambda: self._section_details(role_class),
            "rag_context": self._section_rag_context,
            "badge_legend": self._section_badge_legend,
        }
        return render_document_html("table", header_html, kpis_html, registry, config=self.config)

    def _section_description(self) -> Optional[DocSection]:
        desc_html = (
            f'<p class="description-text">{escape(self.table["description"])}</p>'
            if self.table.get("description")
            else '<p class="description-text description-empty"><em>No description provided in the data model.</em></p>'
        )
        extra_notes = []
        if self.table.get("is_inherited"):
            src = self.table.get("source_schema") or "Remote Semantic Model / DirectQuery"
            extra_notes.append(f'<p style="margin-top: 0.75rem; color: var(--text-muted);"><strong>Inherited Entity</strong>: Sourced via DirectQuery/Composite connection from <code>{escape(src)}</code>.</p>')
        if self.table.get("is_calculated"):
            extra_notes.append('<p style="margin-top: 0.75rem; color: var(--text-muted);"><strong>DAX Calculated Table</strong>: Computed in-memory via a DAX table expression.</p>')

        content = f"""        <div class="content-card description-card">
          <h3 class="content-card-title">Description</h3>
          {desc_html}
          {chr(10).join(extra_notes)}
        </div>"""
        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content=content,
        )

    def _section_dax_formula(self) -> Optional[DocSection]:
        is_calc_group = (
            self.table.get("source_type") == "CalculationGroup"
            or (self.table.get("role") or "").upper() in ("CALCULATION_GROUP", "CALC_GROUP")
        )
        if is_calc_group:
            calc_items = self.table.get("calculation_items") or []
            item_rows = []
            for ci in calc_items:
                ci_name = ci.get("name", "Item") if isinstance(ci, dict) else str(ci)
                item_rows.append(f'<li><strong><code>{escape(ci_name)}</code></strong></li>')
            items_html = f'<ul class="spec-list" style="margin-top: 0.5rem;">{chr(10).join(item_rows)}</ul>' if item_rows else '<p style="color: var(--text-muted);"><em>No calculation items defined.</em></p>'
            content = f"""        <div class="content-card">
          <h3 class="content-card-title">Calculation Group &amp; Lineage</h3>
          <p class="description-text">This entity is a Calculation Group defined within the semantic model, applying dynamic DAX calculation items to evaluate measures across the model rather than ingesting external data via Power Query.</p>
          <div style="margin-top: 1rem;">
            <div class="spec-group-title">Calculation Items ({len(calc_items)})</div>
            {items_html}
          </div>
        </div>"""
            return DocSection(
                section_id="tab-cg",
                title="Calculation Group &amp; Lineage",
                nav_label="Calculation Group",
                content=content,
            )

        is_calc = (
            self.table.get("source_type") == "CalculatedTable"
            or bool(self.table.get("is_calculated"))
            or normalize_role_key(self.table.get("role")) == "CALCULATED_TABLE"
        )
        if not is_calc:
            return None
        if not getattr(self.config, "include_table_dax_formula", True):
            return None

        calc_expr = self.table.get("expression")
        if calc_expr:
            formatted_calc_expr = format_dax(
                calc_expr,
                name=self.name,
                entity_type="calculated_table",
            )
        else:
            formatted_calc_expr = "-- DAX calculation formula defined at partition level"

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">DAX Table Expression</h3>
          <p class="description-text">This table is dynamically computed in-memory within the semantic model using DAX, rather than loaded from an external Power Query data source.</p>
          <div class="code-container" style="margin-top: 1rem;">
            <div class="code-header">
              <span>DAX Formula</span>
            </div>
            <pre><code id="table-dax-code">{escape(formatted_calc_expr)}</code></pre>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-dax",
            title="DAX Table Expression",
            nav_label="DAX Formula",
            content=content,
        )

    def _format_ref_table_html(self, t_name: str, t_obj: Optional[Dict[str, Any]]) -> str:
        if not t_name:
            return '<em>Current Table</em>'
        if t_obj is not None and self.config.is_table_published(t_obj):
            clean_t = sanitize_filename(t_name)
            t_url = f"{clean_t}{self.config.html_ext_suffix}"
            return f'<a href="{t_url}">{escape(t_name)}</a>'
        ext_url = self.config.resolve_external_table_url(t_obj) if t_obj else None
        if ext_url:
            return f'<a href="{ext_url}">{escape(t_name)}</a> <span class="badge badge-dim">External</span>'
        return escape(t_name)

    def _section_referenced_columns(self) -> Optional[DocSection]:
        is_calc = (
            self.table.get("source_type") == "CalculatedTable"
            or bool(self.table.get("is_calculated"))
            or normalize_role_key(self.table.get("role")) == "CALCULATED_TABLE"
        )
        if not is_calc:
            return None
        if not getattr(self.config, "include_table_referenced_columns", True):
            return None

        refs = resolve_upstream_model_references(self.table, self.model)
        standalone_tables = refs["standalone_tables"]
        ref_cols = refs["columns"]
        ref_measures = refs["measures"]

        if not (standalone_tables or ref_cols or ref_measures):
            return None

        ref_rows = []
        for t_entry in standalone_tables:
            t_cell = self._format_ref_table_html(t_entry["name"], t_entry["table_obj"])
            ref_rows.append(f"""          <tr>
            <td><span class="badge badge-type">Table</span></td>
            <td>{t_cell}</td>
            <td>—</td>
          </tr>""")

        for c_entry in ref_cols:
            t_cell = self._format_ref_table_html(c_entry["table"], c_entry["table_obj"])
            c_name = c_entry["column"]
            ref_rows.append(f"""          <tr>
            <td><span class="badge badge-type">Column</span></td>
            <td>{t_cell}</td>
            <td><code>[{escape(c_name)}]</code></td>
          </tr>""")

        meas_sub = self.config.clean_measures_subdir
        model_tables = self.model.get("tables", []) or []
        for m_entry in ref_measures:
            m_name = m_entry["name"]
            m_home_tbl = m_entry["home_table"]
            m_obj = m_entry["measure_obj"]
            home_tbl_obj = m_entry["home_table_obj"]

            if m_obj is not None and m_home_tbl and self.config.is_measure_published(m_obj):
                clean_home_tbl = sanitize_filename(m_home_tbl)
                clean_m = sanitize_filename(m_name)
                m_url = (
                    f"../{meas_sub}/{clean_home_tbl}/{clean_m}{self.config.html_ext_suffix}"
                    if meas_sub
                    else f"../{clean_home_tbl}/{clean_m}{self.config.html_ext_suffix}"
                )
                m_cell = f'<a href="{m_url}">{escape(m_name)}</a>'
                scope_cell = self._format_ref_table_html(m_home_tbl, home_tbl_obj)
            else:
                ext_m_url = self.config.resolve_external_measure_url(m_obj, model_tables) if m_obj else None
                if ext_m_url:
                    m_cell = f'<a href="{ext_m_url}">{escape(m_name)}</a> <span class="badge badge-dim">External</span>'
                else:
                    m_cell = escape(m_name)
                scope_cell = self._format_ref_table_html(m_home_tbl, home_tbl_obj) if m_home_tbl else "—"

            ref_rows.append(f"""          <tr>
            <td><span class="badge badge-type">Measure</span></td>
            <td>{m_cell}</td>
            <td>{scope_cell}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Upstream Model References</h3>
          <p class="description-text">The DAX expression defining this calculated table references the following model entities:</p>
          <div class="table-responsive" style="margin-top: 1rem;">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Entity Type</th>
                  <th>Referenced Entity / Table</th>
                  <th>Column / Scope</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(ref_rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-ref-cols",
            title="Upstream Model References",
            nav_label="Model References",
            content=content,
        )

    def _section_data_source_summary(self) -> Optional[DocSection]:
        sources_summary = self.doc_builder.get_data_sources_summary()
        source_summary_rows = []
        for s in sources_summary:
            stype = s["source_type"]
            conn = s["connection"]
            srv = s["server"]
            db = s["database"]
            sch = s.get("schema", "—")
            itm = s.get("item", "—")
            u_chain = s.get("upstream_chain", [])
            if u_chain:
                pipe_parts = []
                for q in u_chain:
                    clean_q = sanitize_filename(q)
                    if self.config.include_dataflow:
                        pipe_parts.append(f'<a href="../{self.config.clean_expressions_subdir}/{clean_q}{self.config.html_ext_suffix}"><code>{escape(q)}</code></a>')
                    else:
                        pipe_parts.append(f'<code>{escape(q)}</code>')
                pipe_parts.append(f'<strong>{escape(self.name)}</strong>')
                pipe_html = " ➔ ".join(pipe_parts)
            else:
                pipe_html = f'<span class="badge badge-dim">{escape(s["pipeline"])}</span>'

            sch_html = f'<code>{escape(sch)}</code>' if sch != "—" else '<span style="color: var(--text-muted);">—</span>'
            itm_html = f'<code>{escape(itm)}</code>' if itm != "—" else '<span style="color: var(--text-muted);">—</span>'

            source_summary_rows.append(f"""          <tr>
            <td><span class="badge badge-type">{escape(stype)}</span></td>
            <td><code>{escape(conn)}</code></td>
            <td>{escape(srv)}</td>
            <td>{escape(db)}</td>
            <td>{sch_html}</td>
            <td>{itm_html}</td>
            <td>{pipe_html}</td>
          </tr>""")

        clean_tbl = sanitize_filename(self.name)
        expr_sub = self.config.clean_expressions_subdir
        etl_link_html = ""
        is_etl_loaded = (
            self.table.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (self.table.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
            and not self.table.get("is_inherited")
            and (
                self.table.get("power_query_expression")
                or self.table.get("power_query_lineage")
                or self.table.get("m_code")
                or self.table.get("source_type") == "PowerQuery"
            )
        )
        if is_etl_loaded and getattr(self.config, "include_expression_docs", True):
            etl_url = f"../{expr_sub}/{clean_tbl}{self.config.html_ext_suffix}"
            etl_link_html = f"""          <div style="margin-top: 1rem; padding: 0.75rem 1rem; background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 6px; display: flex; align-items: center; justify-content: space-between; gap: 1rem;">
            <span style="font-size: 0.9rem;"><strong>Dedicated ETL Documentation</strong>: view the complete Power Query (M) lineage, transformation steps, and upstream dependencies for this loaded table.</span>
            <a href="{etl_url}" class="badge badge-dim" style="text-decoration: none; padding: 0.4rem 0.8rem; font-weight: 600; white-space: nowrap;">Open ETL Documentation ➔</a>
          </div>"""

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Data Source Summary</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Source Type</th>
                  <th>Connection / Details</th>
                  <th>Server</th>
                  <th>Database</th>
                  <th>Schema</th>
                  <th>Table / Object</th>
                  <th>Data Pipeline / Staging</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(source_summary_rows) if source_summary_rows else '<tr><td colspan="7"><em>No external data sources detected.</em></td></tr>'}
              </tbody>
            </table>
          </div>
{etl_link_html}
        </div>"""
        return DocSection(
            section_id="tab-sources",
            title="Data Source Summary",
            nav_label="Data Source Summary",
            content=content,
        )

    def _section_upstream_pipeline_dependencies(self) -> Optional[DocSection]:
        deps = self.doc_builder.get_upstream_pipeline_dependencies()
        if not deps:
            return None

        rows = []
        for d in deps:
            clean_name = d["clean_name"]
            if self.config.include_dataflow:
                q_link = f'<a href="../{self.config.clean_expressions_subdir}/{clean_name}{self.config.html_ext_suffix}"><strong>{escape(d["name"])}</strong></a>'
            else:
                q_link = f'<strong>{escape(d["name"])}</strong>'
            badge = f'<span class="badge badge-dim">{escape(d["role"])}</span>'
            val_html = f"<code>{escape(d['value_details'])}</code>" if not d['value_details'].startswith("`") else escape(d['value_details'])
            consumed_html = escape(d["consumed_in"])

            rows.append(f"""          <tr>
            <td>{q_link}</td>
            <td>{badge}</td>
            <td>{val_html}</td>
            <td>{consumed_html}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Upstream Pipeline &amp; Expression Dependencies ({len(deps)})</h3>
          <p style="color: var(--color-text-muted); margin-bottom: 1rem;">
            Power Query M expressions, shared staging queries, and parameters feeding this table's transformation pipeline.
          </p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Upstream Query / Parameter</th>
                  <th>Pipeline Role</th>
                  <th>Current Value / Details</th>
                  <th>Consumed in Step(s)</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-upstream-deps",
            title=f"Upstream Pipeline Dependencies ({len(deps)})",
            nav_label=f"Upstream Pipeline ({len(deps)})",
            content=content,
        )

    def _section_data_dictionary(self, col_rows: List[str]) -> Optional[DocSection]:
        if not self.config.include_table_columns_dictionary:
            return None
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Data Dictionary ({len(self.columns)} Columns)</h3>
          <div class="table-responsive">
            <table class="data-table" id="table-columns-table">
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Data Type</th>
                  <th>Type / Origin</th>
                  <th>Format</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(col_rows) if col_rows else '<tr><td colspan="5"><em>No columns defined.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-cols",
            title=f"Data Dictionary ({len(self.columns)})",
            nav_label=f"Data Dictionary ({len(self.columns)})",
            content=content,
        )

    def _section_relationship_diagram(self, direct_rels: List[Dict[str, Any]]) -> Optional[DocSection]:
        if not (self.config.include_relationship_diagrams and direct_rels):
            return None
        try:
            theme_mode = resolve_html_theme_mode(self.config.html_theme)
            svg_gen = RelationshipSvgGenerator(self.model, config=self.config)
            svg_code = svg_gen.generate_table_svg(self.name, theme_mode=theme_mode)
            if not svg_code:
                return None
            is_fact = (normalize_role_key(self.table.get("role")) == "FACT")
            diagram_title = "Star Cluster Relationship Diagram" if is_fact else "1-Hop Relationship Diagram"
            desc_text = (
                "Isolated dimensional star cluster centered on this Fact table, displaying conformed dimensions, outriggers, and bridges."
                if is_fact
                else "Direct 1-hop relationship perimeter connecting this table to adjacent semantic model entities."
            )
            content = f"""        <div class="content-card">
          <h3 class="content-card-title">{diagram_title}</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">
            {desc_text}
          </p>
          <div class="diagram-wrapper" style="overflow-x: auto; padding: 0.5rem 0;">
            {svg_code}
          </div>
        </div>"""
            return DocSection(
                section_id="tab-rel-diagram",
                title=diagram_title,
                nav_label="Diagram",
                content=content,
            )
        except Exception:
            return None

    def _section_relationship_table(self, direct_rels: List[Dict[str, Any]]) -> Optional[DocSection]:
        if not self.config.include_table_topology_section:
            return None

        model_tables = self.model.get("tables", []) or []
        rel_rows = []
        for r in direct_rels:
            is_from = (r.get("from_table") == self.name)
            target_tbl = r.get("to_table") if is_from else r.get("from_table")
            target_col = r.get("to_column") if is_from else r.get("from_column")
            local_col = r.get("from_column") if is_from else r.get("to_column")

            clean_target = sanitize_filename(target_tbl)
            target_tbl_obj = next((t for t in model_tables if t.get("name") == target_tbl), None)
            tbl_pub = self.config.is_table_published(target_tbl_obj) if target_tbl_obj else True
            if tbl_pub:
                target_url = f"{clean_target}{self.config.html_ext_suffix}"
                target_cell = f'<strong><a href="{target_url}">{escape(target_tbl)}</a></strong>'
            else:
                ext_url = self.config.resolve_external_table_url(target_tbl_obj) if target_tbl_obj else None
                if ext_url:
                    target_cell = f'<strong><a href="{ext_url}">{escape(target_tbl)}</a></strong> <span class="badge badge-dim">Remote Entity</span>'
                else:
                    target_cell = f'<code>{escape(target_tbl)}</code> <span class="badge badge-dim">Remote Entity</span>'

            card = r.get("cardinality", "1:N")
            cross = r.get("cross_filtering_behavior", "Single")
            status = "Active" if r.get("is_active", True) else "Inactive"
            status_class = "badge-status-active" if status == "Active" else "badge-status-inactive"

            rel_rows.append(f"""          <tr>
            <td>{target_cell}</td>
            <td><code>[{escape(local_col)}]</code> ➔ <code>[{escape(target_col)}]</code></td>
            <td><span class="badge badge-dim">{escape(card)}</span></td>
            <td>{escape(cross)}</td>
            <td><span class="badge {status_class}">{status}</span></td>
          </tr>""")

        snowflake_html = []
        if self.snowflake_paths:
            for p in self.snowflake_paths:
                path_nodes = p.get("path", [])
                hops = p.get("hops", 1)
                join_keys = p.get("join_keys", [])
                path_str = " ➔ ".join(f"`{escape(n)}`" for n in path_nodes)
                keys_str = ", ".join(f"<code>{escape(jk.get('from'))}</code> ➔ <code>{escape(jk.get('to'))}</code>" for jk in join_keys)
                snowflake_html.append(f"<li><strong>Path ({hops} hops)</strong>: {path_str}<br><span style='color: var(--text-muted); font-size: 0.8rem;'>Join Keys: {keys_str}</span></li>")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Relationships ({len(direct_rels)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Target Table</th>
                  <th>Key Mapping</th>
                  <th>Cardinality</th>
                  <th>Cross Filter</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rel_rows) if rel_rows else '<tr><td colspan="5"><em>No direct active relationships for this table.</em></td></tr>'}
              </tbody>
            </table>
          </div>
          {('<div style="margin-top: 1.25rem;"><h4 class="content-card-title">Transitive Snowflake Outriggers</h4><ul class="spec-list">' + chr(10).join(snowflake_html) + '</ul></div>') if snowflake_html else ''}
        </div>"""
        return DocSection(
            section_id="tab-rels",
            title=f"Relationships ({len(direct_rels)})",
            nav_label=f"Relationships ({len(direct_rels)})",
            content=content,
        )

    def _section_relations(self, direct_rels: List[Dict[str, Any]]) -> Optional[DocSection]:
        if not self.config.include_table_topology_section:
            return None

        sec_table = self._section_relationship_table(direct_rels)
        sec_diagram = self._section_relationship_diagram(direct_rels)

        content_parts = []
        if sec_table:
            content_parts.append(sec_table.content)
        if sec_diagram:
            content_parts.append(sec_diagram.content)

        if not content_parts:
            return None

        return DocSection(
            section_id="tab-rels",
            title=f"Relationships ({len(direct_rels)})",
            nav_label=f"Relationships ({len(direct_rels)})",
            content="\n".join(content_parts),
        )

    def _section_calculated_columns(self, calc_cols: List[Dict[str, Any]]) -> Optional[DocSection]:
        if not calc_cols:
            return None

        calc_col_cards = []
        for cc in calc_cols:
            c_name = cc.get("name", "col")
            slug = sanitize_filename(c_name)
            c_type = cc.get("data_type", "String")
            c_fmt = cc.get("format_string") or ""
            c_desc = cc.get("description") or ""
            c_expr = cc.get("expression") or ""
            formatted_dax = format_dax(
                c_expr,
                name=c_name,
                entity_type="calculated_column",
                table_name=self.name,
            ) if c_expr else "-- No DAX expression provided"

            calc_col_cards.append(f"""        <div id="calc-col-{slug}" class="calc-col-card">
          <div class="calc-col-header">
            <div class="calc-col-title-group">
              <span class="calc-col-name">`{escape(c_name)}`</span>
              <span class="badge badge-type">{escape(c_type)}</span>
              {f'<span class="badge badge-dim">Format: {escape(c_fmt)}</span>' if c_fmt else ''}
            </div>
          </div>
          {f'<p class="calc-col-desc">{escape(c_desc)}</p>' if c_desc else ''}
          <div class="code-container">
            <pre><code id="code-calc-col-{slug}">{escape(formatted_dax)}</code></pre>
          </div>
        </div>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Calculated Columns ({len(calc_cols)})</h3>
          <div style="margin-bottom: 1rem; color: var(--text-muted); font-size: 0.85rem;">
            Calculated columns evaluated via DAX expressions inside this table container:
          </div>
{chr(10).join(calc_col_cards)}
        </div>"""
        return DocSection(
            section_id="tab-calc-cols",
            title=f"Calculated Columns ({len(calc_cols)})",
            nav_label=f"Calculated Columns ({len(calc_cols)})",
            content=content,
        )

    def _section_measures(self, rel_root: str) -> Optional[DocSection]:
        if not self.config.include_table_measures_list:
            return None

        meas_rows = []
        for m in sorted(self.measures, key=lambda x: x.get("name", "")):
            m_name = m.get("name", "Measure")
            clean_m = sanitize_filename(m_name)
            clean_tbl = sanitize_filename(self.name)
            m_url = f"{rel_root}/{self.config.clean_measures_subdir}/{clean_tbl}/{clean_m}{self.config.html_ext_suffix}"
            dax = m.get("dax_expression", "")
            dax_preview = dax[:120] + ("..." if len(dax) > 120 else "")

            meas_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(m_name)}]</a></strong></td>
            <td><span class="badge badge-dim">Depth {m.get('calculation_depth', 0)}</span></td>
            <td><code>{escape(dax_preview)}</code></td>
            <td>{escape(m.get('description', '') or '—')}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Measures ({len(self.measures)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Measure</th>
                  <th>Calculation Depth</th>
                  <th>DAX Preview</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(meas_rows) if meas_rows else '<tr><td colspan="4"><em>No measures hosted in this table.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-meas",
            title=f"Measures ({len(self.measures)})",
            nav_label=f"Measures ({len(self.measures)})",
            content=content,
        )

    def _section_power_query_lineage(self) -> Optional[DocSection]:
        if not self.config.include_table_lineage_section:
            return None

        if self.table.get("source_type") == "CalculatedTable":
            calc_expr = self.table.get("expression") or ""
            formatted_calc = format_dax(calc_expr, name=self.name, entity_type="calculated_table") if calc_expr else ""
            dax_block = f"""        <div class="code-container">
          <div class="code-header"><span>DAX Table Expression</span></div>
          <pre><code id="dax-table-code">{escape(formatted_calc)}</code></pre>
        </div>""" if formatted_calc else "<p style='color: var(--text-muted);'><em>DAX calculation formula defined at partition level.</em></p>"

            ref_rows = []
            for t in self.table.get("referenced_tables", []):
                clean_t = sanitize_filename(t)
                ref_rows.append(f'<li>Table: <a href="{clean_t}{self.config.html_ext_suffix}"><strong>{escape(t)}</strong></a></li>')
            for rc in self.table.get("referenced_columns", []):
                ref_rows.append(f'<li>Column: <code>{escape(rc.get("table", ""))}[{escape(rc.get("column", ""))}]</code></li>')
            for rm in self.table.get("referenced_measures", []):
                ref_rows.append(f'<li>Measure: <code>[{escape(rm)}]</code></li>')

            upstream_block = f"""        <div style="margin-top: 1rem;">
          <h4 style="margin: 0 0 0.5rem 0; font-size: 0.9rem;">Upstream Model References</h4>
          <ul class="spec-list">
{chr(10).join(f"            {r}" for r in ref_rows)}
          </ul>
        </div>""" if ref_rows else ""

            content = f"""        <div class="content-card">
          <h3 class="content-card-title">DAX Table Calculation &amp; Lineage</h3>
          <p style="color: var(--color-text-muted); font-size: 0.875rem; margin-bottom: 1rem;">This table is dynamically computed in-memory within the semantic model using DAX, rather than loaded from an external Power Query data source.</p>
{dax_block}
{upstream_block}
        </div>"""
            return DocSection(
                section_id="tab-m",
                title="DAX Lineage",
                nav_label="Lineage",
                content=content,
            )

        if self.table.get("source_type") == "CalculationGroup" or (self.table.get("role") or "").upper() in ("CALCULATION_GROUP", "CALC_GROUP"):
            calc_items = self.table.get("calculation_items") or []
            item_rows = []
            for ci in calc_items:
                ci_name = ci.get("name", "Item") if isinstance(ci, dict) else str(ci)
                item_rows.append(f'<li><code>{escape(ci_name)}</code></li>')
            items_block = f"""        <div style="margin-top: 1rem;">
          <h4 style="margin: 0 0 0.5rem 0; font-size: 0.9rem;">Calculation Items ({len(calc_items)})</h4>
          <ul class="spec-list">
{chr(10).join(f"            {ir}" for ir in item_rows)}
          </ul>
        </div>""" if item_rows else ""

            content = f"""        <div class="content-card">
          <h3 class="content-card-title">Calculation Group &amp; Lineage</h3>
          <p style="color: var(--color-text-muted); font-size: 0.875rem; margin-bottom: 1rem;">This entity is a Calculation Group defined within the semantic model, applying dynamic DAX calculation items to evaluate measures rather than ingesting external data via Power Query.</p>
{items_block}
        </div>"""
            return DocSection(
                section_id="tab-m",
                title="Calculation Group Lineage",
                nav_label="Lineage",
                content=content,
            )

        lineage_node = self.table.get("power_query_lineage") or self.table.get("lineage_node") or {}
        raw_m = (
            lineage_node.get("full_m_expression")
            or self.table.get("power_query_expression")
            or self.table.get("m_code")
            or ""
        )
        m_code = format_m(raw_m) if raw_m else ""
        m_steps = lineage_node.get("steps", []) if lineage_node else []
        known_expr_names = {e.get("query_name") for e in self.model.get("expressions", []) + self.model.get("shared_queries", []) if e.get("query_name")}

        m_steps_rows = []
        for idx, st in enumerate(m_steps, start=1):
            s_name = st.get("step_name", f"Step_{idx}") if isinstance(st, dict) else getattr(st, "step_name", f"Step_{idx}")
            op = st.get("operation", "Transform") if isinstance(st, dict) else getattr(st, "operation", "Transform")
            col_scope = st.get("transformed_column") if isinstance(st, dict) else getattr(st, "transformed_column", None)
            raw_code = st.get("raw_m_code") if isinstance(st, dict) else getattr(st, "raw_m_code", None)
            details = st.get("details") if isinstance(st, dict) else getattr(st, "details", None)
            expr_preview = details or raw_code or "—"
            if len(expr_preview) > 120:
                expr_preview = expr_preview[:117] + "..."

            refs_raw = st.get("referenced_queries", []) if isinstance(st, dict) else getattr(st, "referenced_queries", [])
            ref_links = []
            for r in refs_raw:
                if self.config.include_dataflow and r in known_expr_names:
                    clean_r = sanitize_filename(r)
                    ref_links.append(f'<a href="../{self.config.clean_expressions_subdir}/{clean_r}{self.config.html_ext_suffix}"><code>{escape(r)}</code></a>')
                else:
                    ref_links.append(f'<code>{escape(r)}</code>')
            refs_display = ", ".join(ref_links) if ref_links else '<span style="color: var(--color-text-muted);">—</span>'
            col_display = f"<code>{escape(col_scope)}</code>" if col_scope else '<span style="color: var(--color-text-muted);">—</span>'

            m_steps_rows.append(f"""          <tr>
            <td><code>#{idx} {escape(s_name)}</code></td>
            <td><span class="badge badge-dim">{escape(op)}</span></td>
            <td>{col_display}</td>
            <td><code>{escape(expr_preview)}</code></td>
            <td>{refs_display}</td>
          </tr>""")

        m_merges = lineage_node.get("merges", []) if lineage_node else []
        m_merges_rows = []
        for m in m_merges:
            if hasattr(m, "joined_query"):
                s_name = getattr(m, "step_name", "Merge")
                j_query = getattr(m, "joined_query", "")
                j_kind = getattr(m, "join_kind", "LeftOuter")
                l_keys = getattr(m, "left_keys", [])
                r_keys = getattr(m, "right_keys", [])
                exp_cols = getattr(m, "expanded_columns", [])
            elif isinstance(m, dict):
                s_name = m.get("step_name", "Merge")
                j_query = m.get("joined_query", "")
                j_kind = m.get("join_kind", "LeftOuter")
                l_keys = m.get("left_keys", [])
                r_keys = m.get("right_keys", [])
                exp_cols = m.get("expanded_columns", [])
            else:
                continue

            l_keys_str = ", ".join(l_keys) or "—"
            r_keys_str = ", ".join(r_keys) or "—"
            if j_kind == "CrossJoin":
                keys_str = "<code>Cartesian Product (Cross Join)</code>"
            else:
                keys_str = f"<code>[{escape(l_keys_str)}]</code> ⟷ <code>[{escape(r_keys_str)}]</code>"
            exp_str = ", ".join(f"<code>{escape(c)}</code>" for c in exp_cols) or "—"

            if self.config.include_dataflow and j_query in known_expr_names:
                j_query_html = f'<a href="../{self.config.clean_expressions_subdir}/{sanitize_filename(j_query)}{self.config.html_ext_suffix}"><strong>{escape(j_query)}</strong></a>'
            else:
                j_query_html = f'<strong>{escape(j_query)}</strong>'

            m_merges_rows.append(f"""          <tr>
            <td><code>{escape(s_name)}</code></td>
            <td>{j_query_html}</td>
            <td><span class="badge badge-dim">{escape(j_kind)}</span></td>
            <td>{keys_str}</td>
            <td>{exp_str}</td>
          </tr>""")

        m_merges_html = f"""        <div style="margin-top: 1.5rem; margin-bottom: 1.25rem;">
          <h4 class="content-card-title">Power Query Table Merges / Joins ({len(m_merges)})</h4>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Step</th>
                  <th>Joined Query</th>
                  <th>Join Type</th>
                  <th>Join Keys</th>
                  <th>Expanded Columns</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(m_merges_rows)}
              </tbody>
            </table>
          </div>
        </div>""" if m_merges_rows else ""

        steps_table_html = f"""        <div class="table-responsive" style="margin-bottom: 1.25rem;">
          <table class="data-table">
            <thead>
              <tr>
                <th># &amp; Step Name</th>
                <th>Operation</th>
                <th>Transformed Column / Scope</th>
                <th>Expression Preview / Details</th>
                <th>Referenced Queries</th>
              </tr>
            </thead>
            <tbody>
{chr(10).join(m_steps_rows)}
            </tbody>
          </table>
        </div>""" if m_steps_rows else ""

        code_block_html = f"""        <div class="code-container">
          <div class="code-header">
            <span>Power Query (M) Script</span>
          </div>
          <pre><code id="m-script-code">{escape(m_code)}</code></pre>
        </div>""" if m_code else "<p style='color: var(--text-muted);'><em>No Power Query M transformation detected (DirectQuery or Calculated table).</em></p>"

        has_m_pipeline = (
            self.table.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (self.table.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
            and bool(raw_m or m_steps)
        )

        dataflow_banner = ""
        if has_m_pipeline and self.config.include_dataflow and self.config.include_expression_docs:
            clean_tbl = sanitize_filename(self.name)
            dataflow_banner = f"""        <div class="content-card" style="display: flex; align-items: center; justify-content: space-between; gap: 1rem; border-left: 4px solid var(--accent-color); margin-bottom: 1.25rem;">
          <div>
            <h4 style="margin: 0 0 0.25rem 0;">ETL Pipeline Documentation</h4>
            <p style="margin: 0; color: var(--color-text-muted); font-size: 0.875rem;">View the dedicated ETL data transformation page, complete lineage step breakdown, and parameters.</p>
          </div>
          <a href="../{self.config.clean_expressions_subdir}/{clean_tbl}{self.config.html_ext_suffix}" class="badge badge-dim" style="padding: 0.5rem 0.85rem; text-decoration: none; white-space: nowrap;">Open ETL Doc ➔</a>
        </div>"""

        banner_html = f"{dataflow_banner}\n" if dataflow_banner else ""
        content = f"""{banner_html}        <div class="content-card">
          <h3 class="content-card-title">Power Query Lineage &amp; Transformation Steps</h3>
{steps_table_html}
{m_merges_html}
{code_block_html}
        </div>"""
        return DocSection(
            section_id="tab-m",
            title="Power Query Lineage",
            nav_label="Power Query Lineage",
            content=content,
        )

    def _section_power_query_columns(self, pq_cols: List[Dict[str, Any]]) -> Optional[DocSection]:
        if not pq_cols:
            return None

        pq_col_cards = []
        for pqc in pq_cols:
            c_name = pqc.get("name", "col")
            slug = sanitize_filename(c_name)
            c_type = pqc.get("data_type", "String")
            c_op = pqc.get("m_operation") or "Power Query Transformation"
            c_step = pqc.get("m_step_name") or ""
            c_expr = pqc.get("m_expression") or ""
            c_src_tbl = pqc.get("m_source_table") or ""
            c_src_col = pqc.get("source_column") or ""

            details = []
            if c_op:
                details.append(f'<span class="badge badge-pq">{escape(c_op)}</span>')
            if c_step:
                details.append(f'<span class="badge badge-dim">Step: `{escape(c_step)}`</span>')
            if c_src_tbl:
                details.append(f'<span class="badge badge-dim">From Query: <strong>{escape(c_src_tbl)}</strong></span>')
            if c_src_col and c_src_col != c_name:
                details.append(f'<span class="badge badge-dim">Source Col: <code>{escape(c_src_col)}</code></span>')

            details_html = " ".join(details)
            expr_block = f"""          <div class="code-container">
            <pre><code id="code-pq-col-{slug}">{escape(c_expr)}</code></pre>
          </div>""" if c_expr else ""

            pq_col_cards.append(f"""        <div id="pq-col-{slug}" class="calc-col-card" style="border-left: 3px solid var(--col-pq-text);">
          <div class="calc-col-header">
            <div class="calc-col-title-group">
              <span class="calc-col-name">`{escape(c_name)}`</span>
              <span class="badge badge-type">{escape(c_type)}</span>
              {details_html}
            </div>
          </div>
          {expr_block}
        </div>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Power Query Calculated and Transformed Columns ({len(pq_cols)})</h3>
          <div style="margin-bottom: 1rem; color: var(--text-muted); font-size: 0.85rem;">
            Columns derived, transformed, or merged in Power Query (M) before loading into the model:
          </div>
{chr(10).join(pq_col_cards)}
        </div>"""
        return DocSection(
            section_id="tab-pq-cols",
            title=f"Power Query Calculated and Transformed Columns ({len(pq_cols)})",
            nav_label=f"Power Query Columns ({len(pq_cols)})",
            content=content,
        )

    def _section_details(self, role_class: str) -> Optional[DocSection]:
        inc = self.table.get("incremental_refresh_policy") or {}
        has_inc = bool(inc.get("is_enabled"))
        criteria_list = self.classification.get("criteria_matched", [])

        inc_card = ""
        if self.config.include_table_incremental_refresh:
            inc_card = f"""
        <div class="content-card" style="margin-top: 1.25rem;">
          <h3 class="content-card-title">Incremental Refresh Policy</h3>
          <table class="data-table">
            <tbody>
              <tr><td><strong>Policy Status</strong></td><td><span class="badge {'badge-status-active' if has_inc else 'badge-status-inactive'}">{'Enabled' if has_inc else 'Disabled'}</span></td></tr>
              <tr><td><strong>Storage Mode</strong></td><td><code>{escape(inc.get('mode', self.table.get('storage_mode', 'Import')))}</code></td></tr>
              <tr><td><strong>Historical Retention (Store)</strong></td><td>{escape(str(inc.get('rolling_window_periods', '—')))} {escape(str(inc.get('rolling_window_granularity', '')))}</td></tr>
              <tr><td><strong>Refresh Period (Refresh)</strong></td><td>{escape(str(inc.get('incremental_periods', '—')))} {escape(str(inc.get('incremental_granularity', '')))}</td></tr>
            </tbody>
          </table>
          {f'''<div style="margin-top: 1rem;"><div class="spec-group-title">Detect Data Changes Expression</div><div class="code-container"><pre><code>{escape(inc.get('polling_expression', ''))}</code></pre></div></div>''' if inc.get('polling_expression') else ''}
        </div>"""

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Star Schema Classification Analysis</h3>
          <p style="margin-bottom: 0.75rem;"><strong>Assigned Role</strong>: <span class="badge {role_class}">{escape(self.role)}</span> (Confidence: {self.classification.get('confidence_score', 1.0):.0%})</p>
          <div style="font-size: 0.825rem; color: var(--text-muted); margin-bottom: 0.5rem;">Criteria Matched:</div>
          <ul class="spec-list">
            {chr(10).join('<li>• ' + escape(c) + '</li>' for c in criteria_list) if criteria_list else '<li>• Standard heuristic criteria applied.</li>'}
          </ul>
        </div>{inc_card}"""
        return DocSection(
            section_id="tab-tech",
            title="Details",
            nav_label="Details",
            content=content,
        )

    def _section_rag_context(self) -> Optional[DocSection]:
        if not self.config.include_table_rag_hints:
            return None

        hints = []
        if self.role in ("FACT", "FACT_TABLE"):
            hints.append(
                f"<li>• <strong>Aggregation Context</strong>: <code>{escape(self.name)}</code> is a Fact table. Prefer using explicit DAX measures rather than summing raw numeric columns directly.</li>"
            )
        elif self.role in ("DATE_DIMENSION", "DATE"):
            hints.append(
                f"<li>• <strong>Time Intelligence Context</strong>: <code>{escape(self.name)}</code> acts as a Date Dimension. Use its primary date column for DAX Time Intelligence functions (<code>TOTALYTD</code>, <code>SAMEPERIODLASTYEAR</code>, <code>DATEADD</code>).</li>"
            )
        else:
            hints.append(
                f"<li>• <strong>Slicing &amp; Grouping Context</strong>: <code>{escape(self.name)}</code> is a Dimension/Lookup table. Use its attributes in <code>SUMMARIZECOLUMNS</code>, <code>TREATAS</code>, or visual axis/legend bindings.</li>"
            )

        key_cols = [c.get("name") for c in self.columns if c.get("is_key")]
        if key_cols:
            hints.append(f"<li>• <strong>Join / Grain Keys</strong>: {', '.join(f'<code>{escape(k)}</code>' for k in key_cols)}</li>")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Semantic Context for AI &amp; RAG</h3>
          <ul class="spec-list">
            {chr(10).join(hints)}
          </ul>
        </div>"""
        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content=content,
        )

    def _section_badge_legend(self) -> DocSection:
        content = """        <div class="content-card">
          <h3 class="content-card-title">Table Documentation Badges &amp; Tags Legend</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">Reference guide explaining all role badges, structural attributes, and key tags utilized across table documentation.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Tag / Badge</th>
                  <th style="width: 180px;">Category</th>
                  <th>Functional Meaning &amp; Architectural Role</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge badge-role-fact">Fact</span></td>
                  <td>Topological Role</td>
                  <td>Central business entity containing quantitative metrics, transactional events, or numeric performance measures.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-dim">Dim</span></td>
                  <td>Topological Role</td>
                  <td>Conformed analytical dimension providing contextual slicing, filtering attributes, and business hierarchies.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-snowflake">Snow</span></td>
                  <td>Topological Role</td>
                  <td>Snowflaked secondary dimension (outrigger) extending another dimension via normalized reference keys.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-bridge">Bridge</span></td>
                  <td>Topological Role</td>
                  <td>Intermediate junction table resolving Many-to-Many relationships or complex multi-parent hierarchies.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-date">Date</span></td>
                  <td>Topological Role</td>
                  <td>Dedicated calendar / date dimension supporting time intelligence calculations and period-over-period comparisons.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-calcgroup">CalcGroup</span></td>
                  <td>Topological Role</td>
                  <td>Calculation Group table dynamically altering measure evaluation context through DAX calculation items.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-utility">Utility</span></td>
                  <td>Topological Role</td>
                  <td>Disconnected parameter, DAX calculation helper, or configuration table with no active data model relationships.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-pk">PK</span></td>
                  <td>Key Constraint</td>
                  <td>Primary Key: unique record identifier column participating in model relationships.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-fk">FK</span></td>
                  <td>Key Constraint</td>
                  <td>Foreign Key: outgoing reference column establishing relationships to primary dimension tables.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-dim">Hidden</span></td>
                  <td>Visibility</td>
                  <td>Attribute hidden from the client report canvas to prevent confusion while remaining active for DAX and relationships.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-legend",
            title="Tags &amp; Badges Legend",
            nav_label="Legend",
            content=content,
        )


class HtmlMeasureBuilder:
    """Builds individual Measure documentation page (measures/<Table>/<Measure>.html)."""

    def __init__(
        self,
        measure_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.doc_builder = MeasureDocBuilder(measure_data, full_model, config, project_name=project_name)
        self.measure = self.doc_builder.measure
        self.model = self.doc_builder.model
        self.config = self.doc_builder.config
        self.project_name = self.doc_builder.project_name
        self.name = self.doc_builder.name
        self.table = self.doc_builder.table
        self.depth = self.doc_builder.depth
        self.dax = self.doc_builder.dax
        self.format_string = self.doc_builder.format_string
        self.description = self.doc_builder.description
        self.direct_deps = self.doc_builder.direct_deps
        self.all_upstream = self.doc_builder.all_upstream
        self.downstream = self.doc_builder.downstream
        self.referenced_functions = self.doc_builder.referenced_functions
        self.referenced_cols = self.doc_builder.referenced_cols
        self.referenced_tables = self.doc_builder.referenced_tables
        self.measure_table_map = self.doc_builder.measure_table_map

    def build_content(self) -> str:
        """Assemble complete HTML content for a Measure following section-driven modular layout."""
        rel_root = "../.."
        clean_tbl = sanitize_filename(self.table)
        tbl_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_tbl}{self.config.html_ext_suffix}"

        upstream_m = self.direct_deps
        downstream_m = self.downstream

        header_html = f"""      <div class="page-header">
        <h1 class="page-title">
          <span>Measure: [{escape(self.name)}]</span>
          <span class="badge badge-dim">Depth {self.depth}</span>
        </h1>
        <p class="page-subtitle">DAX expression logic, referenced column bindings, and calculation DAG dependencies.</p>
      </div>"""

        kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Model</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><a href="{rel_root}/index{self.config.html_ext_suffix}">{escape(self.project_name)}</a></div>
          <div class="kpi-sub">Semantic Model</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Host Table</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><a href="{tbl_url}">{escape(self.table)}</a></div>
          <div class="kpi-sub">Container Entity</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Calculation Depth</div>
          <div class="kpi-value">Depth {self.depth}</div>
          <div class="kpi-sub">{len(upstream_m)} Upstream Precedents</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Downstream Impact</div>
          <div class="kpi-value">{len(downstream_m)}</div>
          <div class="kpi-sub">Dependent Measures</div>
        </div>
      </div>"""

        # Exact Measure Section Sequence:
        # 1. Description
        # 2. DAX
        # 3. Referenced Columns
        # 4. Upstream Dependency
        # 5. Downstream Dependents
        # 6. Technical Specifications
        # 7. Semantic Context for AI & RAG
        registry: Dict[str, Callable[[], Any]] = {
            "description": self._section_description,
            "dax_formula": self._section_dax,
            "referenced_columns": lambda: self._section_referenced_columns(rel_root),
            "direct_dependencies": lambda: self._section_upstream_dependency(rel_root),
            "downstream_dependencies": lambda: self._section_downstream_dependents(rel_root),
            "details": lambda: self._section_technical_specifications(tbl_url),
            "rag_context": self._section_rag_context,
            "badge_legend": self._section_badge_legend,
        }
        return render_document_html("measure", header_html, kpis_html, registry, config=self.config)

    def _section_description(self) -> Optional[DocSection]:
        desc_html = (
            f'<p class="description-text">{escape(self.description)}</p>'
            if self.description
            else '<p class="description-text description-empty"><em>No description provided in the data model.</em></p>'
        )
        content = f"""        <div class="content-card description-card">
          <h3 class="content-card-title">Description</h3>
          {desc_html}
        </div>"""
        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content=content,
        )

    def _section_dax(self) -> Optional[DocSection]:
        if not self.config.include_measure_dax_formula:
            return None
        dax = self.dax
        formatted_dax = format_dax(
            dax,
            name=self.name,
            entity_type="measure",
            table_name=self.table,
        ) if dax else "-- No DAX expression provided"

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">DAX</h3>
          <div class="code-container">
            <div class="code-header">
              <span>DAX Formula</span>
            </div>
            <pre><code id="measure-dax-code">{escape(formatted_dax)}</code></pre>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-dax",
            title="DAX",
            nav_label="DAX",
            content=content,
        )

    def _section_referenced_columns(self, rel_root: str) -> Optional[DocSection]:
        if not self.config.include_measure_referenced_columns:
            return None

        ref_cols = self.referenced_cols
        col_rows = []
        for c in ref_cols:
            if isinstance(c, dict):
                t_name = c.get("table", self.table)
                c_name = c.get("column", "")
            elif isinstance(c, (list, tuple)) and len(c) > 0 and isinstance(c[0], dict):
                t_name = c[0].get("table", self.table)
                c_name = c[0].get("column", "")
            elif isinstance(c, (list, tuple)) and len(c) >= 2:
                t_name, c_name = str(c[0]), str(c[1])
            elif isinstance(c, str) and "[" in c:
                t_name, c_name = c.split("[", 1)
                c_name = c_name.rstrip("]")
            else:
                t_name, c_name = self.table, str(c)

            clean_t = sanitize_filename(t_name)
            t_link = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_t}{self.config.html_ext_suffix}"
            target_tbl = next((t for t in self.model.get("tables", []) if t.get("name") == t_name), None)
            tbl_pub = self.config.is_table_published(target_tbl) if target_tbl else True
            if tbl_pub:
                t_cell = f'<a href="{t_link}">{escape(t_name)}</a>'
            else:
                ext_url = self.config.resolve_external_table_url(target_tbl) if target_tbl else None
                if ext_url:
                    t_cell = f'<a href="{ext_url}">{escape(t_name)}</a> <span class="badge badge-dim">Remote Entity</span>'
                else:
                    t_cell = f'<code>{escape(t_name)}</code> <span class="badge badge-dim">Remote Entity</span>'

            col_rows.append(f"""          <tr>
            <td>{t_cell}</td>
            <td><code>[{escape(c_name)}]</code></td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Referenced Columns ({len(ref_cols)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Column Name</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(col_rows) if col_rows else '<tr><td colspan="2"><em>No physical or calculated columns directly referenced.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-cols",
            title=f"Referenced Columns ({len(ref_cols)})",
            nav_label=f"Referenced Columns ({len(ref_cols)})",
            content=content,
        )

    def _section_upstream_dependency(self, rel_root: str) -> Optional[DocSection]:
        if not self.config.include_measure_upstream_deps:
            return None

        upstream_m = self.direct_deps
        up_rows = []
        for um in upstream_m:
            target_tbl = self.measure_table_map.get(um, self.table)
            clean_u_tbl = sanitize_filename(target_tbl)
            clean_u = sanitize_filename(um)
            m_url = f"{rel_root}/{self.config.clean_measures_subdir}/{clean_u_tbl}/{clean_u}{self.config.html_ext_suffix}"
            u_tbl_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_u_tbl}{self.config.html_ext_suffix}"
            up_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(um)}]</a></strong></td>
            <td><a href="{u_tbl_url}">{escape(target_tbl)}</a></td>
          </tr>""")

        indirect_html = ""
        indirect_deps = [u for u in self.all_upstream if u not in self.direct_deps]
        if indirect_deps:
            ind_items = []
            for ind in indirect_deps:
                target_tbl = self.measure_table_map.get(ind, self.table)
                clean_u_tbl = sanitize_filename(target_tbl)
                clean_u = sanitize_filename(ind)
                m_url = f"{rel_root}/{self.config.clean_measures_subdir}/{clean_u_tbl}/{clean_u}{self.config.html_ext_suffix}"
                ind_items.append(f'<li><a href="{m_url}"><code>[{escape(ind)}]</code></a> ({escape(target_tbl)})</li>')
            indirect_html = f"""
          <div style="margin-top: 1rem;">
            <div class="spec-group-title">Indirect (Transitive) Dependencies ({len(indirect_deps)})</div>
            <ul class="spec-list">
              {chr(10).join(ind_items)}
            </ul>
          </div>"""

        funcs_html = ""
        if self.referenced_functions:
            fn_items = []
            for fn in self.referenced_functions:
                clean_fn = sanitize_filename(fn)
                if getattr(self.config, "include_function_docs", True):
                    fn_url = f"{rel_root}/{self.config.clean_functions_subdir}/{clean_fn}{self.config.html_ext_suffix}"
                    fn_items.append(f'<li><a href="{fn_url}"><code>{escape(fn)}()</code></a></li>')
                else:
                    fn_items.append(f'<li><code>{escape(fn)}()</code></li>')
            funcs_html = f"""
          <div style="margin-top: 1rem;">
            <div class="spec-group-title">Referenced DAX UDF Functions ({len(self.referenced_functions)})</div>
            <ul class="spec-list">
              {chr(10).join(fn_items)}
            </ul>
          </div>"""

        total_upstream = len(upstream_m) + len(self.referenced_functions)
        up_title_suffix = f"Preceding Measures &amp; Functions in DAG - {total_upstream}" if self.referenced_functions else f"Preceding Measures in DAG - {len(upstream_m)}"
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Upstream Dependency ({up_title_suffix})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Measure</th>
                  <th>Host Table</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(up_rows) if up_rows else '<tr><td colspan="2"><em>Leaf calculation: No upstream measures referenced.</em></td></tr>'}
              </tbody>
            </table>
          </div>{indirect_html}{funcs_html}
        </div>"""
        return DocSection(
            section_id="tab-upstream",
            title=f"Upstream Dependency ({total_upstream})",
            nav_label=f"Upstream ({total_upstream})",
            content=content,
        )

    def _section_downstream_dependents(self, rel_root: str) -> Optional[DocSection]:
        if not self.config.include_measure_downstream_impact:
            return None

        downstream_m = self.downstream
        down_rows = []
        for dm in downstream_m:
            target_tbl = self.measure_table_map.get(dm, self.table)
            clean_d_tbl = sanitize_filename(target_tbl)
            clean_d = sanitize_filename(dm)
            m_url = f"{rel_root}/{self.config.clean_measures_subdir}/{clean_d_tbl}/{clean_d}{self.config.html_ext_suffix}"
            d_tbl_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_d_tbl}{self.config.html_ext_suffix}"
            down_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(dm)}]</a></strong></td>
            <td><a href="{d_tbl_url}">{escape(target_tbl)}</a></td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Downstream Dependents (Dependent Measures - {len(downstream_m)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Measure</th>
                  <th>Host Table</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(down_rows) if down_rows else '<tr><td colspan="2"><em>Terminal calculation: No other measures depend on this formula.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-downstream",
            title=f"Downstream Dependents ({len(downstream_m)})",
            nav_label=f"Downstream ({len(downstream_m)})",
            content=content,
        )

    def _section_technical_specifications(self, tbl_url: str) -> Optional[DocSection]:
        depth_label = self.doc_builder._get_depth_label()
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Technical Specifications</h3>
          <table class="data-table">
            <tbody>
              <tr><td><strong>Model Key</strong></td><td><code>{escape(self.measure.get('model_key', f'{self.table}[{self.name}]'))}</code></td></tr>
              <tr><td><strong>Host Table</strong></td><td><a href="{tbl_url}"><strong>{escape(self.table)}</strong></a></td></tr>
              <tr><td><strong>Calculation Depth</strong></td><td><code>{self.depth}</code> ({escape(depth_label)})</td></tr>
              <tr><td><strong>DAG Hierarchy</strong></td><td>{len(self.direct_deps)} direct upstream / {len(self.downstream)} direct downstream</td></tr>
              <tr><td><strong>Display Folder</strong></td><td>{escape(self.measure.get('display_folder', '') or '—')}</td></tr>
              <tr><td><strong>Format String</strong></td><td><code>{escape(self.measure.get('format_string', '') or '—')}</code></td></tr>
              <tr><td><strong>Hidden in View Mode</strong></td><td>{'Yes' if self.measure.get('is_hidden') else 'No'}</td></tr>
              <tr><td><strong>External Bound (Composite)</strong></td><td>{'Yes' if self.measure.get('is_external_measure') else 'No'}</td></tr>
            </tbody>
          </table>
        </div>"""
        return DocSection(
            section_id="tab-tech",
            title="Technical Specifications",
            nav_label="Technical Specifications",
            content=content,
        )

    def _section_rag_context(self) -> Optional[DocSection]:
        if not self.config.include_measure_rag_hints:
            return None

        filter_context_note = "Standard filter context evaluation."
        upper_dax = self.dax.upper()
        if "CALCULATE(" in upper_dax or "CALCULATETABLE(" in upper_dax:
            filter_context_note = "Modifies filter context via <code>CALCULATE</code> / <code>CALCULATETABLE</code>."
        if any(fn in upper_dax for fn in ("ALL(", "ALLEXCEPT(", "ALLSELECTED(", "REMOVEFILTERS(")):
            filter_context_note += " Overrides or clears dimensional filters."
        if any(fn in upper_dax for fn in ("TOTALYTD(", "SAMEPERIODLASTYEAR(", "DATEADD(", "DATESYTD(", "PARALLELPERIOD(")):
            filter_context_note += " Applies Time Intelligence date shifting; requires a contiguous Date Dimension in filter context."
        if "USERELATIONSHIP(" in upper_dax:
            filter_context_note += " Activates an inactive relationship via <code>USERELATIONSHIP</code>."

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Semantic Context for AI &amp; RAG</h3>
          <ul class="spec-list">
            <li>• <strong>Canonical Invocation</strong>: Always reference this measure in DAX queries as <code>[{escape(self.name)}]</code> (do not prefix measure names with table names in DAX).</li>
            <li>• <strong>Filter Context Behavior</strong>: {filter_context_note}</li>
            <li>• <strong>Refactoring Risk</strong>: {'High — ' + str(len(self.downstream)) + ' downstream measure(s) depend on this calculation.' if self.downstream else 'Low — Leaf/Terminal metric with 0 downstream measure dependents.'}</li>
          </ul>
        </div>"""
        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content=content,
        )

    def _section_badge_legend(self) -> DocSection:
        content = """        <div class="content-card">
          <h3 class="content-card-title">Measure Documentation Badges &amp; Tags Legend</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">Reference guide explaining calculation depth tiers, DAX function roles, and dependency indicators.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Tag / Badge</th>
                  <th style="width: 180px;">Category</th>
                  <th>Functional Meaning &amp; Calculation Role</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge badge-dim">Depth 0</span></td>
                  <td>Calculation Depth</td>
                  <td>Base atomic measure: directly aggregates physical table columns (e.g. SUM, COUNTROWS) without referencing other measures.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-dim">Depth 1+</span></td>
                  <td>Calculation Depth</td>
                  <td>Composite / Derived metric: evaluates higher-order business logic, ratios, or time intelligence on top of upstream measures.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-accent">Filter Modifier</span></td>
                  <td>DAX Operation</td>
                  <td>Alters the ambient filter context using functions like CALCULATE, KEEPFILTERS, REMOVEFILTERS, or USERELATIONSHIP.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-dim">Leaf Metric</span></td>
                  <td>Impact Assessment</td>
                  <td>Terminal measure with 0 downstream measure dependents; safe for non-breaking local formula refactoring.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-legend",
            title="Tags &amp; Badges Legend",
            nav_label="Legend",
            content=content,
        )


class HtmlVisualBuilder:
    """Builds individual Report Page documentation (visuals/<PageName>.html)."""

    def __init__(
        self,
        page,
        report_model: PBIPReportModel,
        config: DocGenConfig,
        project_name: Optional[str] = None,
        model_tables: Optional[List[Dict[str, Any]]] = None,
        model_measures: Optional[List[Dict[str, Any]]] = None,
        table_url_resolver: Optional[Callable[[str], Optional[str]]] = None,
        measure_url_resolver: Optional[Callable[[str, str], Optional[str]]] = None,
    ):
        self.page = page
        self.report = report_model
        self.config = config
        self.project_name = project_name or "PBIP"
        self.table_url_resolver = table_url_resolver
        self.measure_url_resolver = measure_url_resolver
        self.model_tables = model_tables or []
        self.model_measures = model_measures or []
        self.table_map = {t.get("name"): t for t in self.model_tables if t.get("name")}
        self.measure_map = get_measure_lookup_map({"measures": self.model_measures})

    def build_content(self) -> str:
        rel_root = ".."
        dynamic_visuals = [v for v in self.page.visuals if v.is_dynamic]

        header_html = f"""      <div class="page-header">
        <h1 class="page-title">
          <span>Report Page: {escape(self.page.display_name)}</span>
          <span class="badge badge-dim">#{self.page.page_number}</span>
        </h1>
        <p class="page-subtitle">Interactive visual layout, spatial coordinates, metric evaluations, and canvas filter context.</p>
      </div>"""

        kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Page Number</div>
          <div class="kpi-value">#{self.page.page_number}</div>
          <div class="kpi-sub">Sequence in Report</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Visibility</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{'Hidden' if self.page.is_hidden else 'Visible'}</div>
          <div class="kpi-sub">View Mode State</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Dynamic Visuals</div>
          <div class="kpi-value">{len(dynamic_visuals)}</div>
          <div class="kpi-sub">Data-Bound Containers</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Canvas Dimensions</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><code>{self.page.width}x{self.page.height}</code></div>
          <div class="kpi-sub">Pixels (Width x Height)</div>
        </div>
      </div>"""

        registry: Dict[str, Callable[[], Any]] = {
            "description": lambda: self._section_description(dynamic_visuals),
            "filters": lambda: self._section_filters(dynamic_visuals),
            "filter_context": lambda: self._section_filters(dynamic_visuals),
            "visuals": lambda: self._section_visuals(dynamic_visuals, rel_root),
            "spatial_layout": lambda: self._section_spatial_layout(dynamic_visuals),
            "badge_legend": self._section_badge_legend,
        }
        return render_document_html("visual_page", header_html, kpis_html, registry, config=self.config)

    def _section_description(self, dynamic_visuals: List[Any]) -> Optional[DocSection]:
        content = f"""        <div class="content-card description-card">
          <h3 class="content-card-title">Description</h3>
          <p class="description-text">Presentation and evaluation context specification for report page <strong>{escape(self.page.display_name)}</strong>. It details the complete filter perimeter (report-level and page-level filter pane constraints, interactive canvas slicers, and visual-level filters) and provides spatial-to-metric mappings for <strong>{len(dynamic_visuals)}</strong> dynamic visual elements.</p>
        </div>"""
        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content=content,
        )

    def _section_filters(self, dynamic_visuals: List[Any]) -> Optional[DocSection]:
        all_pages_filters_rows = []
        page_filters_rows = []
        slicers_rows = []

        all_pages_filters = (
            dynamic_visuals[0].calculation_context.all_pages_filters
            if dynamic_visuals and dynamic_visuals[0].calculation_context.all_pages_filters
            else getattr(self.report, "report_filters", [])
        )
        for af in all_pages_filters:
            vals = ", ".join(af.applied_values) if af.applied_values else (af.default_value or "All (No filter applied)")
            vals_html = escape(vals)
            if (af.operator == "TopN") and getattr(af, "order_by_measure", None):
                meas_name = af.order_by_measure
                meas_tbl = getattr(af, "order_by_table", None) or "Model"
                m_url = self.measure_url_resolver(meas_tbl, meas_name) if (self.measure_url_resolver and self.config.include_models) else None
                m_link = f'<a href="{m_url}">[{escape(meas_name)}]</a>' if m_url else f'[{escape(meas_name)}]'
                needle = f" by [{meas_name}]"
                if needle in vals:
                    prefix = vals.split(needle)[0]
                    vals_html = f"{escape(prefix)} by {m_link}"
                else:
                    vals_html = f"{escape(vals)} by {m_link}"
            t_url = self.table_url_resolver(af.table) if (self.table_url_resolver and self.config.include_models) else None
            t_cell = f'<a href="{t_url}"><strong>{escape(af.table)}</strong></a>' if t_url else f'<strong>{escape(af.table)}</strong>'
            lock_badge = '<span class="badge badge-filter-locked">Locked</span>' if af.is_locked else '<span class="badge badge-filter-unlocked">Unlocked</span>'
            all_pages_filters_rows.append(f"""          <tr>
            <td>{t_cell}</td>
            <td><code>[{escape(af.field)}]</code></td>
            <td><code>{escape(af.operator or 'Custom')}</code></td>
            <td>{vals_html}</td>
            <td>{lock_badge}</td>
          </tr>""")

        if dynamic_visuals:
            first_v = dynamic_visuals[0]
            first_cc = first_v.calculation_context
            p_filters = first_cc.page_filters or (first_cc.locked_active_filters + first_cc.unlocked_available_filters)
            for pf in p_filters:
                vals = ", ".join(pf.applied_values) if pf.applied_values else (pf.default_value or "All (No filter applied)")
                vals_html = escape(vals)
                if (pf.operator == "TopN") and getattr(pf, "order_by_measure", None):
                    meas_name = pf.order_by_measure
                    meas_tbl = getattr(pf, "order_by_table", None) or "Model"
                    m_url = self.measure_url_resolver(meas_tbl, meas_name) if (self.measure_url_resolver and self.config.include_models) else None
                    m_link = f'<a href="{m_url}">[{escape(meas_name)}]</a>' if m_url else f'[{escape(meas_name)}]'
                    needle = f" by [{meas_name}]"
                    if needle in vals:
                        prefix = vals.split(needle)[0]
                        vals_html = f"{escape(prefix)} by {m_link}"
                    else:
                        vals_html = f"{escape(vals)} by {m_link}"
                op_str = pf.operator or ("In" if pf.applied_values else "—")
                t_url = self.table_url_resolver(pf.table) if (self.table_url_resolver and self.config.include_models) else None
                t_cell = f'<a href="{t_url}"><strong>{escape(pf.table)}</strong></a>' if t_url else f'<strong>{escape(pf.table)}</strong>'
                lock_badge = '<span class="badge badge-filter-locked">Locked</span>' if pf.is_locked else '<span class="badge badge-filter-unlocked">Unlocked</span>'
                page_filters_rows.append(f"""          <tr>
            <td>{t_cell}</td>
            <td><code>[{escape(pf.field)}]</code></td>
            <td><code>{escape(op_str)}</code></td>
            <td>{vals_html}</td>
            <td>{lock_badge}</td>
          </tr>""")

            for sl in first_cc.page_slicers:
                synced_label = '<span class="badge badge-status-active">Yes (Synchronized)</span>' if sl.is_synced_across_pages else '<span class="badge badge-dim">No (Local)</span>'
                t_url = self.table_url_resolver(sl.table) if (self.table_url_resolver and self.config.include_models) else None
                t_lbl = f'<a href="{t_url}">{escape(sl.table)}</a>' if t_url else f'<strong>{escape(sl.table)}</strong>'
                slicers_rows.append(f"""          <tr>
            <td><code>{escape(sl.model_key)}</code></td>
            <td>{t_lbl} ➔ <code>[{escape(sl.field)}]</code></td>
            <td>{escape(sl.default_selection)}</td>
            <td>{synced_label}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Report Page Filter Context</h3>
          <div style="margin-bottom: 1.5rem;">
            <div class="spec-group-title">1. Filter Pane (Report Level)</div>
            <p class="description-text" style="color: var(--text-muted); margin-bottom: 0.75rem; font-size: 0.88rem;">Filters configured in the filter pane applied globally across all report pages. These restrict every visual on this canvas.</p>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Target Table</th>
                    <th>Target Field</th>
                    <th>Operator</th>
                    <th>Applied Values</th>
                    <th>Lock Status</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(all_pages_filters_rows) if all_pages_filters_rows else '<tr><td colspan="5"><em>No report-level filters configured in the filter pane.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div style="margin-bottom: 1.5rem;">
            <div class="spec-group-title">2. Filter Pane (Page Level)</div>
            <p class="description-text" style="color: var(--text-muted); margin-bottom: 0.75rem; font-size: 0.88rem;">Filters configured in the filter pane for this page. These govern the calculation perimeter across all visuals on this canvas.</p>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Target Table</th>
                    <th>Target Field</th>
                    <th>Operator</th>
                    <th>Applied Values / Default</th>
                    <th>Lock Status</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(page_filters_rows) if page_filters_rows else '<tr><td colspan="5"><em>No page-level filters configured in the filter pane.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <div class="spec-group-title">3. Interactive Filters</div>
            <p class="description-text" style="color: var(--text-muted); margin-bottom: 0.75rem; font-size: 0.88rem;">Interactive on-canvas slicers and synchronized controls available for end-user exploratory filtering on this page.</p>
            <div class="table-responsive">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Slicer Control</th>
                    <th>Target Field</th>
                    <th>Default Selection</th>
                    <th>Synced Across Pages</th>
                  </tr>
                </thead>
                <tbody>
{chr(10).join(slicers_rows) if slicers_rows else '<tr><td colspan="4"><em>No interactive on-canvas slicers detected.</em></td></tr>'}
                </tbody>
              </table>
            </div>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-filters",
            title="Report Page Filter Context",
            nav_label="Report Page Filter Context",
            content=content,
        )

    def _section_visuals(self, dynamic_visuals: List[Any], rel_root: str) -> Optional[DocSection]:
        all_pages_filters = (
            dynamic_visuals[0].calculation_context.all_pages_filters
            if dynamic_visuals and dynamic_visuals[0].calculation_context.all_pages_filters
            else getattr(self.report, "report_filters", [])
        )

        visual_cards = []
        for idx, v in enumerate(dynamic_visuals, start=1):
            title = v.title or f"Visual {idx}"
            cond_badge = ' <span class="badge badge-dim" style="margin-left: 0.5rem;">Conditional Title</span>' if v.is_conditional_title else ""
            s_pos = v.spatial_position
            zone = s_pos.zone if s_pos else "Center"
            indicative_pos = zone.replace("Middle-", "Center-")
            if indicative_pos in ("Center-Center", "Canvas"):
                indicative_pos = "Center"

            calc = v.calculation_context
            metrics_html = []
            metrics_to_render = v.get_effective_evaluated_metrics()

            for m in metrics_to_render:
                m_name = m.field
                clean_m = sanitize_filename(m_name)
                clean_tbl = sanitize_filename(m.table or "Model")
                is_implicit = bool(m.aggregation) or m.field_type in ("IMPLICIT_MEASURE", "COLUMN")

                if not is_implicit and m.field_type == "MEASURE":
                    if self.measure_url_resolver and self.config.include_models:
                        m_url = self.measure_url_resolver(m.table or "Model", m_name)
                    elif self.config.include_models:
                        m_url = f"{rel_root}/{self.config.clean_measures_subdir}/{clean_tbl}/{clean_m}{self.config.html_ext_suffix}"
                    else:
                        m_url = None
                    if m_url:
                        link_html = f'<a href="{m_url}"><strong>[{escape(m_name)}]</strong></a>'
                    else:
                        link_html = f'<strong>[{escape(m_name)}]</strong>'
                    type_badge = ""
                else:
                    if self.table_url_resolver and self.config.include_models:
                        t_url = self.table_url_resolver(m.table or clean_tbl)
                    elif self.config.include_models:
                        t_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_tbl}{self.config.html_ext_suffix}"
                    else:
                        t_url = None
                    if t_url:
                        link_html = f'<a href="{t_url}">{escape(m.table or clean_tbl)}</a><code>[{escape(m_name)}]</code>'
                    else:
                        link_html = f'<code>{escape(m.table or clean_tbl)}[{escape(m_name)}]</code>'
                    type_badge = ' <span class="badge badge-type" style="font-size: 0.72rem;">Implicit Measure</span>'
                agg_str = f" ({escape(m.aggregation)})" if m.aggregation else ""
                screen_str = f' <span class="badge badge-dim" style="font-size: 0.72rem;">Screen: "{escape(m.display_name)}"</span>' if m.display_name else ""
                metrics_html.append(f'<li>{link_html}{agg_str}{type_badge} <span style="color: var(--text-muted);">(Role: {escape(m.role)})</span>{screen_str}</li>')

            slicing_html = []
            for s in calc.slicing_coordinates:
                clean_tbl = sanitize_filename(s.table)
                if self.table_url_resolver and self.config.include_models:
                    t_url = self.table_url_resolver(s.table)
                elif self.config.include_models:
                    t_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_tbl}{self.config.html_ext_suffix}"
                else:
                    t_url = None
                if t_url:
                    t_link = f'<a href="{t_url}">{escape(s.table)}</a>'
                else:
                    t_link = f'<strong>{escape(s.table)}</strong>'
                screen_str = f' <span class="badge badge-dim" style="font-size: 0.72rem;">Screen: "{escape(s.display_name)}"</span>' if s.display_name else ""
                slicing_html.append(f'<li>{t_link}<code>[{escape(s.field)}]</code> <span style="color: var(--text-muted);">(Role: {escape(s.role)})</span>{screen_str}</li>')

            visual_filters_html = []
            for vf in calc.visual_active_filters:
                clean_tbl = sanitize_filename(vf.table)
                if self.table_url_resolver and self.config.include_models:
                    t_url = self.table_url_resolver(vf.table)
                elif self.config.include_models:
                    t_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_tbl}{self.config.html_ext_suffix}"
                else:
                    t_url = None
                t_link = f'<a href="{t_url}"><strong>{escape(vf.table)}</strong></a>' if t_url else f'<strong>{escape(vf.table)}</strong>'
                lock_badge = '<span class="badge badge-filter-locked" style="font-size: 0.72rem;">Locked</span>' if vf.is_locked else '<span class="badge badge-filter-unlocked" style="font-size: 0.72rem;">Unlocked</span>'

                cond_html = escape(vf.condition)
                if (vf.operator == "TopN" or vf.filter_type == "TopN") and getattr(vf, "order_by_measure", None):
                    meas_name = vf.order_by_measure
                    meas_tbl = getattr(vf, "order_by_table", None) or "Model"
                    if self.measure_url_resolver and self.config.include_models:
                        m_url = self.measure_url_resolver(meas_tbl, meas_name)
                    elif self.config.include_models:
                        clean_m_tbl = sanitize_filename(meas_tbl)
                        clean_m = sanitize_filename(meas_name)
                        m_url = f"{rel_root}/{self.config.clean_measures_subdir}/{clean_m_tbl}/{clean_m}{self.config.html_ext_suffix}"
                    else:
                        m_url = None
                    m_link = f'<a href="{m_url}">[{escape(meas_name)}]</a>' if m_url else f'[{escape(meas_name)}]'
                    needle = f" by [{meas_name}]"
                    if needle in vf.condition:
                        prefix = vf.condition.split(needle)[0]
                        cond_html = f"{escape(prefix)} by {m_link}"
                    else:
                        cond_html = f"{escape(vf.condition)} by {m_link}"

                visual_filters_html.append(
                    f'<li>{t_link}<code>[{escape(vf.field)}]</code>: '
                    f'<code class="filter-condition-badge">{cond_html}</code> '
                    f'{lock_badge}</li>'
                )

            svg_url = self.config.resolve_visual_svg_url(self.page.display_name, v.visual_id)

            visual_cards.append(f"""      <div class="visual-card">
        <div class="visual-card-header">
          <div>
            <strong>#{idx}. {escape(title)}</strong>
            <span class="badge badge-dim" style="margin-left: 0.5rem;">{escape(v.visual_type)}</span>{cond_badge}
          </div>
          <span class="badge badge-type">Position: {escape(indicative_pos)}</span>
        </div>
        <div class="visual-card-body">
          <div class="visual-minimap-col">
            <img src="{svg_url}" class="visual-minimap-img" alt="{escape(title)} Canvas Location">
          </div>
          <div class="visual-specs-col">
            <div>
              <div class="spec-group-title">Evaluated Metrics</div>
              {('<ul class="spec-list">' + chr(10).join(metrics_html) + '</ul>') if metrics_html else '<p style="color: var(--text-muted);"><em>No metrics evaluated (slicer or structural visual).</em></p>'}
            </div>
            <div>
              <div class="spec-group-title">Slicing Coordinates</div>
              {('<ul class="spec-list">' + chr(10).join(slicing_html) + '</ul>') if slicing_html else '<p style="color: var(--text-muted);"><em>No slicing coordinates.</em></p>'}
            </div>
            <div>
              <div class="spec-group-title">Visual-Level Filters</div>
              {('<ul class="spec-list">' + chr(10).join(visual_filters_html) + '</ul>') if visual_filters_html else '<p style="color: var(--text-muted);"><em>No visual-level filters configured.</em></p>'}
            </div>
          </div>
        </div>
      </div>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Dynamic Visual Containers ({len(dynamic_visuals)})</h3>
{chr(10).join(visual_cards) if visual_cards else '<p style="color: var(--text-muted);"><em>No dynamic data-bound visual containers on this page.</em></p>'}
        </div>"""
        return DocSection(
            section_id="tab-visuals",
            title=f"Visuals ({len(dynamic_visuals)})",
            nav_label=f"Visuals ({len(dynamic_visuals)})",
            content=content,
        )

    def _section_spatial_layout(self, dynamic_visuals: List[Any]) -> Optional[DocSection]:
        coords_rows = []
        for idx, v in enumerate(dynamic_visuals, start=1):
            sp = v.spatial_position
            bbox = sp.bounding_box if sp else None
            bx = f"{bbox.x:.0f}" if bbox else "—"
            by = f"{bbox.y:.0f}" if bbox else "—"
            bw = f"{bbox.width:.0f}" if bbox else "—"
            bh = f"{bbox.height:.0f}" if bbox else "—"
            bz = f"{bbox.z}" if bbox else "0"

            coords_rows.append(f"""          <tr>
            <td>#{idx}</td>
            <td><strong>{escape(v.title or f'Visual {idx}')}</strong></td>
            <td><code>{escape(v.visual_id)}</code></td>
            <td><span class="badge badge-type">{escape(v.visual_type)}</span></td>
            <td><code>({bx}, {by})</code></td>
            <td><code>{bw}x{bh}</code></td>
            <td>{bz}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Exact Spatial Coordinates &amp; Container Specifications</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Visual Title</th>
                  <th>Visual ID</th>
                  <th>Type</th>
                  <th>Position (X, Y)</th>
                  <th>Size (W x H)</th>
                  <th>Z-Index</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(coords_rows) if coords_rows else '<tr><td colspan="7"><em>No visual containers detected.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-tech",
            title="Spatial Layout & Geometry",
            nav_label="Spatial Layout & Geometry",
            content=content,
        )

    def _section_badge_legend(self) -> DocSection:
        content = """        <div class="content-card">
          <h3 class="content-card-title">Report Page Badges &amp; Tags Legend</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">Reference guide explaining canvas visual types, panel filter behaviors, and coordinate classifications.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Tag / Badge</th>
                  <th style="width: 180px;">Category</th>
                  <th>Functional Meaning &amp; Presentation Behavior</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge badge-filter-locked">Locked</span></td>
                  <td>Filter Pane Behavior</td>
                  <td>Enforced business constraint: active filter permanently locked in view mode; cannot be altered or cleared by report consumers.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-filter-unlocked">Unlocked</span></td>
                  <td>Filter Pane Behavior</td>
                  <td>Interactive default filter: pre-filtered on initial load but available for consumer interaction, modification, or clearing.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-accent">TopN</span></td>
                  <td>Filter Pane Behavior</td>
                  <td>Dynamic ranking filter restricting visual data to top or bottom N records based on a specified DAX metric or column.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-dim">Explicit Measure</span></td>
                  <td>Metric Type</td>
                  <td>Centralized DAX formula defined within the semantic model, evaluated dynamically within the visual filter context.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-type">Implicit Measure</span></td>
                  <td>Metric Type</td>
                  <td>Client-side aggregation applied on an unmodeled raw column (e.g. Sum of Amount) directly inside the visual container.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-legend",
            title="Tags &amp; Badges Legend",
            nav_label="Legend",
            content=content,
        )


class HtmlExpressionBuilder:
    """Builds individual Shared Expression page (expressions/<Expression>.html)."""

    def __init__(
        self,
        expression_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.doc_builder = ExpressionDocBuilder(expression_data, full_model, config, project_name=project_name)
        self.expression = self.doc_builder.expr
        self.model = self.doc_builder.model
        self.config = self.doc_builder.config
        self.project_name = self.doc_builder.project_name
        self.name = self.doc_builder.name
        self.is_staging = self.doc_builder.is_staging
        self.full_m = self.doc_builder.full_m
        self.direct_deps = self.doc_builder.direct_deps

    def build_content(self) -> str:
        rel_root = ".."
        q_name = self.expression.get("query_name", self.name)
        target_table = self.expression.get("target_table") or "None (Staging Query)"
        is_staging = self.expression.get("is_staging", True)
        direct_deps = self.expression.get("direct_dependencies", [])

        exp_type = self.doc_builder.expression_type
        badge_cls, badge_text, _ = get_expression_badge_info(exp_type or self.expression)

        header_html = f"""      <div class="page-header">
        <h1 class="page-title">
          <span>ETL: {escape(q_name)}</span>
          <span class="badge {badge_cls}">{badge_text}</span>
        </h1>
        <p class="page-subtitle">Power Query M transformation pipeline, staging dependencies, and loaded model impact.</p>
      </div>"""

        model_link = f'<a href="{rel_root}/index{self.config.html_ext_suffix}">{escape(self.project_name)}</a>' if self.config.include_models else escape(self.project_name)
        if exp_type == "PARAMETER":
            p_val = self.expression.get("parameter_value") or "—"
            p_type = self.expression.get("parameter_type") or "Any"
            p_req = "Yes" if self.expression.get("parameter_required") else "No"
            downstream_cnt = len(self.expression.get("downstream_tables", [])) + len(self.expression.get("downstream_queries", []))
            kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Model</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{model_link}</div>
          <div class="kpi-sub">Semantic Model</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Pipeline Role</div>
          <div class="kpi-value" style="font-size: 1.25rem;"><span class="badge {badge_cls}">{badge_text}</span></div>
          <div class="kpi-sub">Environment Config</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Current Value</div>
          <div class="kpi-value" style="font-size: 1.15rem; word-break: break-all;"><code>{escape(p_val[:30] + ('...' if len(p_val) > 30 else ''))}</code></div>
          <div class="kpi-sub">Type: {escape(p_type)} | Req: {p_req}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Consuming Items</div>
          <div class="kpi-value">{downstream_cnt}</div>
          <div class="kpi-sub">Downstream Impact</div>
        </div>
      </div>"""
        else:
            target_cell = f'<a href="../{self.config.clean_tables_subdir}/{sanitize_filename(target_table)}{self.config.html_ext_suffix}"><strong>{escape(target_table)}</strong></a>' if (target_table != 'None (Staging Query)' and self.config.include_models) else escape(target_table)
            kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Model</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{model_link}</div>
          <div class="kpi-sub">Semantic Model</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Pipeline Role</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><span class="badge {badge_cls}">{badge_text}</span></div>
          <div class="kpi-sub">Data Load Mode</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Target Table</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{target_cell}</div>
          <div class="kpi-sub">Loaded Entity</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Dependencies</div>
          <div class="kpi-value">{len(direct_deps)}</div>
          <div class="kpi-sub">Direct Upstream Queries</div>
        </div>
      </div>"""

        registry: Dict[str, Callable[[], Any]] = {
            "description": self._section_description,
            "data_source_summary": self._section_data_source_summary,
            "function_parameters": self._section_function_parameters,
            "inline_definition": self._section_inline_table,
            "inline_table": self._section_inline_table,
            "m_formula": self._section_m_script,
            "power_query_m": self._section_m_script,
            "lineage_steps": self._section_transformation_steps,
            "calculated_columns": self._section_calculated_columns,
            "pq_columns": self._section_calculated_columns,
            "unused_steps": self._section_unused_steps,
            "upstream_dependencies": self._section_upstream_dependencies,
            "downstream_dependencies": lambda: self._section_downstream_dependents(rel_root),
            "downstream_dependents": lambda: self._section_downstream_dependents(rel_root),
            "details": self._section_technical_specifications,
            "rag_context": self._section_rag_context,
            "badge_legend": self._section_badge_legend,
        }
        return render_document_html("expression", header_html, kpis_html, registry, config=self.config)

    def _section_description(self) -> Optional[DocSection]:
        desc_html = (
            f'<p class="description-text">{escape(self.expression["description"])}</p>'
            if self.expression.get("description")
            else '<p class="description-text description-empty"><em>No description provided in the data model.</em></p>'
        )
        content = f"""        <div class="content-card description-card">
          <h3 class="content-card-title">Description</h3>
          {desc_html}
        </div>"""
        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content=content,
        )

    def _section_function_parameters(self) -> Optional[DocSection]:
        params = self.expression.get("m_function_parameters", [])
        ret_type = self.expression.get("m_function_return_type")
        if self.doc_builder.expression_type != "CUSTOM_FUNCTION" and not params:
            return None

        param_rows = []
        for p in params:
            p_name = p.name if hasattr(p, "name") else p.get("name", "")
            p_type = (p.data_type if hasattr(p, "data_type") else p.get("data_type")) or "any"
            p_opt = "Yes" if (p.is_optional if hasattr(p, "is_optional") else p.get("is_optional")) else "No"
            p_desc = (p.description if hasattr(p, "description") else p.get("description")) or "—"
            param_rows.append(f"""            <tr>
              <td><code>{escape(p_name)}</code></td>
              <td><code>{escape(p_type)}</code></td>
              <td><span class="badge badge-dim">{escape(p_opt)}</span></td>
              <td>{escape(p_desc)}</td>
            </tr>""")

        ret_info = f'<p style="margin-bottom: 0.75rem;"><strong>Return Type:</strong> <code>{escape(ret_type)}</code></p>' if ret_type else ""

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Function Signature & Parameters</h3>
          {ret_info}
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Parameter</th>
                  <th>Type</th>
                  <th>Optional</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(param_rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-params",
            title="Function Signature & Parameters",
            nav_label="Parameters",
            content=content,
        )

    def _section_inline_table(self) -> Optional[DocSection]:
        if not (self.config.include_expression_inline_table and self.doc_builder.is_inline_table):
            return None

        cols = self.doc_builder.inline_cols
        rows = self.doc_builder.inline_rows
        types = self.doc_builder.inline_types

        col_headers = "".join(f"<th>{escape(c)}</th>" for c in cols)
        row_trs = []
        for r in rows[:15]:
            tds = "".join(f"<td>{escape(str(v) if v is not None else 'null')}</td>" for v in r)
            row_trs.append(f"            <tr>{tds}</tr>")

        types_info = ""
        if types:
            items = [f"<code>{escape(c)}</code>: <em>{escape(t)}</em>" for c, t in types.items()]
            types_info = f'<p style="margin-bottom: 0.75rem;"><strong>Column Types:</strong> {", ".join(items)}</p>'

        more_note = f'<p class="table-note" style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--color-text-muted);"><em>Showing top {min(len(rows), 15)} of {len(rows)} rows</em></p>' if len(rows) > 15 else ""

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Inline Table Definition (<code>#table</code>)</h3>
          <p style="margin-bottom: 0.5rem; color: var(--color-text-muted);">Static in-memory lookup table containing <strong>{len(cols)} columns</strong> and <strong>{len(rows)} rows</strong>.</p>
          {types_info}
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>{col_headers}</tr>
              </thead>
              <tbody>
{chr(10).join(row_trs)}
              </tbody>
            </table>
          </div>
          {more_note}
        </div>"""
        return DocSection(
            section_id="tab-inline",
            title="Inline Table Definition",
            nav_label="Inline Table",
            content=content,
        )

    def _section_unused_steps(self) -> Optional[DocSection]:
        unused = self.expression.get("unused_steps", [])
        if not (self.config.include_m_unused_steps and unused):
            return None

        rows = []
        for st in unused:
            s_name = getattr(st, "step_name", None) or (st.get("step_name") if isinstance(st, dict) else "")
            op = getattr(st, "operation", None) or (st.get("operation") if isinstance(st, dict) else "")
            code_snip = getattr(st, "raw_m_code", None) or (st.get("raw_m_code") if isinstance(st, dict) else "")
            rows.append(f"""            <tr>
              <td><code>{escape(s_name)}</code></td>
              <td><span class="badge badge-dim">{escape(op)}</span></td>
              <td><code>{escape(code_snip[:120])}</code></td>
            </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Unused / Dead Steps ({len(unused)})</h3>
          <p style="margin-bottom: 0.75rem; color: var(--color-text-muted);">These steps are defined in the Power Query script but are not referenced by the terminal <code>in</code> expression or active DAG slice.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Step Name</th>
                  <th>Operation</th>
                  <th>Code Snippet</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-unused",
            title=f"Unused Steps ({len(unused)})",
            nav_label=f"Unused Steps ({len(unused)})",
            content=content,
        )

    def _section_m_script(self) -> Optional[DocSection]:
        raw_m = self.expression.get("full_m_expression") or self.expression.get("raw_m_code") or ""
        m_code = format_m(raw_m) if raw_m else ""
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Power Query (M) Script</h3>
          <div class="code-container">
            <div class="code-header">
              <span>Power Query Script</span>
            </div>
            <pre><code id="expression-m-code">{escape(m_code)}</code></pre>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-m",
            title="Power Query (M) Script",
            nav_label="Power Query (M) Script",
            content=content,
        )

    def _section_transformation_steps(self) -> Optional[DocSection]:
        steps = self.doc_builder.steps
        if not steps:
            return None
        step_rows = []
        for idx, s in enumerate(steps, start=1):
            s_name = s.get("step_name", f"Step_{idx}") if isinstance(s, dict) else getattr(s, "step_name", f"Step_{idx}")
            s_op = s.get("operation", "Transform") if isinstance(s, dict) else getattr(s, "operation", "Transform")
            col_scope = s.get("transformed_column") if isinstance(s, dict) else getattr(s, "transformed_column", None)
            raw_code = s.get("raw_m_code") if isinstance(s, dict) else getattr(s, "raw_m_code", None)
            details = s.get("details") if isinstance(s, dict) else getattr(s, "details", None)
            s_expr = details or raw_code or (s.get("raw_expression", "") if isinstance(s, dict) else getattr(s, "raw_expression", ""))
            if len(s_expr) > 120:
                s_expr = s_expr[:117] + "..."

            refs_raw = s.get("referenced_queries", []) if isinstance(s, dict) else getattr(s, "referenced_queries", [])
            ref_links = []
            for r in refs_raw:
                clean_r = sanitize_filename(r)
                ref_links.append(f'<a href="{clean_r}{self.config.html_ext_suffix}"><code>{escape(r)}</code></a>')
            refs_display = ", ".join(ref_links) if ref_links else '<span style="color: var(--color-text-muted);">—</span>'
            col_display = f"<code>{escape(col_scope)}</code>" if col_scope else '<span style="color: var(--color-text-muted);">—</span>'

            step_rows.append(f"""          <tr>
            <td><code>#{idx} {escape(s_name)}</code></td>
            <td><span class="badge badge-dim">{escape(s_op)}</span></td>
            <td>{col_display}</td>
            <td><code>{escape(s_expr)}</code></td>
            <td>{refs_display}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Transformation Steps ({len(steps)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th># &amp; Step Name</th>
                  <th>Operation</th>
                  <th>Transformed Column / Scope</th>
                  <th>Expression Preview / Details</th>
                  <th>Referenced Queries</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(step_rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-steps",
            title=f"Transformation Steps ({len(steps)})",
            nav_label=f"Transformation Steps ({len(steps)})",
            content=content,
        )

    def _section_data_source_summary(self) -> Optional[DocSection]:
        root_sources = getattr(self.doc_builder, "root_sources", [])
        if not root_sources:
            return None
        rows = []
        for s in root_sources:
            s_dict = s if isinstance(s, dict) else s.__dict__
            stype = s_dict.get("source_type", "GENERIC")
            conn = str(s_dict.get("connection_string", "—")).replace("\\", "/")
            srv = s_dict.get("server", "—")
            db = s_dict.get("database", "—")
            sch = s_dict.get("schema", "—")
            itm = s_dict.get("item") or s_dict.get("endpoint_or_path") or "—"
            sch_html = f'<code>{escape(sch)}</code>' if sch != "—" else '<span style="color: var(--text-muted);">—</span>'
            itm_html = f'<code>{escape(itm)}</code>' if itm != "—" else '<span style="color: var(--text-muted);">—</span>'
            rows.append(f"""          <tr>
            <td><span class="badge badge-type">{escape(stype)}</span></td>
            <td><code>{escape(conn)}</code></td>
            <td>{escape(srv)}</td>
            <td>{escape(db)}</td>
            <td>{sch_html}</td>
            <td>{itm_html}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Physical Data Sources of Origin ({len(root_sources)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Source Type</th>
                  <th>Connection / Details</th>
                  <th>Server</th>
                  <th>Database</th>
                  <th>Schema</th>
                  <th>Table / Object</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-sources",
            title=f"Data Sources ({len(root_sources)})",
            nav_label=f"Data Sources ({len(root_sources)})",
            content=content,
        )

    def _section_upstream_dependencies(self) -> Optional[DocSection]:
        direct_deps = self.expression.get("direct_dependencies", [])
        steps = self.doc_builder.steps

        # Map each dependency to consuming step(s)
        dep_steps_map: Dict[str, List[str]] = {}
        for idx, s in enumerate(steps, start=1):
            s_name = s.get("step_name", f"Step_{idx}") if isinstance(s, dict) else getattr(s, "step_name", f"Step_{idx}")
            refs = s.get("referenced_queries", []) if isinstance(s, dict) else getattr(s, "referenced_queries", [])
            for r in refs:
                dep_steps_map.setdefault(r, []).append(f"#{idx} {s_name}")

        model_expressions = self.model.get("expressions", [])
        model_tables = self.model.get("tables", [])

        rows = []
        for d in direct_deps:
            clean_d = sanitize_filename(d)
            target_expr = next((e for e in model_expressions if e.get("query_name") == d), None)
            target_tbl = next((t for t in model_tables if t.get("name") == d), None)

            if target_expr:
                b_cls, b_lbl, _ = get_expression_badge_info(target_expr)
                nature_badge = f'<span class="badge {b_cls}">{b_lbl}</span>'
                if b_lbl == "Param":
                    role_text = "Environment Config / Endpoint"
                elif b_lbl == "Func":
                    role_text = "Custom Transformation Function"
                elif b_lbl == "Inline":
                    role_text = "Static Reference Table"
                else:
                    role_text = "Intermediate Cleansed Ingestion"
                entity_link = f'<a href="{clean_d}{self.config.html_ext_suffix}"><strong>{escape(d)}</strong></a>'
            elif target_tbl:
                b_cls, b_lbl, _ = get_expression_badge_info("LOADED_TABLE")
                nature_badge = f'<span class="badge {b_cls}">{b_lbl}</span>'
                role_text = "Tabular Model Entity"
                entity_link = f'<a href="{clean_d}{self.config.html_ext_suffix}"><strong>{escape(d)}</strong></a>'
            else:
                nature_badge = '<span class="badge badge-dim">Source</span>'
                role_text = "Physical Ingestion / Service"
                entity_link = f'<strong>{escape(d)}</strong>'

            c_steps = dep_steps_map.get(d, [])
            if c_steps:
                steps_display = ", ".join(f"<code>{escape(s)}</code>" for s in c_steps)
            else:
                steps_display = '<code>#Source</code>'

            rows.append(f"""          <tr>
            <td>{entity_link}</td>
            <td>{nature_badge}</td>
            <td>{steps_display}</td>
            <td>{role_text}</td>
          </tr>""")

        table_rows_html = chr(10).join(rows) if rows else '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.25rem;"><em>Root query: No direct upstream queries or parameters referenced.</em></td></tr>'

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Upstream Dependencies ({len(direct_deps)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Entity Name</th>
                  <th>Dependency Nature</th>
                  <th>Consuming Step(s)</th>
                  <th>Data Pipeline Role</th>
                </tr>
              </thead>
              <tbody>
{table_rows_html}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-upstream",
            title=f"Upstream Dependencies ({len(direct_deps)})",
            nav_label=f"Upstream ({len(direct_deps)})",
            content=content,
        )

    def _section_downstream_dependents(self, rel_root: str) -> Optional[DocSection]:
        down_tables = self.doc_builder.downstream_tables
        down_queries = self.doc_builder.downstream_queries
        total_down = len(down_tables) + len(down_queries)

        model_tables = {t.get("name"): t for t in self.model.get("tables", [])}
        model_expressions = {e.get("query_name"): e for e in self.model.get("expressions", [])}

        rows = []
        for t in down_tables:
            clean_t = sanitize_filename(t)
            t_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_t}{self.config.html_ext_suffix}" if self.config.include_models else f"../{self.config.clean_tables_subdir}/{clean_t}{self.config.html_ext_suffix}"
            tbl_meta = model_tables.get(t, {})
            t_role = tbl_meta.get("role", "Dimension")
            role_badge = f'<span class="badge {get_table_role_badge_class(t_role)}">{get_table_role_short(t_role)}</span>'
            cols_cnt = len(tbl_meta.get("columns", []))

            is_tbl_inh = tbl_meta.get("is_inherited") or not self.config.is_table_published(tbl_meta)
            if is_tbl_inh:
                ext_url = self.config.resolve_external_table_url(tbl_meta) if tbl_meta else None
                if ext_url:
                    t_cell = f'<a href="{ext_url}"><strong>{escape(t)}</strong></a>'
                else:
                    t_cell = f'<strong><code>{escape(t)}</code></strong>'
                status_badge = '<span class="badge badge-dim">DirectQuery Remote Entity</span>'
                details = f"Remote Tabular Entity ({cols_cnt} cols)"
            else:
                t_cell = f'<a href="{t_url}"><strong>{escape(t)}</strong></a>'
                status_badge = '<span class="badge badge-etl-loaded">Loaded</span>'
                details = f"Loaded Tabular Model Table ({cols_cnt} cols)"

            rows.append(f"""          <tr>
            <td>{t_cell}</td>
            <td>{status_badge}</td>
            <td>{role_badge}</td>
            <td>{details}</td>
          </tr>""")

        for q in down_queries:
            clean_q = sanitize_filename(q)
            q_url = f"{clean_q}{self.config.html_ext_suffix}"
            q_meta = model_expressions.get(q, {})
            b_cls, b_lbl, _ = get_expression_badge_info(q_meta or q)
            nature_badge = f'<span class="badge {b_cls}">{b_lbl}</span>'
            role_badge = '<span class="badge badge-dim">ETL Query</span>'
            details = "Intermediate Pipeline Transformation"
            rows.append(f"""          <tr>
            <td><a href="{q_url}"><strong>{escape(q)}</strong></a></td>
            <td>{nature_badge}</td>
            <td>{role_badge}</td>
            <td>{details}</td>
          </tr>""")

        table_rows_html = chr(10).join(rows) if rows else '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1.25rem;"><em>Leaf query: No downstream queries or published tables reference this expression.</em></td></tr>'

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Downstream Dependents &amp; Model Impact ({total_down})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Consumer Entity</th>
                  <th>Consumer Nature</th>
                  <th>Architectural Role</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
{table_rows_html}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-downstream",
            title=f"Downstream Dependents ({total_down})",
            nav_label=f"Downstream ({total_down})",
            content=content,
        )

    def _get_calculated_columns(self) -> List[Dict[str, Any]]:
        """Extracts Power Query calculated and transformed columns for this expression."""
        cols: List[Dict[str, Any]] = []
        target = self.expression.get("target_table") or self.name
        tables = self.model.get("tables", [])
        matched_table = next((t for t in tables if t.get("name") == target), None)
        if matched_table:
            for c in matched_table.get("columns", []):
                origin = c.get("origin")
                is_pq = origin == "power_query" or bool(c.get("m_expression")) or bool(c.get("m_operation"))
                if is_pq:
                    cols.append(c)
        if not cols:
            for s in self.doc_builder.steps:
                s_op = s.get("operation") if isinstance(s, dict) else getattr(s, "operation", "")
                t_col = s.get("transformed_column") if isinstance(s, dict) else getattr(s, "transformed_column", None)
                if t_col and (s_op in ("Calculated Column", "Add Column", "Custom Column", "Added Custom", "Added Column") or "Column" in str(s_op)):
                    cols.append({
                        "name": t_col,
                        "data_type": "Any",
                        "m_operation": s_op,
                        "m_step_name": s.get("step_name") if isinstance(s, dict) else getattr(s, "step_name", ""),
                        "m_expression": s.get("raw_m_code") or s.get("details") if isinstance(s, dict) else getattr(s, "raw_m_code", ""),
                    })
        return cols

    def _section_calculated_columns(self) -> Optional[DocSection]:
        pq_cols = self._get_calculated_columns()
        if not pq_cols:
            return None

        pq_col_cards = []
        for pqc in pq_cols:
            c_name = pqc.get("name", "col")
            slug = sanitize_filename(c_name)
            c_type = pqc.get("data_type", "String")
            c_op = pqc.get("m_operation") or "Calculated Column"
            c_step = pqc.get("m_step_name") or ""
            c_expr = pqc.get("m_expression") or ""
            c_src_tbl = pqc.get("m_source_table") or ""
            c_src_col = pqc.get("source_column") or ""

            details = []
            if c_op and c_op.lower().strip() not in ("calculated column", "calculated_column", "calculatedcolumns"):
                details.append(f'<span class="badge badge-dim">{escape(c_op)}</span>')
            if c_step:
                details.append(f'<span class="badge badge-dim">Step: `{escape(c_step)}`</span>')
            if c_src_tbl:
                details.append(f'<span class="badge badge-dim">From Query: <strong>{escape(c_src_tbl)}</strong></span>')
            if c_src_col and c_src_col != c_name:
                details.append(f'<span class="badge badge-dim">Source Col: <code>{escape(c_src_col)}</code></span>')

            details_html = " ".join(details)
            expr_block = f"""          <div class="code-container">
            <pre><code id="code-pq-col-{slug}">{escape(c_expr)}</code></pre>
          </div>""" if c_expr else ""

            pq_col_cards.append(f"""        <div id="pq-col-{slug}" class="calc-col-card" style="border-left: 3px solid var(--border-color);">
          <div class="calc-col-header">
            <div class="calc-col-title-group">
              <span class="calc-col-name">`{escape(c_name)}`</span>
              <span class="badge badge-type">{escape(c_type)}</span>
              {details_html}
            </div>
          </div>
          {expr_block}
        </div>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Calculated &amp; Transformed Columns ({len(pq_cols)})</h3>
          <div style="margin-bottom: 1rem; color: var(--text-muted); font-size: 0.85rem;">
            Columns derived, transformed, or merged in Power Query (M) before loading into the model:
          </div>
{chr(10).join(pq_col_cards)}
        </div>"""
        return DocSection(
            section_id="tab-calc-cols",
            title=f"Calculated Columns ({len(pq_cols)})",
            nav_label=f"Calculated Columns ({len(pq_cols)})",
            content=content,
        )

    def _section_technical_specifications(self) -> Optional[DocSection]:
        role_badge = "Staging / Shared ETL Query" if self.is_staging else f"Table Query ({self.doc_builder.target_table})"
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Technical Specifications</h3>
          <table class="data-table">
            <tbody>
              <tr><td><strong>Query Name</strong></td><td><code>{escape(self.name)}</code></td></tr>
              <tr><td><strong>Expression Type</strong></td><td><code>{escape(self.expression.get('expression_type', 'SharedQuery'))}</code></td></tr>
              <tr><td><strong>Pipeline Role</strong></td><td><code>{escape(role_badge)}</code></td></tr>
              <tr><td><strong>Target Table</strong></td><td><code>{escape(self.doc_builder.target_table or 'None (Staging / Shared)')}</code></td></tr>
              <tr><td><strong>Query Group</strong></td><td><code>{escape(self.doc_builder.query_group or 'Root')}</code></td></tr>
              <tr><td><strong>Steps Count</strong></td><td>{len(self.doc_builder.steps)}</td></tr>
            </tbody>
          </table>
        </div>"""
        return DocSection(
            section_id="tab-tech",
            title="Technical Specifications",
            nav_label="Technical Specifications",
            content=content,
        )

    def _section_rag_context(self) -> Optional[DocSection]:
        if not self.config.include_expression_rag_hints:
            return None
        down_tables = self.doc_builder.downstream_tables
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Semantic Context for AI &amp; RAG</h3>
          <ul class="spec-list">
            <li>• <strong>ETL Lineage Hint</strong>: When tracing how data enters {', '.join(f'<code>{escape(t)}</code>' for t in down_tables) if down_tables else 'downstream tables'}, inspect <code>{escape(self.name)}</code> for source filtering, parameter bindings, or intermediate joins.</li>
            <li>• <strong>VertiPaq Availability</strong>: {'This query is NOT loaded as a DAX-queryable table; do not reference <code>' + escape(self.name) + '</code> in DAX queries.' if self.is_staging else 'Loaded into table <code>' + escape(str(self.doc_builder.target_table)) + '</code>.'}</li>
          </ul>
        </div>"""
        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content=content,
        )

    def _section_badge_legend(self) -> DocSection:
        content = """        <div class="content-card">
          <h3 class="content-card-title">Power Query ETL Badges &amp; Tags Legend</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">Reference guide explaining ETL pipeline roles, shared query archetypes, and data ingestion tags.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 160px;">Tag / Badge</th>
                  <th style="width: 180px;">Category</th>
                  <th>Functional Meaning &amp; Data Pipeline Role</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge badge-etl-loaded">Loaded</span></td>
                  <td>Pipeline Role</td>
                  <td>Production table pipeline: final transformed dataset persisted directly into the in-memory tabular model engine.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-staging">Staging</span></td>
                  <td>Pipeline Role</td>
                  <td>Intermediate shared query: extracts or shapes data used as an upstream building block for multiple destination tables.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-param">Param</span></td>
                  <td>Pipeline Role</td>
                  <td>Configurable environmental parameter (e.g. ServerName, DatabaseName, Environment) controlling data source routing.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-func">Func</span></td>
                  <td>Pipeline Role</td>
                  <td>Reusable custom Power Query function parameterized to execute repetitive transformations across diverse streams.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-inline">Inline</span></td>
                  <td>Pipeline Role</td>
                  <td>Static inline dataset created via <code>#table(...)</code> or manual data entry without external physical source calls.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-legend",
            title="Tags &amp; Badges Legend",
            nav_label="Legend",
            content=content,
        )


class HtmlFunctionBuilder:
    """Builds individual DAX UDF page (functions/<Function>.html)."""

    def __init__(
        self,
        function_data: Dict[str, Any],
        full_model: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.doc_builder = FunctionDocBuilder(function_data, full_model, config, project_name=project_name)
        self.function = self.doc_builder.fn
        self.model = self.doc_builder.model
        self.config = self.doc_builder.config
        self.project_name = self.doc_builder.project_name
        self.name = self.doc_builder.name
        self.signature = self.doc_builder.signature
        self.downstream_measures = self.doc_builder.downstream_measures

    def build_content(self) -> str:
        """Assemble complete HTML content for a DAX UDF Function following section-driven modular layout."""
        rel_root = ".."
        f_name = self.name
        ret_type = (self.function.get("return_type") or "").strip() or "Variant"
        params = self.function.get("parameters", [])

        header_html = f"""      <div class="page-header">
        <h1 class="page-title">
          <span>Function: {escape(f_name)}</span>
          <span class="badge badge-dim">UDF</span>
        </h1>
        <p class="page-subtitle">Parameterized DAX function signature, evaluation logic, and dependent measures.</p>
      </div>"""

        model_link = f'<a href="{rel_root}/index{self.config.html_ext_suffix}">{escape(self.project_name)}</a>' if self.config.include_models else escape(self.project_name)
        kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Model</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{model_link}</div>
          <div class="kpi-sub">Semantic Model</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Return Type</div>
          <div class="kpi-value" style="font-size: 1.5rem;"><code>{escape(ret_type)}</code></div>
          <div class="kpi-sub">Result Data Type</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Parameters</div>
          <div class="kpi-value">{len(params)}</div>
          <div class="kpi-sub">Input Arguments</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Dependent Measures</div>
          <div class="kpi-value">{len(self.downstream_measures)}</div>
          <div class="kpi-sub">Downstream Usage</div>
        </div>
      </div>"""

        # 3-Tab Structure for UDF Function (Definition, Dependencies, Details)
        registry: Dict[str, Callable[[], Any]] = {
            "description": self._section_description,
            "parameters": self._section_parameters,
            "dax_formula": self._section_dax,
            "referenced_columns": lambda: self._section_referenced_columns(rel_root),
            "upstream_dependency": self._section_upstream_dependency,
            "downstream_dependents": lambda: self._section_downstream_dependents(rel_root),
            "details": lambda: self._section_technical_specifications(ret_type, params),
            "badge_legend": self._section_badge_legend,
            "rag_context": self._section_rag_context,
            "udf_definition": self._section_udf_definition,
        }
        return render_document_html("function", header_html, kpis_html, registry, config=self.config)

    def _section_description(self) -> Optional[DocSection]:
        desc_html = (
            f'<p class="description-text">{escape(self.function["description"])}</p>'
            if self.function.get("description")
            else '<p class="description-text description-empty"><em>No description provided in the data model.</em></p>'
        )
        content = f"""        <div class="content-card description-card">
          <h3 class="content-card-title">Description</h3>
          {desc_html}
        </div>"""
        return DocSection(
            section_id="tab-desc",
            title="Description",
            nav_label="Description",
            content=content,
        )

    def _section_parameters(self) -> Optional[DocSection]:
        params = self.function.get("parameters", [])
        param_rows = []
        for p in params:
            p_name = str(p.get("name") or "").strip().strip("`")
            p_type = (p.get("data_type") or "").strip() or "Variant"
            p_desc = p.get("description") or "—"
            param_rows.append(f"""          <tr>
            <td><code>{escape(p_name)}</code></td>
            <td><code>{escape(p_type)}</code></td>
            <td>{escape(p_desc)}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Parameters ({len(params)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Parameter Name</th>
                  <th>Data Type</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(param_rows) if param_rows else '<tr><td colspan="3"><em>No parameters required.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-params",
            title=f"Parameters ({len(params)})",
            nav_label=f"Parameters ({len(params)})",
            content=content,
        )

    def _section_dax(self) -> Optional[DocSection]:
        body = self.function.get("expression") or self.function.get("body") or ""
        formatted_dax = format_dax(
            body,
            name=self.name,
            entity_type="function",
            parameters_signature=self.signature,
        ) if body else "-- No DAX body provided"

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">DAX</h3>
          <div class="code-container">
            <div class="code-header">
              <span>DAX Body</span>
            </div>
            <pre><code id="function-dax-code">{escape(formatted_dax)}</code></pre>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-dax",
            title="DAX",
            nav_label="DAX",
            content=content,
        )

    def _section_badge_legend(self) -> DocSection:
        content = """        <div class="content-card">
          <h3 class="content-card-title">Function Documentation Badges &amp; Tags Legend</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">Reference guide explaining DAX user-defined function classifications, parameter roles, and invocation semantics.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Tag / Badge</th>
                  <th style="width: 180px;">Category</th>
                  <th>Functional Meaning &amp; Role</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge badge-dim">UDF</span></td>
                  <td>Architecture</td>
                  <td>User-Defined Function: reusable DAX formula defined at the model level with parameterized signature.</td>
                </tr>
                <tr>
                  <td><code>Type</code></td>
                  <td>Data Type</td>
                  <td>Return and argument types (e.g. Variant, Double, String) enforced during DAX expression evaluation.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-legend",
            title="Legend",
            nav_label="Legend",
            content=content,
        )

    def _section_udf_definition(self) -> Optional[DocSection]:
        s_desc = self._section_description()
        s_params = self._section_parameters()
        s_dax = self._section_dax()
        parts = [s.content for s in (s_desc, s_params, s_dax) if s and s.content]
        return DocSection(
            section_id="tab-desc",
            title="UDF Definition",
            nav_label="UDF Definition",
            content="\n\n".join(parts),
        )

    def _section_referenced_columns(self, rel_root: str) -> Optional[DocSection]:
        ref_cols = self.doc_builder.referenced_cols
        col_rows = []
        for rc in ref_cols:
            if isinstance(rc, dict):
                t_name = rc.get("table", "")
                c_name = rc.get("column", "")
            elif isinstance(rc, (list, tuple)) and len(rc) >= 2:
                t_name, c_name = str(rc[0]), str(rc[1])
            elif isinstance(rc, str) and "[" in rc:
                t_name, c_name = rc.split("[", 1)
                c_name = c_name.rstrip("]")
            else:
                t_name, c_name = "", str(rc)
            clean_t = sanitize_filename(t_name) if t_name else ""
            t_cell = f'<a href="{rel_root}/{self.config.clean_tables_subdir}/{clean_t}{self.config.html_ext_suffix}">{escape(t_name)}</a>' if t_name else "—"
            col_rows.append(f"""          <tr>
            <td>{t_cell}</td>
            <td><code>[{escape(c_name)}]</code></td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Referenced Columns ({len(ref_cols)})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Table</th>
                  <th>Column Name</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(col_rows) if col_rows else '<tr><td colspan="2"><em>No physical model columns directly referenced in this UDF body.</em></td></tr>'}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-cols",
            title=f"Referenced Columns ({len(ref_cols)})",
            nav_label=f"Referenced Columns ({len(ref_cols)})",
            content=content,
        )

    def _section_upstream_dependency(self) -> Optional[DocSection]:
        ref_funcs = self.doc_builder.referenced_functions
        fn_links = []
        for rf in ref_funcs:
            clean_rf = sanitize_filename(rf)
            fn_links.append(f'<li><a href="{clean_rf}{self.config.html_ext_suffix}"><code>{escape(rf)}()</code></a></li>')

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Upstream Dependency ({len(ref_funcs)})</h3>
          {('<ul class="spec-list">' + chr(10).join(fn_links) + '</ul>') if fn_links else '<p style="color: var(--text-muted);"><em>Leaf UDF: No upstream UDF functions or measures referenced.</em></p>'}
        </div>"""
        return DocSection(
            section_id="tab-upstream",
            title=f"Upstream Dependency ({len(ref_funcs)})",
            nav_label=f"Upstream ({len(ref_funcs)})",
            content=content,
        )

    def _section_downstream_dependents(self, rel_root: str) -> Optional[DocSection]:
        down_measures = self.downstream_measures
        down_funcs = self.doc_builder.downstream_functions
        total_down = len(down_measures) + len(down_funcs)

        measure_lookup = get_measure_lookup_map(self.model)
        meas_rows = []
        for dm in down_measures:
            if isinstance(dm, dict):
                m_name = dm.get("name", "")
                t_name = dm.get("table", "Model")
            else:
                m_name = str(dm)
                m_info = measure_lookup.get(m_name, {})
                t_name = m_info.get("table", "Model")
            clean_m = sanitize_filename(m_name)
            clean_t = sanitize_filename(t_name)
            m_url = f"{rel_root}/{self.config.clean_measures_subdir}/{clean_t}/{clean_m}{self.config.html_ext_suffix}"
            t_url = f"{rel_root}/{self.config.clean_tables_subdir}/{clean_t}{self.config.html_ext_suffix}"
            meas_rows.append(f"""          <tr>
            <td><strong><a href="{m_url}">[{escape(m_name)}]</a></strong></td>
            <td><a href="{t_url}">{escape(t_name)}</a></td>
          </tr>""")

        funcs_html = ""
        if down_funcs:
            fn_items = [f'<li><a href="{sanitize_filename(df)}{self.config.html_ext_suffix}"><code>{escape(df)}()</code></a></li>' for df in down_funcs]
            funcs_html = f"""
          <div style="margin-top: 1rem;">
            <div class="spec-group-title">Dependent UDF Functions ({len(down_funcs)})</div>
            <ul class="spec-list">
              {chr(10).join(fn_items)}
            </ul>
          </div>"""

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Downstream Dependents ({total_down})</h3>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Measure</th>
                  <th>Host Table</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(meas_rows) if meas_rows else '<tr><td colspan="2"><em>No measures currently invoke this function.</em></td></tr>'}
              </tbody>
            </table>
          </div>{funcs_html}
        </div>"""
        return DocSection(
            section_id="tab-downstream",
            title=f"Downstream Dependents ({total_down})",
            nav_label=f"Downstream ({total_down})",
            content=content,
        )

    def _section_technical_specifications(self, ret_type: str, params: List[Dict[str, Any]]) -> Optional[DocSection]:
        safe_ret = (ret_type or "").strip() or "Variant"
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Technical Specifications</h3>
          <table class="data-table">
            <tbody>
              <tr><td><strong>Function Name</strong></td><td><code>{escape(self.name)}</code></td></tr>
              <tr><td><strong>Signature</strong></td><td><code>{escape(self.name)}{escape(self.signature)}</code></td></tr>
              <tr><td><strong>Return Type</strong></td><td><code>{escape(safe_ret)}</code></td></tr>
              <tr><td><strong>Parameters Count</strong></td><td>{len(params)}</td></tr>
              <tr><td><strong>Downstream Dependent Measures</strong></td><td>{len(self.downstream_measures)}</td></tr>
            </tbody>
          </table>
        </div>"""
        return DocSection(
            section_id="tab-tech",
            title="Technical Specifications",
            nav_label="Technical Specifications",
            content=content,
        )

    def _section_rag_context(self) -> Optional[DocSection]:
        if not self.config.include_function_rag_hints:
            return None
        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Semantic Context for AI &amp; RAG</h3>
          <ul class="spec-list">
            <li>• <strong>Invocation Syntax</strong>: Call this function inside DAX measures or calculated columns using <code>{escape(self.name)}{escape(self.signature)}</code>.</li>
            <li>• <strong>Reuse Guidance</strong>: Prefer invoking <code>{escape(self.name)}</code> over duplicating its inline DAX logic when implementing new measures with identical parameterization.</li>
          </ul>
        </div>"""
        return DocSection(
            section_id="tab-rag",
            title="Semantic Context for AI & RAG",
            nav_label="AI & RAG Context",
            content=content,
        )


class HtmlDataflowOverviewBuilder:
    """Builds the Dataflow & Power Query Overview dashboard (models/<ModelName>/expressions/index.html)."""

    def __init__(
        self,
        data: Dict[str, Any],
        config: DocGenConfig,
        project_name: Optional[str] = None,
    ):
        self.data = data
        self.config = config
        self.project_name = clean_project_name(
            project_name or config.project_name or data.get("project_name") or data.get("model_name") or "PBIP"
        )
        self.tables = [t for t in self.data.get("tables", []) if self.config.is_table_published(t)]
        self.exprs = self.data.get("expressions") or self.data.get("shared_queries") or []

        self.dataflow_tables = [
            t for t in self.tables
            if (
                t.get("source_type", "PowerQuery") == "PowerQuery"
                or bool(t.get("power_query_lineage") and t.get("power_query_lineage", {}).get("full_m_expression"))
            )
            and t.get("source_type") not in ("CalculatedTable", "CalculationGroup")
            and (t.get("role") or "").upper() not in ("CALCULATION_GROUP", "CALC_GROUP")
        ]

        self.params = [
            e for e in self.exprs
            if resolve_expression_type_and_inline(e)["expression_type"] == "PARAMETER"
        ]
        self.functions = [
            e for e in self.exprs
            if resolve_expression_type_and_inline(e)["expression_type"] == "CUSTOM_FUNCTION"
        ]
        self.staging = [
            e for e in self.exprs
            if e not in self.params and e not in self.functions
        ]

    def build_content(self) -> str:
        header_html = f"""      <div class="page-header">
        <h1 class="page-title">
          <span>ETL Overview: {escape(self.project_name)}</span>
          <span class="page-title-icon" title="ETL">{get_svg_dataflow(width=22, height=22, css_class="header-icon-dataflow")}</span>
        </h1>
        <p class="page-subtitle">Centralized ETL pipelines, source ingestion, parameters, and shared queries.</p>
      </div>"""

        model_link = f'<a href="../index{self.config.html_ext_suffix}">{escape(self.project_name)}</a>' if self.config.include_models else escape(self.project_name)
        kpis_html = f"""      <div class="kpi-grid">
        <div class="kpi-card">
          <div class="kpi-label">Semantic Model</div>
          <div class="kpi-value" style="font-size: 1.5rem;">{model_link}</div>
          <div class="kpi-sub">Target Model Architecture</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Ingested Tables</div>
          <div class="kpi-value">{len(self.dataflow_tables)}</div>
          <div class="kpi-sub">ETL Ingestion Pipelines</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Staging Queries</div>
          <div class="kpi-value">{len(self.staging)}</div>
          <div class="kpi-sub">Intermediate &amp; Lookup Transformations</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Parameters &amp; Functions</div>
          <div class="kpi-value">{len(self.params) + len(self.functions)}</div>
          <div class="kpi-sub">{len(self.params)} Params | {len(self.functions)} Functions</div>
        </div>
      </div>"""

        registry: Dict[str, Callable[[], Any]] = {
            "loaded_tables": self._section_loaded_tables,
            "loaded_queries": self._section_loaded_tables,
            "data_source_summary": self._section_data_source_summary,
            "staging_queries": self._section_staging_queries,
            "parameters_and_functions": self._section_parameters_and_functions,
            "badge_legend": self._section_badge_legend,
        }
        return render_document_html("dataflow_overview", header_html, kpis_html, registry, config=self.config)

    def _section_loaded_tables(self) -> Optional[DocSection]:
        if not self.dataflow_tables:
            return None
        rows = []
        for t in sorted(self.dataflow_tables, key=lambda x: x.get("name", "")):
            t_name = t.get("name", "Table")
            clean_t = sanitize_filename(t_name)
            role = t.get("role", "DIM")
            role_class = get_table_role_badge_class(role)
            role_short = get_table_role_short(role)
            lineage = t.get("power_query_lineage") or {}
            steps_cnt = len(lineage.get("steps", []))
            deps = lineage.get("direct_dependencies", [])
            dep_links = [f'<a href="{sanitize_filename(d)}{self.config.html_ext_suffix}">{escape(d)}</a>' for d in deps]
            deps_str = ", ".join(dep_links) or '<span style="color: var(--color-text-muted);">— (Direct Source)</span>'

            sources = t.get("root_data_sources", [])
            src_types = list({s.get("source_type", "Source") for s in sources if s.get("source_type")})
            src_str = ", ".join(f"<code>{escape(st)}</code>" for st in src_types) or '<span style="color: var(--color-text-muted);">—</span>'

            rows.append(f"""          <tr>
            <td><strong><a href="{clean_t}{self.config.html_ext_suffix}">{escape(t_name)}</a></strong></td>
            <td><span class="badge {role_class}">{escape(role_short)}</span></td>
            <td><code>{steps_cnt}</code></td>
            <td>{deps_str}</td>
            <td>{src_str}</td>
            <td><strong><a href="../{self.config.clean_tables_subdir}/{clean_t}{self.config.html_ext_suffix}">{escape(t_name)}</a></strong></td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Loaded ({len(self.dataflow_tables)})</h3>
          <p style="color: var(--color-text-muted); margin-bottom: 1rem;">Power Query pipelines feeding tables directly into the in-memory semantic model.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Ingested Table</th>
                  <th>Role</th>
                  <th>Steps</th>
                  <th>Direct Dependencies</th>
                  <th>Physical Sources</th>
                  <th>Model Destination</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-loaded",
            title=f"Loaded ({len(self.dataflow_tables)})",
            nav_label=f"Loaded ({len(self.dataflow_tables)})",
            content=content,
        )

    def _section_data_source_summary(self) -> Optional[DocSection]:
        sources_map = {}
        table_names = {t.get("name") for t in self.tables}
        for t in self.tables:
            for s in t.get("root_data_sources", []):
                s_dict = s if isinstance(s, dict) else s.__dict__
                key = (s_dict.get("source_type"), s_dict.get("server"), s_dict.get("database"), s_dict.get("schema"), s_dict.get("item") or s_dict.get("endpoint_or_path"))
                t_name = t.get("name")
                if key not in sources_map:
                    sources_map[key] = {
                        "source": s_dict,
                        "targets": [t_name] if t_name else []
                    }
                else:
                    if t_name and t_name not in sources_map[key]["targets"]:
                        sources_map[key]["targets"].append(t_name)

        for e in self.exprs:
            for s in e.get("root_sources", []):
                s_dict = s if isinstance(s, dict) else s.__dict__
                key = (s_dict.get("source_type"), s_dict.get("server"), s_dict.get("database"), s_dict.get("schema"), s_dict.get("item") or s_dict.get("endpoint_or_path"))
                q_name = e.get("query_name", e.get("name"))
                if key not in sources_map:
                    sources_map[key] = {
                        "source": s_dict,
                        "targets": [q_name] if q_name else []
                    }
                else:
                    if q_name and q_name not in sources_map[key]["targets"]:
                        sources_map[key]["targets"].append(q_name)

        if not sources_map:
            return None

        rows = []
        for item in sources_map.values():
            s = item["source"]
            st = s.get("source_type") or "Source"
            srv = s.get("server") or "—"
            db = s.get("database") or "—"
            sch = s.get("schema") or "—"
            obj = s.get("item") or s.get("endpoint_or_path") or "—"
            details = s.get("endpoint_or_path") or s.get("server") or s.get("database") or "—"
            targets_links = []
            for tgt in item["targets"]:
                if tgt in table_names:
                    url = f"../{self.config.clean_tables_subdir}/{sanitize_filename(tgt)}{self.config.html_ext_suffix}"
                else:
                    url = f"{sanitize_filename(tgt)}{self.config.html_ext_suffix}"
                targets_links.append(f'<a href="{url}"><code>{escape(tgt)}</code></a>')
            targets_str = ", ".join(targets_links) if targets_links else "—"

            rows.append(f"""          <tr>
            <td><span class="badge badge-dim">{escape(st)}</span></td>
            <td><code>{escape(details)}</code></td>
            <td><code>{escape(srv)}</code></td>
            <td><code>{escape(db)}</code></td>
            <td><code>{escape(sch)}</code></td>
            <td><code>{escape(obj)}</code></td>
            <td>{targets_str}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Data Source Summary ({len(sources_map)})</h3>
          <p style="color: var(--color-text-muted); margin-bottom: 1rem;">Physical storage systems, external databases, and connection endpoints consumed by the ETL pipelines.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Source Type</th>
                  <th>Connection / Details</th>
                  <th>Server</th>
                  <th>Database</th>
                  <th>Schema</th>
                  <th>Table / Object</th>
                  <th>Ingested In</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-sources",
            title=f"Data Sources ({len(sources_map)})",
            nav_label=f"Data Sources ({len(sources_map)})",
            content=content,
        )

    def _section_staging_queries(self) -> Optional[DocSection]:
        if not self.staging:
            return None
        rows = []
        for s in sorted(self.staging, key=lambda x: x.get("query_name", "")):
            q_name = s.get("query_name", "Query")
            clean_q = sanitize_filename(q_name)
            b_class, b_label, _ = get_expression_badge_info(s)
            steps_cnt = len(s.get("steps", []))
            deps = s.get("direct_dependencies", [])
            dep_links = [f'<a href="{sanitize_filename(d)}{self.config.html_ext_suffix}"><code>{escape(d)}</code></a>' for d in deps]
            deps_str = ", ".join(dep_links) or '<span style="color: var(--color-text-muted);">—</span>'

            downs = s.get("downstream_tables", []) + s.get("downstream_queries", [])
            down_links = [f'<a href="{sanitize_filename(d)}{self.config.html_ext_suffix}"><code>{escape(d)}</code></a>' for d in downs]
            downs_str = ", ".join(down_links) or '<span style="color: var(--color-text-muted);">—</span>'

            rows.append(f"""          <tr>
            <td><strong><a href="{clean_q}{self.config.html_ext_suffix}">{escape(q_name)}</a></strong></td>
            <td><span class="badge {b_class}">{escape(b_label)}</span></td>
            <td><code>{steps_cnt}</code></td>
            <td>{deps_str}</td>
            <td>{downs_str}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Staging &amp; Intermediate Queries ({len(self.staging)})</h3>
          <p style="color: var(--color-text-muted); margin-bottom: 1rem;">Intermediate data transformations, base staging queries, and static inline reference tables.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Query Name</th>
                  <th>Kind</th>
                  <th>Steps</th>
                  <th>Direct Dependencies</th>
                  <th>Downstream Impact</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-staging",
            title=f"Staging Queries ({len(self.staging)})",
            nav_label=f"Staging Queries ({len(self.staging)})",
            content=content,
        )

    def _section_parameters_and_functions(self) -> Optional[DocSection]:
        items = self.params + self.functions
        if not items:
            return None
        rows = []
        for it in sorted(items, key=lambda x: x.get("query_name", "")):
            name = it.get("query_name", "Item")
            clean_n = sanitize_filename(name)
            is_param = it in self.params
            b_class, b_label, _ = get_expression_badge_info(it)
            val = it.get("parameter_value", "—") if is_param else (it.get("m_function_return_type") or "λ function")
            req = ("Yes" if it.get("parameter_required") else "No") if is_param else "—"

            downs = it.get("downstream_tables", []) + it.get("downstream_queries", [])
            down_str = f"{len(downs)} items" if downs else '<span style="color: var(--color-text-muted);">—</span>'

            rows.append(f"""          <tr>
            <td><strong><a href="{clean_n}{self.config.html_ext_suffix}">{escape(name)}</a></strong></td>
            <td><span class="badge {b_class}">{escape(b_label)}</span></td>
            <td><code>{escape(val)}</code></td>
            <td>{escape(req)}</td>
            <td>{down_str}</td>
          </tr>""")

        content = f"""        <div class="content-card">
          <h3 class="content-card-title">Parameters &amp; Custom Functions ({len(items)})</h3>
          <p style="color: var(--color-text-muted); margin-bottom: 1rem;">Configurable environment parameters and reusable Power Query M functions.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Item Name</th>
                  <th>Category</th>
                  <th>Value / Return Type</th>
                  <th>Required</th>
                  <th>Downstream Items</th>
                </tr>
              </thead>
              <tbody>
{chr(10).join(rows)}
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-params",
            title=f"Parameters & Functions ({len(items)})",
            nav_label=f"Parameters & Functions ({len(items)})",
            content=content,
        )

    def _section_badge_legend(self) -> DocSection:
        content = """        <div class="content-card">
          <h3 class="content-card-title">Dataflow &amp; ETL Badges &amp; Tags Legend</h3>
          <p style="color: var(--text-muted); margin-bottom: 1rem;">Reference guide explaining model target classifications, ETL query archetypes, and expression pipeline categories.</p>
          <div class="table-responsive">
            <table class="data-table">
              <thead>
                <tr>
                  <th style="width: 140px;">Tag / Badge</th>
                  <th style="width: 180px;">Category</th>
                  <th>Functional Meaning &amp; Pipeline Role</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td><span class="badge badge-etl-loaded">Loaded</span></td>
                  <td>Ingestion State</td>
                  <td>Target table actively loaded and ingested into the Tabular / VertiPaq semantic model.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-fact">Fact</span></td>
                  <td>Target Model Role</td>
                  <td>Central business entity containing quantitative metrics, transactional events, or numeric performance measures.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-dim">Dim</span></td>
                  <td>Target Model Role</td>
                  <td>Conformed analytical dimension providing contextual slicing, filtering attributes, and business hierarchies.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-snowflake">Snow</span></td>
                  <td>Target Model Role</td>
                  <td>Snowflaked secondary dimension (outrigger) extending another dimension via normalized reference keys.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-bridge">Bridge</span></td>
                  <td>Target Model Role</td>
                  <td>Intermediate junction table resolving Many-to-Many relationships or complex multi-parent hierarchies.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-date">Date</span></td>
                  <td>Target Model Role</td>
                  <td>Dedicated calendar / date dimension supporting time intelligence calculations and period-over-period comparisons.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-role-utility">Utility</span></td>
                  <td>Target Model Role</td>
                  <td>Disconnected parameter, DAX calculation helper, or configuration table with no active data model relationships.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-staging">Staging</span></td>
                  <td>Expression Class</td>
                  <td>Intermediate transformation query providing cleansed data to downstream tables without being loaded directly into the model.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-param">Param</span></td>
                  <td>Expression Class</td>
                  <td>Configurable scalar value used across M queries (e.g., environment URL, file path, threshold).</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-func">Func</span></td>
                  <td>Expression Class</td>
                  <td>Reusable custom Power Query M function dynamically invoked by transformation pipelines.</td>
                </tr>
                <tr>
                  <td><span class="badge badge-etl-inline">Inline</span></td>
                  <td>Expression Class</td>
                  <td>Static inline reference data or configuration table hardcoded via Power Query M literals.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>"""
        return DocSection(
            section_id="tab-legend",
            title="Tags &amp; Badges Legend",
            nav_label="Legend",
            content=content,
        )
