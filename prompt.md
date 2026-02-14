# 🧠 MASTER IMPLEMENTATION PROMPT

## PHASE: INTERVENTION SUGGESTION + VISUALIZATION + COMMUNITY INPUT

> **IMPORTANT**
> You are extending an existing FastAPI + React (Vite) application.
>
> The app already has:
>
> * Multi-exposure priority (NDVI + LST + AQI)
> * Corridor geometries
> * Corridor visualization on a Leaflet map
>
> ❌ Do NOT refactor core analytics
> ❌ Do NOT change corridor detection logic
>
> Your job is to **translate corridors into understandable, community-oriented proposals**.

---

## ROLE

You are a **full-stack geospatial product engineer** building a **collaborative urban planning prototype**.

Your goal is to make corridors:

* Understandable
* Actionable
* Open to public input

---

## HIGH-LEVEL OBJECTIVE

Upgrade the system from:

> “These are priority corridors”

to:

> **“Here is what could be done on this corridor, what it might look like, and what people think.”**

This must directly satisfy the **Minimum Requirements**.

---

## PART 1 — INTERVENTION SUGGESTION ENGINE (BACKEND)

### 1️⃣ Define corridor exposure profile

For each corridor, compute and store:

```json
{
  "heat_score": 0.78,
  "pollution_score": 0.65,
  "green_deficit_score": 0.42
}
```

These already exist implicitly — just expose them cleanly.

---

### 2️⃣ Corridor type classification (RULE-BASED)

Implement **simple, deterministic rules**:

```text
IF heat_score is dominant
→ corridor_type = "Heat Mitigation"

IF pollution_score is dominant
→ corridor_type = "Air Quality Buffer"

IF green_deficit_score is dominant
→ corridor_type = "Green Connectivity"

IF mixed
→ corridor_type = "Multi-Benefit"
```

⚠️ No ML. No tuning. No black box.

---

### 3️⃣ Map corridor type → suggested interventions

Create a **static intervention lookup table**:

```json
{
  "Heat Mitigation": [
    "Continuous street tree canopy",
    "Shaded pedestrian walkways",
    "High-albedo or permeable paving"
  ],
  "Air Quality Buffer": [
    "Dense roadside vegetation buffers",
    "Green screens or hedges",
    "Setback planting near traffic lanes"
  ],
  "Green Connectivity": [
    "Tree-lined walking corridors",
    "Cycle-friendly green streets",
    "Pocket greens at intersections"
  ],
  "Multi-Benefit": [
    "Mixed tree canopy and shaded paths",
    "Cycle + pedestrian green corridors"
  ]
}
```

For each corridor:

* Attach **1–3 suggested interventions**
* Store them with the corridor document

---

### 4️⃣ Backend API additions

Add **one new endpoint**:

```
GET /corridors/{id}/proposal
```

Returns:

```json
{
  "corridor_type": "Heat Mitigation",
  "suggested_interventions": [...],
  "exposure_breakdown": {...}
}
```

---

## PART 2 — BEFORE / AFTER VISUAL MOCKUP (FRONTEND)

### 5️⃣ Conceptual “Before / After” visualization (NOT simulation)

This is **illustrative**, not quantitative.

#### BEFORE

* Existing corridor geometry
* Exposure color (current map)

#### AFTER (mock)

Overlay:

* Tree icons along the corridor
* Semi-transparent green shading
* Optional dashed line for shaded walkway

⚠️ This is a **visual suggestion**, not a predicted outcome.

---

### 6️⃣ UI Implementation

When a corridor is clicked:

* Open a **Corridor Proposal Panel**
* Tabs:

  * **Overview**
  * **Suggested Interventions**
  * **Before / After**

Before/After can be:

* Toggle switch
* Or side-by-side map view (simple)

---

### 7️⃣ UI copy (important)

Use **careful language**:

✅ “Suggested intervention”
✅ “Conceptual illustration”
❌ “Predicted impact”
❌ “Simulated reduction”

This keeps the prototype honest and defensible.

---

## PART 3 — COMMUNITY INPUT (LIGHTWEIGHT)

### 8️⃣ User suggestions

Allow users to:

* Click a corridor
* Submit a **text suggestion**:

  * “Add benches”
  * “Too narrow for trees”
  * “Good cycling route”

Backend:

```
POST /corridors/{id}/feedback
```

Store:

```json
{
  "corridor_id": "...",
  "comment": "...",
  "timestamp": "...",
  "votes": 0
}
```

No authentication required (MVP).

---

### 9️⃣ Voting mechanism

For each corridor:

* 👍 Upvote
* 👎 Downvote

Votes:

* Stored per corridor
* Displayed as **community support indicator**
* Do NOT affect analytics

---

### 10️⃣ Frontend display

In Corridor Proposal Panel:

* Show:

  * Vote count
  * Top 3 comments
* Sort comments by votes

Keep UI minimal.

---

## WHAT NOT TO DO (VERY IMPORTANT)

❌ Do NOT recompute corridors based on votes
❌ Do NOT introduce budgets or costs
❌ Do NOT claim health or AQI reduction
❌ Do NOT add login/auth
❌ Do NOT over-design visuals

This is **collaborative planning**, not execution.

---

## EXPECTED END STATE

After this phase, the platform:

✔ Identifies green corridors
✔ Suggests **context-appropriate interventions**
✔ Shows a **clear before/after vision**
✔ Allows **public participation**
✔ Stays scientifically honest

And **perfectly matches** the problem statement.

---

## FINAL CHECKLIST

Before finishing:

* Corridor click → proposal panel works
* Suggested interventions are consistent
* Before/after toggle is clear
* Users can comment and vote
* No core analytics were altered

---

## NOW IMPLEMENT THIS PHASE.