# Architecture & Engine Design: `pbip-doc`

> **Technical Architecture Guide for Contributors and AI Coding Agents.**  
> Explains the internal pipeline, data structures, module boundaries, and design constraints of the `pbip-doc` core engine.

---

## 🏛️ Core Non-Negotiable Architectural Principles

Every contribution and refactoring in `pbip-doc` must adhere to these foundational constraints:

1. **Zero External Runtime Dependencies**:
   - The core engine relies **100% on the Python Standard Library** (`pathlib`, `re`, `json`, `dataclasses`, `enum`, `typing`, `argparse`, `unittest`, `base64`, `math`, `html`, `hashlib`).
   - Third-party packages (e.g. Jinja2, BeautifulSoup, NetworkX, Pandas, PyYAML) are **strictly forbidden** at runtime.
2. **Deterministic & Air-Gapped**:
   - The tool operates in fully disconnected, air-gapped environments without any network calls, telemetry, or remote API dependencies.
3. **Pure Zero-JS HTML Architecture**:
   - The HTML documentation portal generates 100% offline-ready HTML5 files without `<script>` tags, CDN scripts, or external stylesheets.
   - All interactive mechanisms (multi-tab navigation via `:checked`, collapsible `<details>` sidebar accordion trees, build-time `--theme auto|light|dark` with `prefers-color-scheme: dark` support, filter-context mini-maps, and hover-focus SVG diagrams) are powered exclusively by standard HTML5 and CSS (custom properties and flexbox/grid).
4. **Dual-Format Parity**:
   - Every semantic feature documented in HTML must also be exposed in atomic, pure GitHub-Flavored Markdown enriched with YAML frontmatter for LLM / AI RAG pipelines.
5. **Universal Portability**:
   - No hardcoded absolute local paths (`C:\...`, `/home/...`). All cross-document references are strictly relative (`../tables/Table.html`, `measures/Table/Measure.md`).

---

## 🔄 Three-Stage Decoupled Pipeline

```text
┌────────────────────────────────────────────────────────┐
│               STAGE 1: INGESTION & PARSING             │
│  - TMDL Lexer / Parser   (tmdl_lexer.py, parser.py)    │
│  - TMSL / BIM Parser     (parser.py)                   │
│  - PBIR Report Parser    (report_parser.py)            │
│  - Power Query M AST     (m_parser.py, m_step_graph.py)│
│  - Multi-Artifact Scan   (codebase_scanner.py)         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│            STAGE 2: SEMANTIC GRAPH & SCHEMAS           │
│  - Dataclass AST Models  (model_schema.py)             │
│  - Report Visual Models  (report_schema.py)            │
│  - M Lineage Engine      (m_lineage.py)                │
│  - Star/Snowflake Topo   (star_schema.py)              │
│  - DAX DAG Resolver      (measure_analyzer.py)         │
│  - SVG Topology Engine   (docgen/relationship_diagram) │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│             STAGE 3: DOCUMENT GENERATION               │
│  ├── Markdown Generator  (docgen/engine.py, table_doc) │
│  └── HTML Portal Engine  (docgen/html_engine.py, etc.) │
└────────────────────────────────────────────────────────┘
```

---

## 📂 Module Map & Responsibilities

### 1. Ingestion & Semantic Graph (`pbip_doc/`)

File | Primary Role | Output Dataclasses / Signatures
:--- | :--- | :---
[`parser.py`](pbip_doc/parser.py) | Top-level semantic model parser for TMDL and TMSL/BIM formats | `parse_tmdl_model()`, `parse_bim_model()` -> `SemanticModel`
[`tmdl_lexer.py`](pbip_doc/tmdl_lexer.py) | Indentation-aware lexer for Tabular Model Definition Language | `TMDLToken`, `tokenize_tmdl()`
[`m_parser.py`](pbip_doc/m_parser.py) | Tokenizer and recursive-descent AST parser for Power Query (M) | `parse_m()` -> `MASTNode`
[`m_step_graph.py`](pbip_doc/m_step_graph.py) | Dependency graph builder across `let...in` transformation steps | `build_step_graph()` -> `MStepGraph`
[`m_lineage.py`](pbip_doc/m_lineage.py) | Multi-hop lineage resolver tracing upstream data sources | `MLineageEngine` -> `MLineageSummary`
[`m_formatter.py`](pbip_doc/m_formatter.py) | Standardized Power Query (M) expression code formatter | `format_m()`, `strip_m_comments()`
[`m_table_parser.py`](pbip_doc/m_table_parser.py) | Parser and Markdown table renderer for M inline `#table(...)` definitions | `MInlineTable`, `parse_m_inline_table()`
[`dax_formatter.py`](pbip_doc/dax_formatter.py) | SQLBI-style DAX code formatter with signature header and indentation | `format_dax()`, `strip_dax_comments()`
[`star_schema.py`](pbip_doc/star_schema.py) | Topology classifier: identifies Fact, Dimension, Snowflake, Bridge | `classify_model_topology()` -> `ModelTopology`
[`measure_analyzer.py`](pbip_doc/measure_analyzer.py) | DAX formula tokenizer and DAG depth / downstream dependency resolver | `analyze_measure_dependencies()`
[`report_parser.py`](pbip_doc/report_parser.py) | Parser for modern PBIR and legacy Power BI report definitions | `ReportParser` -> `PBIPReportModel`
[`codebase_scanner.py`](pbip_doc/codebase_scanner.py) | Multi-artifact workspace discovery (scans directory for all models & reports) | `scan_workspace()` -> `WorkspaceScanResult`
[`model_schema.py`](pbip_doc/model_schema.py) | Strongly-typed dataclass contracts for semantic models, tables, columns, measures | `SemanticModel`, `TableDefinition`, `MeasureDefinition`
[`report_schema.py`](pbip_doc/report_schema.py) | Strongly-typed dataclass contracts for report pages, visual containers, filters | `PBIPReportModel`, `PageDefinition`, `VisualDefinition`

---

### 2. Document Generators & Layout Engine (`pbip_doc/docgen/`)

File | Primary Role | Key Mechanism
:--- | :--- | :---
[`config.py`](pbip_doc/docgen/config.py) | Centralized, scoped hierarchical configuration engine | `DocGenConfig`, `--set` CLI overrides, JSON presets
[`engine.py`](pbip_doc/docgen/engine.py) | Markdown generator for single semantic models | `MarkdownDocGenerator`
[`html_engine.py`](pbip_doc/docgen/html_engine.py) | Standalone HTML documentation generator for single models | `HtmlDocGenerator`
[`workspace_engine.py`](pbip_doc/docgen/workspace_engine.py) | Multi-artifact workspace orchestrator (master catalog, inventory, cross-artifact linking) | `WorkspaceDocGenerator`
[`section_engine.py`](pbip_doc/docgen/section_engine.py) | Deterministic section ordering and tab synchronization | `DocSection`, `assemble_markdown_document()`, `assemble_html_tabs()`
[`layout_engine.py`](pbip_doc/docgen/layout_engine.py) | Customizable tab and card layout configuration | `DEFAULT_LAYOUT_CONFIG`, canonical 3-level schema
[`html_builders.py`](pbip_doc/docgen/html_builders.py) | HTML page body renderers (Model Overview, Table Doc, Measure Doc, ETL Doc, UDF Doc) | `HtmlIndexBuilder`, `HtmlTableBuilder`, `HtmlMeasureBuilder`, `HtmlFunctionBuilder`, `HtmlExpressionBuilder`
[`relationship_diagram.py`](pbip_doc/docgen/relationship_diagram.py) | Pure Python Standard Library vector SVG relationship diagram generator | `RelationshipSvgGenerator` (Full Model & 1-Hop Focal Views)
[`html_assets.py`](pbip_doc/docgen/html_assets.py) | Embedded zero-dependency CSS stylesheet with Light/Dark executive palette | `get_html_css()`
[`html_layout.py`](pbip_doc/docgen/html_layout.py) | Master HTML frame, collapsible `<details>` sidebar navigation, and logo resolver | `HtmlLayoutBuilder`, `wrap_page()`, `get_sidebar_icon_svg()`

---

### 3. CLI & Entrypoints

File | Primary Role
:--- | :---
[`cli.py`](pbip_doc/cli.py) | Command-line interface with subcommands: `docgen`, `extract`, `inspect`, `config`, `report-extract`, `report-inspect`.
[`__main__.py`](pbip_doc/__main__.py) | Package execution entry point enabling `python -m pbip_doc <command>`.

---

## 🧪 Testing Guidelines

- **Run all unit tests**:
  ```bash
  python -m unittest discover tests -v
  ```
- **End-to-End Verification**:
  ```bash
  python -m pbip_doc docgen samples -o temp_doc -f both
  ```
- **Test Integrity Rules**:
  - Always write tests using `unittest.TestCase` (Python Standard Library).
  - Keep test function names descriptive of the functional behavior (e.g. `test_multi_port_bezier_staggering`), avoiding internal ticket numbers or opaque codes.

