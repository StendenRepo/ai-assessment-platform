# POC Bridge Deprecation Plan

## Goal

Retire the file-backed PlatformStore POC bridge and keep only SQL-backed module/project/student APIs under `/api/v1/modules/...`.

## Current State (Why POC Cannot Be Removed Immediately)

The POC layer is still an active runtime dependency:

- Backend bridge routes live in `backend/app/api/v1/endpoints/modules.py`:
    - `POST /{module_id}/projects/{project_id}/ensure`
    - `POST /{module_id}/projects/{project_id}/analyze`
    - `GET /{module_id}/projects/{project_id}/analyze/status`
    - `GET /{module_id}/projects/{project_id}/students/{student_id}/ai-insights`
- System seed route in `backend/app/api/v1/endpoints/platform.py`:
    - `POST /seed-demo`
- Frontend calls these endpoints from `frontend/src/lib/platformApi.js`.
- Tests in `test/backend/test_platform.py` (and overlap tests) are built around `platform_store.json` behavior.

## Scope

In scope:

- Replace POC bridge behaviors with SQL-backed services and jobs.
- Remove direct `app.store` dependency from API endpoints/services that are now transitional.
- Update frontend and tests to stop relying on POC-only routes/seed mechanics.
- Remove POC docs and data artifacts once cutover is complete.

Out of scope:

- Reworking unrelated auth/admin/health endpoint behavior.
- Broad frontend redesign.

## Target Architecture

- Source of truth: SQL database only.
- Analysis flow:
    - Request starts an analysis job tied to SQL entities.
    - Job progress/status stored in SQL.
    - Student insights generated from SQL-linked analysis outputs.
- Demo/dev setup:
    - Deterministic DB fixtures or migration seed scripts, not file-backed `platform_store.json`.

## Phased Plan

### Phase 0: Baseline and Guardrails (1-2 days)

- Add clear deprecation markers (comments + docs) on all POC bridge routes.
- Add feature flag: `ENABLE_POC_BRIDGE` (default `true` in dev, `false` in prod profile).
- Add telemetry/audit counters for bridge endpoint usage.

Exit criteria:

- Every bridge route logs usage with module/project identifiers.
- Feature flag can disable bridge endpoints in a non-dev environment.

### Phase 1: SQL Equivalents for Bridge Functionality (3-5 days)

- Implement SQL-backed equivalents for:
    - ensure context
    - analyze start/status
    - student AI insights
- Add persistence for analysis job lifecycle in SQL (new table or existing audit/job table extension).
- Ensure background tasks operate on DB models, not `PlatformStore` objects.

Exit criteria:

- New SQL-backed endpoints return equivalent payload shape (or versioned replacement contract).
- End-to-end analysis works without reading/writing `platform_store.json`.

### Phase 2: Frontend Cutover (1-2 days)

- Update `frontend/src/lib/platformApi.js` to call SQL-backed endpoints only.
- Remove `ensureGroup` and `seedDemo` usage from active UI flows, or replace with DB fixture setup endpoints reserved for dev.
- Verify overlap/insights UI works with SQL-backed responses.

Exit criteria:

- No runtime calls from frontend to deprecated POC-only endpoints.
- Smoke-tested key flows: create module/project, add students, analyze, view insights, overlap views.

### Phase 3: Test Migration (2-4 days)

- Rewrite tests in `test/backend/test_platform.py` and overlap tests to DB fixtures.
- Remove monkeypatch patterns that replace `store` objects across modules.
- Add integration tests for SQL analysis status transitions and insights payload.

Exit criteria:

- Test suite passes without creating `platform_store.json`.
- No tests import or patch `app.store` for API behavior.

### Phase 4: Removal (1-2 days)

- Delete bridge helpers/routes from `backend/app/api/v1/endpoints/modules.py`.
- Delete `seed-demo` from `backend/app/api/v1/endpoints/platform.py` (or keep only if implemented as DB seed utility and clearly dev-only).
- Remove unused POC services/docs/data artifacts:
    - `docs/POC_DEV_UI_INTEGRATION.md` (or archive)
    - `data/platform_store.json` usage in runtime
- Remove `sync_platform_store` dependency wiring from API router where no longer needed.

Exit criteria:

- No import of `app.store` from active API endpoints (except explicitly dev-only tooling, if retained).
- Deprecated endpoints return `404` or are fully removed from OpenAPI.

### Phase 5: Stabilization and Cleanup (1-2 days)

- Run full backend/frontend/integration smoke tests.
- Remove feature flag and dead code after one release cycle (if no rollback needed).
- Update docs to reflect SQL-only architecture.

Exit criteria:

- No POC bridge code paths in production runtime.
- Documentation and tests match deployed behavior.

## Endpoint Deprecation Map

Current POC/transitional endpoints:

- `POST /api/v1/modules/{module_id}/projects/{project_id}/ensure`
- `POST /api/v1/modules/{module_id}/projects/{project_id}/analyze`
- `GET /api/v1/modules/{module_id}/projects/{project_id}/analyze/status`
- `GET /api/v1/modules/{module_id}/projects/{project_id}/students/{student_id}/ai-insights`
- `POST /api/v1/seed-demo`

Recommended policy:

- Mark as deprecated now.
- Keep active for one transition release.
- Remove after frontend + tests are migrated.

## Risks and Mitigations

- Risk: analysis behavior regressions when moving from file-backed objects to ORM models.
    - Mitigation: parity tests for insights payload and status transitions.
- Risk: frontend still calling deprecated paths.
    - Mitigation: usage telemetry + CI smoke tests + grep gate.
- Risk: dev demo flow breaks without seed-demo.
    - Mitigation: replace with DB fixture seed command/task.

## Rollback Plan

- Keep `ENABLE_POC_BRIDGE=true` path available during transition release.
- If SQL analysis path fails in staging:
    - Re-enable POC bridge flag.
    - Route frontend back to bridge endpoints.
    - Preserve SQL migration scripts; fix forward.

## Implementation Checklist

- [ ] Add deprecation notices and usage logging to bridge endpoints.
- [ ] Add `ENABLE_POC_BRIDGE` config and route guards.
- [ ] Build SQL analysis job/status persistence.
- [ ] Build SQL insights endpoint parity.
- [ ] Migrate frontend API calls.
- [ ] Migrate platform/overlap tests to DB fixtures.
- [ ] Remove `app.store` dependencies from active endpoints.
- [ ] Remove deprecated routes and POC docs/data artifacts.
- [ ] Final docs and release notes update.

## Suggested Timeline

- Week 1: Phase 0 + Phase 1
- Week 2: Phase 2 + Phase 3
- Week 3: Phase 4 + Phase 5

## Definition of Done

- Production runtime has no dependency on file-backed PlatformStore POC routes.
- Frontend and tests are SQL-first.
- Deprecated endpoints are removed (or disabled in all non-dev environments) and documented as retired.
