"""
Static CSS and JavaScript assets for native HTML documentation portal.
Enterprise C-Level executive aesthetic: neutral palette, clean borders, professional typography.
Zero third-party dependencies, zero CDN requests, 100% air-gap and file:// protocol safe.
"""

import textwrap

_DARK_THEME_TOKENS_CSS = """color-scheme: dark;
/* Executive Neutral Dark Gray Palette */
--bg-body: #16181d;
--bg-surface: #21252d;
--bg-surface-hover: #2b313b;
--bg-sidebar: #181a1f;
--bg-sidebar-hover: #22262e;
--bg-sidebar-active: #2b313b;
--bg-sidebar-input: #121418;
--bg-sidebar-badge: rgba(255, 255, 255, 0.08);

/* Code Cells Dark Mode (Adaptive) */
--bg-code: #14161a;
--bg-code-header: #1b1e24;
--border-code: #2d333b;
--text-code: #e2e8f0;
--text-code-muted: #8b949e;
--bg-copy-btn: rgba(255, 255, 255, 0.08);
--border-copy-btn: rgba(255, 255, 255, 0.15);
--text-copy-btn: #e2e8f0;
--bg-copy-btn-hover: rgba(255, 255, 255, 0.16);

/* Global Scrollbars Dark Mode */
--scrollbar-track: transparent;
--scrollbar-thumb: #343a46;
--scrollbar-thumb-hover: #4b5563;

--text-main: #d0d7de;
--text-muted: #8b949e;
--text-sidebar: #9da7b3;
--text-sidebar-bright: #f0f3f6;

--border-color: #343a46;
--border-subtle: #272c35;
--border-sidebar: #272c35;

--primary: #d0d7de;
--primary-hover: #f0f3f6;
--accent: #60a5fa;
--accent-hover: #93c5fd;

--link-color: #60a5fa;
--link-hover: #93c5fd;

/* Role Badges Dark Mode (Harmonious desaturated pastel tints) */
--role-fact-bg: rgba(147, 197, 253, 0.12);
--role-fact-text: #93c5fd;
--role-fact-border: rgba(147, 197, 253, 0.25);

--role-dim-bg: rgba(134, 239, 172, 0.12);
--role-dim-text: #a7f3d0;
--role-dim-border: rgba(134, 239, 172, 0.25);

--role-snow-bg: rgba(253, 224, 71, 0.12);
--role-snow-text: #fef08a;
--role-snow-border: rgba(253, 224, 71, 0.25);

--role-bridge-bg: rgba(216, 180, 254, 0.12);
--role-bridge-text: #e9d5ff;
--role-bridge-border: rgba(216, 180, 254, 0.25);

--role-date-bg: rgba(125, 211, 252, 0.12);
--role-date-text: #bae6fd;
--role-date-border: rgba(125, 211, 252, 0.25);

--role-calcgroup-bg: rgba(165, 180, 252, 0.12);
--role-calcgroup-text: #c7d2fe;
--role-calcgroup-border: rgba(165, 180, 252, 0.25);

--role-utility-bg: rgba(212, 212, 216, 0.1);
--role-utility-text: #d4d4d8;
--role-utility-border: rgba(212, 212, 216, 0.2);

--col-imported-bg: rgba(212, 212, 216, 0.08);
--col-imported-text: #cbd5e1;
--col-imported-border: rgba(212, 212, 216, 0.18);

--col-calc-bg: rgba(125, 211, 252, 0.12);
--col-calc-text: #7dd3fc;
--col-calc-border: rgba(125, 211, 252, 0.22);

--col-pq-bg: rgba(196, 181, 253, 0.12);
--col-pq-text: #c4b5fd;
--col-pq-border: rgba(196, 181, 253, 0.22);

--col-key-bg: rgba(253, 224, 71, 0.12);
--col-key-text: #fde047;
--col-key-border: rgba(253, 224, 71, 0.22);

--badge-pk-text: #93c5fd;
--badge-fk-text: #cbd5e1;

/* ETL & Dataflow Pipeline Roles Dark Mode */
--etl-loaded-bg: rgba(110, 231, 183, 0.12);
--etl-loaded-text: #6ee7b7;
--etl-loaded-border: rgba(110, 231, 183, 0.25);

--etl-staging-bg: rgba(252, 211, 77, 0.12);
--etl-staging-text: #fcd34d;
--etl-staging-border: rgba(252, 211, 77, 0.25);

--etl-param-bg: rgba(196, 181, 253, 0.12);
--etl-param-text: #c4b5fd;
--etl-param-border: rgba(196, 181, 253, 0.25);

--etl-func-bg: rgba(125, 211, 252, 0.12);
--etl-func-text: #7dd3fc;
--etl-func-border: rgba(125, 211, 252, 0.25);

--etl-inline-bg: rgba(203, 213, 225, 0.12);
--etl-inline-text: #cbd5e1;
--etl-inline-border: rgba(203, 213, 225, 0.25);

/* Semantic Status & Neutral Badges Dark Mode */
--badge-neutral-bg: rgba(255, 255, 255, 0.06);
--badge-neutral-text: #9da7b3;
--badge-neutral-border: rgba(255, 255, 255, 0.1);

--status-active-bg: rgba(134, 239, 172, 0.12);
--status-active-text: #86efac;
--status-active-border: rgba(134, 239, 172, 0.22);

--status-inactive-bg: rgba(253, 224, 71, 0.12);
--status-inactive-text: #fde047;
--status-inactive-border: rgba(253, 224, 71, 0.22);

/* Visual-Level Filter Badges Dark Mode (Solid Dark Gray, High Contrast) */
--badge-filter-val-bg: #15181e;
--badge-filter-val-text: #f0f6fc;
--badge-filter-val-border: #3b4252;

--badge-filter-type-bg: #272c35;
--badge-filter-type-text: #d0d7de;
--badge-filter-type-border: #444c56;

--badge-filter-locked-bg: #374151;
--badge-filter-locked-text: #f3f4f6;
--badge-filter-locked-border: #6b7280;

--badge-filter-unlocked-bg: #272c35;
--badge-filter-unlocked-text: #9ca3af;
--badge-filter-unlocked-border: #3b4252;"""

STYLE_CSS = (
    """/* pbip-doc-gen - Enterprise BI Documentation Stylesheet */
:root {
  color-scheme: light;
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  
  /* Executive Neutral Light Gray Palette */
  --bg-body: #eaedf0;
  --bg-surface: #f5f7f9;
  --bg-surface-hover: #e2e6eb;
  --bg-sidebar: #f8fafc;
  --bg-sidebar-hover: #edf2f7;
  --bg-sidebar-active: #e2e8f0;
  --bg-sidebar-input: #ffffff;
  --bg-sidebar-badge: #e2e8f0;

  /* Code Cells (Adaptive) */
  --bg-code: #ffffff;
  --bg-code-header: #f1f3f5;
  --border-code: #cbd2d9;
  --text-code: #1f2328;
  --text-code-muted: #57606a;
  --bg-copy-btn: #ffffff;
  --border-copy-btn: #cbd2d9;
  --text-copy-btn: #24292f;
  --bg-copy-btn-hover: #e9ecef;

  /* Global Scrollbars */
  --scrollbar-track: transparent;
  --scrollbar-thumb: #cbd2d9;
  --scrollbar-thumb-hover: #9ca3af;
  
  --text-main: #24292f;
  --text-muted: #57606a;
  --text-sidebar: #57606a;
  --text-sidebar-bright: #1f2328;
  
  --border-color: #cbd2d9;
  --border-subtle: #dde2e6;
  --border-sidebar: #cbd2d9;
  
  --primary: #1e2229;
  --primary-hover: #374151;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;

  --link-color: #1d4ed8;
  --link-hover: #1e40af;

  /* Table Role Badges (Harmonious desaturated pastel tints, refined clean borders) */
  --role-fact-bg: #f0f4f8;
  --role-fact-text: #1e3a5f;
  --role-fact-border: #cbd5e1;

  --role-dim-bg: #f0f7f4;
  --role-dim-text: #164e3b;
  --role-dim-border: #c2e0d3;

  --role-snow-bg: #fdf8f0;
  --role-snow-text: #713f12;
  --role-snow-border: #e8d5b5;

  --role-bridge-bg: #f7f4fa;
  --role-bridge-text: #4c1d95;
  --role-bridge-border: #d8cbde;

  --role-date-bg: #f0f6fa;
  --role-date-text: #0c4a6e;
  --role-date-border: #c6dbe7;

  --role-calcgroup-bg: #f3f4f8;
  --role-calcgroup-text: #2e2d6b;
  --role-calcgroup-border: #d1d3e2;

  --role-utility-bg: #f4f5f7;
  --role-utility-text: #334155;
  --role-utility-border: #cbd5e1;

  /* Column Types (Crisp, desaturated) */
  --col-imported-bg: #f8fafc;
  --col-imported-text: #475569;
  --col-imported-border: #cbd5e1;

  --col-calc-bg: #f0f6fa;
  --col-calc-text: #0369a1;
  --col-calc-border: #bae6fd;

  --col-pq-bg: #f5f3ff;
  --col-pq-text: #6d28d9;
  --col-pq-border: #ddd6fe;

  --col-key-bg: #fefce8;
  --col-key-text: #854d0e;
  --col-key-border: #fef08a;

  --badge-pk-text: #1e3a8a;
  --badge-fk-text: #475569;

  /* ETL & Dataflow Pipeline Roles */
  --etl-loaded-bg: #f0fdf4;
  --etl-loaded-text: #047857;
  --etl-loaded-border: #a7f3d0;

  --etl-staging-bg: #fffbeb;
  --etl-staging-text: #b45309;
  --etl-staging-border: #fde68a;

  --etl-param-bg: #f5f3ff;
  --etl-param-text: #6d28d9;
  --etl-param-border: #ddd6fe;

  --etl-func-bg: #f0f9ff;
  --etl-func-text: #0284c7;
  --etl-func-border: #bae6fd;

  --etl-inline-bg: #f8fafc;
  --etl-inline-text: #475569;
  --etl-inline-border: #cbd5e1;

  /* Semantic Status & Neutral Badges */
  --badge-neutral-bg: #f4f5f7;
  --badge-neutral-text: #4b5563;
  --badge-neutral-border: #cbd5e1;

  --status-active-bg: #ecfdf5;
  --status-active-text: #065f46;
  --status-active-border: #a7f3d0;

  --status-inactive-bg: #fefce8;
  --status-inactive-text: #854d0e;
  --status-inactive-border: #fef08a;

  /* Visual-Level Filter Badges (High Contrast, Enterprise Neutral) */
  --badge-filter-val-bg: #eef2f6;
  --badge-filter-val-text: #0f172a;
  --badge-filter-val-border: #cbd5e1;

  --badge-filter-type-bg: #e2e8f0;
  --badge-filter-type-text: #1e293b;
  --badge-filter-type-border: #94a3b8;

  --badge-filter-locked-bg: #cbd5e1;
  --badge-filter-locked-text: #0f172a;
  --badge-filter-locked-border: #94a3b8;

  --badge-filter-unlocked-bg: #e2e8f0;
  --badge-filter-unlocked-text: #1e293b;
  --badge-filter-unlocked-border: #cbd5e1;

  /* Geometric Minimalist Radii (Clean, sharp, less material design) */
  --radius-sm: 2px;
  --radius-md: 3px;
  --radius-lg: 4px;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
/* __DARK_THEME_TOKENS_MEDIA__ */
  }
}

:root[data-theme="light"] {
  color-scheme: light;
}

:root[data-theme="dark"],
[data-theme="dark"] {
/* __DARK_THEME_TOKENS_DATA__ */
}


/* Base Reset & Core Typography */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
}

/* Global Uniform Scrollbars (WebKit & Blink) */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--scrollbar-track);
}

::-webkit-scrollbar-thumb {
  background-color: var(--scrollbar-thumb);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background-color: var(--scrollbar-thumb-hover);
}

::-webkit-scrollbar-corner {
  background: transparent;
}

body {
  font-family: var(--font-family);
  background-color: var(--bg-body);
  color: var(--text-main);
  line-height: 1.5;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Core Links & Non-Purple Visited State */
a {
  color: var(--link-color);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s ease, text-decoration 0.15s ease;
}

a:visited {
  color: var(--link-color);
}

a:hover, a:focus {
  color: var(--link-hover);
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* Master Layout Grid */
.wiki-layout {
  display: flex;
  min-height: 100vh;
  background-color: var(--bg-body);
  color: var(--text-main);
}

/* Sidebar Styles */
.sidebar-toggle-input {
  display: none;
}

.wiki-sidebar {
  width: 330px;
  background-color: var(--bg-sidebar);
  color: var(--text-sidebar);
  border-right: 1px solid var(--border-sidebar);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  flex-shrink: 0;
  transition: margin-left 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

#sidebar-toggle:checked ~ .wiki-sidebar {
  margin-left: -330px;
}

.sidebar-header {
  padding: 1.25rem 1.25rem 1rem 1.25rem;
  border-bottom: 1px solid var(--border-sidebar);
}

.sidebar-logo,
.sidebar-logo:visited,
.sidebar-title-link,
.sidebar-title-link:visited {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
  color: var(--text-sidebar-bright);
  text-decoration: none;
  width: 100%;
  min-width: 0;
  transition: opacity 0.15s ease;
}

.sidebar-logo:hover,
.sidebar-logo:hover:visited,
.sidebar-title-link:hover,
.sidebar-title-link:hover:visited {
  color: var(--text-sidebar-bright);
  text-decoration: none;
  opacity: 0.9;
}

.sidebar-logo-image {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  width: 100%;
}

.sidebar-logo-image svg.logo-icon,
.sidebar-logo-image svg.sidebar-title-icon,
svg.logo-icon,
svg.sidebar-title-icon {
  height: 68px;
  width: auto;
  max-width: 220px;
  flex-shrink: 0;
  display: block;
}

.sidebar-logo-image img.logo-icon,
.sidebar-logo-image img.sidebar-title-icon,
img.logo-icon,
img.sidebar-title-icon {
  max-height: 68px;
  max-width: 220px;
  width: auto;
  height: auto;
  object-fit: contain;
  flex-shrink: 0;
  display: block;
}

.sidebar-logo-text {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  gap: 0.5rem;
  min-width: 0;
}

.sidebar-logo-text > span:first-child,
.sidebar-logo .logo-text,
.sidebar-title-link span:not(.sidebar-badge) {
  display: block;
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-sidebar-bright);
  line-height: 1.35;
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex: 1;
}

.sidebar-badge {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.15rem 0.45rem;
  border-radius: 2px;
  background-color: transparent;
  color: var(--text-sidebar);
  border: 1px solid var(--border-sidebar);
  margin-left: auto;
  flex-shrink: 0;
}

.sidebar-search-container {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-sidebar);
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon-svg {
  position: absolute;
  left: 0.75rem;
  width: 14px;
  height: 14px;
  color: var(--text-sidebar);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.45rem 0.6rem 0.45rem 2.2rem;
  background-color: var(--bg-sidebar-input);
  border: 1px solid var(--border-sidebar);
  border-radius: var(--radius-sm);
  color: var(--text-sidebar-bright);
  font-size: 0.825rem;
  outline: none;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.search-input:focus {
  border-color: var(--primary);
  background-color: var(--bg-sidebar-input);
  box-shadow: 0 0 0 1px var(--primary);
}

.search-input::placeholder {
  color: var(--text-sidebar);
  opacity: 0.75;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0.5rem;
}

.nav-section {
  margin-bottom: 1rem;
}

.nav-section-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  color: var(--text-sidebar);
  padding: 0.35rem 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  opacity: 0.85;
}

.nav-list {
  list-style: none;
}

.nav-item {
  margin: 1px 0;
}

.nav-link,
.nav-link:visited {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0;
  padding: 0.35rem 0.5rem 0.35rem 0.75rem;
  color: var(--text-sidebar);
  text-decoration: none;
  border-radius: var(--radius-sm);
  font-size: 0.825rem;
  transition: all 0.12s ease;
  min-width: 0;
}

.nav-link > span:first-child {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex: 1;
  padding-right: 0.5rem;
}

.nav-link:hover,
.nav-link:hover:visited {
  background-color: var(--bg-sidebar-hover);
  color: var(--text-sidebar-bright);
}

.nav-link:hover > span:first-child,
.nav-link:hover:visited > span:first-child {
  color: var(--text-sidebar-bright);
}

.nav-link.active,
.nav-link.active:visited {
  background-color: var(--bg-sidebar-active);
  color: var(--text-sidebar-bright);
  font-weight: 600;
}

.nav-badge-cell {
  width: 66px;
  min-width: 66px;
  max-width: 66px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  border-left: 1px solid var(--border-sidebar);
  margin-left: auto;
  flex-shrink: 0;
  box-sizing: border-box;
  padding: 0.15rem 0.25rem;
}

.nav-badge-cell .badge,
.nav-badge-cell .nav-item-badge {
  background-color: transparent !important;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border: 1px solid currentColor;
  border-radius: 2px;
  white-space: nowrap;
  box-sizing: border-box;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: auto;
  min-width: 0;
  max-width: 100%;
  line-height: 1.2;
}

.nav-item-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  border: 1px solid currentColor;
  border-radius: 2px;
  box-sizing: border-box;
  background-color: transparent !important;
  white-space: nowrap;
}

.nav-item .badge {
  background-color: transparent !important;
}

.nav-subgroup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.35rem 0.75rem;
  color: var(--text-sidebar);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.12s ease, color 0.12s ease;
}

.nav-subgroup-header > span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
  flex: 1;
}

.nav-subgroup-header .nav-item-badge {
  margin-left: auto;
  flex-shrink: 0;
}

.nav-subgroup-header:hover {
  background-color: var(--bg-sidebar-hover);
  color: var(--text-sidebar-bright);
}

.nav-folder-icon {
  width: 20px;
  height: 20px;
  margin-right: 6px;
  opacity: 0.85;
  flex-shrink: 0;
  vertical-align: text-bottom;
}

.nav-subgroup-icon {
  width: 20px;
  height: 20px;
  margin-right: 6px;
  color: var(--text-sidebar);
  opacity: 0.85;
  flex-shrink: 0;
  vertical-align: text-bottom;
}

.nav-subgroup-header:hover .nav-subgroup-icon {
  color: var(--text-sidebar-bright);
  opacity: 1;
}

.nav-subgroup-items {
  padding-left: 0.75rem;
}

.subgroup-icon {
  font-size: 0.75rem;
  opacity: 0.6;
}

/* Sidebar Footer & Version */
.sidebar-footer {
  padding: 0.75rem 1.25rem;
  border-top: 1px solid var(--border-sidebar);
  background-color: var(--bg-sidebar);
  flex-shrink: 0;
}

.sidebar-footer-info {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.75rem;
  color: var(--text-sidebar-muted);
}

.sidebar-footer .footer-lbl {
  color: var(--text-sidebar-muted);
}

.sidebar-footer .footer-app {
  font-weight: 700;
  color: var(--text-sidebar-bright);
}

.sidebar-footer .footer-version {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  background: rgba(255, 255, 255, 0.08);
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-sm);
  color: var(--text-sidebar);
  margin-left: auto;
}

/* Main Content Area */
.wiki-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* Topbar Header */
.wiki-topbar {
  background-color: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  padding: 0.75rem 2rem;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 0.75rem;
  position: sticky;
  top: 0;
  z-index: 20;
}

.sidebar-toggle-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: color 0.15s ease, background-color 0.15s ease;
  user-select: none;
  flex-shrink: 0;
  margin-right: 0.25rem;
}

.sidebar-toggle-btn:hover {
  color: var(--text-main);
  background-color: var(--bg-surface-hover);
}

.breadcrumbs {
  font-size: 0.85rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.breadcrumbs a {
  color: var(--text-muted);
  text-decoration: none;
}

.breadcrumbs a:hover {
  color: var(--text-main);
  text-decoration: underline;
}

.breadcrumb-sep {
  opacity: 0.5;
}

.breadcrumb-current {
  color: var(--text-main);
  font-weight: 600;
}

/* Main Article Content */
.wiki-article {
  padding: 2rem 2.5rem 4rem 2.5rem;
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 1.75rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-main);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  line-height: 1.35;
}

.page-title .badge {
  display: inline-flex;
  align-items: center;
  font-size: 0.8rem;
  padding: 0.2rem 0.6rem;
  border-radius: var(--radius-sm);
  line-height: 1.2;
  vertical-align: middle;
}

.page-title-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding-left: 0.75rem;
  border-left: 1px solid var(--border-color);
  color: var(--text-muted);
  flex-shrink: 0;
}

.page-title-icon svg {
  display: block;
}

.page-subtitle {
  font-size: 0.95rem;
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}

/* KPI Summary Cards Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.75rem;
}

.kpi-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
}

.kpi-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.kpi-value {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-main);
  line-height: 1.3;
  display: flex;
  align-items: center;
  min-height: 2.2rem;
}

.kpi-value .badge {
  font-size: 0.85rem;
  padding: 0.2rem 0.65rem;
  vertical-align: middle;
}

.kpi-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.45rem;
}

/* Zero-JS In-Page Section Radio Tabs (Pure CSS Architecture) */
.page-tabs-container {
  display: flex;
  flex-direction: column;
  margin-top: 1.25rem;
}

.page-tab-radio {
  position: absolute;
  opacity: 0;
  pointer-events: none;
  width: 0;
  height: 0;
}

.page-tab-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
  padding: 0.35rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 1.5rem;
}

.page-tab-btn {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem 0.85rem;
  font-size: 0.825rem;
  font-weight: 500;
  color: var(--text-muted);
  background-color: transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.page-tab-btn:hover {
  color: var(--text-main);
  background-color: var(--bg-surface-hover);
}

.page-quicknav {
  display: none;
}

.content-section {
  display: none;
  margin-bottom: 2.25rem;
  scroll-margin-top: 1.5rem;
}

@media print {
  .page-tab-bar, .page-tab-radio {
    display: none !important;
  }
  .content-section {
    display: block !important;
  }
}

.section-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 0.85rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Ensure all content containers are visible in Zero-JS mode */
.tab-content {
  display: block !important;
  margin-bottom: 1.5rem;
}

/* Native HTML5 Details/Summary in Sidebar & Collapsible Sections */
details.nav-details {
  width: 100%;
}

details.nav-details summary.nav-subgroup-header {
  list-style: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}

details.nav-details summary::-webkit-details-marker {
  display: none;
}

details.nav-details summary::after {
  content: "▸";
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: auto;
}

details.nav-details[open] summary::after {
  content: "▾";
}

/* Target highlighting for anchor navigation */
:target {
  scroll-margin-top: 2rem;
}

.calc-col-card:target {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

/* Content Cards & Sections */
.content-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
}

.content-card-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Multi-Function Unified Block Components */
.content-block-section {
  margin-top: 1.25rem;
  padding-top: 1.25rem;
  border-top: 1px solid var(--border-subtle);
}

.content-block-section:first-child {
  margin-top: 0;
  padding-top: 0;
  border-top: none;
}

.content-block-subtitle {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.description-card {
  border-left: 4px solid var(--accent);
}

.description-text {
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--text-main);
  margin: 0;
}

.description-empty {
  color: var(--text-muted);
  font-style: italic;
}

/* Calculated Column Card & Deep-Link Highlighting */
.calc-col-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.25rem;
  margin-bottom: 1.25rem;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.calc-col-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.calc-col-title-group {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.calc-col-name {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-main);
}

.calc-col-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.highlight-pulse {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 1px var(--accent) !important;
}

/* Data Tables */
.table-toolbar {
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.table-filter-input {
  width: 280px;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background-color: var(--bg-surface);
  color: var(--text-main);
  font-size: 0.8rem;
  outline: none;
}

.table-filter-input:focus {
  border-color: var(--text-main);
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background-color: var(--bg-surface);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.825rem;
}

.data-table th {
  background-color: var(--bg-body);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

.data-table th svg,
.data-table th .table-header-icon {
  vertical-align: -2px;
  margin-right: 5px;
  display: inline-block;
}

.data-table td {
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-main);
  vertical-align: middle;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tr:hover td {
  background-color: var(--bg-surface-hover);
}

.data-table a {
  color: var(--link-color);
  text-decoration: none;
  font-weight: 500;
}

.data-table a:visited {
  color: var(--link-color);
}

.data-table a:hover {
  color: var(--link-hover);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.data-table code {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  background: var(--bg-surface-hover);
  padding: 0.15rem 0.35rem;
  border-radius: 3px;
  border: 1px solid var(--border-color);
}

/* Badges & Tags */
.badge {
  display: inline-flex;
  align-items: center;
  font-size: 0.725rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  white-space: nowrap;
  line-height: 1.3;
}

/* Table Role Badges - Transparent Background, Squared Colored Border, Consistent with Type */
.badge-role-fact, .badge-fact {
  background-color: transparent;
  color: var(--role-fact-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-role-dim {
  background-color: transparent;
  color: var(--role-dim-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

/* Neutral Tags & Modifiers */
.badge-dim, .badge-neutral {
  background-color: var(--badge-neutral-bg);
  color: var(--badge-neutral-text);
  border: 1px solid var(--badge-neutral-border);
}

/* Filter Status Badges (Locked / Unlocked - Subtle, Non-Flashy Contrast) */
.badge-filter-locked {
  background-color: var(--badge-filter-locked-bg);
  color: var(--badge-filter-locked-text);
  border: 1px solid var(--badge-filter-locked-border);
  font-weight: 600;
}

.badge-filter-unlocked {
  background-color: var(--badge-filter-unlocked-bg);
  color: var(--badge-filter-unlocked-text);
  border: 1px solid var(--badge-filter-unlocked-border);
  font-weight: 500;
}

.badge-outline {
  background-color: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border-color);
  border-radius: 2px;
}

/* Semantic Status Badges */
.badge-status-active {
  background-color: var(--status-active-bg);
  color: var(--status-active-text);
  border: 1px solid var(--status-active-border);
}

.badge-status-inactive {
  background-color: var(--status-inactive-bg);
  color: var(--status-inactive-text);
  border: 1px solid var(--status-inactive-border);
}

.badge-role-snowflake, .badge-snowflake {
  background-color: transparent;
  color: var(--role-snow-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-role-bridge, .badge-bridge {
  background-color: transparent;
  color: var(--role-bridge-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-role-date, .badge-date {
  background-color: transparent;
  color: var(--role-date-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-role-calcgroup {
  background-color: transparent;
  color: var(--role-calcgroup-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-role-utility {
  background-color: transparent;
  color: var(--role-utility-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

/* ETL & Dataflow Pipeline Badges - Transparent Background, Squared Colored Border */
.badge-etl-loaded, .badge-loaded {
  background-color: transparent;
  color: var(--etl-loaded-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-etl-staging, .badge-staging {
  background-color: transparent;
  color: var(--etl-staging-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-etl-param, .badge-param, .badge-parameter {
  background-color: transparent;
  color: var(--etl-param-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-etl-func, .badge-func, .badge-function {
  background-color: transparent;
  color: var(--etl-func-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-etl-inline, .badge-inline {
  background-color: transparent;
  color: var(--etl-inline-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

/* Column Origin Badges */
.badge-imported {
  background-color: var(--col-imported-bg);
  color: var(--col-imported-text);
  border: 1px solid var(--col-imported-border);
}

.badge-calc, .badge-pq {
  background-color: var(--badge-neutral-bg);
  color: var(--link-color);
  border: 1px solid var(--badge-neutral-border);
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s ease;
}

.badge-calc:hover, .badge-pq:hover {
  text-decoration: underline;
  border-color: var(--accent);
}

.badge-pq:hover {
  text-decoration: underline;
  border-color: var(--col-pq-text);
}

.badge-key {
  background-color: var(--col-key-bg);
  color: var(--col-key-text);
  border: 1px solid var(--col-key-border);
}

.badge-pk {
  background-color: transparent;
  color: var(--badge-pk-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-fk {
  background-color: transparent;
  color: var(--badge-fk-text);
  border: 1px solid currentColor;
  border-radius: 2px;
}

.badge-type {
  background-color: var(--bg-surface-hover);
  color: var(--text-muted);
  border: 1px solid var(--border-color);
  font-family: var(--font-mono);
  font-size: 0.7rem;
}

/* Visual-Level Filter Badges & Condition Tags */
.filter-condition-badge {
  background-color: var(--badge-filter-val-bg);
  color: var(--badge-filter-val-text);
  border: 1px solid var(--badge-filter-val-border);
  font-family: var(--font-mono);
  font-size: 0.775rem;
  font-weight: 600;
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
  display: inline-block;
  line-height: 1.35;
  vertical-align: middle;
}

.badge-filter-type {
  background-color: var(--badge-filter-type-bg);
  color: var(--badge-filter-type-text);
  border: 1px solid var(--badge-filter-type-border);
  font-size: 0.7rem;
  font-weight: 700;
  padding: 0.12rem 0.45rem;
  border-radius: var(--radius-sm);
  display: inline-flex;
  align-items: center;
  letter-spacing: 0.02em;
  vertical-align: middle;
}

/* Code Snippets & Containers */
.code-container {
  background-color: var(--bg-code);
  border: 1px solid var(--border-code);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin: 0.75rem 0;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.45rem 0.85rem;
  background-color: var(--bg-code-header);
  border-bottom: 1px solid var(--border-code);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-code-muted);
}

.code-container pre {
  padding: 1rem;
  overflow-x: auto;
  margin: 0;
  background-color: transparent;
}

.code-container code {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--text-code);
  line-height: 1.5;
  background: transparent;
  border: none;
  padding: 0;
}

.copy-btn {
  background-color: var(--bg-copy-btn);
  border: 1px solid var(--border-copy-btn);
  color: var(--text-copy-btn);
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.copy-btn:hover {
  background-color: var(--bg-copy-btn-hover);
  color: var(--text-copy-btn);
}

/* Inline Code Elements */
:not(pre) > code {
  font-family: var(--font-mono);
  font-size: 0.825em;
  background-color: var(--bg-surface-hover);
  color: var(--text-main);
  padding: 0.15rem 0.35rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

/* Visual Container Cards */
.visual-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 1.25rem;
  overflow: hidden;
}

.visual-card-header {
  padding: 0.75rem 1rem;
  background-color: var(--bg-body);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.visual-card-body {
  padding: 1rem;
  display: flex;
  gap: 1.5rem;
}

.visual-minimap-col {
  width: 260px;
  flex-shrink: 0;
}

.visual-minimap-img {
  width: 100%;
  height: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: transparent;
  display: block;
}

.visual-specs-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.spec-group-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.spec-list {
  list-style: none;
  font-size: 0.825rem;
}

.spec-list li {
  margin-bottom: 0.25rem;
}

/* Star Cluster Pure CSS Radio Tabs (Zero-JS Architecture) */
.starcluster-container {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1.5rem;
}

.starcluster-radio {
  position: absolute;
  opacity: 0;
  pointer-events: none;
  width: 0;
  height: 0;
}

.starcluster-nav-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0.35rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.starcluster-nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.85rem;
  font-size: 0.825rem;
  font-weight: 600;
  color: var(--text-muted);
  background-color: transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.15s ease;
  user-select: none;
}

.starcluster-nav-btn:hover {
  color: var(--text-main);
  background-color: var(--bg-surface-hover);
}

.cluster-badge {
  display: inline-block;
  font-size: 0.72rem;
  padding: 0.1rem 0.45rem;
  border-radius: 9999px;
  background-color: var(--bg-surface-hover);
  border: 1px solid var(--border-color);
  color: var(--text-muted);
  font-weight: 500;
}

.starcluster-panel {
  display: none;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.25rem;
}

.starcluster-meta-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid var(--border-color);
  font-size: 0.825rem;
}

.starcluster-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.45rem;
  font-weight: 500;
  color: var(--text-muted);
}

.starcluster-chip strong {
  color: var(--text-main);
}

.starcluster-chip .badge {
  font-size: 0.65rem;
  font-weight: 700;
  padding: 0.1rem 0.35rem;
  vertical-align: middle;
}

/* Responsive Breakpoints */
@media (max-width: 900px) {
  .wiki-layout {
    flex-direction: column;
  }
  .wiki-sidebar {
    width: 100%;
    height: auto;
    position: relative;
  }
  #sidebar-toggle:checked ~ .wiki-sidebar {
    display: none;
    margin-left: 0;
  }
  .visual-card-body {
    flex-direction: column;
  }
  .visual-minimap-col {
    width: 100%;
  }
  .wiki-article {
    padding: 1.25rem;
  }
}
"""
    .replace("/* __DARK_THEME_TOKENS_MEDIA__ */", textwrap.indent(_DARK_THEME_TOKENS_CSS, "    "))
    .replace("/* __DARK_THEME_TOKENS_DATA__ */", textwrap.indent(_DARK_THEME_TOKENS_CSS, "  "))
)

# Zero-JS Policy: PBIP HTML documentation is 100% pure HTML5 and CSS.
# No JavaScript files or script tags are emitted or executed, ensuring full compliance
# with strict enterprise SharePoint Modern sandboxes, air-gapped intranets, and CSP policies.
APP_JS = ""


def get_html_css() -> str:
    """Returns the core CSS stylesheet for the HTML documentation portal."""
    return STYLE_CSS


def get_html_js() -> str:
    """
    Returns the client-side JavaScript for the HTML documentation portal.
    In Zero-JS mode, this always returns an empty string as no JavaScript is used.
    """
    return APP_JS

