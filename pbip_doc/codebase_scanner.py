"""
PBIP Codebase Scanner & Lineage Discovery Engine.
Recursively discovers Semantic Models, Reports, and PBIP projects across an entire codebase/workspace.
Resolves report-to-dataset bindings, builds symbol indexes (tables, measures), and maps multi-artifact lineage.
Pure Vanilla Python standard library.
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple, Union

from .docgen.utils import (
    clean_project_name,
    sanitize_filename,
    extract_by_connection_model_candidates,
)
from .docgen.config import DocGenConfig
from .model_schema import PBIPSemanticModel
from .report_schema import PBIPReportModel


DEFAULT_IGNORED_DIRS = {
    ".git",
    ".github",
    ".vscode",
    ".vs",
    ".idea",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "temp_doc",
    "docs",
    "dist",
    "build",
    "site-packages",
    "bin",
    "obj",
}


@dataclass
class DiscoveredArtifact:
    """Base representation of a discovered artifact in a PBIP repository."""
    name: str
    path: Path
    rel_path: str
    raw_name: str


@dataclass
class DiscoveredModel(DiscoveredArtifact):
    """Represents a discovered Power BI Semantic Model."""
    model_format: str  # "TMDL", "BIM", "UNKNOWN"
    is_standalone_bim: bool = False
    definition_path: Optional[Path] = None
    bound_reports: List[str] = field(default_factory=list)  # Report artifact IDs
    tables: List[str] = field(default_factory=list)
    inherited_tables: Dict[str, Optional[str]] = field(default_factory=dict)  # table_name -> inherited_model_name
    table_roles: Dict[str, str] = field(default_factory=dict)  # table_name -> role (FACT, DIM, etc.)
    measures: Dict[str, str] = field(default_factory=dict)  # measure_name -> table_name
    inherited_measures: Dict[str, Optional[str]] = field(default_factory=dict)  # measure_name -> inherited_model_name
    expressions: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    model_obj: Optional[PBIPSemanticModel] = None

    @property
    def artifact_id(self) -> str:
        return self.rel_path.replace("\\", "/")

    def get_published_tables(self, scoped_cfg: Optional[DocGenConfig] = None) -> List[str]:
        """Returns table names that are in local documentation scope (excluding auto-date/excluded and inherited unless enabled)."""
        include_inh = getattr(scoped_cfg, "include_inherited_entities", False) if scoped_cfg else False
        is_excl = scoped_cfg.is_table_excluded if (scoped_cfg and hasattr(scoped_cfg, "is_table_excluded")) else (lambda _: False)
        return [
            t for t in self.tables
            if not is_excl(t) and (include_inh or t not in self.inherited_tables)
        ]

    def get_published_measures(self, scoped_cfg: Optional[DocGenConfig] = None) -> Dict[str, str]:
        """Returns {measure_name: table_name} for measures in local documentation scope."""
        include_inh = getattr(scoped_cfg, "include_inherited_entities", False) if scoped_cfg else False
        is_excl = scoped_cfg.is_table_excluded if (scoped_cfg and hasattr(scoped_cfg, "is_table_excluded")) else (lambda _: False)
        return {
            k: tbl for k, tbl in self.measures.items()
            if not is_excl(tbl) and (include_inh or k not in self.inherited_measures)
        }

    def get_dataflow_tables(self) -> List[str]:
        """Returns tables loaded via Power Query M (excluding DAX calculated tables, calculation groups, and inherited entities)."""
        if self.model_obj and hasattr(self.model_obj, "tables"):
            return [
                t.name for t in self.model_obj.tables
                if t.name in self.tables
                and (
                    getattr(t, "source_type", "PowerQuery") == "PowerQuery"
                    or bool(getattr(getattr(t, "power_query_lineage", None), "full_m_expression", None))
                )
                and getattr(t, "source_type", "") not in ("CalculatedTable", "CalculationGroup", "InheritedEntity")
                and not getattr(t, "is_inherited", False)
                and (getattr(t, "role", None) != "CALCULATION_GROUP" and getattr(getattr(t, "role", None), "value", "") != "CALCULATION_GROUP")
                and t.name not in self.inherited_tables
            ]
        return [
            t for t in self.tables
            if self.table_roles.get(t) not in ("CALCULATION_GROUP", "CALC_GROUP")
            and t not in self.inherited_tables
        ]


@dataclass
class DiscoveredReport(DiscoveredArtifact):
    """Represents a discovered Power BI Report."""
    report_format: str  # "PBIR", "LEGACY"
    bound_model_name: Optional[str] = None
    bound_model_path: Optional[Path] = None
    bound_model_id: Optional[str] = None
    is_external_model: bool = False
    dataset_reference: Optional[Dict[str, Any]] = None
    page_names: List[str] = field(default_factory=list)
    report_obj: Optional[PBIPReportModel] = None

    @property
    def artifact_id(self) -> str:
        return self.rel_path.replace("\\", "/")


@dataclass
class DiscoveredPbip(DiscoveredArtifact):
    """Represents a discovered .pbip project file."""
    artifacts_data: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class WorkspaceScanResult:
    """Result of scanning a codebase for PBIP artifacts with full lineage and symbol maps."""
    root_path: Path
    models: Dict[str, DiscoveredModel] = field(default_factory=dict)     # key: artifact_id or unique name
    reports: Dict[str, DiscoveredReport] = field(default_factory=dict)   # key: artifact_id or unique name
    pbips: List[DiscoveredPbip] = field(default_factory=list)

    @property
    def total_artifacts(self) -> int:
        return len(self.models) + len(self.reports)

    def is_single_artifact(self) -> bool:
        """Returns True if the scanned scope represents a single isolated artifact (e.g. 1 model or 1 model + 1 paired report)."""
        if len(self.models) == 1 and len(self.reports) == 0:
            return True
        if len(self.models) == 0 and len(self.reports) == 1:
            return True
        if len(self.models) == 1 and len(self.reports) == 1:
            m = next(iter(self.models.values()))
            r = next(iter(self.reports.values()))
            if r.bound_model_id == m.artifact_id or r.bound_model_name == m.name:
                return True
        return False

    def get_model(self, key_or_name: str) -> Optional[DiscoveredModel]:
        """Looks up a model by artifact_id, name, or raw_name."""
        if key_or_name in self.models:
            return self.models[key_or_name]
        clean_key = clean_project_name(key_or_name).lower()
        norm_key = re.sub(r'[\s_\-]+', '', key_or_name).lower()
        for m in self.models.values():
            if clean_project_name(m.name).lower() == clean_key or m.raw_name.lower() == key_or_name.lower():
                return m
            if Path(m.rel_path).name.lower() == key_or_name.lower():
                return m
            if re.sub(r'[\s_\-]+', '', m.name).lower() == norm_key:
                return m
            if re.sub(r'[\s_\-]+', '', Path(m.rel_path).stem).lower() == norm_key:
                return m
            if re.sub(r'[\s_\-]+', '', Path(m.rel_path).parent.name).lower() == norm_key:
                return m
        return None

    def get_report(self, key_or_name: str) -> Optional[DiscoveredReport]:
        """Looks up a report by artifact_id, name, or raw_name."""
        if key_or_name in self.reports:
            return self.reports[key_or_name]
        clean_key = clean_project_name(key_or_name).lower()
        norm_key = re.sub(r'[\s_\-]+', '', key_or_name).lower()
        for r in self.reports.values():
            if clean_project_name(r.name).lower() == clean_key or r.raw_name.lower() == key_or_name.lower():
                return r
            if Path(r.rel_path).name.lower() == key_or_name.lower():
                return r
            if re.sub(r'[\s_\-]+', '', r.name).lower() == norm_key:
                return r
            if re.sub(r'[\s_\-]+', '', Path(r.rel_path).stem).lower() == norm_key:
                return r
            if re.sub(r'[\s_\-]+', '', Path(r.rel_path).parent.name).lower() == norm_key:
                return r
        return None

    def get_bound_model_for_report(self, report_key_or_name: str) -> Optional[DiscoveredModel]:
        """Resolves the bound local model for a given report."""
        report = self.get_report(report_key_or_name)
        if not report:
            return None
        if report.bound_model_id and report.bound_model_id in self.models:
            return self.models[report.bound_model_id]
        if report.bound_model_name:
            return self.get_model(report.bound_model_name)
        if report.bound_model_path:
            for m in self.models.values():
                if m.path.resolve() == report.bound_model_path.resolve():
                    return m
        return None

    def find_measure(self, measure_name: str, preferred_model: Optional[str] = None) -> List[Tuple[DiscoveredModel, str]]:
        """
        Searches all models in the workspace for a measure by name.
        Returns list of (DiscoveredModel, table_name) tuples.
        Prioritizes native (non-inherited) measures over composite/inherited ones.
        """
        results: List[Tuple[DiscoveredModel, str]] = []
        clean_m_name = measure_name.strip("[]'\"").lower()

        if preferred_model:
            pm = self.get_model(preferred_model)
            if pm:
                for m_k, tbl in pm.measures.items():
                    if m_k.strip("[]'\"").lower() == clean_m_name:
                        inh_m = pm.inherited_measures.get(m_k) if hasattr(pm, "inherited_measures") else None
                        if inh_m:
                            src_m = self.get_model(inh_m)
                            if src_m:
                                src_tbl = src_m.measures.get(m_k, tbl)
                                results.append((src_m, src_tbl))
                        results.append((pm, tbl))

        native_matches = []
        inherited_matches = []
        for m_id, model in self.models.items():
            if preferred_model and (model.artifact_id == preferred_model or model.name == preferred_model):
                continue
            for m_k, tbl in model.measures.items():
                if m_k.strip("[]'\"").lower() == clean_m_name:
                    is_inh = (hasattr(model, "inherited_measures") and m_k in model.inherited_measures)
                    if is_inh:
                        inherited_matches.append((model, tbl))
                    else:
                        native_matches.append((model, tbl))

        for item in native_matches:
            if item not in results:
                results.append(item)
        for item in inherited_matches:
            if item not in results:
                results.append(item)

        return results

    def find_table(self, table_name: str, preferred_model: Optional[str] = None) -> List[DiscoveredModel]:
        """
        Searches all models in the workspace for a table by name.
        Prioritizes native (non-inherited) tables over composite/inherited ones.
        """
        results: List[DiscoveredModel] = []
        clean_t_name = table_name.strip("'\"[]").lower()

        if preferred_model:
            pm = self.get_model(preferred_model)
            if pm:
                for t in pm.tables:
                    if t.strip("'\"[]").lower() == clean_t_name:
                        inh_m = pm.inherited_tables.get(t) if hasattr(pm, "inherited_tables") else None
                        if inh_m:
                            src_m = self.get_model(inh_m)
                            if src_m and src_m not in results:
                                results.append(src_m)
                        results.append(pm)
                        break

        native_matches = []
        inherited_matches = []
        for m_id, model in self.models.items():
            if preferred_model and (model.artifact_id == preferred_model or model.name == preferred_model):
                continue
            for t in model.tables:
                if t.strip("'\"[]").lower() == clean_t_name:
                    is_inh = (hasattr(model, "inherited_tables") and t in model.inherited_tables)
                    if is_inh:
                        inherited_matches.append(model)
                    else:
                        native_matches.append(model)
                    break

        for m in native_matches:
            if m not in results:
                results.append(m)
        for m in inherited_matches:
            if m not in results:
                results.append(m)

        return results

    def get_model_dependencies(self) -> Dict[str, Set[str]]:
        """
        Builds a mapping of model_id -> set of upstream model_ids that this model depends on
        (via inherited entities, external measures, upstream_models, or DirectQuery / AS partitions).
        """
        deps: Dict[str, Set[str]] = {m_id: set() for m_id in self.models}

        def _register_dep(m_id: str, model: DiscoveredModel, cand: Optional[str]) -> None:
            if not cand or cand == "—":
                return
            up = self.get_model(cand)
            if up and up.artifact_id != m_id:
                deps[m_id].add(up.artifact_id)
            elif not up and cand != m_id and cand != model.name:
                deps[m_id].add(cand)

        remote_source_types = {
            "POWERBI_SEMANTIC_MODEL",
            "ANALYSIS_SERVICES",
            "ANALYSISSERVICES",
            "POWERBI",
        }

        for m_id, model in self.models.items():
            for t_name, inh_m in getattr(model, "inherited_tables", {}).items():
                _register_dep(m_id, model, inh_m)
            for m_name, inh_m in getattr(model, "inherited_measures", {}).items():
                _register_dep(m_id, model, inh_m)
            if model.model_obj:
                for up_item in getattr(model.model_obj, "upstream_models", []) or []:
                    up_name = (
                        up_item.get("name")
                        if isinstance(up_item, dict)
                        else getattr(up_item, "name", None)
                    )
                    _register_dep(m_id, model, up_name)
                for ds in getattr(model.model_obj, "data_sources_summary", []) or []:
                    s_db = ds.get("database") if isinstance(ds, dict) else getattr(ds, "database", None)
                    s_type = ds.get("source_type") if isinstance(ds, dict) else getattr(ds, "source_type", None)
                    is_rem = ds.get("is_remote_model", False) if isinstance(ds, dict) else getattr(ds, "is_remote_model", False)
                    if s_db and s_db != "—":
                        s_type_up = str(s_type or "").upper()
                        if s_type_up in remote_source_types or is_rem or self.get_model(s_db) is not None:
                            _register_dep(m_id, model, s_db)
                for t in getattr(model.model_obj, "tables", []):
                    inh = getattr(t, "inherited_model_name", None)
                    _register_dep(m_id, model, inh)
                    for s in getattr(t, "root_data_sources", []):
                        s_db = getattr(s, "database", None) if hasattr(s, "database") else (s.get("database") if isinstance(s, dict) else None)
                        _register_dep(m_id, model, s_db)
                for meas in getattr(model.model_obj, "measures", []):
                    inh = getattr(meas, "inherited_model_name", None)
                    _register_dep(m_id, model, inh)
        return deps

    def get_downstream_reports(self, model_key: str) -> List[Dict[str, Any]]:
        """
        Returns all reports connected to this model directly or transitively
        (i.e. reports connected to semantic models that inherit from or connect to this model).
        Ordered deterministically: direct reports sorted by report name, followed by
        transitive reports sorted by report name.
        Returns list of dicts:
            {
                "report": DiscoveredReport,
                "is_direct": bool,
                "via_model": Optional[str],
            }
        """
        target = self.get_model(model_key)
        if not target:
            return []

        direct_results: List[Dict[str, Any]] = []
        transitive_results: List[Dict[str, Any]] = []
        seen_report_ids: Set[str] = set()

        # 1. Direct reports
        for r_id in target.bound_reports:
            rep = self.get_report(r_id)
            if rep and rep.artifact_id not in seen_report_ids:
                seen_report_ids.add(rep.artifact_id)
                direct_results.append({
                    "report": rep,
                    "is_direct": True,
                    "via_model": None,
                })

        # 2. Transitive reports via downstream models (multi-hop BFS: A -> B -> C -> Report)
        deps = self.get_model_dependencies()
        downstream_map: Dict[str, Set[str]] = {m_id: set() for m_id in self.models}
        for down_id, up_set in deps.items():
            for up_id in up_set:
                if up_id in downstream_map:
                    downstream_map[up_id].add(down_id)

        first_hop_ids = sorted(
            [down_id for down_id in downstream_map.get(target.artifact_id, set()) if down_id in self.models],
            key=lambda mid: (self.models[mid].name.lower(), mid),
        )
        queue: List[Tuple[str, str]] = [(down_id, self.models[down_id].name) for down_id in first_hop_ids]
        visited_models: Set[str] = {target.artifact_id}

        while queue:
            curr_id, via_name = queue.pop(0)
            if curr_id in visited_models:
                continue
            visited_models.add(curr_id)
            curr_model = self.models.get(curr_id)
            if not curr_model:
                continue

            for r_id in curr_model.bound_reports:
                rep = self.get_report(r_id)
                if rep and rep.artifact_id not in seen_report_ids:
                    seen_report_ids.add(rep.artifact_id)
                    transitive_results.append({
                        "report": rep,
                        "is_direct": False,
                        "via_model": via_name,
                    })

            next_ids = sorted(
                [nd for nd in downstream_map.get(curr_id, set()) if nd not in visited_models and nd in self.models],
                key=lambda mid: (self.models[mid].name.lower(), mid),
            )
            for next_down in next_ids:
                queue.append((next_down, via_name))

        direct_results.sort(key=lambda item: (item["report"].name.lower(), item["report"].artifact_id))
        transitive_results.sort(key=lambda item: (item["report"].name.lower(), item["report"].artifact_id))
        return direct_results + transitive_results

    def get_artifacts_by_folder(self, folder_depth: int = 1) -> Dict[str, Dict[str, Any]]:
        """
        Groups discovered models and reports by their top-level domain or project directory
        up to folder_depth (default: 1, e.g. 'finance', 'sales').
        Prevents 1-to-1 leaf folder explosion when reports reside in individual subfolders.
        Returns:
            Dict[folder_rel_path, {
                "folder_path": folder_rel_path,
                "folder_name": folder_display_name,
                "models": List[DiscoveredModel],
                "reports": List[DiscoveredReport],
                "total_count": int,
            }]
        Folders are sorted alphabetically, with root (if any) placed first.
        """
        folders: Dict[str, Dict[str, Any]] = {}

        def _get_folder_key(artifact: DiscoveredArtifact) -> str:
            parts = Path(artifact.rel_path).parts
            dir_parts = parts[:-1]
            if not dir_parts:
                return "(Root)"
            eff_depth = max(1, folder_depth)
            chosen = dir_parts[:eff_depth]
            return "/".join(chosen)

        for m in self.models.values():
            f_key = _get_folder_key(m)
            if f_key not in folders:
                folders[f_key] = {
                    "folder_path": "" if f_key == "(Root)" else f_key,
                    "folder_name": Path(self.root_path.name).name if f_key == "(Root)" else Path(f_key).name,
                    "models": [],
                    "reports": [],
                    "total_count": 0,
                }
            folders[f_key]["models"].append(m)
            folders[f_key]["total_count"] += 1

        for r in self.reports.values():
            f_key = _get_folder_key(r)
            if f_key not in folders:
                folders[f_key] = {
                    "folder_path": "" if f_key == "(Root)" else f_key,
                    "folder_name": Path(self.root_path.name).name if f_key == "(Root)" else Path(f_key).name,
                    "models": [],
                    "reports": [],
                    "total_count": 0,
                }
            folders[f_key]["reports"].append(r)
            folders[f_key]["total_count"] += 1

        for f_data in folders.values():
            f_data["models"].sort(key=lambda x: x.name)
            f_data["reports"].sort(key=lambda x: x.name)

        sorted_keys = sorted(
            folders.keys(),
            key=lambda k: (0 if k == "(Root)" else 1, k.lower())
        )
        return {k: folders[k] for k in sorted_keys}


class CodebaseScanner:
    """
    Scans a directory tree to discover all PBIP artifacts, resolve report dataset bindings,
    and index tables/measures for cross-artifact documentation navigation.
    """

    def __init__(
        self,
        root_dir: Union[str, Path],
        config: Optional[DocGenConfig] = None,
        ignored_dirs: Optional[Set[str]] = None,
    ):
        self.root_path = Path(root_dir).resolve()
        self.config = config or DocGenConfig()
        self.ignored_dirs = set(DEFAULT_IGNORED_DIRS)
        if ignored_dirs:
            self.ignored_dirs.update(ignored_dirs)

    def scan(self, populate_symbols: bool = True) -> WorkspaceScanResult:
        """
        Executes the discovery pass across the root path.
        """
        result = WorkspaceScanResult(root_path=self.root_path)

        if not self.root_path.exists():
            return result

        # Handle direct artifact target (single .SemanticModel, .Report, or model.bim given as root)
        if self._is_single_direct_target(self.root_path):
            self._process_direct_target(self.root_path, result, populate_symbols=populate_symbols)
            self._resolve_lineage(result)
            return result

        # 1. Discover file and directory artifacts recursively
        model_paths: List[Path] = []
        report_paths: List[Path] = []
        pbip_paths: List[Path] = []
        standalone_bim_paths: List[Path] = []

        for current_root, dirs, files in os.walk(str(self.root_path)):
            current_path = Path(current_root)

            # Filter out ignored directories in-place to avoid descending into them
            dirs[:] = [
                d for d in dirs
                if d.lower() not in self.ignored_dirs
                and not d.startswith(".")
                and not any(d.lower().startswith(ign) for ign in ("doc_", "temp_doc"))
            ]

            # Check if current directory is a SemanticModel or Report
            if current_path.suffix.lower() == ".semanticmodel":
                model_paths.append(current_path)
                dirs.clear()  # Do not descend inside artifact directory
                continue

            if current_path.suffix.lower() == ".report":
                report_paths.append(current_path)
                dirs.clear()  # Do not descend inside artifact directory
                continue

            # Check for PBIP and standalone BIM files
            for file_name in files:
                f_lower = file_name.lower()
                f_path = current_path / file_name

                if f_lower.endswith(".pbip"):
                    pbip_paths.append(f_path)
                elif f_lower == "model.bim":
                    # Only treat as standalone if not inside a .SemanticModel
                    if not any(p.suffix.lower() == ".semanticmodel" for p in f_path.parents):
                        standalone_bim_paths.append(f_path)

        # 2. Ingest Discovered Models
        for m_path in model_paths:
            self._ingest_model_dir(m_path, result, populate_symbols=populate_symbols)

        for bim_path in standalone_bim_paths:
            self._ingest_standalone_bim(bim_path, result, populate_symbols=populate_symbols)

        # 3. Ingest Discovered Reports
        for r_path in report_paths:
            self._ingest_report_dir(r_path, result, populate_symbols=populate_symbols)

        # 4. Ingest Discovered PBIP files
        for p_path in pbip_paths:
            self._ingest_pbip_file(p_path, result)

        # 5. Resolve Lineage & Bindings
        self._resolve_lineage(result)

        return result

    def _is_single_direct_target(self, path: Path) -> bool:
        """Determines if the root path itself is an individual model or report."""
        if path.is_file():
            if path.suffix.lower() in (".pbip", ".bim") or path.name.lower() in ("model.bim", "report.json"):
                return True
        elif path.is_dir():
            s = path.suffix.lower()
            if s in (".semanticmodel", ".report"):
                return True
            if (path / "model.bim").is_file():
                return True
            if (path / "definition" / "model.tmdl").is_file() or (path / "model.tmdl").is_file():
                return True
            if (path / "definition.pbir").is_file() or (path / "report.json").is_file():
                return True
        return False

    def _process_direct_target(self, path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        """Processes a single target directly provided as root."""
        if path.is_file():
            if path.suffix.lower() == ".pbip":
                self._ingest_pbip_file(path, result)
                # Also inspect siblings of the pbip
                parent = path.parent
                for child in parent.iterdir():
                    if child.is_dir() and child.suffix.lower() == ".semanticmodel":
                        self._ingest_model_dir(child, result, populate_symbols=populate_symbols)
                    elif child.is_dir() and child.suffix.lower() == ".report":
                        self._ingest_report_dir(child, result, populate_symbols=populate_symbols)
            elif path.name.lower() == "model.bim":
                self._ingest_standalone_bim(path, result, populate_symbols=populate_symbols)
            elif path.name.lower() == "report.json":
                self._ingest_report_dir(path.parent, result, populate_symbols=populate_symbols)
        else:
            s = path.suffix.lower()
            if s == ".semanticmodel" or (path / "model.bim").is_file() or (path / "definition" / "model.tmdl").is_file():
                self._ingest_model_dir(path, result, populate_symbols=populate_symbols)
            elif s == ".report" or (path / "definition.pbir").is_file() or (path / "report.json").is_file():
                self._ingest_report_dir(path, result, populate_symbols=populate_symbols)

    def _ingest_model_dir(self, model_path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        raw_name = model_path.name
        clean_name = clean_project_name(model_path.stem)
        try:
            rel_path = str(model_path.relative_to(self.root_path))
        except ValueError:
            rel_path = model_path.name

        # Detect format
        model_format = "TMDL"
        def_path = model_path / "definition"
        if not def_path.exists():
            def_path = model_path

        if (model_path / "model.bim").is_file() and not (def_path / "model.tmdl").is_file():
            model_format = "BIM"

        discovered = DiscoveredModel(
            name=clean_name,
            path=model_path,
            rel_path=rel_path,
            raw_name=raw_name,
            model_format=model_format,
            is_standalone_bim=False,
            definition_path=def_path if def_path.exists() else None,
        )

        if populate_symbols:
            self._populate_model_symbols(discovered)

        # Unique key
        key = discovered.artifact_id or clean_name
        result.models[key] = discovered

    def _ingest_standalone_bim(self, bim_path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        parent = bim_path.parent
        raw_name = parent.name if parent != self.root_path else bim_path.stem
        clean_name = clean_project_name(raw_name)
        try:
            rel_path = str(bim_path.relative_to(self.root_path))
        except ValueError:
            rel_path = bim_path.name

        discovered = DiscoveredModel(
            name=clean_name,
            path=bim_path,
            rel_path=rel_path,
            raw_name=raw_name,
            model_format="BIM",
            is_standalone_bim=True,
            definition_path=bim_path,
        )

        if populate_symbols:
            self._populate_model_symbols(discovered)

        key = discovered.artifact_id or clean_name
        result.models[key] = discovered

    def _ingest_report_dir(self, report_path: Path, result: WorkspaceScanResult, populate_symbols: bool):
        raw_name = report_path.name
        clean_name = clean_project_name(report_path.stem)
        try:
            rel_path = str(report_path.relative_to(self.root_path))
        except ValueError:
            rel_path = report_path.name

        # Detect format
        report_format = "PBIR"
        if (report_path / "report.json").is_file() and not (report_path / "definition" / "pages").exists():
            report_format = "LEGACY"

        # Check definition.pbir for datasetReference
        ds_ref, bound_model_name, is_external = self._inspect_pbir(report_path)

        discovered = DiscoveredReport(
            name=clean_name,
            path=report_path,
            rel_path=rel_path,
            raw_name=raw_name,
            report_format=report_format,
            bound_model_name=bound_model_name,
            is_external_model=is_external,
            dataset_reference=ds_ref,
        )

        if populate_symbols:
            self._populate_report_symbols(discovered)

        key = discovered.artifact_id or clean_name
        result.reports[key] = discovered

    def _ingest_pbip_file(self, pbip_path: Path, result: WorkspaceScanResult):
        raw_name = pbip_path.name
        clean_name = clean_project_name(pbip_path.stem)
        try:
            rel_path = str(pbip_path.relative_to(self.root_path))
        except ValueError:
            rel_path = pbip_path.name

        artifacts_data: List[Dict[str, Any]] = []
        try:
            with open(pbip_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            if isinstance(content, dict) and "artifacts" in content:
                artifacts_data = content["artifacts"]
        except Exception:
            pass

        discovered = DiscoveredPbip(
            name=clean_name,
            path=pbip_path,
            rel_path=rel_path,
            raw_name=raw_name,
            artifacts_data=artifacts_data,
        )
        result.pbips.append(discovered)

    def _inspect_pbir(self, report_dir: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
        """Inspects definition.pbir to extract datasetReference."""
        candidates = [
            report_dir / "definition.pbir",
            report_dir / "definition" / "definition.pbir",
            report_dir.parent / f"{report_dir.stem}.pbir",
        ]
        pbir_file = next((c for c in candidates if c.is_file()), None)
        if not pbir_file:
            return None, None, False

        try:
            with open(pbir_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            ds_ref = data.get("datasetReference")
            if not isinstance(ds_ref, dict):
                return None, None, False

            by_path = ds_ref.get("byPath")
            if isinstance(by_path, dict) and "path" in by_path:
                rel = by_path["path"]
                stem = Path(rel).stem or Path(rel).name
                return ds_ref, clean_project_name(stem), False

            by_conn = ds_ref.get("byConnection")
            if isinstance(by_conn, dict):
                candidates = extract_by_connection_model_candidates(by_conn)
                if candidates:
                    return ds_ref, clean_project_name(candidates[0]), True
                return ds_ref, "Remote Semantic Model", True

            return ds_ref, None, False
        except Exception:
            return None, None, False

    def _populate_model_symbols(self, model: DiscoveredModel):
        """Extracts tables, measures, functions, and expressions into model index."""
        scoped_cfg = self.config.get_scoped_config(model.artifact_id)
        try:
            from .parser import PBIPParser
            parser = PBIPParser(config=scoped_cfg)
            parsed_model = parser.parse(str(model.path), config=scoped_cfg)
            model.model_obj = parsed_model
            model.tables = [t.name for t in parsed_model.tables if not scoped_cfg.is_table_excluded(t.name)]
            model.inherited_tables = {
                t.name: getattr(t, "inherited_model_name", None)
                for t in parsed_model.tables
                if (getattr(t, "is_inherited", False) or getattr(t, "source_type", "") == "InheritedEntity")
                and not scoped_cfg.is_table_excluded(t.name)
            }
            model.table_roles = {
                t.name: (t.role.value if hasattr(t.role, "value") else str(t.role))
                for t in parsed_model.tables
                if not scoped_cfg.is_table_excluded(t.name)
            }
            model.measures = {
                m.name: (m.table if hasattr(m, 'table') else getattr(m, 'table_name', ''))
                for m in parsed_model.measures
                if not scoped_cfg.is_table_excluded(getattr(m, 'table', getattr(m, 'table_name', '')))
            }
            model.inherited_measures = {
                m.name: getattr(m, "inherited_model_name", None)
                for m in parsed_model.measures
                if (getattr(m, "is_inherited", False) or getattr(m, "is_external_measure", False))
                and not scoped_cfg.is_table_excluded(getattr(m, 'table', getattr(m, 'table_name', '')))
            }
            model.expressions = [
                getattr(e, 'name', getattr(e, 'query_name', ''))
                for e in parsed_model.expressions
            ]
            model.functions = [getattr(f, 'name', '') for f in parsed_model.functions]
        except Exception:
            # Fallback to lightweight filesystem inspection if full parse fails
            if model.model_format == "TMDL":
                tables_dir = (model.definition_path or model.path) / "tables"
                if tables_dir.is_dir():
                    model.tables = [
                        f.stem for f in tables_dir.glob("*.tmdl")
                        if not scoped_cfg.is_table_excluded(f.stem)
                    ]
            elif model.path.is_file() and model.path.suffix.lower() == ".bim":
                try:
                    with open(model.path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    m = data.get("model", {})
                    model.tables = [
                        t.get("name") for t in m.get("tables", [])
                        if t.get("name") and not scoped_cfg.is_table_excluded(t.get("name"))
                    ]
                except Exception:
                    pass

    def _populate_report_symbols(self, report: DiscoveredReport):
        """Extracts report page names and optionally parses presentation model."""
        try:
            from .report_parser import ReportParser
            parser = ReportParser()
            parsed_report = parser.parse(str(report.path))
            report.report_obj = parsed_report
            report.page_names = [p.display_name for p in parsed_report.pages]
        except Exception:
            # Fallback: inspect pages directory in PBIR
            pages_dir = report.path / "definition" / "pages"
            if pages_dir.is_dir():
                for p_dir in pages_dir.iterdir():
                    if p_dir.is_dir() and (p_dir / "page.json").is_file():
                        try:
                            with open(p_dir / "page.json", "r", encoding="utf-8") as f:
                                pj = json.load(f)
                            report.page_names.append(pj.get("displayName", p_dir.name))
                        except Exception:
                            report.page_names.append(p_dir.name)

    def _resolve_lineage(self, result: WorkspaceScanResult):
        """Resolves report-to-model bindings and cross-references."""
        # 1. Match Reports via datasetReference
        for report in result.reports.values():
            resolved_model: Optional[DiscoveredModel] = None

            if report.dataset_reference:
                by_path = report.dataset_reference.get("byPath")
                if isinstance(by_path, dict) and "path" in by_path:
                    raw_rel = by_path["path"]
                    # Try resolving relative path from report dir
                    target_path = (report.path / raw_rel).resolve()
                    for m in result.models.values():
                        if m.path.resolve() == target_path:
                            resolved_model = m
                            break

                    # Fallback: check matching stem / name or canonical workspace lookup
                    if not resolved_model:
                        stem = clean_project_name(Path(raw_rel).stem)
                        for m in result.models.values():
                            if clean_project_name(m.name).lower() == stem.lower() or m.raw_name.lower() == Path(raw_rel).name.lower():
                                resolved_model = m
                                break
                        if not resolved_model and stem:
                            resolved_model = result.get_model(stem)

                # Fallback for byConnection (Live Connection / Thin Report):
                # try Initial Catalog first, then pbiModelDatabaseName against local workspace models
                if not resolved_model:
                    by_conn = report.dataset_reference.get("byConnection")
                    if isinstance(by_conn, dict):
                        for cand in extract_by_connection_model_candidates(by_conn):
                            if cand and cand != "Remote Semantic Model":
                                resolved_model = result.get_model(cand)
                                if resolved_model:
                                    break

            # 1b. Canonical lookup via report.bound_model_name if still unresolved
            if not resolved_model and report.bound_model_name and report.bound_model_name != "Remote Semantic Model":
                resolved_model = result.get_model(report.bound_model_name)

            # 2. Sibling / PBIP matching if still unresolved
            if not resolved_model:
                # Check if there is a model in the same parent directory with matching name
                for m in result.models.values():
                    if m.path.parent == report.path.parent:
                        if clean_project_name(m.name).lower() == clean_project_name(report.name).lower():
                            resolved_model = m
                            break

            # 3. Apply resolved binding
            if resolved_model:
                report.bound_model_name = resolved_model.name
                report.bound_model_path = resolved_model.path
                report.bound_model_id = resolved_model.artifact_id
                report.is_external_model = False
                if report.artifact_id not in resolved_model.bound_reports:
                    resolved_model.bound_reports.append(report.artifact_id)
                if resolved_model.model_obj:
                    resolved_model.model_obj.bound_reports_count = len(resolved_model.bound_reports)
            else:
                if report.bound_model_name:
                    # Model not present in local workspace
                    report.is_external_model = True

        # 4. Inject cross-model workspace linkability into pre-documentation model objects
        for model in result.models.values():
            if not model.model_obj:
                continue
            for up in getattr(model.model_obj, "upstream_models", []):
                target_dm = result.get_model(up.name)
                if target_dm:
                    up.is_in_workspace = True
                    up.target_model_slug = sanitize_filename(target_dm.name)
            for src in getattr(model.model_obj, "data_sources_summary", []):
                if src.database and src.database != "—":
                    target_dm = result.get_model(src.database)
                    if target_dm:
                        src.is_in_workspace = True
                        src.target_model_slug = sanitize_filename(target_dm.name)
                        src.is_remote_model = True
            for t in getattr(model.model_obj, "tables", []):
                if getattr(t, "inherited_model_name", None):
                    target_dm = result.get_model(t.inherited_model_name)
                    if target_dm:
                        t.target_model_slug = sanitize_filename(target_dm.name)
            for m in getattr(model.model_obj, "measures", []):
                if getattr(m, "inherited_model_name", None):
                    target_dm = result.get_model(m.inherited_model_name)
                    if target_dm:
                        m.target_model_slug = sanitize_filename(target_dm.name)
