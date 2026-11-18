"""
Publication Scope and Link Resolver Engine.
Enforces the Zero Broken Links (Zero 404) guarantee across HTML and Markdown documentation.
When an entity or macro-documentation family (Model, Report, Dataflow) is not published,
links degrade gracefully to plain text or styled non-anchor elements.
100% Python Standard Library. Zero external dependencies.
"""

from dataclasses import dataclass, field
import html
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple, Union

from .utils import sanitize_filename


@dataclass
class PublicationScope:
    """
    Defines the publication perimeter for documentation generation.
    Tracks both macro-family publication status and granular entity whitelists.
    """
    include_models: bool = True
    include_reports: bool = True
    include_dataflow: bool = True

    # Granular published entity identifiers (case-sensitive or normalized)
    published_models: Set[str] = field(default_factory=set)
    published_reports: Set[str] = field(default_factory=set)
    published_tables: Set[str] = field(default_factory=set)
    published_measures: Set[Tuple[str, str]] = field(default_factory=set)  # (table, measure)
    published_functions: Set[str] = field(default_factory=set)
    published_expressions: Set[str] = field(default_factory=set)
    published_report_pages: Set[Tuple[str, str]] = field(default_factory=set)  # (report, page)

    def is_model_published(self, model_name: Optional[str] = None) -> bool:
        if not self.include_models:
            return False
        if not model_name or not self.published_models:
            return True
        return model_name in self.published_models

    def is_report_published(self, report_name: Optional[str] = None) -> bool:
        if not self.include_reports:
            return False
        if not report_name or not self.published_reports:
            return True
        return report_name in self.published_reports

    def is_dataflow_published(self) -> bool:
        return bool(self.include_dataflow)

    def is_table_published(self, table_name: str, model_name: Optional[str] = None) -> bool:
        if not self.include_models:
            return False
        if model_name and self.published_models and model_name not in self.published_models:
            return False
        if self.published_tables:
            return table_name in self.published_tables
        return True

    def is_measure_published(self, table_name: str, measure_name: str, model_name: Optional[str] = None) -> bool:
        if not self.include_models:
            return False
        if model_name and self.published_models and model_name not in self.published_models:
            return False
        if self.published_measures:
            return (table_name, measure_name) in self.published_measures
        if self.published_tables:
            return table_name in self.published_tables
        return True

    def is_function_published(self, func_name: str, model_name: Optional[str] = None) -> bool:
        if not self.include_models:
            return False
        if model_name and self.published_models and model_name not in self.published_models:
            return False
        if self.published_functions:
            return func_name in self.published_functions
        return True

    def is_expression_published(self, expression_name: str) -> bool:
        if not self.include_dataflow:
            return False
        if self.published_expressions:
            return expression_name in self.published_expressions
        return True

    def is_report_page_published(self, report_name: str, page_name: str) -> bool:
        if not self.include_reports:
            return False
        if self.published_reports and report_name not in self.published_reports:
            return False
        if self.published_report_pages:
            return (report_name, page_name) in self.published_report_pages
        return True


class LinkResolver:
    """
    Central link resolution authority.
    Guarantees that an anchor <a> (HTML) or [label](url) (Markdown) is emitted
    ONLY if the target is genuinely published in the active scope.
    Otherwise, returns formatted plain text or non-link span.
    """

    def __init__(
        self,
        scope: Optional[PublicationScope] = None,
        rel_root: str = ".",
        is_html: bool = True,
        tables_subdir: str = "tables",
        measures_subdir: str = "measures",
        functions_subdir: str = "functions",
        expressions_subdir: str = "etl",
        visuals_subdir: str = "visuals",
        target_model_name: Optional[str] = None,
        target_report_name: Optional[str] = None,
        custom_table_url_resolver: Optional[Callable[[str], Optional[str]]] = None,
        custom_measure_url_resolver: Optional[Callable[[str, str], Optional[str]]] = None,
    ):
        self.scope = scope or PublicationScope()
        self.rel_root = rel_root.rstrip("/\\") if rel_root != "." else "."
        self.is_html = is_html
        self.tables_subdir = tables_subdir.strip("/\\")
        self.measures_subdir = measures_subdir.strip("/\\")
        self.functions_subdir = functions_subdir.strip("/\\")
        self.expressions_subdir = expressions_subdir.strip("/\\")
        self.visuals_subdir = visuals_subdir.strip("/\\")
        self.target_model_name = target_model_name
        self.target_report_name = target_report_name
        self.custom_table_url_resolver = custom_table_url_resolver
        self.custom_measure_url_resolver = custom_measure_url_resolver

    def _format_node(
        self,
        url: Optional[str],
        label: str,
        css_class: str = "doc-link",
        tag: str = "strong",
        is_code: bool = False,
    ) -> str:
        """Formats an entity reference as either an active link or graceful plain text."""
        escaped_label = html.escape(label) if self.is_html else label

        if self.is_html:
            inner = f"<code>{escaped_label}</code>" if is_code else (f"<{tag}>{escaped_label}</{tag}>" if tag else escaped_label)
            if url:
                cls_attr = f' class="{css_class}"' if css_class else ""
                return f'<a href="{url}"{cls_attr}>{inner}</a>'
            return inner
        else:
            inner = f"`{label}`" if is_code else (f"**{label}**" if tag == "strong" else label)
            if url:
                return f"[{inner}]({url})"
            return inner

    def link_to_table(
        self,
        table_name: str,
        label: Optional[str] = None,
        model_name: Optional[str] = None,
        css_class: str = "doc-link",
        tag: str = "strong",
        is_code: bool = False,
    ) -> str:
        """Resolves link to a semantic model table document."""
        lbl = label or table_name
        effective_model = model_name or self.target_model_name

        if not self.scope.is_table_published(table_name, effective_model):
            return self._format_node(None, lbl, css_class, tag, is_code)

        if self.custom_table_url_resolver:
            url = self.custom_table_url_resolver(table_name)
            if url:
                return self._format_node(url, lbl, css_class, tag, is_code)

        clean_tbl = sanitize_filename(table_name)
        ext = "html" if self.is_html else "md"
        if self.rel_root == ".":
            url = f"{self.tables_subdir}/{clean_tbl}.{ext}"
        else:
            url = f"{self.rel_root}/{self.tables_subdir}/{clean_tbl}.{ext}"
        return self._format_node(url, lbl, css_class, tag, is_code)

    def link_to_measure(
        self,
        table_name: str,
        measure_name: str,
        label: Optional[str] = None,
        model_name: Optional[str] = None,
        css_class: str = "doc-link",
        tag: str = "strong",
        is_code: bool = False,
    ) -> str:
        """Resolves link to a semantic model measure document."""
        lbl = label or measure_name
        effective_model = model_name or self.target_model_name

        if not self.scope.is_measure_published(table_name, measure_name, effective_model):
            return self._format_node(None, lbl, css_class, tag, is_code)

        if self.custom_measure_url_resolver:
            url = self.custom_measure_url_resolver(table_name, measure_name)
            if url:
                return self._format_node(url, lbl, css_class, tag, is_code)

        clean_tbl = sanitize_filename(table_name or "Model")
        clean_m = sanitize_filename(measure_name)
        ext = "html" if self.is_html else "md"
        if self.rel_root == ".":
            url = f"{self.measures_subdir}/{clean_tbl}/{clean_m}.{ext}"
        else:
            url = f"{self.rel_root}/{self.measures_subdir}/{clean_tbl}/{clean_m}.{ext}"
        return self._format_node(url, lbl, css_class, tag, is_code)

    def link_to_function(
        self,
        func_name: str,
        label: Optional[str] = None,
        model_name: Optional[str] = None,
        css_class: str = "doc-link",
        tag: str = "strong",
        is_code: bool = False,
    ) -> str:
        """Resolves link to a DAX User-Defined Function (UDF) document."""
        lbl = label or func_name
        effective_model = model_name or self.target_model_name

        if not self.scope.is_function_published(func_name, effective_model):
            return self._format_node(None, lbl, css_class, tag, is_code)

        clean_f = sanitize_filename(func_name)
        ext = "html" if self.is_html else "md"
        if self.rel_root == ".":
            url = f"{self.functions_subdir}/{clean_f}.{ext}"
        else:
            url = f"{self.rel_root}/{self.functions_subdir}/{clean_f}.{ext}"
        return self._format_node(url, lbl, css_class, tag, is_code)

    def link_to_expression(
        self,
        expression_name: str,
        label: Optional[str] = None,
        css_class: str = "doc-link",
        tag: str = "strong",
        is_code: bool = False,
    ) -> str:
        """Resolves link to a Power Query Dataflow expression document."""
        lbl = label or expression_name

        if not self.scope.is_expression_published(expression_name):
            return self._format_node(None, lbl, css_class, tag, is_code)

        clean_e = sanitize_filename(expression_name)
        ext = "html" if self.is_html else "md"
        if self.rel_root == ".":
            url = f"{self.expressions_subdir}/{clean_e}.{ext}"
        else:
            url = f"{self.rel_root}/{self.expressions_subdir}/{clean_e}.{ext}"
        return self._format_node(url, lbl, css_class, tag, is_code)

    def link_to_dataflow_overview(
        self,
        label: str = "Power Query Dataflow",
        css_class: str = "doc-link",
        tag: str = "strong",
    ) -> str:
        """Resolves link to the Dataflow Overview index."""
        if not self.scope.is_dataflow_published():
            return self._format_node(None, label, css_class, tag, is_code=False)

        ext = "html" if self.is_html else "md"
        if self.rel_root == ".":
            url = f"{self.expressions_subdir}/index.{ext}"
        else:
            url = f"{self.rel_root}/{self.expressions_subdir}/index.{ext}"
        return self._format_node(url, label, css_class, tag, is_code=False)

    def link_to_report_page(
        self,
        report_name: str,
        page_name: str,
        label: Optional[str] = None,
        css_class: str = "doc-link",
        tag: str = "strong",
    ) -> str:
        """Resolves link to a specific report visual page document."""
        lbl = label or page_name

        if not self.scope.is_report_page_published(report_name, page_name):
            return self._format_node(None, lbl, css_class, tag, is_code=False)

        clean_p = sanitize_filename(page_name)
        ext = "html" if self.is_html else "md"
        if self.rel_root == ".":
            url = f"{self.visuals_subdir}/{clean_p}.{ext}"
        else:
            url = f"{self.rel_root}/{self.visuals_subdir}/{clean_p}.{ext}"
        return self._format_node(url, lbl, css_class, tag, is_code=False)

    def link_to_model_overview(
        self,
        model_name: Optional[str] = None,
        label: Optional[str] = None,
        css_class: str = "doc-link",
        tag: str = "strong",
    ) -> str:
        """Resolves link to a Semantic Model Overview document."""
        lbl = label or (model_name or "Model Overview")

        if not self.scope.is_model_published(model_name):
            return self._format_node(None, lbl, css_class, tag, is_code=False)

        ext = "html" if self.is_html else "md"
        if model_name:
            clean_m = sanitize_filename(model_name)
            if self.rel_root == ".":
                url = f"models/{clean_m}/index.{ext}"
            else:
                url = f"{self.rel_root}/models/{clean_m}/index.{ext}"
        else:
            url = f"{self.rel_root}/index.{ext}" if self.rel_root != "." else f"index.{ext}"

        return self._format_node(url, lbl, css_class, tag, is_code=False)

    def link_to_report_overview(
        self,
        report_name: Optional[str] = None,
        label: Optional[str] = None,
        css_class: str = "doc-link",
        tag: str = "strong",
    ) -> str:
        """Resolves link to a Report Overview document."""
        lbl = label or (report_name or "Report Overview")

        if not self.scope.is_report_published(report_name):
            return self._format_node(None, lbl, css_class, tag, is_code=False)

        ext = "html" if self.is_html else "md"
        if report_name:
            clean_r = sanitize_filename(report_name)
            if self.rel_root == ".":
                url = f"reports/{clean_r}/index.{ext}"
            else:
                url = f"{self.rel_root}/reports/{clean_r}/index.{ext}"
        else:
            url = f"{self.rel_root}/reports/index.{ext}" if self.rel_root != "." else f"reports/index.{ext}"

        return self._format_node(url, lbl, css_class, tag, is_code=False)
