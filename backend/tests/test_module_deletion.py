"""Direct tests for ModuleService.delete_module cleanup behavior."""
import uuid

from app.config import settings
from app.models.enums import EmbeddingStatus, FileType, SourceType
from app.models.evidence import Evidence
from app.models.file_record import FileRecord
from app.models.module import Module
from app.models.project import Project
from app.models.student import Student
from app.models.teacher import Teacher
from app.services.module_service import RUBRIC_UPLOAD_DIR, ModuleService


def _teacher(db) -> Teacher:
    from app.core.security import hash_password

    teacher = Teacher(
        id=uuid.uuid4(),
        name="Deletion Test Teacher",
        email=f"deletion-{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password("password123"),
    )
    db.add(teacher)
    db.flush()
    return teacher


def _module(db, teacher: Teacher, name: str = "Test Module") -> Module:
    module = Module(teacher_id=teacher.id, name=name)
    db.add(module)
    db.flush()
    return module


def _project(db, module: Module, name: str = "Group A") -> Project:
    project = Project(
        module_id=module.id,
        name=name,
        group_name=name,
    )
    db.add(project)
    db.flush()
    return project


def _student(db, project: Project, number: str = "1001", name: str = "Alice") -> Student:
    student = Student(name=name, student_number=number)
    db.add(student)
    db.flush()
    student.projects.append(project)
    db.flush()
    return student


def _evidence(db, student: Student, file_path: str, project: Project | None = None) -> Evidence:
    evidence = Evidence(
        id=uuid.uuid4(),
        student_id=student.student_number,
        project_id=project.id if project else None,
        file_name="report.md",
        file_type=FileType.markdown,
        file_path=file_path,
        source_type=SourceType.upload,
        embedding_status=EmbeddingStatus.completed,
    )
    db.add(evidence)
    db.flush()
    return evidence


class TestModuleServiceDelete:
    def test_deletes_orphan_student_and_evidence(self, db, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir(parents=True)
        teacher = _teacher(db)
        module = _module(db, teacher)
        project = _project(db, module)
        student = _student(db, project)

        student_dir = evidence_dir / student.student_number
        student_dir.mkdir(parents=True)
        evidence_file = student_dir / "abc123_report.md"
        evidence_file.write_text("# Evidence")
        relative_path = str(evidence_file.relative_to(evidence_dir))

        evidence = _evidence(db, student, relative_path)
        student_number = student.student_number
        evidence_id = evidence.id
        db.commit()

        assert db.query(Student).filter(Student.student_number == student_number).count() == 1
        assert db.query(Evidence).filter(Evidence.id == evidence_id).count() == 1
        assert evidence_file.exists()

        ModuleService.delete_module(module, db)
        db.commit()

        assert db.query(Module).filter(Module.id == module.id).count() == 0
        assert db.query(Student).filter(Student.student_number == student_number).count() == 0
        assert db.query(Evidence).filter(Evidence.id == evidence_id).count() == 0
        assert not evidence_file.exists()

    def test_preserves_student_in_other_module(self, db):
        teacher = _teacher(db)
        module_a = _module(db, teacher, name="Module A")
        module_b = _module(db, teacher, name="Module B")
        project_a = _project(db, module_a, name="Group A")
        project_b = _project(db, module_b, name="Group B")
        student = _student(db, project_a, number="2002", name="Bob")
        student.projects.append(project_b)
        db.commit()

        ModuleService.delete_module(module_a, db)
        db.commit()

        assert db.query(Module).filter(Module.id == module_a.id).count() == 0
        assert db.query(Module).filter(Module.id == module_b.id).count() == 1
        remaining = db.query(Student).filter(Student.student_number == student.student_number).first()
        assert remaining is not None
        assert remaining.name == "Bob"
        assert len(remaining.projects) == 1
        assert remaining.projects[0].id == project_b.id

    def test_deletes_shared_project_evidence(self, db, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir(parents=True)
        teacher = _teacher(db)
        module = _module(db, teacher)
        project = _project(db, module)
        student = _student(db, project)

        shared_file = evidence_dir / "shared_doc.pdf"
        shared_file.write_bytes(b"%PDF-shared")
        relative_path = str(shared_file.relative_to(evidence_dir))

        evidence = _evidence(db, student, relative_path, project=project)
        db.commit()

        ModuleService.delete_module(module, db)
        db.commit()

        assert db.query(Evidence).filter(Evidence.id == evidence.id).count() == 0
        assert not shared_file.exists()

    def test_deletes_rubric_file_from_disk(self, db, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))

        teacher = _teacher(db)
        module = _module(db, teacher)
        rubric_dir = RUBRIC_UPLOAD_DIR / str(module.id)
        rubric_dir.mkdir(parents=True)
        stored_name = "rubric123_test.pdf"
        rubric_path = rubric_dir / stored_name
        rubric_path.write_bytes(b"%PDF-rubric")

        record = FileRecord(
            file_name="test.pdf",
            path=stored_name,
            file_type="pdf",
            size_bytes=len(b"%PDF-rubric"),
            hash="abc",
        )
        db.add(record)
        db.flush()
        module.rubric_file_id = record.id
        db.commit()

        ModuleService.delete_module(module, db)
        db.commit()

        assert not rubric_path.exists()
        assert db.query(FileRecord).filter(FileRecord.id == record.id).count() == 0
