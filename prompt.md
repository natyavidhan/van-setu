# 🧠 MASTER IMPLEMENTATION PROMPT — **PHASE 2: CORRIDOR AGGREGATION**

> **IMPORTANT:**
> You are extending an existing application.
> Do **not** rewrite, refactor, or “clean up” unrelated parts.

---

## ROLE & EXPECTATION

You are a **senior geospatial backend + frontend engineer**.

Your task is to add **corridor aggregation** on top of an existing **road-segment priority system**.

You must:

* Convert **individual road segments** into **continuous green corridors**
* Preserve all existing segment-level APIs and UI
* Add corridor functionality as a **new abstraction layer**

This phase is about **grouping**, not budgeting, not reports, not carbon.

---

## EXISTING SYSTEM (ASSUME THIS IS DONE)

### Backend

* FastAPI
* MongoDB
* Road segments stored with:

  * geometry
  * heat_norm
  * ndvi_norm
  * aqi_norm
  * final priority_score
* API that returns road segments with priority

### Frontend

* React (Vite)
* Map UI showing:

  * Road segments
  * Color-coded by priority
* Segment hover + tooltip working

---

## PHASE 2 OBJECTIVE

Upgrade the system from:

> “These individual streets are high priority”

to:

> **“These are the top continuous corridors where intervention should happen.”**

A **corridor** is:

* A **connected chain of adjacent road segments**
* All segments have **high priority**
* The geometry is continuous and meaningful

---

## CORE DESIGN PRINCIPLES (MANDATORY)

* Corridors are **derived**, not manually drawn
* Corridors must be:

  * Deterministic
  * Reproducible
  * Explainable
* Corridors must **not overlap**
* Segments belong to **at most one corridor**
* Segment-level functionality must remain untouched

---

## BACKEND TASKS (STEP BY STEP)

---

### 1️⃣ DEFINE “HIGH PRIORITY” SEGMENTS

Create a reusable function that classifies a segment as **eligible for corridor aggregation**.

Rules:

* Use **priority_score** (already computed)
* Threshold should be configurable (default example):

  ```
  priority_score >= 0.70
  ```

Do NOT hardcode this inline — make it a constant or config.

---

### 2️⃣ BUILD SEGMENT CONNECTIVITY GRAPH

Using road geometry:

* Treat each segment as a node
* Two segments are **connected** if:

  * Their geometries touch or intersect
  * OR their endpoints are within a small tolerance (e.g. 5–10 meters)

Implementation options:

* Shapely geometry touches/intersects
* Spatial index (STRtree or MongoDB geo queries)

This graph **must only include high-priority segments**.

---

### 3️⃣ AGGREGATE CONNECTED COMPONENTS → CORRIDORS

Algorithm:

* For all eligible segments:

  * Build adjacency graph
  * Find **connected components**
* Each connected component = **one corridor**

For each corridor compute:

* Corridor ID
* List of segment IDs
* Total length (meters)
* Mean priority score
* Mean AQI / heat / NDVI (optional but recommended)
* Combined geometry (MultiLineString or merged LineString)

---

### 4️⃣ FILTER OUT TRIVIAL CORRIDORS

To avoid noise:

* Discard corridors shorter than a minimum length

  * Example: `< 200 meters`
* This threshold must be configurable

---

### 5️⃣ STORE CORRIDORS (NEW COLLECTION)

Create a new MongoDB collection: `corridors`

Example schema:

```json
{
  "corridor_id": "uuid",
  "segment_ids": [...],
  "geometry": "GeoJSON",
  "length_m": 1240,
  "mean_priority": 0.82,
  "mean_aqi": 0.76,
  "created_at": "ISO-8601"
}
```

Segments must NOT be duplicated across corridors.

---

### 6️⃣ BACKEND APIS (NEW, READ-ONLY)

Add **new endpoints** (do not modify existing ones):

```
GET /corridors
```

Returns:

* corridor_id
* length
* mean_priority
* bounding box

```
GET /corridors/{id}
```

Returns:

* full geometry
* all metrics
* list of segment IDs

These APIs must be fast and paginated if needed.

---

## FRONTEND TASKS (STEP BY STEP)

---

### 7️⃣ CORRIDOR LAYER TOGGLE

Add a new map layer:

* **“Priority Corridors”**
* Off by default

Behavior:

* Displays corridor geometries
* Thicker lines than segments
* Colored by mean_priority

Segments remain available as a separate layer.

---

### 8️⃣ CORRIDOR INTERACTION

When a corridor is clicked:

* Highlight the full corridor
* Dim everything else
* Show a **corridor card** with:

  * Length
  * Mean priority
  * Mean AQI
  * Number of segments

No reports, no PDFs yet — just info.

---

### 9️⃣ UI RULES

* Corridor view must NOT clutter the map
* Only show top N corridors by default (e.g., top 10)
* Provide a slider or dropdown:

  * “Show top X corridors”

---

## WHAT NOT TO DO (IMPORTANT)

❌ Do not introduce budgets
❌ Do not introduce phases
❌ Do not introduce carbon logic
❌ Do not change AQI logic
❌ Do not break segment APIs
❌ Do not attempt “optimal path” or AI routing

This phase is **pure aggregation**, nothing more.

---

## EXPECTED END STATE

After this phase:

* The system clearly answers:

  > “Which **continuous corridors** matter most?”
* Segments still exist and work
* Corridors are:

  * Stored
  * Queryable
  * Visualized
* The app feels like a **planning tool**, not a heatmap demo

---

## VERIFICATION CHECKLIST (MANDATORY)

Before marking complete:

* Segments still render correctly
* Corridor results are stable across reloads
* Changing priority threshold changes corridors
* No segment appears in two corridors
* Performance acceptable for Delhi-scale data

---

## FINAL INSTRUCTION

Implement corridor aggregation **cleanly and incrementally**.

At the end, include:

* Short code comments explaining:

  * How corridors are built
  * Why connected components were chosen
* A brief README update:

  * “How corridor aggregation works”

---

## NOW IMPLEMENT THIS PHASE.
