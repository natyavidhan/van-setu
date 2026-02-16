# 🧠 MASTER IMPLEMENTATION PROMPT

## **FEATURE: COMMUNITY SUGGESTIONS & UPVOTING (CORRIDOR-LEVEL)**

> **IMPORTANT:**
> This feature extends the **existing corridor right-side panel**.
> Do NOT create a new page or modal.
> Do NOT introduce authentication.

---

## ROLE & EXPECTATION

You are a **senior full-stack engineer** working on a geospatial planning platform.

Your task is to add **community participation features** that allow users to:

* Submit suggestions for a selected corridor
* Upvote existing suggestions
* See community sentiment per corridor

This must be:

* Lightweight
* Abuse-resistant (basic rate limiting)
* Easy to remove or expand later

---

## EXISTING SYSTEM (ASSUME THIS IS DONE)

### Frontend

* React (Vite)
* Map with corridors
* Clicking a corridor:

  * Zooms map
  * Opens right-side panel
  * Shows intervention suggestions

### Backend

* FastAPI
* MongoDB
* Corridor data already exists
* No authentication system

---

## FEATURE OBJECTIVE

Upgrade the corridor panel from:

> “Here is what the system suggests”

to:

> **“Here is what the system suggests — and what people think.”**

This directly satisfies:

> “Allows users to submit suggestions and vote on proposed corridors”

---

## PART 1 — DATA MODEL (BACKEND)

### 1️⃣ CREATE NEW COLLECTION: `corridor_suggestions`

MongoDB schema (minimal, explicit):

```json
{
  "_id": "ObjectId",
  "corridor_id": "string",
  "text": "string",
  "upvotes": 0,
  "created_at": "ISO-8601",
  "client_ip": "string"
}
```

Rules:

* Suggestions are **always tied to a corridor**
* Store `client_ip` only for rate limiting (not identity)
* No usernames, no profiles

Add indexes:

* `corridor_id`
* `created_at`

---

## PART 2 — BACKEND API DESIGN

### 2️⃣ CREATE SUGGESTION ENDPOINTS

#### POST a suggestion

```
POST /corridors/{id}/suggestions
```

Request body:

```json
{
  "text": "Plant dense trees near the bus stop"
}
```

Rules:

* Max length: 300 characters
* Trim whitespace
* Reject empty or spam-like content

---

#### GET suggestions for a corridor

```
GET /corridors/{id}/suggestions
```

Returns:

```json
[
  {
    "id": "...",
    "text": "...",
    "upvotes": 12,
    "created_at": "..."
  }
]
```

Sorted by:

1. Upvotes (desc)
2. Created time (asc)

---

#### UPVOTE a suggestion

```
POST /suggestions/{id}/upvote
```

Rules:

* Increment upvotes by 1
* Apply rate limiting (see below)

---

## PART 3 — RATE LIMITING (MANDATORY)

### 3️⃣ SIMPLE IP-BASED RATE LIMITING

No auth, so do **basic protection**:

#### Limits:

* Suggestion creation:

  * Max **3 per IP per corridor per hour**
* Upvotes:

  * Max **10 per IP per hour**

Implementation options:

* In-memory store (acceptable for prototype)
* OR MongoDB `rate_limits` collection

On limit exceeded:

* Return `429 Too Many Requests`
* Include friendly message

⚠️ Do NOT use Redis unless already present.

---

## PART 4 — FRONTEND UI (RIGHT PANEL)

### 4️⃣ EXTEND EXISTING RIGHT PANEL

Add a new section **below intervention suggestions**:

---

### 🗣️ Community Suggestions

#### A. Suggestion Input

* Textarea
* Placeholder:

  > “Suggest an improvement for this corridor…”
* Character counter (300 max)
* Submit button (disabled if empty)

---

#### B. Suggestions List

For each suggestion:

* Text
* Upvote button (⬆️)
* Upvote count

Rules:

* Disable upvote button after clicking (session-level)
* Optimistic UI update is OK

---

### 5️⃣ UI/UX RULES

* Suggestions load when corridor panel opens
* No page reload
* Panel scrolls independently
* If no suggestions:

  > “No community suggestions yet. Be the first.”

---

## PART 5 — STATE MANAGEMENT (FRONTEND)

Required state additions:

```ts
suggestions[]
isSubmittingSuggestion
isUpvoting
```

Rules:

* Suggestions reset when corridor changes
* Closing the panel clears suggestion state
* Errors shown inline (small, friendly)

---

## WHAT NOT TO DO

❌ Do not add user accounts
❌ Do not add comments on comments
❌ Do not add moderation workflows
❌ Do not persist sessions
❌ Do not over-style the UI

This is **participation**, not a social network.

---

## EXPECTED END STATE

User flow:

1. User clicks a corridor
2. Right panel opens
3. Sees:

   * System-recommended interventions
   * Community suggestions
4. User:

   * Adds a suggestion
   * Upvotes others
5. All data persists via MongoDB
6. System remains clean and fast

---

## VERIFICATION CHECKLIST

Before marking complete:

* Suggestions tied correctly to corridor IDs
* Rate limiting works (manual test)
* Panel UX remains smooth
* No crashes on repeated clicks
* Suggestions survive reload

---

## FINAL INSTRUCTION

Implement this **cleanly and minimally**.

At the end:

* Add a short README note:
  **“Community suggestions are advisory and do not affect corridor ranking.”**

---

## NOW IMPLEMENT THIS FEATURE.