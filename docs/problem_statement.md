# Track 2 Problem Statement: The Trust-Weighted Care Gap Navigator

## The Challenge

Healthcare planners and NGO coordinators in India currently face a "data fog" when trying to allocate resources to underserved areas. While they have access to 10,000 facility records, these records are noisy, repetitive, and unevenly supported, with extracted fields like "capability" and "equipment" often being mere claims rather than verified truths.

The core difficulty is distinguishing a real care gap from a data-poor region. When a planner sees a region on a map with no reported ICU beds, they cannot tell if care is actually absent or if the local facilities simply haven't provided reliable data. Presenting weak evidence as fact leads to poor resource allocation and a lack of trust in digital planning tools.

## The Solution

Our app will build a **Geospatial Lakehouse on Databricks** to transform these 10,000 messy records into a **Trust-Weighted Care Gap Map**. Using a Bronze-Silver-Gold architecture, we will standardize raw facility claims and index them using H3 hexagonal grid systems via the Mosaic library to enable high-performance spatial aggregation.

## Key Technical Objectives

- **Aggregate Trust Signals:** Instead of simple counts, we will produce regional care scores weighted by evidence strength (strong, partial, or suspicious).
- **Communicate Uncertainty:** We will use Kepler.gl visualizations to distinguish between regions where care is "proven absent" versus regions that are "data-deficient," using visual cues like color gradients or transparency to represent confidence levels.
- **Drill-Down Transparency:** Every regional aggregate will allow the user to drill into specific facility records, providing direct citations of the underlying free-text descriptions to justify the score.
- **Scenario Planning:** Planners will be able to persist user actions, such as noting overrides for suspicious claims or saving specific "what-if" resource allocation scenarios for future NGO coordination.

## The Impact

By turning claimed capabilities into verified evidence, this app empowers non-technical analysts to move beyond "guessing" at care gaps. It provides a reliable foundation for saving lives by ensuring that critical care infrastructure—like ICU, maternity, and trauma services—is deployed where it is truly needed most.
