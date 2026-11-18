"""
PBIP Relationship Configuration and Color Design Tokens.
Single source of truth for table roles, badges, and diagram color tokens.
Pure Python standard library implementation with zero external dependencies.
"""

from typing import Any, Dict


ROLE_CONFIG: Dict[str, Dict[str, Any]] = {
    "FACT": {
        "short": "Fact",
        "badge_class": "badge-role-fact",
        "diagram_class": "fact",
        "light": {
            "badge_bg": "#f0f4f8",
            "badge_fg": "#1e3a5f",
            "badge_border": "#cbd5e1",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(147, 197, 253, 0.12)",
            "badge_fg": "#93c5fd",
            "badge_border": "rgba(147, 197, 253, 0.25)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
    "DIMENSION": {
        "short": "Dim",
        "badge_class": "badge-role-dim",
        "diagram_class": "dim",
        "light": {
            "badge_bg": "#f0f7f4",
            "badge_fg": "#164e3b",
            "badge_border": "#c2e0d3",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(134, 239, 172, 0.12)",
            "badge_fg": "#a7f3d0",
            "badge_border": "rgba(134, 239, 172, 0.25)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
    "LOOKUP_OUTRIGGER": {
        "short": "Snow",
        "badge_class": "badge-role-snowflake",
        "diagram_class": "snow",
        "light": {
            "badge_bg": "#fdf8f0",
            "badge_fg": "#713f12",
            "badge_border": "#e8d5b5",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(253, 224, 71, 0.12)",
            "badge_fg": "#fef08a",
            "badge_border": "rgba(253, 224, 71, 0.25)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
    "BRIDGE": {
        "short": "Bridge",
        "badge_class": "badge-role-bridge",
        "diagram_class": "bridge",
        "light": {
            "badge_bg": "#f7f4fa",
            "badge_fg": "#4c1d95",
            "badge_border": "#d8cbde",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(216, 180, 254, 0.12)",
            "badge_fg": "#e9d5ff",
            "badge_border": "rgba(216, 180, 254, 0.25)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
    "DATE_DIMENSION": {
        "short": "Date",
        "badge_class": "badge-role-date",
        "diagram_class": "date",
        "light": {
            "badge_bg": "#f0f6fa",
            "badge_fg": "#0c4a6e",
            "badge_border": "#c6dbe7",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(125, 211, 252, 0.12)",
            "badge_fg": "#bae6fd",
            "badge_border": "rgba(125, 211, 252, 0.25)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
    "CALCULATION_GROUP": {
        "short": "CalcGroup",
        "badge_class": "badge-role-calcgroup",
        "diagram_class": "calcgroup",
        "light": {
            "badge_bg": "#f3f4f8",
            "badge_fg": "#2e2d6b",
            "badge_border": "#d1d3e2",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(165, 180, 252, 0.12)",
            "badge_fg": "#c7d2fe",
            "badge_border": "rgba(165, 180, 252, 0.25)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
    "PARAMETER_UTILITY": {
        "short": "Utility",
        "badge_class": "badge-role-utility",
        "diagram_class": "utility",
        "light": {
            "badge_bg": "#f4f5f7",
            "badge_fg": "#334155",
            "badge_border": "#cbd5e1",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(212, 212, 216, 0.1)",
            "badge_fg": "#d4d4d8",
            "badge_border": "rgba(212, 212, 216, 0.2)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
    "UNKNOWN": {
        "short": "Utility",
        "badge_class": "badge-role-utility",
        "diagram_class": "utility",
        "light": {
            "badge_bg": "#f4f5f7",
            "badge_fg": "#334155",
            "badge_border": "#cbd5e1",
            "header_bg": "#f8fafc",
            "card_border": "#cbd5e1",
            "divider": "#e2e8f0",
        },
        "dark": {
            "badge_bg": "rgba(212, 212, 216, 0.1)",
            "badge_fg": "#d4d4d8",
            "badge_border": "rgba(212, 212, 216, 0.2)",
            "header_bg": "#1e2229",
            "card_border": "#343a46",
            "divider": "#2d333b",
        },
    },
}


def normalize_role_key(role: Any) -> str:
    """Normalizes role strings, enums, or aliases to canonical ROLE_CONFIG key."""
    r = (role.value if hasattr(role, "value") else str(role or "UNKNOWN")).upper()
    if r in ("FACT", "FACT_TABLE"):
        return "FACT"
    elif r in ("DIMENSION", "DIM"):
        return "DIMENSION"
    elif r in ("LOOKUP_OUTRIGGER", "SNOWFLAKE", "OUTRIGGER", "SNOW"):
        return "LOOKUP_OUTRIGGER"
    elif r in ("BRIDGE", "BRIDGE_TABLE"):
        return "BRIDGE"
    elif r in ("DATE_DIMENSION", "DATE", "CALENDAR"):
        return "DATE_DIMENSION"
    elif r in ("CALCULATION_GROUP", "CALCGROUP"):
        return "CALCULATION_GROUP"
    elif r in ("PARAMETER_UTILITY", "UTILITY", "PARAMETER"):
        return "PARAMETER_UTILITY"
    return "UNKNOWN"


def get_table_role_short(role: Any) -> str:
    """Returns canonical short display label for a table role (e.g. 'Fact', 'Dim')."""
    key = normalize_role_key(role)
    return ROLE_CONFIG.get(key, ROLE_CONFIG["UNKNOWN"])["short"]


def get_table_role_badge_class(role: Any) -> str:
    """Returns CSS badge class for a table role (e.g. 'badge-role-fact')."""
    key = normalize_role_key(role)
    return ROLE_CONFIG.get(key, ROLE_CONFIG["UNKNOWN"])["badge_class"]
