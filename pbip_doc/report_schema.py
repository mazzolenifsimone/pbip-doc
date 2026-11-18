"""
Data contracts and schema definitions for the PBIP Report documentation JSON output.
Fully serializable with Python standard library.
"""

from dataclasses import dataclass, field, asdict
import re
from typing import List, Dict, Optional, Any, Tuple


def parse_measure_reference(ref_str: str) -> Tuple[str, str]:
    """Parses 'Table'[Measure] or Table[Measure] or [Measure] into (table, field)."""
    if not ref_str:
        return "", ""
    ref = ref_str.strip()
    m = re.match(r"^(?:(?:'([^']+)')|([A-Za-z0-9_ ]+))?\[([^\]]+)\]$", ref)
    if m:
        table = (m.group(1) or m.group(2) or "").strip()
        field = m.group(3).strip()
        return table, field
    return "", ref


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float
    z: int = 0


@dataclass
class SpatialPosition:
    center_x: float
    center_y: float
    zone: str  # "Top-Left", "Top-Center", "Top-Right", "Middle-Left", "Center", "Middle-Right", "Bottom-Left", "Bottom-Center", "Bottom-Right"
    bounding_box: BoundingBox


@dataclass
class EvaluatedMetric:
    table: str
    field: str
    field_type: str  # "MEASURE" | "COLUMN" | "IMPLICIT_MEASURE"
    role: str        # "Y", "Values", "Data", "Size"
    model_key: str   # "Table[Field]"
    aggregation: Optional[str] = None  # "Sum", "Count", "Average", "Min", "Max", etc.
    display_name: Optional[str] = None  # Visual on-screen alias or column header name


@dataclass
class SlicingCoordinate:
    role: str        # "Category (Axis)", "Series (Legend)", "Rows", "Columns", "Tooltips", etc.
    table: str
    field: str
    model_key: str   # "Table[Field]"
    display_name: Optional[str] = None  # Visual on-screen alias or column header name


@dataclass
class ActiveFilter:
    table: str
    field: str
    filter_type: str
    condition: str
    scope: str = "Visual"
    is_locked: bool = False
    operator: Optional[str] = None
    applied_values: Optional[List[str]] = None
    visual_id: Optional[str] = None
    visual_title: Optional[str] = None
    order_by_table: Optional[str] = None
    order_by_measure: Optional[str] = None


@dataclass
class PagePanelFilter:
    scope: str       # "Page Filter Panel (Locked)" | "Page Filter Panel (Interactive)"
    table: str
    field: str
    is_locked: bool
    applied_values: Optional[List[str]] = None
    default_value: Optional[str] = None
    operator: Optional[str] = None
    order_by_table: Optional[str] = None
    order_by_measure: Optional[str] = None


@dataclass
class PageSlicer:
    slicer_visual_id: str
    table: str
    field: str
    model_key: str
    default_selection: str = "All"
    is_synced_across_pages: bool = False


@dataclass
class CalculationContext:
    evaluated_metrics: List[EvaluatedMetric] = field(default_factory=list)
    slicing_coordinates: List[SlicingCoordinate] = field(default_factory=list)
    visual_active_filters: List[ActiveFilter] = field(default_factory=list)
    all_pages_filters: List[PagePanelFilter] = field(default_factory=list)  # Report-level filters ("All pages")
    locked_active_filters: List[PagePanelFilter] = field(default_factory=list)  # Page-level locked
    unlocked_available_filters: List[PagePanelFilter] = field(default_factory=list)  # Page-level interactive
    page_slicers: List[PageSlicer] = field(default_factory=list)
    page_filters: List[PagePanelFilter] = field(default_factory=list)  # Unified Page Filter Panel list

    def __post_init__(self):
        if not self.page_filters:
            # Reconstruct unified list preserving existing filters
            self.page_filters = list(self.locked_active_filters) + list(self.unlocked_available_filters)
        else:
            if not self.locked_active_filters:
                self.locked_active_filters = [
                    f for f in self.page_filters 
                    if f.is_locked and (f.applied_values or f.operator or f.default_value != "All (No filter applied)")
                ]
            if not self.unlocked_available_filters:
                self.unlocked_available_filters = [f for f in self.page_filters if not f.is_locked]


@dataclass
class VisualDefinition:
    visual_id: str
    title: Optional[str]
    visual_type: str
    is_hidden: bool = False
    is_slicer: bool = False
    is_conditional_title: bool = False
    spatial_position: Optional[SpatialPosition] = None
    calculation_context: CalculationContext = field(default_factory=CalculationContext)
    parent_group_name: Optional[str] = None

    @property
    def is_dynamic(self) -> bool:
        """
        Determines whether this visual element is dynamic (in-scope for documentation)
        vs static (purely decorative line, shape, or static image).
        """
        if self.is_slicer:
            return True
        if self.is_conditional_title:
            return True
        if self.calculation_context.evaluated_metrics:
            return True
        if self.calculation_context.slicing_coordinates:
            return True
        if self.calculation_context.visual_active_filters:
            return True
        return False

    def get_effective_evaluated_metrics(self) -> List[EvaluatedMetric]:
        """
        Returns evaluated metrics for this visual, ensuring that any conditional title
        measure reference is included even on raw/synthetic VisualDefinition instances.
        """
        metrics = list(self.calculation_context.evaluated_metrics)
        if self.is_conditional_title and self.title:
            has_cond = any(
                m.role == "Conditional Title" or (m.field and m.field in self.title)
                for m in metrics
            )
            if not has_cond:
                tbl, prop = parse_measure_reference(self.title)
                if prop:
                    metrics.append(
                        EvaluatedMetric(
                            table=tbl or "Model",
                            field=prop,
                            field_type="MEASURE",
                            role="Conditional Title",
                            model_key=f"{tbl}[{prop}]" if tbl else f"[{prop}]",
                        )
                    )
        return metrics


@dataclass
class PageDefinition:
    page_id: str
    display_name: str
    page_number: int
    is_hidden: bool = False
    page_type: str = "NORMAL"  # "NORMAL" | "TOOLTIP" | "DRILLTHROUGH"
    width: int = 1920
    height: int = 1080
    visuals: List[VisualDefinition] = field(default_factory=list)


@dataclass
class ReportSummary:
    total_pages: int = 0
    visible_pages: int = 0
    hidden_pages: int = 0
    total_visuals: int = 0
    visual_types_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class PBIPReportModel:
    report_name: str
    format: str  # "PBIR" | "LEGACY"
    source_path: str
    summary: ReportSummary = field(default_factory=ReportSummary)
    pages: List[PageDefinition] = field(default_factory=list)
    target_dataset_name: Optional[str] = None
    dataset_reference: Optional[Dict[str, Any]] = None
    report_filters: List[PagePanelFilter] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire report model to standard Python dictionary ready for JSON dump."""
        return asdict(self)
