"""
pbip-doc
Automatic documentation generator and semantic dependency resolver for Power BI Project (PBIP) files.
"""

__version__ = "0.2.0"

from .model_schema import (
    PBIPSemanticModel,
    TableDefinition,
    ColumnDefinition,
    RelationshipDefinition,
    MeasureDefinition,
    PowerQuerySource,
    PowerQueryLineageNode,
    PowerQueryMergeJoin,
    SnowflakePath,
    TableRole,
)
from .parser import PBIPParser
from .m_lineage import MLineageResolver
from .star_schema import StarSchemaResolver
from .measure_analyzer import MeasureDependencyResolver
from .docgen import DocGenConfig, MarkdownDocGenerator, HtmlDocGenerator, WorkspaceDocGenerator
from .codebase_scanner import CodebaseScanner, WorkspaceScanResult
from .dax_formatter import format_dax, strip_dax_comments
from .m_formatter import format_m, strip_m_comments

__all__ = [
    "PBIPSemanticModel",
    "TableDefinition",
    "ColumnDefinition",
    "RelationshipDefinition",
    "MeasureDefinition",
    "PowerQuerySource",
    "PowerQueryLineageNode",
    "PowerQueryMergeJoin",
    "SnowflakePath",
    "TableRole",
    "PBIPParser",
    "MLineageResolver",
    "StarSchemaResolver",
    "MeasureDependencyResolver",
    "DocGenConfig",
    "MarkdownDocGenerator",
    "HtmlDocGenerator",
    "WorkspaceDocGenerator",
    "CodebaseScanner",
    "WorkspaceScanResult",
    "format_dax",
    "strip_dax_comments",
    "format_m",
    "strip_m_comments",
]
