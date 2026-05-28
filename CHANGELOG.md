# Changelog — Project Relay

All notable changes to Relay are recorded here. This doubles as the "built" column of the
portfolio page: each version is a frozen, citable milestone.

---

## v0.1 — Working MVP (closed 2026-05)

The first end-to-end working version: a supporter-relationship platform that prioritizes and
explains who to follow up with. Rule-driven, single-user, demo-data backed.

### Shipped
- **Dashboard** — summary cards (total supporters · total donated · needs-follow-up · high
  priority); top-10 supporters by total given; 8 most-recent donations; most-recent event
  name as subtitle.
- **Supporter List** — browse all relationships; filter by Status (ACTIVE / WARM / LAPSED) and
  RelationshipType; name search; Tier badge (Bronze / Silver / Gold / Platinum); CSV export.
- **Supporter Profile** — full contact info; giving history; event-participation timeline with
  staff notes; manual Status override (resettable to auto-computed); live staff-note logging.
- **Relationship Brief** — rule-driven (who they are · why they matter · recent signal ·
  risk/opportunity flag); Suggested Next Action; one-click copy / open email draft.
- **Follow-up Workflow** — Not Started → Planned → Completed, persisted to the database.
- **Events** — list with name, date, attendee count, total revenue, ticket price.

### Known limitations (carried into v0.2 planning)
- Relationship Brief and priority score are rule-based, not learned.
- No record yet of *why* a human overrides a suggested action (the override signal).
- Single-user only; no authentication or multi-user access control.
- Seeded demo data; no import path from real CRM or spreadsheet.
- Rollups (Status, PriorityScore) only recompute on new transactions — go stale between updates.
- No pagination; supporter list capped at 100 results.

### How to revisit this exact version
Commit `fb91a86` is the baseline. No git tag has been cut yet; tag `v0.1` once a stable
demo URL exists and add it here.

---

## v0.2 — Bug fixes + disposition loop (2026-05)

### Shipped
- **Events revenue fix** — replaced 3-table join with correlated subqueries; eliminates
  Cartesian-product inflation that reported one event as ~13× its actual revenue.
- **Events sort** — events now always order by date descending (was non-deterministic due
  to the same join bug).
- **Status override correctness** — `PATCH /donors/{id}/status` now writes `Status` and
  `StatusOverride` together so the recommendation engine, queue filter, and dashboard KPIs
  all immediately reflect the override without waiting for a transaction rollup. Reset
  (`null`) triggers a full rollup recompute.
- **Dashboard KPI accuracy** — "Need Follow-Up" now counts only `ACTIVE` and `WARM`
  donors (was `!= NEW`, which included LAPSED and inflated the count).
- **Suggestion-disposition loop** — every generated recommendation is logged to
  `RecommendationLog` with its inputs and rule version. Operators can mark each suggestion
  accepted, edited (with the edited text), dismissed, or deferred. Accepting/editing
  auto-advances `FollowUpStatus` to `PLANNED`. Dismissed action types are skipped for
  60 days on that donor's next brief load. BriefPanel shows the four disposition buttons
  inline below the suggestion.
- **Schema completeness** — `RecommendationLog` added to `schema.sql` (was only in the
  startup hook and `migrate_v3.py`).
