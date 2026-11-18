"""
3-Level Layout-as-Code Configuration Engine (Document -> Radio Tab -> Block [Riquadro] -> Functions).
Enables declarative composition, reordering, grouping, and styling of documentation pages.
100% Python Standard Library. Zero external dependencies.
"""

from dataclasses import dataclass, field
import html
import json
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, Set


def slugify(text: str) -> str:
    """Converts a label into a clean, URL-safe and CSS-safe slug identifier."""
    if not text:
        return "item"
    cleaned = re.sub(r'[^a-zA-Z0-9_\-]+', '-', text.lower().strip())
    cleaned = re.sub(r'-+', '-', cleaned).strip('-')
    return cleaned or "item"


@dataclass
class BlockLayout:
    """
    Level 3: Block (Riquadro unico).
    Aggregates the output of one or more atomic generator functions into a single visual card (.content-card).
    """
    id: str
    title: Optional[str] = None
    functions: List[str] = field(default_factory=list)
    css_class: Optional[str] = None


@dataclass
class TabLayout:
    """
    Level 2: Radio Tab.
    Represents an interactive horizontal tab containing one or more blocks.
    """
    id: str
    label: str
    blocks: List[BlockLayout] = field(default_factory=list)


@dataclass
class DocumentLayout:
    """
    Level 1: Document.
    Root specification for a documentation page archetype (e.g. table, model, measure).
    """
    document_type: str
    tabs: List[TabLayout] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Default 3-Level Layout Configurations (100% Backward-Compatible)
# ---------------------------------------------------------------------------

DEFAULT_LAYOUT_CONFIG: Dict[str, Dict[str, Any]] = {
    "table": {
        "tabs": [
            {
                "id": "tab-summary",
                "label": "Summary",
                "blocks": [
                    {"id": "desc_block", "functions": ["description"]},
                    {"id": "dax_block", "functions": ["dax_formula", "referenced_columns"]},
                    {"id": "diagram_block", "functions": ["relationship_diagram"]},
                    {"id": "sources_block", "functions": ["data_source_summary", "upstream_pipeline"]},
                ]
            },
            {
                "id": "tab-cols",
                "label": "Table Columns",
                "blocks": [
                    {"id": "cols_block", "functions": ["data_dictionary"]}
                ]
            },
            {
                "id": "tab-calc-cols",
                "label": "DAX Calculated Columns",
                "blocks": [
                    {"id": "calc_cols_block", "functions": ["calculated_columns"]}
                ]
            },
            {
                "id": "tab-rels",
                "label": "Relationships",
                "blocks": [
                    {"id": "rels_block", "functions": ["relationship_table"]}
                ]
            },
            {
                "id": "tab-meas",
                "label": "Measures",
                "blocks": [
                    {"id": "meas_block", "functions": ["measures"]}
                ]
            },
            {
                "id": "tab-details",
                "label": "Details",
                "blocks": [
                    {"id": "details_block", "functions": ["details"]},
                    {"id": "legend_block", "functions": ["badge_legend"]},
                ]
            }
        ]
    },
    "model": {
        "tabs": [
            {
                "id": "tab-summary",
                "label": "Summary",
                "blocks": [
                    {"id": "desc_block", "functions": ["description"]},
                    {"id": "star_schema_block", "functions": ["star_schema_diagram"]},
                    {"id": "sources_block", "functions": ["physical_data_sources"]},
                ]
            },
            {
                "id": "tab-tables",
                "label": "Tables List",
                "blocks": [
                    {"id": "tables_block", "functions": ["published_tables"]}
                ]
            },
            {
                "id": "tab-relationships",
                "label": "Relationships",
                "blocks": [
                    {"id": "relationships_block", "functions": ["relationship_table"]}
                ]
            },
            {
                "id": "tab-functions",
                "label": "User Defined Functions (UDF)",
                "blocks": [
                    {"id": "functions_block", "functions": ["udf_functions"]}
                ]
            },
            {
                "id": "tab-measures",
                "label": "Measures",
                "blocks": [
                    {"id": "measures_block", "functions": ["measures"]}
                ]
            },
            {
                "id": "tab-reports",
                "label": "Reports",
                "blocks": [
                    {"id": "reports_block", "functions": ["reports"]}
                ]
            },
            {
                "id": "tab-details",
                "label": "Details",
                "blocks": [
                    {"id": "details_block", "functions": ["details"]},
                    {"id": "legend_block", "functions": ["badge_legend"]},
                ]
            }
        ]
    },
    "measure": {
        "tabs": [
            {
                "id": "tab-definition",
                "label": "Definition",
                "blocks": [
                    {"id": "desc_block", "functions": ["description"]},
                    {"id": "dax_block", "functions": ["dax_formula"]},
                    {"id": "cols_block", "functions": ["referenced_columns"]},
                ]
            },
            {
                "id": "tab-dependencies",
                "label": "Dependencies",
                "blocks": [
                    {"id": "upstream_block", "functions": ["direct_dependencies"]},
                    {"id": "downstream_block", "functions": ["downstream_dependencies"]},
                ]
            },
            {
                "id": "tab-details",
                "label": "Details",
                "blocks": [
                    {"id": "details_block", "functions": ["details"]},
                    {"id": "legend_block", "functions": ["badge_legend"]},
                ]
            }
        ]
    },
    "expression": {
        "tabs": [
            {
                "id": "tab-definitions",
                "label": "Definitions",
                "blocks": [
                    {"id": "desc_block", "functions": ["description"]},
                    {"id": "params_block", "functions": ["function_parameters"]},
                    {"id": "inline_block", "functions": ["inline_definition"]},
                    {"id": "steps_m_block", "functions": ["lineage_steps", "power_query_m"]},
                    {"id": "unused_block", "functions": ["unused_steps"]},
                ]
            },
            {
                "id": "tab-calc-cols",
                "label": "Calculated Columns",
                "blocks": [
                    {"id": "calc_cols_block", "functions": ["calculated_columns"]}
                ]
            },
            {
                "id": "tab-dependencies",
                "label": "Dependencies",
                "blocks": [
                    {"id": "upstream_block", "functions": ["upstream_dependencies"]},
                    {"id": "downstream_block", "functions": ["downstream_dependents"]},
                ]
            },
            {
                "id": "tab-details",
                "label": "Details",
                "blocks": [
                    {"id": "details_block", "functions": ["details"]},
                    {"id": "legend_block", "functions": ["badge_legend"]},
                ]
            }
        ]
    },
    "function": {
        "tabs": [
            {
                "id": "tab-definition",
                "label": "Definition",
                "blocks": [
                    {"id": "desc_block", "functions": ["description"]},
                    {"id": "params_block", "functions": ["parameters"]},
                    {"id": "dax_block", "functions": ["dax_formula"]},
                    {"id": "cols_block", "functions": ["referenced_columns"]},
                ]
            },
            {
                "id": "tab-dependencies",
                "label": "Dependencies",
                "blocks": [
                    {"id": "upstream_block", "functions": ["upstream_dependency"]},
                    {"id": "downstream_block", "functions": ["downstream_dependents"]},
                ]
            },
            {
                "id": "tab-details",
                "label": "Details",
                "blocks": [
                    {"id": "details_block", "functions": ["details"]},
                    {"id": "legend_block", "functions": ["badge_legend"]},
                ]
            }
        ]
    },
    "visual_page": {
        "tabs": [
            {
                "id": "tab-context",
                "label": "Page Context",
                "blocks": [
                    {"id": "desc_block", "functions": ["description"]},
                    {"id": "filters_block", "functions": ["filter_context"]},
                ]
            },
            {
                "id": "tab-visuals",
                "label": "Dynamic Visuals",
                "blocks": [
                    {"id": "visuals_block", "functions": ["visuals"]}
                ]
            },
            {
                "id": "tab-details",
                "label": "Details",
                "blocks": [
                    {"id": "spatial_block", "functions": ["spatial_layout"]},
                    {"id": "legend_block", "functions": ["badge_legend"]},
                ]
            }
        ]
    },
    "dataflow_overview": {
        "tabs": [
            {
                "id": "tab-queries",
                "label": "Query List",
                "blocks": [
                    {"id": "sources_block", "functions": ["data_source_summary"]},
                    {"id": "loaded_block", "functions": ["loaded_tables"]},
                    {"id": "staging_block", "functions": ["staging_queries"]},
                    {"id": "params_funcs_block", "functions": ["parameters_and_functions"]},
                ]
            },
            {
                "id": "tab-legend",
                "label": "Legend",
                "blocks": [
                    {"id": "legend_block", "functions": ["badge_legend"]}
                ]
            }
        ]
    },
    "report_overview": {
        "tabs": [
            {
                "id": "tab-summary",
                "label": "Summary",
                "blocks": [
                    {"id": "desc_block", "functions": ["description"]},
                    {"id": "models_block", "functions": ["models"]},
                    {"id": "pages_block", "functions": ["pages"]},
                ]
            }
        ]
    }
}


# ---------------------------------------------------------------------------
# Normalization & Schema Parsing
# ---------------------------------------------------------------------------

def normalize_document_layout(raw_layout: Any, doc_type: str) -> DocumentLayout:
    """
    Parses and normalizes raw configuration (canonical 3-level list or dict shorthand)
    into a typed DocumentLayout.
    """
    if not raw_layout:
        raw_layout = DEFAULT_LAYOUT_CONFIG.get(doc_type, {})

    # If already DocumentLayout, return as is
    if isinstance(raw_layout, DocumentLayout):
        return raw_layout

    # 1. Canonical list of tabs: {"tabs": [{"id": ..., "label": ..., "blocks": [...]}]}
    if isinstance(raw_layout, dict) and "tabs" in raw_layout and isinstance(raw_layout["tabs"], list):
        tabs: List[TabLayout] = []
        for t_idx, t in enumerate(raw_layout["tabs"]):
            if not isinstance(t, dict):
                continue
            t_label = t.get("label") or t.get("title") or f"Tab {t_idx + 1}"
            t_id = t.get("id") or (f"tab-{slugify(t_label)}" if not slugify(t_label).startswith("tab-") else slugify(t_label))
            
            blocks: List[BlockLayout] = []
            for b_idx, b in enumerate(t.get("blocks", [])):
                if isinstance(b, dict):
                    b_title = b.get("title")
                    b_id = b.get("id") or slugify(b_title or f"block_{b_idx + 1}")
                    funcs = b.get("functions") or b.get("items") or []
                    if isinstance(funcs, str):
                        funcs = [funcs]
                    blocks.append(BlockLayout(id=b_id, title=b_title, functions=funcs, css_class=b.get("css_class")))
                elif isinstance(b, str):
                    # Shorthand: string function ID
                    blocks.append(BlockLayout(id=b, title=None, functions=[b]))
                elif isinstance(b, list):
                    # Shorthand: list of functions
                    blocks.append(BlockLayout(id=f"block_{b_idx + 1}", functions=b))
            
            tabs.append(TabLayout(id=t_id, label=t_label, blocks=blocks))
        return DocumentLayout(document_type=doc_type, tabs=tabs)

    # 2. Dict shorthand: {"Tab Label": {"Block Name": ["fn1", "fn2"]} or [{"title": ..., "functions": ...}] or ["fn1", "fn2"]}
    if isinstance(raw_layout, dict):
        tabs = []
        for tab_label, tab_val in raw_layout.items():
            t_id = f"tab-{slugify(tab_label)}" if not slugify(tab_label).startswith("tab-") else slugify(tab_label)
            blocks = []
            
            if isinstance(tab_val, dict):
                for b_name, b_val in tab_val.items():
                    b_id = slugify(b_name)
                    if isinstance(b_val, list):
                        blocks.append(BlockLayout(id=b_id, title=b_name, functions=b_val))
                    elif isinstance(b_val, dict):
                        b_funcs = b_val.get("functions") or b_val.get("items") or []
                        if isinstance(b_funcs, str):
                            b_funcs = [b_funcs]
                        b_title = b_val.get("title", b_name)
                        blocks.append(BlockLayout(id=b_id, title=b_title, functions=b_funcs, css_class=b_val.get("css_class")))
                    elif isinstance(b_val, str):
                        blocks.append(BlockLayout(id=b_id, title=b_name, functions=[b_val]))
            elif isinstance(tab_val, list):
                # Could be list of block objects or list of function strings
                all_strings = all(isinstance(x, str) for x in tab_val)
                if all_strings:
                    # 1 single block uniting all functions in this tab
                    blocks.append(BlockLayout(id=f"{slugify(tab_label)}_block", title=None, functions=tab_val))
                else:
                    for b_idx, b in enumerate(tab_val):
                        if isinstance(b, dict):
                            b_title = b.get("title")
                            b_id = b.get("id") or slugify(b_title or f"block_{b_idx + 1}")
                            funcs = b.get("functions") or b.get("items") or []
                            if isinstance(funcs, str):
                                funcs = [funcs]
                            blocks.append(BlockLayout(id=b_id, title=b_title, functions=funcs, css_class=b.get("css_class")))
                        elif isinstance(b, str):
                            blocks.append(BlockLayout(id=b, functions=[b]))
                        elif isinstance(b, list):
                            blocks.append(BlockLayout(id=f"block_{b_idx + 1}", functions=b))
            
            tabs.append(TabLayout(id=t_id, label=tab_label, blocks=blocks))
        return DocumentLayout(document_type=doc_type, tabs=tabs)

    # Fallback to default
    return normalize_document_layout(DEFAULT_LAYOUT_CONFIG.get(doc_type, {}), doc_type)


# ---------------------------------------------------------------------------
# Declarative Opt-In Tabs (AI RAG Semantic Context)
# ---------------------------------------------------------------------------

RAG_OPT_IN_FLAGS: Dict[str, str] = {
    "table": "include_table_rag_hints",
    "measure": "include_measure_rag_hints",
    "function": "include_function_rag_hints",
    "expression": "include_expression_rag_hints",
}

RAG_DECLARATIVE_TAB = TabLayout(
    id="tab-rag",
    label="Semantic Context",
    blocks=[BlockLayout(id="rag_block", functions=["rag"])],
)


def resolve_declarative_opt_in_tabs(
    layout: DocumentLayout,
    doc_type: str,
    config: Optional[Any] = None,
) -> DocumentLayout:
    """
    Pure declarative resolution for opt-in documentation tabs (e.g. AI RAG semantic hints).
    Applies immutable functional composition without runtime deepcopy or procedural tree mutations.
    """
    if config is None:
        return layout

    flag_name = RAG_OPT_IN_FLAGS.get(doc_type)
    if not (flag_name and getattr(config, flag_name, False)):
        return layout

    has_rag = any(
        any(fn in ("rag", "rag_context") for fn in b.functions)
        for t in layout.tabs
        for b in t.blocks
    )
    if has_rag:
        return layout

    return DocumentLayout(
        document_type=layout.document_type,
        tabs=list(layout.tabs) + [RAG_DECLARATIVE_TAB],
    )


def get_effective_document_layout(
    doc_type: str,
    config: Optional[Any] = None,
    layout_override: Optional[Union[Dict[str, Any], DocumentLayout]] = None,
) -> DocumentLayout:
    """Resolves effective layout configuration for a document type."""
    if layout_override is not None:
        if isinstance(layout_override, DocumentLayout):
            layout = layout_override
        elif isinstance(layout_override, dict):
            if doc_type in layout_override:
                layout = normalize_document_layout(layout_override[doc_type], doc_type)
            else:
                layout = normalize_document_layout(layout_override, doc_type)
        else:
            layout = normalize_document_layout(DEFAULT_LAYOUT_CONFIG.get(doc_type, {}), doc_type)
    elif config is not None:
        cfg_dict = getattr(config, "get_layout_config", lambda: {})()
        if cfg_dict and doc_type in cfg_dict:
            layout = normalize_document_layout(cfg_dict[doc_type], doc_type)
        else:
            layout = normalize_document_layout(DEFAULT_LAYOUT_CONFIG.get(doc_type, {}), doc_type)
    else:
        layout = normalize_document_layout(DEFAULT_LAYOUT_CONFIG.get(doc_type, {}), doc_type)

    return resolve_declarative_opt_in_tabs(layout, doc_type, config)


# ---------------------------------------------------------------------------
# Card Extraction & Multi-Function Block Assembly
# ---------------------------------------------------------------------------

def extract_card_content(card_html: str) -> Tuple[Optional[str], str]:
    """
    Extracts the title and inner body HTML from a rendered .content-card div.
    Returns (card_title, inner_html).
    """
    if not card_html or not card_html.strip():
        return None, ""

    clean = card_html.strip()
    match = re.search(r'<h3 class="content-card-title">(.*?)</h3>', clean, re.DOTALL)
    title = match.group(1).strip() if match else None

    # Strip opening <div class="content-card..."> and closing </div>
    inner = clean
    inner = re.sub(r'^\s*<div\b[^>]*class="[^"]*content-card[^"]*"[^>]*>', '', inner, count=1)
    inner = re.sub(r'</div>\s*$', '', inner, count=1)

    # Strip the <h3 class="content-card-title"> if it was at the top of inner
    if match:
        inner = re.sub(r'^\s*<h3 class="content-card-title">.*?</h3>', '', inner, count=1, flags=re.DOTALL)

    return title, inner.strip()


def render_block(
    block: BlockLayout,
    registry: Dict[str, Callable[[], Any]],
) -> Optional[str]:
    """
    Renders a single Block (Riquadro).
    Executes all functions listed in block.functions.
    If multiple functions are present, combines their outputs into a single .content-card (riquadro unico).
    If all functions return empty/None, returns None.
    """
    from .section_engine import DocSection

    fn_outputs: List[Tuple[str, str, Optional[str]]] = []  # (fn_id, raw_content, title)

    for fn_id in block.functions:
        fn = registry.get(fn_id)
        if not fn:
            continue
        try:
            res = fn()
        except Exception:
            continue

        if res is None:
            continue

        if isinstance(res, DocSection):
            raw_content = res.content.strip() if res.content else ""
            res_title = res.title or res.nav_label
        elif isinstance(res, str):
            raw_content = res.strip()
            res_title = None
        else:
            raw_content = str(res).strip()
            res_title = None

        if raw_content:
            fn_outputs.append((fn_id, raw_content, res_title))

    if not fn_outputs:
        return None

    css_cls = f" {block.css_class}" if block.css_class else ""

    # Case 1: Exactly 1 function in block -> preserve card as is
    if len(fn_outputs) == 1:
        fn_id, raw_html, res_title = fn_outputs[0]
        if 'class="content-card' in raw_html:
            if block.title:
                if '<h3 class="content-card-title">' in raw_html:
                    raw_html = re.sub(
                        r'<h3 class="content-card-title">.*?</h3>',
                        f'<h3 class="content-card-title">{html.escape(block.title)}</h3>',
                        raw_html,
                        count=1,
                        flags=re.DOTALL,
                    )
            if 'id="block-' not in raw_html and block.id:
                if not re.search(r'<div\b[^>]*\bid="[^"]*"', raw_html):
                    raw_html = re.sub(
                        r'<div\b([^>]*class="[^"]*content-card[^"]*")',
                        f'<div id="block-{html.escape(block.id)}"\\1',
                        raw_html,
                        count=1,
                    )
            return raw_html
        else:
            title_str = block.title or res_title
            title_html = f'          <h3 class="content-card-title">{html.escape(title_str)}</h3>\n' if title_str else ""
            return f"""        <div class="content-card{css_cls}" id="block-{html.escape(block.id)}">
{title_html}          {raw_html}
        </div>"""

    # Case 2: 2 or more functions combined into a SINGLE riquadro (.content-card)!
    items: List[str] = []
    for fn_id, raw_html, res_title in fn_outputs:
        if 'class="content-card' in raw_html:
            extracted_title, inner_body = extract_card_content(raw_html)
            title = extracted_title or res_title or fn_id.replace("_", " ").title()
        else:
            inner_body = raw_html
            title = res_title or fn_id.replace("_", " ").title()

        subtitle_html = f'            <h4 class="content-block-subtitle">{html.escape(title)}</h4>\n' if title else ""
        item_html = f"""          <div class="content-block-section" id="fn-{html.escape(fn_id)}">
{subtitle_html}            {inner_body}
          </div>"""
        items.append(item_html)

    block_title_html = f'          <h3 class="content-card-title">{html.escape(block.title)}</h3>\n' if block.title else ""
    return f"""        <div class="content-card{css_cls}" id="block-{html.escape(block.id)}">
{block_title_html}{chr(10).join(items)}
        </div>"""


def render_document_tabs(
    doc_type: str,
    registry: Dict[str, Callable[[], Any]],
    config: Optional[Any] = None,
    layout_override: Optional[Union[Dict[str, Any], DocumentLayout]] = None,
) -> List[Any]:
    """
    Renders all configured tabs and blocks for a given document type.
    Returns an ordered list of DocSection objects ready for assemble_html_document().
    """
    from .section_engine import DocSection

    layout = get_effective_document_layout(doc_type, config=config, layout_override=layout_override)

    sections: List[DocSection] = []

    for tab in layout.tabs:
        rendered_blocks: List[str] = []
        for block in tab.blocks:
            b_html = render_block(block, registry)
            if b_html and b_html.strip():
                rendered_blocks.append(b_html.strip())

        if rendered_blocks:
            tab_content = "\n\n".join(rendered_blocks)
            sections.append(
                DocSection(
                    section_id=tab.id,
                    title=tab.label,
                    nav_label=tab.label,
                    content=tab_content,
                )
            )

    return sections


def get_default_layout_json(indent: int = 2) -> str:
    """Exports the entire default layout configuration as a clean JSON string."""
    return json.dumps(DEFAULT_LAYOUT_CONFIG, indent=indent)


def render_document_html(
    doc_type: str,
    header_html: str,
    kpis_html: str,
    registry: Dict[str, Callable[[], Any]],
    config: Optional[Any] = None,
    layout_override: Optional[Union[Dict[str, Any], DocumentLayout]] = None,
    template: Optional[str] = None,
) -> str:
    """
    Renders an HTML documentation page according to the configured document layout.
    Uses an explicit template with placeholders ({{PAGE_HEADER}}, {{PAGE_KPIS}},
    {{PAGE_TAB_RADIOS}}, {{PAGE_TAB_STYLES}}, {{PAGE_TAB_NAV}}, {{PAGE_TAB_PANELS}}),
    which are populated via for-loops driven by the layout for the given doc_type.
    Falls back automatically to DEFAULT_LAYOUT_CONFIG[doc_type] if not explicitly declared.
    """
    from .section_engine import assemble_html_document

    sections = render_document_tabs(
        doc_type=doc_type,
        registry=registry,
        config=config,
        layout_override=layout_override,
    )

    return assemble_html_document(
        header_html=header_html,
        kpis_html=kpis_html,
        sections=sections,
        template=template,
    )


def render_document_markdown(
    doc_type: str,
    frontmatter_str: Optional[str],
    header_block: Optional[str],
    registry: Dict[str, Callable[[], Any]],
    config: Optional[Any] = None,
    layout_override: Optional[Union[Dict[str, Any], DocumentLayout]] = None,
) -> str:
    """
    Renders a Markdown documentation page according to the declarative document layout.
    Ensures layout parity with the interactive HTML engine while producing clean, RAG-ready markdown.
    """
    from .section_engine import DocSection

    layout = get_effective_document_layout(doc_type, config=config, layout_override=layout_override)

    parts: List[str] = []

    if frontmatter_str and frontmatter_str.strip():
        parts.append(frontmatter_str.strip())

    if header_block and header_block.strip():
        parts.append(header_block.strip())

    executed_fns: Set[str] = set()

    for tab in layout.tabs:
        for block in tab.blocks:
            for fn_id in block.functions:
                if fn_id in executed_fns:
                    continue
                executed_fns.add(fn_id)

                fn = registry.get(fn_id)
                if not fn:
                    continue
                try:
                    res = fn()
                except Exception:
                    continue

                if res is None:
                    continue

                if isinstance(res, DocSection):
                    content = res.content.strip() if res.content else ""
                elif isinstance(res, str):
                    content = res.strip()
                else:
                    content = str(res).strip()

                if content:
                    parts.append(content)

    return "\n\n".join(parts) + "\n"
