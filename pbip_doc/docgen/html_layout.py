"""
Master HTML Shell & Layout Builder for Native Documentation Portal.
Generates responsive executive layout with collapsible tree sidebar, client-side search,
breadcrumbs, and theme toggling.
100% Vanilla Python standard library.
"""

from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import html

from .config import DocGenConfig
from .utils import sanitize_filename, clean_project_name
from ..model_schema import resolve_expression_type_and_inline
from ..report_schema import PBIPReportModel
from .. import __version__


def resolve_html_theme_mode(html_theme: Optional[str]) -> Optional[str]:
    """Normalizes html_theme config into 'light', 'dark', or None (for 'auto')."""
    normalized = (html_theme or "auto").strip().lower()
    if normalized in ("light", "dark"):
        return normalized
    return None


def get_html_theme_attr(html_theme: Optional[str]) -> str:
    """Returns the HTML root data-theme attribute string for forced light/dark themes."""
    mode = resolve_html_theme_mode(html_theme)
    return f' data-theme="{mode}"' if mode else ""


def get_relative_root(current_path: str) -> str:
    """Calculates relative root path (e.g. '.', '..', '../..') from current file path."""
    parts = current_path.replace("\\", "/").strip("/").split("/")
    depth = len(parts) - 1
    if depth <= 0:
        return "."
    return "/".join([".."] * depth)


from .relationship_diagram import (
    ROLE_CONFIG,
    get_table_role_badge_class,
    get_table_role_short,
)


def get_expression_badge_info(expr_or_data: Any) -> Tuple[str, str, str]:
    """
    Returns canonical (badge_class, display_label, short_label) for a Power Query ETL expression.
    - badge_class: CSS badge class ('badge-etl-loaded', 'badge-etl-staging', etc.)
    - display_label: Standard label for titles and KPI cards ('Loaded', 'Staging', 'Param', 'Func', 'Inline')
    - short_label: Standard label for sidebar ('Loaded', 'Staging', 'Param', 'Func', 'Inline')
    """
    if isinstance(expr_or_data, str):
        k = expr_or_data.upper().strip()
    else:
        k = resolve_expression_type_and_inline(expr_or_data)["expression_type"]

    if k in ("LOADED_TABLE", "LOADED", "TABLE"):
        return "badge-etl-loaded", "Loaded", "Loaded"
    if k in ("PARAMETER", "PARAM"):
        return "badge-etl-param", "Param", "Param"
    if k in ("CUSTOM_FUNCTION", "FUNCTION", "FUNC"):
        return "badge-etl-func", "Func", "Func"
    if k in ("INLINE_TABLE", "INLINE"):
        return "badge-etl-inline", "Inline", "Inline"
    return "badge-etl-staging", "Staging", "Staging"


def get_sidebar_icon_svg(icon_choice: Optional[str] = "default", base_path: Optional[Path] = None, css_class: str = "sidebar-title-icon") -> str:
    """
    Resolves and returns HTML/SVG for sidebar header logo.
    Supports:
      - 'default' / 'logo' / 'pbip_doc_logo_large' / 'logo_large': Official extended PBIP Doc Gen logo with wordmark (pbip_doc_logo_large.svg)
      - 'pbip_doc_logo' / 'logo_compact': Official compact square isometric icon (pbip_doc_logo.svg)
      - Presets: 'cube', 'database', 'barchart', 'fabric', 'catalog', 'book'
      - Path to local .svg file (e.g. './pbip_doc_logo.svg')
      - Path to local .png / .jpg / .webp file (e.g. './logo.png' -> Base64 Data-URI <img>)
      - Direct inline <svg> or <img> snippet
      - Direct Data-URI ('data:image/...')
    100% Vanilla Python standard library with full offline capability.
    """
    choice = (icon_choice or "default").strip()

    # 1. Direct inline SVG, IMG, or Data-URI
    if choice.startswith("<svg"):
        if f'class="{css_class}"' not in choice:
            choice = choice.replace("<svg", f'<svg class="{css_class}"', 1)
        return choice

    if choice.startswith("<img"):
        if f'class="{css_class}"' not in choice:
            choice = choice.replace("<img", f'<img class="{css_class}"', 1)
        return choice

    if choice.startswith("data:image/"):
        return f'<img src="{choice}" class="{css_class}" alt="Logo">'

    # 2. Built-in presets & Official Logo
    key = choice.lower().replace(".svg", "").replace("-", "_")

    if key in ("cube", "semantic_model"):
        return f"""<svg class="{css_class}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
            <line x1="12" y1="22.08" x2="12" y2="12"></line>
          </svg>"""

    if key in ("database", "cylinder"):
        return f"""<svg class="{css_class}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
          </svg>"""

    if key in ("barchart", "chart", "analytics"):
        return f"""<svg class="{css_class}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="20" x2="18" y2="10"></line>
            <line x1="12" y1="20" x2="12" y2="4"></line>
            <line x1="6" y1="20" x2="6" y2="14"></line>
            <line x1="3" y1="20" x2="21" y2="20"></line>
          </svg>"""

    if key in ("fabric", "hexagon", "workspace"):
        return f"""<svg class="{css_class}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
            <path d="M2 17l10 5 10-5"></path>
            <path d="M2 12l10 5 10-5"></path>
          </svg>"""

    if key in ("catalog", "book"):
        return f"""<svg class="{css_class}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
          </svg>"""

    if key in ("default", "logo", "pbip_doc_logo_large", "logo_large"):
        return f"""<svg class="{css_class}" viewBox="0 0 500 180" fill="none">
            <g stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">
              <!-- Book 1 (Bottom) -->
              <g transform="translate(18, 74)">
                <path d="M 8,12 L 42,-9 V 43 L 0" fill="none" />
                <path d="M 8,12 C 2,16 12,24 22,19 L 41,7 V 58 L 22,71 C 12,76 2,68 8,64 Z" fill="none" />
                <line x1="22" y1="19" x2="22" y2="71" />
              </g>

              <!-- Book 2 (Middle) -->
              <g transform="translate(52, 48)">
                <path d="M 8,12 L 42,-9 V 69 L 0" fill="none" />
                <path d="M 8,12 C 2,16 12,24 22,19 L 41,7 V 85 L 22,97 C 12,102 2,94 8,90 Z" fill="none" />
                <line x1="22" y1="19" x2="22" y2="97" />
              </g>

              <!-- Book 3 (Top) -->
              <g transform="translate(86, 22)">
                <path d="M 8,12 L 42,-9 V 5 L 0" fill="none" />
                <path d="M 8,12 C 2,16 12,24 22,19 L 54,-1 V 103 L 22,123 C 12,128 2,120 8,116 Z" fill="none" />
                <line x1="22" y1="19" x2="22" y2="123" />

                <!-- Isometric Curly Brackets -->
                <g fill="none" stroke="currentColor" stroke-width="4" transform="translate(38, 61) scale(0.7) skewY(-31)">
                  <path d="M -4,-14 C -8,-14 -10,-12 -10,-8 C -10,-4 -12,-2 -14,0 C -12,2 -10,4 -10,8 C -10,12 -8,14 -4,14" />
                  <path d="M 4,-14 C 8,-14 10,-12 10,-8 C 10,-4 12,-2 14,0 C 12,2 10,4 10,8 C 10,12 8,14 4,14" />
                </g>

                <!-- Ribbon Bookmark -->
                <polygon points="33.2,12 41.2,7 41.2,34 37.2,30 33.2,37" fill="currentColor" stroke="none" />
                <line x1="22" y1="19" x2="54" y2="-1" />
              </g>
            </g>

            <!-- Project Name -->
            <text x="160" y="80" fill="currentColor" font-family="system-ui, -apple-system, BlinkMacSystemFont, &#39;Segoe UI&#39;, Roboto, Helvetica, Arial, sans-serif" font-size="73" font-weight="600" letter-spacing="-0.03em" dominant-baseline="central">pbip-doc</text>
          </svg>"""

    if key in ("pbip_doc_logo", "logo_compact"):
        return f"""<svg class="{css_class}" viewBox="0 0 180 180" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
            <g stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round">
              <!-- Book 1 (Bottom) -->
              <g transform="translate(18, 74)">
                <path d="M 8,12 L 42,-9 V 43 L 0" fill="none" />
                <path d="M 8,12 C 2,16 12,24 22,19 L 41,7 V 58 L 22,71 C 12,76 2,68 8,64 Z" fill="none" />
                <line x1="22" y1="19" x2="22" y2="71" />
              </g>

              <!-- Book 2 (Middle) -->
              <g transform="translate(52, 48)">
                <path d="M 8,12 L 42,-9 V 69 L 0" fill="none" />
                <path d="M 8,12 C 2,16 12,24 22,19 L 41,7 V 85 L 22,97 C 12,102 2,94 8,90 Z" fill="none" />
                <line x1="22" y1="19" x2="22" y2="97" />
              </g>

              <!-- Book 3 (Top) -->
              <g transform="translate(86, 22)">
                <path d="M 8,12 L 42,-9 V 5 L 0" fill="none" />
                <path d="M 8,12 C 2,16 12,24 22,19 L 54,-1 V 103 L 22,123 C 12,128 2,120 8,116 Z" fill="none" />
                <line x1="22" y1="19" x2="22" y2="123" />

                <!-- Isometric Curly Brackets -->
                <g fill="none" stroke="currentColor" stroke-width="2" transform="translate(38, 61) scale(0.7) skewY(-31)">
                  <path d="M -4,-14 C -8,-14 -10,-12 -10,-8 C -10,-4 -12,-2 -14,0 C -12,2 -10,4 -10,8 C -10,12 -8,14 -4,14" />
                  <path d="M 4,-14 C 8,-14 10,-12 10,-8 C 10,-4 12,-2 14,0 C 12,2 10,4 10,8 C 10,12 8,14 4,14" />
                </g>

                <!-- Ribbon Bookmark -->
                <polygon points="33.2,12 41.2,7 41.2,34 37.2,30 33.2,37" fill="currentColor" stroke="none" />
                <line x1="22" y1="19" x2="54" y2="-1" />
              </g>
            </g>
          </svg>"""

    # 3. Path to local image file (.svg, .png, .jpg, .webp, etc.)
    file_candidate = None
    for p in [Path(choice), (base_path / choice if base_path else None), Path.cwd() / choice]:
        if p and p.is_file():
            file_candidate = p
            break

    if file_candidate and file_candidate.is_file():
        suffix = file_candidate.suffix.lower()
        if suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
            try:
                import base64
                mime = "image/png" if suffix == ".png" else ("image/jpeg" if suffix in (".jpg", ".jpeg") else f"image/{suffix.lstrip('.')}")
                with open(file_candidate, "rb") as bf:
                    b64_data = base64.b64encode(bf.read()).decode("ascii")
                return f'<img src="data:{mime};base64,{b64_data}" class="{css_class}" alt="Logo">'
            except Exception:
                pass
        else:
            try:
                with open(file_candidate, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content.startswith("<svg"):
                    if f'class="{css_class}"' not in content:
                        content = content.replace("<svg", f'<svg class="{css_class}"', 1)
                    return content
            except Exception:
                pass

    # Fallback to default
    return get_sidebar_icon_svg("default", css_class=css_class)


class HtmlLayoutBuilder:
    """
    Renders the outer HTML5 responsive shell wrapping all modular documentation pages.
    """

    def __init__(
        self,
        project_name: str,
        data: Dict[str, Any],
        config: DocGenConfig,
        report_model: Optional[PBIPReportModel] = None,
    ):
        self.project_name = project_name
        self.data = data
        self.config = config
        self.report = report_model

    def wrap_page(
        self,
        current_path: str,
        page_title: str,
        breadcrumbs: List[Tuple[str, Optional[str]]],
        content_html: str,
    ) -> str:
        """
        Wraps content_html into complete HTML document with sidebar, topbar, and assets.
        """
        rel_root = get_relative_root(current_path)
        css_url = f"{rel_root}/assets/style.css"
        index_url = f"{rel_root}/index{self.config.html_ext_suffix}"

        sidebar_html = self._build_sidebar(current_path, rel_root)
        breadcrumbs_html = self._build_breadcrumbs(breadcrumbs)

        escaped_title = html.escape(page_title)
        escaped_project = html.escape(self.config.html_title or self.project_name)

        sidebar_icon_svg = get_sidebar_icon_svg(self.config.sidebar_icon)
        theme_attr = get_html_theme_attr(self.config.html_theme)

        return f"""<!DOCTYPE html>
<html lang="en"{theme_attr}>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{escaped_title} - {escaped_project} Documentation</title>
  <link rel="stylesheet" href="{css_url}">
</head>
<body>
  <div class="wiki-layout">
    <input type="checkbox" id="sidebar-toggle" class="sidebar-toggle-input" hidden>
    <aside class="wiki-sidebar" id="sidebar">
      <div class="sidebar-header">
        <a href="{index_url}" class="sidebar-title-link" title="{escaped_project}">
          <div class="sidebar-logo-image">
            {sidebar_icon_svg}
          </div>
          <div class="sidebar-logo-text">
            <span>{escaped_project}</span>
            <span class="sidebar-badge">Docs</span>
          </div>
        </a>
      </div>
      <nav class="sidebar-nav">
{sidebar_html}
      </nav>
      <div class="sidebar-footer">
        <div class="sidebar-footer-info">
          <span class="footer-lbl">Generated by</span>
          <span class="footer-app">pbip-doc</span>
          <span class="footer-version">v{__version__}</span>
        </div>
      </div>
    </aside>

    <div class="wiki-main">
      <header class="wiki-topbar">
        <label for="sidebar-toggle" class="sidebar-toggle-btn" title="Toggle Sidebar">
          <svg class="sidebar-toggle-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        </label>
        <div class="breadcrumbs">
{breadcrumbs_html}
        </div>
      </header>

      <main class="wiki-article">
{content_html}
      </main>
    </div>
  </div>
</body>
</html>
"""

    def _build_breadcrumbs(self, breadcrumbs: List[Tuple[str, Optional[str]]]) -> str:
        lines = []
        for idx, (label, link) in enumerate(breadcrumbs):
            escaped_lbl = html.escape(label)
            if idx > 0:
                lines.append('<span class="breadcrumb-sep">/</span>')
            if link:
                lines.append(f'<a href="{html.escape(link)}">{escaped_lbl}</a>')
            else:
                lines.append(f'<span class="breadcrumb-current">{escaped_lbl}</span>')
        return " ".join(lines)

    def _build_sidebar(self, current_path: str, rel_root: str) -> str:
        lines = []
        ext_sfx = self.config.html_ext_suffix
        index_active = " active" if current_path == f"index{ext_sfx}" else ""
        lines.append(f"""        <div class="nav-section">
          <ul class="nav-list">
            <li class="nav-item">
              <a href="{rel_root}/index{ext_sfx}" class="nav-link{index_active}">
                <span>Model Overview</span>
              </a>
            </li>
          </ul>
        </div>""")

        # 1. Dataflow Section
        if self.config.include_expression_docs and getattr(self.config, "include_expression_sidebar_chapter", False):
            exprs = self.data.get("expressions") or self.data.get("shared_queries") or []
            if exprs:
                lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Dataflow</span>
            <span class="sidebar-badge">{len(exprs)}</span>
          </div>
          <ul class="nav-list">""")
                df_overview_path = f"{self.config.clean_expressions_subdir}/index{ext_sfx}"
                df_overview_active = " active" if current_path == df_overview_path else ""
                lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{df_overview_path}" class="nav-link{df_overview_active}">
                <span>Dataflow Overview</span>
              </a>
            </li>""")
                for e in exprs:
                    q_name = e.get("query_name") or "Expression"
                    clean_q = sanitize_filename(q_name)
                    e_rel = f"{self.config.clean_expressions_subdir}/{clean_q}{ext_sfx}"
                    is_active = " active" if current_path == e_rel else ""
                    b_class, _, b_short = get_expression_badge_info(e)
                    badge_tag = f'<span class="nav-badge-cell"><span class="nav-item-badge badge {b_class}">{b_short}</span></span>'

                    lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{e_rel}" class="nav-link{is_active}">
                <span>{html.escape(q_name)}</span>
                {badge_tag}
              </a>
            </li>""")
                lines.append("          </ul>\n        </div>")

        # 2. Tables Section (Model)
        tables = [t for t in self.data.get("tables", []) if self.config.is_table_published(t)]
        if self.config.include_models and tables:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Tables</span>
            <span class="sidebar-badge">{len(tables)}</span>
          </div>
          <ul class="nav-list">""")
            for t in sorted(tables, key=lambda x: x.get("name", "")):
                t_name = t.get("name", "Table")
                clean_name = sanitize_filename(t_name)
                t_rel = f"{self.config.clean_tables_subdir}/{clean_name}{ext_sfx}"
                is_active = " active" if current_path == t_rel else ""
                role = t.get("role", "DIM")
                role_class = get_table_role_badge_class(role)
                role_short = get_table_role_short(role)

                lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{t_rel}" class="nav-link{is_active}" title="{html.escape(t_name)}">
                <span>{html.escape(t_name)}</span>
                <span class="nav-badge-cell"><span class="nav-item-badge badge {role_class}">{role_short}</span></span>
              </a>
            </li>""")
            lines.append("          </ul>\n        </div>")

        # 3. Measures Section (Model - Grouped by host table)
        published_measures = [m for m in self.data.get("measures", []) if self.config.is_measure_published(m)]
        # Fallback if self.data["measures"] was empty
        if not published_measures:
            for t in tables:
                for m in t.get("measures", []):
                    if not m.get("table"):
                        m["table"] = t.get("name")
                    if self.config.is_measure_published(m):
                        published_measures.append(m)

        if self.config.include_models and published_measures:
            measures_by_table: Dict[str, List[Dict[str, Any]]] = {}
            for m in published_measures:
                tbl = m.get("table", "Model")
                measures_by_table.setdefault(tbl, []).append(m)

            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Measures</span>
            <span class="sidebar-badge">{len(published_measures)}</span>
          </div>
          <ul class="nav-list">""")

            for tbl, m_list in sorted(measures_by_table.items()):
                clean_tbl = sanitize_filename(tbl)
                is_current_table = current_path.startswith(f"{self.config.clean_measures_subdir}/{clean_tbl}/")
                open_attr = " open" if is_current_table else ""

                lines.append(f"""            <li class="nav-subgroup">
              <details class="nav-details"{open_attr}>
                <summary class="nav-subgroup-header">
                  <span>{html.escape(tbl)} ({len(m_list)})</span>
                </summary>
                <ul class="nav-list nav-subgroup-items">""")

                for m in sorted(m_list, key=lambda x: x.get("name", "")):
                    m_name = m.get("name", "Measure")
                    clean_m = sanitize_filename(m_name)
                    m_rel = f"{self.config.clean_measures_subdir}/{clean_tbl}/{clean_m}{ext_sfx}"
                    is_active = " active" if current_path == m_rel else ""
                    lines.append(f"""                <li class="nav-item">
                  <a href="{rel_root}/{m_rel}" class="nav-link{is_active}" title="{html.escape(m_name)}">
                    <span>{html.escape(m_name)}</span>
                  </a>
                </li>""")
                lines.append("                </ul>\n              </details>\n            </li>")

            lines.append("          </ul>\n        </div>")

        # 4. Functions Section (Model)
        funcs = self.data.get("functions", [])
        if self.config.include_models and funcs:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Functions</span>
            <span class="sidebar-badge">{len(funcs)}</span>
          </div>
          <ul class="nav-list">""")
            for fn in funcs:
                f_name = fn.get("name") or "Function"
                clean_f = sanitize_filename(f_name)
                f_rel = f"{self.config.clean_functions_subdir}/{clean_f}{ext_sfx}"
                is_active = " active" if current_path == f_rel else ""
                lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{f_rel}" class="nav-link{is_active}">
                <span>{html.escape(f_name)}</span>
              </a>
            </li>""")
            lines.append("          </ul>\n        </div>")

        # 5. Report & Visual Pages Section (Report)
        if self.config.include_reports and self.config.include_visual_docs and self.report and self.report.pages:
            lines.append(f"""        <div class="nav-section">
          <div class="nav-section-title">
            <span>Report Pages</span>
            <span class="sidebar-badge">{len(self.report.pages)}</span>
          </div>
          <ul class="nav-list">""")
            for p_idx, p in enumerate(self.report.pages, start=1):
                clean_p = sanitize_filename(p.display_name)
                p_rel = f"{self.config.clean_visuals_subdir}/{clean_p}{ext_sfx}"
                is_active = " active" if current_path == p_rel else ""
                p_num = getattr(p, "page_number", p_idx) or p_idx
                lines.append(f"""            <li class="nav-item">
              <a href="{rel_root}/{p_rel}" class="nav-link{is_active}" title="{html.escape(p.display_name)}">
                <span>{html.escape(p.display_name)}</span>
                <span class="nav-badge-cell"><span class="nav-item-badge badge badge-dim">#{p_num}</span></span>
              </a>
            </li>""")
            lines.append("          </ul>\n        </div>")

        return "\n".join(lines)
