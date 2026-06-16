# Implementation diagram

End-to-end view of the Trust-Weighted Care Gap Navigator as built. Distinct
from `logical_architecture.md` — that one explains the *why*; this one is a
single-page Mermaid map of the actual files and table flow.

```mermaid
graph TD
    SRC[(psb_catalog.virtue_foundation_dataset<br/>3 tables)] --> BRONZE

    subgraph "Lakehouse · medallion"
      BRONZE[Bronze<br/>verbatim Delta copies] --> SILVER_CORE
      SILVER_CORE[Silver · core<br/>silver_facilities · silver_pincode_directory · silver_nfhs5_district<br/>H3 6/7/8 via DBR built-in h3_longlatash3] --> SILVER_CLAIMS
      SILVER_CORE --> SILVER_GEO
      SILVER_CLAIMS[silver_facility_capability_claims<br/>per-(facility, capability) trust + citations]
      SILVER_GEO[silver_facilities_geo<br/>H3 9/10/11 + NFHS-5 demand attached]
      SILVER_CLAIMS --> GOLD
      SILVER_GEO --> GOLD_OPT
      GOLD[Gold · canonical<br/>h3_care_score · care_score_by_state · care_score_by_district]
      GOLD_OPT[Gold · supplemental<br/>medical_desert_h3 · medical_desert_districts]
    end

    GOLD --> UC{Unity Catalog<br/>certified · domain tags · h3_index column tags}
    GOLD_OPT --> UC

    UC --> APP
    UC --> GENIE
    UC --> CATALOG_BROWSE[Catalog Explorer<br/>Genie One mobile]

    subgraph "App · Streamlit on Databricks Apps"
      APP[main.py · Executive Command Center]
      APP --> P1[Care Gap Navigator<br/>pydeck H3HexagonLayer<br/>color=score, alpha=confidence]
      APP --> P3[Action Center<br/>citations · NACHC root-cause panel<br/>override notes]
      APP --> P4[Performance<br/>district risk stratification]
      APP --> P5[Scenarios<br/>filter bookmarks · scenario log]
      APP --> P2[Genie · inline chat]
    end

    P2 --> GENIE[Genie Space<br/>10 tables · User Skills as sample questions]

    P1 -. cell selected .-> P3
    P3 -. NACHC tag .-> LB
    P3 -. override note .-> LB
    P5 -. bookmark / scenario .-> LB
    LB[(Lakebase<br/>scenarios · overrides<br/>gap_categorizations · bookmarks)]

    style GOLD fill:#0d6f7a,color:#fff,stroke:#0a5560
    style GOLD_OPT fill:#f4a261,color:#1d3557,stroke:#d68146
    style UC fill:#f1f5f9,stroke:#1d3557,stroke-dasharray:5 5
    style LB fill:#dfd,stroke:#1d3557
    style APP fill:#bbf,stroke:#1d3557
```

## Stack realities (vs. older drafts)

| Concern | What's actually used |
| --- | --- |
| H3 indexing | DBR built-in `h3_longlatash3` (not Mosaic library) |
| Map rendering | pydeck (`H3HexagonLayer`, `ScatterplotLayer` clustering) on Carto Positron (not Kepler.gl) |
| Persistence | Lakebase Delta tables: scenarios, overrides, gap_categorizations, bookmarks |
| Trust signal alpha | `alpha = 50 + confidence × 160` per row, applied in pandas before pydeck render |
| Data-deficient cells | Rendered neutral grey (`(170,174,180)`) — never red — so they don't read as "proven absent" |

## Headline trust formula

Every gold cell carries:

- `score ∈ [0,1]` — supply quality from claim weights and source-URL coverage
- `confidence ∈ [0,1]` — evidence trust, drives map alpha
- `evidence_state ∈ {data_deficient, care_gap, covered}`
- `data_deficient ∈ BOOL` — TRUE when confidence is too low to trust the score

A high score with low confidence means *evidence is thin*, not that care is good — the map's transparency channel makes that visible immediately.
