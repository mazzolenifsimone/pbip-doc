"""
Section-Driven Document Assembly Engine for Markdown and HTML Generators.
Enforces deterministic section ordering and automatic HTML quick-navigation synchronization.
100% Python Standard Library.
"""

from dataclasses import dataclass
import html
from typing import List, Optional


@dataclass
class DocSection:
    """
    Represents a single atomic section of a documentation page (Markdown or HTML).
    """
    section_id: str
    title: str
    nav_label: Optional[str] = None
    content: str = ""


DEFAULT_PAGE_HTML_TEMPLATE = """
{{PAGE_HEADER}}
{{PAGE_KPIS}}
    <div class="page-tabs-container">
{{PAGE_TAB_RADIOS}}
{{PAGE_TAB_STYLES}}
{{PAGE_TAB_NAV}}

{{PAGE_TAB_PANELS}}
    </div>
"""


def assemble_markdown_document(
    frontmatter: Optional[str],
    header_block: str,
    sections: List[Optional[DocSection]],
) -> str:
    """
    Assembles a Markdown document from optional YAML frontmatter, a top-level header block,
    and an ordered list of DocSection objects. Empty or None sections are ignored.
    """
    blocks: List[str] = []
    if frontmatter and frontmatter.strip():
        blocks.append(frontmatter.strip())
    if header_block and header_block.strip():
        blocks.append(header_block.strip())

    for section in sections:
        if section is not None and section.content and section.content.strip():
            blocks.append(section.content.strip())

    return "\n\n".join(blocks) + "\n"


def assemble_html_document(
    header_html: str,
    kpis_html: str,
    sections: List[Optional[DocSection]],
    template: Optional[str] = None,
) -> str:
    """
    Assembles an HTML article body using a template with placeholders
    ({{PAGE_HEADER}}, {{PAGE_KPIS}}, {{PAGE_TAB_RADIOS}}, {{PAGE_TAB_STYLES}},
    {{PAGE_TAB_NAV}}, {{PAGE_TAB_PANELS}}).
    Components are populated via for-loops over valid sections, guaranteeing 100% by-design
    alignment between radio tabs and section order in the page body (Zero-JS architecture).
    """
    valid_sections = [
        s for s in sections
        if s is not None and s.content and s.content.strip()
    ]

    clean_header = header_html.strip("\n") if header_html and header_html.strip() else ""
    clean_kpis = kpis_html.strip("\n") if kpis_html and kpis_html.strip() else ""

    tpl = template or DEFAULT_PAGE_HTML_TEMPLATE

    if not valid_sections:
        # If no sections, replace placeholders and prune empty tabs container
        res = tpl
        res = res.replace("{{PAGE_HEADER}}", clean_header)
        res = res.replace("{{PAGE_KPIS}}", clean_kpis)
        res = res.replace("{{PAGE_TAB_RADIOS}}", "")
        res = res.replace("{{PAGE_TAB_STYLES}}", "")
        res = res.replace("{{PAGE_TAB_NAV}}", "")
        res = res.replace("{{PAGE_TAB_PANELS}}", "")
        import re
        res = re.sub(r'<div class="page-tabs-container">\s*</div>', '', res)
        parts = [p.strip() for p in res.strip().split("\n\n") if p.strip()]
        return "\n" + "\n\n".join(parts) + "\n" if parts else ""

    radio_inputs = []
    tab_buttons = []
    style_rules = []
    rendered_sections = []

    for idx, s in enumerate(valid_sections):
        tab_id = f"page-tab-{s.section_id}"
        checked = " checked" if idx == 0 else ""
        lbl_text = s.nav_label or s.title
        radio_inputs.append(f'      <input type="radio" name="page-tab" id="{tab_id}" class="page-tab-radio"{checked}>')
        tab_buttons.append(f'        <label for="{tab_id}" class="page-tab-btn">{html.escape(lbl_text)}</label>')
        style_rules.append(
            f'        #{tab_id}:checked ~ .page-tab-bar label[for="{tab_id}"] {{ background-color: var(--accent); color: #ffffff; font-weight: 600; }}\n'
            f'        @media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) #{tab_id}:checked ~ .page-tab-bar label[for="{tab_id}"] {{ color: #0f172a; }} }}\n'
            f'        :root[data-theme="dark"] #{tab_id}:checked ~ .page-tab-bar label[for="{tab_id}"], .theme-force-dark #{tab_id}:checked ~ .page-tab-bar label[for="{tab_id}"] {{ color: #0f172a !important; }}\n'
            f'        #{tab_id}:checked ~ #{html.escape(s.section_id)} {{ display: block; }}'
        )
        rendered_sections.append(
            f'      <section id="{html.escape(s.section_id)}" class="content-section">\n'
            f'{s.content.strip(chr(10))}\n'
            f'      </section>'
        )

    style_block = "      <style>\n" + "\n".join(style_rules) + "\n      </style>"
    nav_block = (
        '      <nav class="page-tab-bar">\n'
        + "\n".join(tab_buttons) + "\n"
        '      </nav>'
    )

    res = tpl
    res = res.replace("{{PAGE_HEADER}}", clean_header)
    res = res.replace("{{PAGE_KPIS}}", clean_kpis)
    res = res.replace("{{PAGE_TAB_RADIOS}}", "\n".join(radio_inputs))
    res = res.replace("{{PAGE_TAB_STYLES}}", style_block)
    res = res.replace("{{PAGE_TAB_NAV}}", nav_block)
    res = res.replace("{{PAGE_TAB_PANELS}}", "\n\n".join(rendered_sections))

    parts = [p.strip() for p in res.strip().split("\n\n") if p.strip()]
    return "\n" + "\n\n".join(parts) + "\n"
