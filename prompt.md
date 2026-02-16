# 🧠 MASTER IMPLEMENTATION PROMPT

## **PHASE: INTERVENTION SUGGESTION + CORRIDOR FOCUS UX**

> **CRITICAL:**
> This is an incremental UI + logic enhancement.
> Do NOT rewrite analytics, corridor aggregation, or priority logic.

---

## ROLE & EXPECTATION

You are a **senior frontend-heavy full-stack engineer** with experience in:

* React (Vite)
* Mapbox GL JS or Leaflet
* Animated UI interactions
* GeoJSON-driven UX patterns

Your task is to:

1. **Classify corridors into intervention types** using already-computed exposure metrics
2. **Suggest appropriate green interventions per corridor**
3. Upgrade the UX so that:

   * Clicking a corridor zooms to it (animated)
   * A right-side panel slides in with suggestions
   * Closing the panel resets the map view (animated)

---

## EXISTING SYSTEM (ASSUME THIS IS TRUE)

### Backend

* Each corridor already has:

```json
{
  "corridor_id": "...",
  "mean_heat": 0.52,
  "mean_aqi": 0.31,
  "mean_green_deficit": 0.17,
  "geometry": "GeoJSON LineString or MultiLineString"
}
```

* These values are already exposed via:

```
GET /corridors
GET /corridors/{id}
```

### Frontend

* Map already renders corridors
* Hovering a corridor shows exposure stats
* No click interaction yet (or minimal)

---

## OBJECTIVE

Upgrade the system from:

> “Corridors show exposure stats on hover”

to:

> **“Click a corridor → focus on it → see what intervention fits and why.”**

This must feel:

* Smooth
* Intuitive
* Intentional
* Demo-ready

---

## PART 1 — INTERVENTION CLASSIFICATION LOGIC (BACKEND)

### 1️⃣ ADD CORRIDOR TYPE CLASSIFICATION (RULE-BASED)

Using existing metrics, compute **exposure shares**:

```text
Total = mean_heat + mean_aqi + mean_green_deficit

heat_share      = mean_heat / Total
pollution_share = mean_aqi / Total
green_share     = mean_green_deficit / Total
```

### Classification rules (deterministic)

* **Heat-dominated**

```text
heat_share ≥ 0.45
```

* **Pollution-dominated**

```text
pollution_share ≥ 0.40
```

* **Green-deficit / connectivity**

```text
green_share ≥ 0.35
```

* Else:

```text
mixed_exposure
```

---

### 2️⃣ MAP CORRIDOR TYPE → INTERVENTIONS

Add a static mapping table in backend code:

```ts
heat_dominated → [
  "Street tree canopy",
  "Shaded pedestrian walkways"
]

pollution_dominated → [
  "Dense vegetation buffers",
  "Green screens along sidewalks"
]

green_deficit → [
  "Pocket green spaces",
  "Cycle lanes with greening"
]

mixed_exposure → [
  "Combined tree planting and shading"
]
```

---

### 3️⃣ EXTEND CORRIDOR API RESPONSE

Without breaking existing clients, extend corridor response:

```json
{
  "corridor_type": "heat_dominated",
  "recommended_interventions": [
    "Street tree canopy",
    "Shaded pedestrian walkways"
  ],
  "intervention_rationale": "Heat exposure dominates along this corridor"
}
```

⚠️ Do NOT remove existing fields.

---

## PART 2 — MAP CLICK → ANIMATED ZOOM (FRONTEND)

### 4️⃣ CORRIDOR CLICK BEHAVIOR

When a corridor is clicked:

1. Compute its bounding box from GeoJSON
2. Animate map view so that:

   * Corridor fits screen
   * Padding on right side (to account for panel)
   * Smooth easing (500–800 ms)

Example behavior (conceptual):

```js
map.fitBounds(bounds, {
  padding: { top: 40, bottom: 40, left: 40, right: 420 },
  duration: 700,
  easing: easeInOut
})
```

---

### 5️⃣ VISUAL STATE CHANGES

On click:

* Selected corridor:

  * Thicker stroke
  * Higher opacity
* Other corridors:

  * Dimmed
  * Non-interactive

This reinforces focus.

---

## PART 3 — RIGHT-SIDE INTERVENTION PANEL

### 6️⃣ PANEL BEHAVIOR

* Panel slides in from the **right**
* Width ~350–420px
* Animated entrance (CSS or Framer Motion)
* Panel content:

  * Corridor title / ID
  * Corridor type badge
  * Recommended interventions (1–2 max)
  * Short rationale text

---

### 7️⃣ PANEL CONTENT STRUCTURE

```text
[ Corridor Selected ]

Type: Heat-Dominated Corridor

Suggested Interventions:
🌳 Street tree canopy
☂️ Shaded pedestrian walkways

Why this works:
This corridor experiences high surface heat exposure with limited shade.
```

⚠️ No numbers.
⚠️ No equations.
⚠️ No jargon.

---

### 8️⃣ CLOSE / RESET INTERACTION

Add a **close (✕) button** on the panel.

On close:

1. Panel slides out (animated)
2. Map animates back to:

   * Previous zoom
   * Previous center
3. Corridor highlighting resets
4. All corridors become visible again

This reset must feel **intentional**, not abrupt.

---

## PART 4 — STATE MANAGEMENT (IMPORTANT)

### Required frontend state:

```ts
selectedCorridorId
previousMapView
isPanelOpen
```

Rules:

* Only one corridor can be selected at a time
* Clicking a new corridor replaces the previous one
* Hover behavior disabled when a corridor is selected

---

## WHAT NOT TO DO

❌ Do not re-fetch all data on click
❌ Do not add new datasets
❌ Do not compute anything in the frontend
❌ Do not add charts
❌ Do not clutter the panel

This is about **clarity, not density**.

---

## EXPECTED END STATE

User flow:

1. User sees corridors
2. User clicks one
3. Map smoothly zooms to it
4. Right panel slides in
5. User understands:

   * Why this corridor matters
   * What type of green intervention fits
6. User closes panel
7. Map returns to exploration mode

This **directly satisfies**:

> “Identifies corridors”
> “Suggests interventions per route”
> “Practical, visual planning”

---

## FINAL INSTRUCTION

Implement this cleanly, with:

* Minimal new state
* Clear animations
* No breaking changes

At the end:

* Comment the classification logic
* Add a small README note:
  **“How intervention suggestions are derived”**

---

## NOW IMPLEMENT THIS PHASE.