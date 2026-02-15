# 🧠 MASTER IMPLEMENTATION PROMPT — **POINT-BASED CORRIDOR AGGREGATION**

> **IMPORTANT:**
> This is an extension of an existing system.
> Do **not** recompute priority, exposure, AQI, NDVI, or LST.
> Treat existing high-priority points as **ground truth**.

---

## ROLE & EXPECTATION

You are a **senior geospatial engineer** extending an existing FastAPI + React (Vite) application.

Your task is to create a **corridor aggregation feature** that:

* Takes **existing high-priority points** as input
* Connects **spatially continuous points** into **corridors**
* Preserves **all original points**
* Adds a **new corridor abstraction layer** on top

This phase is **pure geometry + topology**, not analytics.

---

## CURRENT SYSTEM (ASSUME THIS EXISTS)

### Backend

* FastAPI
* MongoDB
* A collection of **high-priority points**, each with:

  * Geometry (Point)
  * Priority score
  * AQI / heat / NDVI metadata
* API already returns these points

### Frontend

* React (Vite)
* Map UI showing:

  * Individual high-priority points
  * Color-coded by priority
* Points render correctly and are trusted

---

## OBJECTIVE OF THIS PHASE

Upgrade the system from:

> “These are isolated high-priority locations”

to:

> **“These points form continuous exposure corridors.”**

A **corridor** is defined as:

* A connected chain of nearby high-priority points
* Representing a continuous path of human exposure
* Derived *without losing or modifying point-level data*

---

## CORE DESIGN PRINCIPLES (MANDATORY)

* ❌ Do NOT delete points
* ❌ Do NOT merge points
* ❌ Do NOT change priority scores
* ✅ Corridors reference points, not replace them
* ✅ Points may belong to **only one corridor**
* ✅ Corridors are deterministic and reproducible

---

## BACKEND TASKS (STEP BY STEP)

---

### 1️⃣ INPUT: EXISTING HIGH-PRIORITY POINTS

Use the existing collection:

```json
{
  "point_id": "...",
  "geometry": { "type": "Point", "coordinates": [...] },
  "priority_score": 0.87,
  "aqi": 0.74,
  "heat": 0.81,
  "ndvi": 0.19
}
```

No filtering or recomputation allowed in this phase.

---

### 2️⃣ DEFINE CONNECTIVITY RULE (VERY IMPORTANT)

Two points **A** and **B** are considered connected if:

* Distance(A, B) ≤ `D_max`

Recommended default:

```
D_max = 30 meters
```

Justification:

* Matches street-scale continuity
* Avoids jumping across blocks
* Supported by walkability & exposure literature

Make `D_max` configurable.

---

### 3️⃣ BUILD POINT CONNECTIVITY GRAPH

Algorithm:

* Treat each point as a node
* Add an edge between nodes if:

  * Distance ≤ D_max
* Use:

  * KD-tree / BallTree
  * OR spatial index (Shapely STRtree)

⚠️ This graph includes **only existing points**.

---

### 4️⃣ EXTRACT CONNECTED COMPONENTS → CORRIDORS

* Find **connected components** in the graph
* Each connected component = **one corridor**

This guarantees:

* No point is lost
* No point appears in two corridors
* Corridors emerge naturally from spatial continuity

---

### 5️⃣ FILTER TRIVIAL CORRIDORS (OPTIONAL BUT RECOMMENDED)

To reduce noise:

* Discard corridors with:

  * Fewer than `N_min` points (e.g. < 5)
* These points remain visible individually
* They simply don’t form a corridor

This preserves data while improving signal clarity.

---

### 6️⃣ COMPUTE CORRIDOR METADATA (DERIVED ONLY)

For each corridor:

* Corridor ID (UUID)
* List of point IDs
* Convex hull OR ordered polyline (for visualization)
* Mean priority score
* Mean AQI / heat / NDVI
* Approximate corridor length (sum of inter-point distances)

⚠️ Do NOT modify underlying point records.

---

### 7️⃣ STORE CORRIDORS (NEW COLLECTION)

Create a new MongoDB collection: `corridors`

Example:

```json
{
  "corridor_id": "uuid",
  "point_ids": [...],
  "geometry": "LineString or MultiPoint",
  "mean_priority": 0.83,
  "mean_aqi": 0.71,
  "num_points": 18,
  "created_at": "ISO-8601"
}
```

Points remain stored separately.

---

### 8️⃣ BACKEND API (NEW, READ-ONLY)

Add new endpoints **without modifying existing ones**:

```
GET /corridors
```

Returns:

* corridor_id
* geometry
* mean_priority
* num_points

```
GET /corridors/{id}
```

Returns:

* full metadata
* list of point IDs
* linked point details (optional)

---

## FRONTEND TASKS (STEP BY STEP)

---

### 9️⃣ CORRIDOR VISUALIZATION LAYER

Add a new toggle:

> **“High-Exposure Corridors”**

Behavior:

* Draw corridors as lines connecting points
* Thickness > points
* Color by mean priority
* Points remain visible underneath

---

### 🔟 INTERACTION BEHAVIOR

On corridor click:

* Highlight corridor
* Highlight constituent points
* Show corridor summary:

  * Number of points
  * Avg exposure
  * Dominant exposure type

Points should still be clickable individually.

---

## OPTIONAL IMPROVEMENTS (SAFE IDEAS)

If needed, you MAY:

* Order points along the corridor using nearest-neighbor chaining
* Smooth the line visually (for UI only)
* Add a “corridor confidence” score based on point density

These are **visual improvements only**, not analytics.

---

## WHAT NOT TO DO (CRITICAL)

❌ Do not introduce road segments
❌ Do not recalculate exposure
❌ Do not cluster by priority value
❌ Do not merge or average points
❌ Do not delete orphan points

This phase is **connecting dots**, not redefining them.

---

## EXPECTED END STATE

After implementation:

* All original points still exist
* Corridors appear naturally from spatial proximity
* Map clearly shows:

  * Isolated hotspots
  * Continuous exposure paths
* The system feels **cleaner, not heavier**

---

## VERIFICATION CHECKLIST

Before marking complete:

* Every point still renders
* No point appears in two corridors
* Changing `D_max` changes corridor shapes
* Orphan points still visible
* Corridor results are stable across reloads

---

## FINAL INSTRUCTION

Implement this as a **non-destructive aggregation layer**.

Add:

* Clear comments explaining:

  * Why distance-based connectivity was chosen
  * Why points are preserved

---

## NOW IMPLEMENT THIS FEATURE.