# Demo Script: Trust-Weighted Care Gap Navigator

## Overview

This script is designed for a ~7-10 minute audio walkthrough of the Care Gap Navigator
application. Each section has a suggested pace. Speak naturally throughout — this is a
product demo for a domain-expert audience (public health planners, policymakers, and
data analysts).

---

## 1. Introduction — The Problem We Solve (60 seconds)

Welcome. This is the Trust-Weighted Care Gap Navigator, built on Databricks.

India faces a critical healthcare challenge: we don't know where the gaps are. A
district may appear well-served on paper because a hospital exists, but that hospital
might lack an ICU, might have unreliable data, or might serve a population far larger
than its capacity. Meanwhile, underserved communities go unnoticed because their data is
simply absent — not flagged, just invisible.

This application solves that problem. It combines government health surveys, facility
registries, and capability evidence into a single unified view of India's healthcare
supply — weighted by trust. Every score carries a confidence level: green means
well-served, red means a verified gap, and transparent means we simply don't know.

The app runs on Databricks, powered by Unity Catalog, with a FastAPI backend and a
browser-based frontend. Let me walk through each page.

---

## 2. Home Page (15 seconds)

The home screen is a landing page with a simple headline: "Closing India's Medical
Deserts with Data." From here, use the sidebar to navigate between pages. The sidebar
also contains global filters that persist across all pages — domain, capability, state,
and map resolution.

---

## 3. Care Gap Navigator — The Main Map (2 minutes)

This is the heart of the application. Select "Care Gap Navigator" from the sidebar.

You're looking at a hexagon map of India. Each hexagon represents a region at a
configurable resolution — level 6 for state-level, level 7 or 8 for finer granularity.

The color tells you the care score: green means well-served, yellow means partial,
red means a care gap. But the opacity tells you something equally important —
confidence. A fully opaque hexagon means we have strong evidence. A pale, faded
hexagon means we lack data, so trust that score less.

Above the map, a KPI strip shows aggregate metrics: total facilities tracked,
percentage of regions with data, and overall coverage scores.

Below the map, a disease-burden ribbon lets you overlay NFHS-5 health indicators —
infant mortality, anemia rates, and more — at the district level. This lets you ask
questions like: where do high disease burden AND low care supply overlap?

Select any hexagon on the map to drill down. A panel opens showing every facility
in that cell, along with a regional rollup comparing state and district performance.

You can switch capabilities using the sidebar filter. Change from ICU to maternity to
dialysis, and the map recomputes scores in real time.

---

## 4. Genie — Natural Language Q&A (90 seconds)

Click "Genie" in the sidebar.

This is a natural-language interface powered by Databricks Genie. Instead of writing
SQL, you type a question in plain English.

For example: "Which districts have the lowest ICU coverage?"

Genie translates your question to SQL, runs it on the warehouse, and returns the
answer. Single values appear as metrics, comparisons show as bar charts, and larger
result sets render as tables.

Crucially, Genie shows you the generated SQL. This builds trust — analysts can verify
the logic and learn from it. The conversation is multi-turn, so you can ask follow-ups
like "What about Bihar specifically?" and Genie understands the context.

Starter prompts are available to help you begin.

---

## 5. Action Center — Evidence Drill-Down (90 seconds)

Click "Action Center" in the sidebar.

This page is for the analyst who needs to verify the data behind the map. It shows a
facility map for a selected region, with markers color-coded by evidence strength:
strong is green, partial is yellow, suspicious is orange, and unknown is grey.

A trust-signal summary at the top shows counts for each category. Below that,
facility cards are expandable — each card shows structured citations: what capability
is claimed, what source provided the evidence, and a link to the original data.

From here, you can take action. Use the override form to add a note, flag a claim as
suspicious, or mark it as verified. This feedback is written back to Lakebase and
persists across sessions.

The root-cause analysis panel — based on NACHC frameworks — lets you categorize each
gap as a Data Gap, a Service Delivery Gap, or an Engagement Gap, with severity and
notes. All categorizations are visible to your teammates, enabling collaborative
validation.

---

## 6. Performance — Risk and Trajectory (60 seconds)

Click "Performance" in the sidebar.

This page answers two questions: where should I focus first, and are we improving?

The risk-band panel shows districts grouped into four tiers: Critical, At-Risk,
Adequate, and Well-Served. Below that, a ranked district list with progress bars
lets you compare scores across regions.

The time-series chart shows how scores have changed over time. If your Databricks
pipeline has run multiple ETL snapshots, these are real trends. If only one snapshot
exists, the app projects a deterministic improvement curve based on modeling
assumptions, giving you a trajectory to work with.

---

## 7. Scenarios — Planning Workspace (60 seconds)

Click "Scenarios" in the sidebar.

This is the planning workspace. You can save the current filter state — capability,
region, resolution — as a named scenario with a hypothesis. For example: "Target ICU
expansion in Bihar — focus on level-7 hexagons with scores below 0.3."

Saved scenarios are readable as JSON with a facility map preview. You can inspect,
share, and revisit them later.

Filter bookmarks let you capture your current sidebar settings. If shared with
teammates, they become collaborative starting points.

The page also shows recent root-cause tags and override notes from across your team,
so everyone stays aligned.

---

## 8. Technical Architecture — Brief (30 seconds)

Behind the scenes, the app is a FastAPI server with 25 REST endpoints deployed on
Databricks Apps. Data lives in Unity Catalog across bronze, silver, and gold layers.
The gold layer provides curated, query-optimized views for care scores, facility
capabilities, and NFHS-5 indicators.

Persistent user data — overrides, scenarios, bookmarks, and categorizations — is stored
in Lakebase, Databricks's transactional PostgreSQL-compatible database.

The frontend is a single-page application that communicates with the API, handling
filters, maps, and charts entirely in the browser.

---

## 9. Closing (15 seconds)

That covers the Care Gap Navigator. The key takeaway: this app doesn't just show
where healthcare is missing — it shows how confident we are in that assessment, and
it gives planners the tools to investigate, annotate, and act on the data.

The app URL is in your browser. The rest of this repository contains the ETL pipelines,
SQL views, and bundle configuration that power it end to end.
