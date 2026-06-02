# Overlap detection (G2-122 – G2-129)

Branch: `feature/G2-overlap-detection` (from `feature/integrate-poc-dev-ui`)

## Stories

| Story | Summary | Status |
|-------|---------|--------|
| **G2-122** | Within-group textual overlap between all students in a group | Done |
| **G2-123** | Cross-group overlap (compare evidence across groups in a project) | Done |
| **G2-124** | Similarity score; list API `sort` / `order` / `status` / `scope` | Done |
| **G2-125** | Side-by-side passages with highlighted shared text | Done |
| **G2-126** | Teacher overlap list (confirmed / possible tabs, scope filter) | Done |
| **G2-127** | Separate confirmed vs possible lists (tabs + dedicated routes) | Done |
| **G2-129** | Overlap dossier export (ZIP + embedded in student dossier) | Done |

Thresholds: **confirmed** ≥ 55% cosine similarity, **possible** 38–55%.

Demo fixtures: `student_a.txt` / `student_b.txt` (group-1), `student_c.txt` (group-2) share `OVERLAP_DEMO_BLOCK` for within- and cross-group hits.

## API

| Method | Path | Story |
|--------|------|-------|
| POST | `/api/v1/projects/{projectId}/groups/{groupId}/overlaps/detect` | G2-122 |
| POST | `/api/v1/projects/{projectId}/overlaps/detect-all` | G2-122 + G2-123 |
| POST | `/api/v1/projects/{projectId}/overlaps/cross-group/detect` | G2-123 |
| GET | `/api/v1/projects/{projectId}/groups/{groupId}/overlaps?status=&scope=&sort=&order=` | G2-124, G2-126 |
| GET | `.../overlaps/confirmed` | G2-127 |
| GET | `.../overlaps/possible` | G2-127 |
| GET | `.../overlaps/{overlapId}` | G2-125 |
| GET | `.../overlaps/export/zip` | G2-129 |

Student dossier ZIP (`/api/v1/modules/.../export/zip`) includes `overlap_report.md` and `overlap_report.json` when overlap data exists.

## UI

- Project page → **Project overlaps** (group-1 list as entry)
- Group page → **Review overlaps**
- `/projects/.../groups/.../overlaps` — list, scan, export, tabs, scope filter
- `/projects/.../groups/.../overlaps/[id]` — side-by-side (cross-group badge when applicable)

## Verify

```bash
docker compose up -d --build
./test/run.sh
```

Open `http://localhost:3000/projects/proj-1/groups/group-1/overlaps`, run **Scan group** or **Full project scan**, then open a row for side-by-side review.
