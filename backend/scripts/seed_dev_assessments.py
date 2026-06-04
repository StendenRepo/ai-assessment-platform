"""Dev-only seed: create assessments for the mock students used by the UI.

The student pages are still driven by frontend/src/lib/mockData.js, whose
students carry hardcoded assessment UUIDs. The recording/consent endpoints are
keyed on real Assessment rows, so without these rows the UI returns
"Assessment not found". This script creates the minimal FK chain
(module -> project -> student -> assessment) so recording can be exercised
locally.

It is idempotent and NOT wired into application startup. Re-run it any time the
database volume is reset:

    docker exec -i backend python scripts/seed_dev_assessments.py

Remove this script (and the mockData wiring) once the real assessment-creation
flow lands from dev.
"""
import os
import sys
import uuid

# Allow running as a plain script (python scripts/seed_dev_assessments.py):
# ensure the backend root (parent of this scripts/ dir) is importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.assessment import Assessment
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher

# Must match the assessmentId values in frontend/src/lib/mockData.js
MOCK_ASSESSMENT_IDS = [
    "40000000-0000-4000-8000-000000000001",
    "40000000-0000-4000-8000-000000000002",
    "40000000-0000-4000-8000-000000000003",
    "40000000-0000-4000-8000-000000000004",
]

SEED_TEACHER_EMAIL = "admin@example.com"
MODULE_CODE = "TEST-101"
PROJECT_NAME = "Test Project"


def main() -> None:
    db = SessionLocal()
    try:
        teacher = (
            db.query(Teacher).filter_by(email=SEED_TEACHER_EMAIL).first()
        )
        if teacher is None:
            raise SystemExit(
                f"Seed teacher {SEED_TEACHER_EMAIL!r} not found. Run migrations first."
            )

        module = db.query(Module).filter_by(code=MODULE_CODE).first()
        if module is None:
            module = Module(
                teacher_id=teacher.id, name="Test Module", code=MODULE_CODE
            )
            db.add(module)
            db.flush()

        project = (
            db.query(Project)
            .filter_by(name=PROJECT_NAME, module_id=module.id)
            .first()
        )
        if project is None:
            project = Project(module_id=module.id, name=PROJECT_NAME)
            db.add(project)
            db.flush()

        created = []
        for i, sid in enumerate(MOCK_ASSESSMENT_IDS, start=1):
            assessment_id = uuid.UUID(sid)
            if db.get(Assessment, assessment_id) is not None:
                continue
            student = Student(project_id=project.id, name=f"Demo Student {i}")
            db.add(student)
            db.flush()
            db.add(
                Assessment(
                    id=assessment_id,
                    student_id=student.id,
                    teacher_id=teacher.id,
                )
            )
            created.append(sid)

        db.commit()
        print(f"teacher: {teacher.email} ({teacher.id})")
        print(f"created assessments: {created or '(all already existed)'}")
        print(f"total assessments now: {db.query(Assessment).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
