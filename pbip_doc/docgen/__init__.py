"""
Documentation Generator Package for PBIP Semantic Models.
Produces modular, AI-RAG-optimized and human-readable Markdown documents with YAML frontmatter.
"""

from .config import DocGenConfig
from .link_resolver import PublicationScope, LinkResolver
from .section_engine import DocSection, assemble_markdown_document, assemble_html_document, DEFAULT_PAGE_HTML_TEMPLATE
from .layout_engine import (
    BlockLayout,
    TabLayout,
    DocumentLayout,
    DEFAULT_LAYOUT_CONFIG,
    normalize_document_layout,
    get_effective_document_layout,
    render_document_tabs,
    render_document_html,
    get_default_layout_json,
)
from .table_doc import TableDocBuilder
from .measure_doc import MeasureDocBuilder
from .function_doc import FunctionDocBuilder
from .expression_doc import ExpressionDocBuilder
from .index_doc import IndexDocBuilder
from .visual_doc import PageVisualDocBuilder, VisualDocLabels
from .engine import MarkdownDocGenerator
from .html_engine import HtmlDocGenerator
from .workspace_engine import WorkspaceDocGenerator, WorkspaceHtmlLayoutBuilder

__all__ = [
    "DocGenConfig",
    "PublicationScope",
    "LinkResolver",
    "DocSection",
    "assemble_markdown_document",
    "assemble_html_document",
    "DEFAULT_PAGE_HTML_TEMPLATE",
    "TableDocBuilder",
    "MeasureDocBuilder",
    "FunctionDocBuilder",
    "ExpressionDocBuilder",
    "IndexDocBuilder",
    "PageVisualDocBuilder",
    "VisualDocLabels",
    "MarkdownDocGenerator",
    "HtmlDocGenerator",
    "WorkspaceDocGenerator",
    "WorkspaceHtmlLayoutBuilder",
    "BlockLayout",
    "TabLayout",
    "DocumentLayout",
    "DEFAULT_LAYOUT_CONFIG",
    "normalize_document_layout",
    "get_effective_document_layout",
    "render_document_tabs",
    "render_document_html",
    "get_default_layout_json",
]

