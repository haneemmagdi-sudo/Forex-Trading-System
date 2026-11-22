---
name: Forex Trading System
description: Institutional algorithmic forex command terminal
colors:
  bg-base: "#0B0E14"
  bg-surface: "#111722"
  bg-elevated: "#182232"
  border-subtle: "#1E293B"
  border-strong: "#334155"
  text-primary: "#F8FAFC"
  text-secondary: "#94A3B8"
  text-muted: "#64748B"
  accent-green: "#10B981"
  accent-red: "#EF4444"
  accent-amber: "#F59E0B"
  accent-cyan: "#06B6D4"
typography:
  display:
    fontFamily: "JetBrains Mono, SF Mono, Consolas, monospace"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  heading:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, system-ui, -apple-system, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "0em"
  tabular:
    fontFamily: "JetBrains Mono, SF Mono, Consolas, monospace"
    fontSize: "0.875rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0em"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  card-panel:
    backgroundColor: "{colors.bg-surface}"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.md}"
    padding: "16px"
  badge-long:
    backgroundColor: "rgba(16, 185, 129, 0.15)"
    textColor: "{colors.accent-green}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
  badge-short:
    backgroundColor: "rgba(239, 68, 68, 0.15)"
    textColor: "{colors.accent-red}"
    rounded: "{rounded.sm}"
    padding: "4px 8px"
---

# Design System

## Overview

The design system for the Forex Trading System delivers an institutional trading floor terminal aesthetic. The interface is optimized for continuous operation, maximum data density, instant cognitive recognition of market states, and zero visual slop.

Mode: **Operate** — Every element exists to provide actionable clarity, track exposure, and manage risk without extraneous decoration.

## Colors

- **Surfaces:**
  - Base Background: `{colors.bg-base}` (`#0B0E14`) — deep dark slate reducing eye fatigue during prolonged monitoring sessions.
  - Panel Surface: `{colors.bg-surface}` (`#111722`) — clear card definition with zero intrusive borders.
  - Elevated Popovers & Tooltips: `{colors.bg-elevated}` (`#182232`).
- **Data & Text:**
  - Primary Text: `{colors.text-primary}` (`#F8FAFC`).
  - Secondary Labels & Headers: `{colors.text-secondary}` (`#94A3B8`).
  - Muted Timestamps & Meta: `{colors.text-muted}` (`#64748B`).
- **Semantic Financial Signals:**
  - Long / Profit / Healthy: `{colors.accent-green}` (`#10B981`).
  - Short / Loss / Warning Limit: `{colors.accent-red}` (`#EF4444`).
  - Caution / Shadow Council / Hold: `{colors.accent-amber}` (`#F59E0B`).
  - Execution Engine / Connectivity: `{colors.accent-cyan}` (`#06B6D4`).

## Typography

- **Headers & Interface Copy:** Clean grotesque system font stack with deliberate optical hierarchy.
- **Financial & Market Data:** Monospace with enabled tabular numbers (`tabular-nums`) to ensure price updates, bid/ask spreads, and lot sizes never jump horizontally on re-render.
- **Hierarchy Scale:**
  - Page Titles: 20px / Semibold
  - Section Headers: 16px / Semibold
  - Body & Table Cells: 14px / Regular
  - Metric Values: 16px–24px / Tabular Semibold
  - Captions & Sub-labels: 12px / Medium (strict floor: no UI text below 11px)

## Layout

- Modular dashboard grid with 12-column flexibility.
- Standard 12px / 16px gutters between analytical modules.
- Compact padding inside metric tiles (12px–16px) to maintain high information density without claustrophobic crowding.

## Elevation & Depth

- Low-elevation aesthetic: depth is communicated via subtle 1px border dividers (`{colors.border-subtle}`) and slight background tint shifts rather than large fuzzy drop shadows.
- No colored halo glows or saturated radial gradients behind cards.

## Shapes

- Restrained corner rounding: `4px` (`{rounded.sm}`) for status tags and inputs, `6px` (`{rounded.md}`) for analytical cards.
- Avoid large circular pill buttons or exaggerated bubbly radius corners that clash with trading data grids.

## Components

- **Metric Cards:** Compact panel displaying ticker, current bid/ask, daily change percentage, and active strategy state.
- **Agent Council Table:** Tabular list showing agent votes (Market Analyst, HMM, Order Flow, Debate), confidence scores, and shadow consensus.
- **Execution Log:** Scrollable monospace event log with timestamp, action type, pair, volume, and execution status.
- **Kill-Switch / Risk Banner:** High-priority pinned status bar reflecting gateway health and drawdown thresholds.

## Do's and Don'ts

### Do
- Always use monospace tabular numbers (`font-variant-numeric: tabular-nums`) for currency prices, timestamps, and PnL.
- Accompany color status changes with explicit text or directional icons (`+` / `-`, `▲` / `▼`).
- Use subtle solid tints for badges (`rgba(16, 185, 129, 0.12)`).
- Preserve high contrast (> 4.5:1) for all critical financial figures.

### Don't
- **NO AI Slop:** No purple-to-blue decorative gradients (`from-purple-500 to-indigo-500`).
- **NO Side-Tabs:** No thick colored left/right borders on cards (`border-r-4`, `border-l-4`).
- **NO Nested Cards:** Avoid wrapping cards inside cards; use dividers and clean whitespace instead.
- **NO Gradient Text:** Never apply text-clip gradients to price quotes or metrics.
- **NO Floating Cursors or Marquees:** No artificial typewriter cursors or auto-scrolling tickers.
- **NO Sub-11px Text:** Keep all interactive and data text strictly at or above 11px.
