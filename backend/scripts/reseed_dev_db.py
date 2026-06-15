#!/usr/bin/env python3

import os
import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy.dialects.postgresql as pg
from sqlalchemy import String, Text, TypeDecorator, create_engine
from sqlalchemy.orm import sessionmaker


class SQLiteUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return uuid.UUID(str(value)) if value is not None else None


# Patch PostgreSQL-only types so the existing models can create SQLite tables.
pg.UUID = lambda as_uuid=True: SQLiteUUID()
pg.JSONB = Text
pg.INET = String

from app.core.security import hash_password  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import (  # noqa: E402
    Assessment,
    Department,
    Module,
    Project,
    Student,
    Teacher,
)
from app.models.enums import (  # noqa: E402
    AssessmentStatus,
    ConsentStatus,
    ModuleStatus,
    ProjectStatus,
    StudentStatus,
)


def uid(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"ai-assessment-seed::{name}")


def resolve_output_path() -> str:
    if os.path.isdir("/app"):
        return "/app/database/database.db"
    here = os.path.dirname(os.path.abspath(__file__))
    backend_root = os.path.dirname(here)
    return os.path.join(backend_root, "database", "database.db")


def build_seed_database(seed_path: str) -> None:
    os.makedirs(os.path.dirname(seed_path), exist_ok=True)
    if os.path.exists(seed_path):
        os.remove(seed_path)

    engine = create_engine(f"sqlite:///{seed_path}")
    session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    session = session_cls()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    departments = [
        Department(id=uid("dept-cs"), name="Computer Science", created_at=now - timedelta(days=400)),
        Department(id=uid("dept-ds"), name="Data Science", created_at=now - timedelta(days=380)),
        Department(id=uid("dept-se"), name="Software Engineering", created_at=now - timedelta(days=360)),
    ]
    session.add_all(departments)

    teachers = [
        Teacher(
            id=uid("teacher-alice"),
            name="Alice Johnson",
            email="alice.johnson@university.edu",
            password_hash=hash_password("password123"),
            is_admin=False,
            is_seed=False,
            department_id=uid("dept-cs"),
            created_at=now - timedelta(days=280),
            last_login=now - timedelta(hours=6),
        ),
        Teacher(
            id=uid("teacher-bob"),
            name="Bob Singh",
            email="bob.singh@university.edu",
            password_hash=hash_password("password123"),
            is_admin=False,
            is_seed=False,
            department_id=uid("dept-ds"),
            created_at=now - timedelta(days=275),
            last_login=now - timedelta(hours=18),
        ),
        Teacher(
            id=uid("teacher-clara"),
            name="Clara Nunez",
            email="clara.nunez@university.edu",
            password_hash=hash_password("password123"),
            is_admin=False,
            is_seed=False,
            department_id=uid("dept-se"),
            created_at=now - timedelta(days=260),
            last_login=now - timedelta(days=2),
        ),
    ]
    session.add_all(teachers)

    modules = [
        Module(
            id=uid("module-programmeren-2-2026"),
            teacher_id=uid("teacher-bob"),
            name="Programmeren 2 (HBO-ICT Informatica)",
            academic_year="2025-2026",
            deadline="2026-07-15",
            created_at=now - timedelta(days=220),
            status=ModuleStatus.active,
        ),
        Module(
            id=uid("module-databases-2026"),
            teacher_id=uid("teacher-clara"),
            name="Databases",
            academic_year="2025-2026",
            deadline="2026-06-30",
            created_at=now - timedelta(days=210),
            status=ModuleStatus.active,
        ),
        Module(
            id=uid("module-webtech-2026"),
            teacher_id=uid("teacher-alice"),
            name="Webtechnologie",
            academic_year="2025-2026",
            deadline="2026-07-10",
            created_at=now - timedelta(days=205),
            status=ModuleStatus.active,
        ),
        Module(
            id=uid("module-se-project-2024"),
            teacher_id=uid("teacher-alice"),
            name="Software Engineering Project",
            academic_year="2023-2024",
            deadline="2024-06-15",
            created_at=now - timedelta(days=600),
            status=ModuleStatus.archived,
        ),
    ]
    session.add_all(modules)

    project_specs = [
        ("prog2-team-1", "CLI Planningsapp in Python", "Team Alpha", "module-programmeren-2-2026", ProjectStatus.active),
        ("prog2-team-2", "Algoritme Visualizer", "Team Beta", "module-programmeren-2-2026", ProjectStatus.active),
        ("prog2-team-3", "Refactor van Legacy Java Tool", "Team Gamma", "module-programmeren-2-2026", ProjectStatus.completed),
        ("db-team-1", "Ontwerp van Studentvolgsysteem Database", "Team Delta", "module-databases-2026", ProjectStatus.active),
        ("db-team-2", "SQL Rapportage voor Studievoortgang", "Team Epsilon", "module-databases-2026", ProjectStatus.active),
        ("db-team-3", "Normalisatie en Migratiecase", "Team Zeta", "module-databases-2026", ProjectStatus.completed),
        ("web-team-1", "Frontend voor Stageportaal", "Team Eta", "module-webtech-2026", ProjectStatus.active),
        ("web-team-2", "REST API Dashboard met Next.js", "Team Theta", "module-webtech-2026", ProjectStatus.active),
        ("sep-team-1", "Scrum Project: Campus Service App", "Team Iota", "module-se-project-2024", ProjectStatus.archived),
    ]
    projects = []
    for idx, (key, name, group_name, module_key, status) in enumerate(project_specs):
        projects.append(
            Project(
                id=uid(f"project-{key}"),
                module_id=uid(module_key),
                name=name,
                group_name=group_name,
                created_at=now - timedelta(days=180 - idx * 3),
                status=status,
            )
        )
    session.add_all(projects)

    students = []
    student_index = 1
    for project in projects:
        count = 3 if project.status == ProjectStatus.archived else 6
        for i in range(count):
            s = Student(
                name=f"Student {student_index:03d}",
                student_number=f"{student_index:07d}",
                status=StudentStatus.active if i < count - 1 else StudentStatus.inactive,
                consent_given=(i % 2 == 0),
            )
            s.projects.append(project)
            students.append(s)
            student_index += 1
    session.add_all(students)
    session.flush()

    # Build lookup maps after flush so student_projects rows exist
    from app.models.student import student_projects as sp_table
    student_project_rows = session.execute(sp_table.select()).all()
    student_to_project = {row.student_id: row.project_id for row in student_project_rows}

    project_by_id = {p.id: p for p in projects}
    module_by_id = {m.id: m for m in modules}

    assessments = []
    for i, student in enumerate(students):
        if i % 7 == 0:
            continue

        project_id = student_to_project.get(student.student_number)
        if project_id is None:
            continue
        project = project_by_id[project_id]
        module = module_by_id[project.module_id]

        if i % 5 == 0:
            status = AssessmentStatus.final
            completed_at = now - timedelta(days=(i % 30))
        elif i % 3 == 0:
            status = AssessmentStatus.reviewed
            completed_at = now - timedelta(days=(i % 15))
        else:
            status = AssessmentStatus.draft
            completed_at = None

        assessments.append(
            Assessment(
                id=uid(f"assessment-{student.student_number}"),
                student_id=student.student_number,
                teacher_id=module.teacher_id,
                status=status,
                draft_form_json='{"criteria": {"analysis": "good progress", "implementation": "solid"}}',
                final_form_json='{"grade": "B+", "summary": "Consistent work across milestones"}'
                if status != AssessmentStatus.draft
                else None,
                consent_status=ConsentStatus.accepted
                if student.consent_given
                else ConsentStatus.pending,
                consent_confirmed_at=(now - timedelta(days=2)) if student.consent_given else None,
                consent_confirmed_by=module.teacher_id if student.consent_given else None,
                created_at=now - timedelta(days=45 - (i % 20)),
                completed_at=completed_at,
            )
        )
    session.add_all(assessments)

    session.commit()

    print(f"Seed database created: {seed_path}")
    print(f"departments={session.query(Department).count()}")
    print(f"teachers={session.query(Teacher).count()}")
    print(f"modules={session.query(Module).count()}")
    print(f"projects={session.query(Project).count()}")
    print(f"students={session.query(Student).count()}")
    print(f"assessments={session.query(Assessment).count()}")

    session.close()


if __name__ == "__main__":
    build_seed_database(resolve_output_path())
