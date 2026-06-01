"""Prototype persistence (JSON file) — modules, projects, students, audit (week 4)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORE_FILE = DATA_DIR / "platform_store.json"

DEFAULT_CRITERIA = [
    {
        "id": "c1",
        "title": "Individual contribution",
        "description": "Student clearly describes their personal role in the project.",
    },
    {
        "id": "c2",
        "title": "Technical implementation",
        "description": "Evidence of hands-on technical work aligned with the module book.",
    },
    {
        "id": "c3",
        "title": "Reflection & documentation",
        "description": "Quality of reflection and supporting documentation.",
    },
]

PHASES = ["configure", "ingest", "prepare", "conduct", "grade", "export"]


@dataclass
class EvidenceFile:
    id: str
    filename: str
    content_preview: str
    uploaded_at: str
    file_type: str = "text"


@dataclass
class Student:
    id: str
    name: str
    student_number: str = ""
    evidence: list[EvidenceFile] = field(default_factory=list)
    analysis: dict | None = None
    draft_form: list[dict] = field(default_factory=list)
    phase: str = "ingest"
    consent_given: bool = False
    recording_note: str = ""
    transcript: str = ""


@dataclass
class Project:
    id: str
    name: str
    students: list[Student] = field(default_factory=list)
    phase: str = "configure"


@dataclass
class Module:
    id: str
    name: str
    academic_year: str
    criteria: list[dict]
    projects: list[Project] = field(default_factory=list)
    created_at: str = ""
    rubric_text: str = ""
    module_guide_text: str = ""


class PlatformStore:
    def __init__(self) -> None:
        self.modules: dict[str, Module] = {}
        self.audit_log: list[dict] = []
        self.chat_history: list[dict] = []
        self.current_teacher: str = ""
        self._evidence_content: dict[str, str] = {}
        self._analysis_jobs: dict[str, dict] = {}
        self._file_mtime: float | None = None
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.load()

    def reload_if_changed(self) -> None:
        """Sync in-memory state when another worker updated the JSON store."""
        if not STORE_FILE.exists():
            return
        mtime = STORE_FILE.stat().st_mtime
        if self._file_mtime is not None and mtime == self._file_mtime:
            return
        self.load()

    def _analysis_job_key(self, module_id: str, project_id: str) -> str:
        return f"{module_id}:{project_id}"

    def _new_id(self) -> str:
        return str(uuid.uuid4())[:8]

    def save(self) -> None:
        payload = {
            "modules": self._serialize_modules(),
            "audit_log": self.audit_log[-500:],
            "chat_history": self.chat_history[-200:],
            "current_teacher": self.current_teacher,
            "evidence_content": self._evidence_content,
        }
        payload["analysis_jobs"] = self._analysis_jobs
        STORE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if STORE_FILE.exists():
            self._file_mtime = STORE_FILE.stat().st_mtime

    def load(self) -> None:
        if not STORE_FILE.exists():
            self._seed_demo()
            if STORE_FILE.exists():
                self._file_mtime = STORE_FILE.stat().st_mtime
            return
        data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
        self.audit_log = data.get("audit_log", [])
        self.chat_history = data.get("chat_history", [])
        self.current_teacher = data.get("current_teacher", "")
        self._evidence_content = data.get("evidence_content", {})
        self._analysis_jobs = data.get("analysis_jobs", {})
        self.modules = {}
        for m in data.get("modules", []):
            projects = []
            for p in m.get("projects", []):
                students = [
                    Student(
                        id=s["id"],
                        name=s["name"],
                        student_number=s.get("student_number", ""),
                        evidence=[EvidenceFile(**e) for e in s.get("evidence", [])],
                        analysis=s.get("analysis"),
                        draft_form=s.get("draft_form", []),
                        phase=s.get("phase", "ingest"),
                        consent_given=s.get("consent_given", False),
                        recording_note=s.get("recording_note", ""),
                        transcript=s.get("transcript", ""),
                    )
                    for s in p.get("students", [])
                ]
                projects.append(
                    Project(
                        id=p["id"],
                        name=p["name"],
                        students=students,
                        phase=p.get("phase", "configure"),
                    )
                )
            self.modules[m["id"]] = Module(
                id=m["id"],
                name=m["name"],
                academic_year=m["academic_year"],
                criteria=m.get("criteria", DEFAULT_CRITERIA),
                projects=projects,
                created_at=m.get("created_at", ""),
                rubric_text=m.get("rubric_text", ""),
                module_guide_text=m.get("module_guide_text", ""),
            )
        self._file_mtime = STORE_FILE.stat().st_mtime

    def _serialize_modules(self) -> list[dict]:
        out = []
        for module in self.modules.values():
            d = asdict(module)
            out.append(d)
        return out

    def _seed_demo(self) -> None:
        fixtures = Path(__file__).parent / "ai" / "fixtures"
        mod = self.create_module("Applied AI 2026", "2025-2026")
        proj = self.create_project(mod.id, "Group 2 — Assessment Platform")
        if fixtures.exists():
            for fname, sname in [("student_a.txt", "Lisa Anderson"), ("student_b.txt", "Thomas Johnson")]:
                fpath = fixtures / fname
                if fpath.exists():
                    st = self.add_student(mod.id, proj.id, sname, "S2000001")
                    if st:
                        self.add_evidence(
                            mod.id,
                            proj.id,
                            st.id,
                            fname,
                            fpath.read_text(encoding="utf-8"),
                            "txt",
                        )
        proj.phase = "ingest"
        self.save()

    def set_teacher(self, name: str, pin: str | None = None) -> bool:
        if pin and pin != "1234" and pin != "":
            return False
        self.current_teacher = name.strip()
        self.save()
        return True

    def create_module(self, name: str, academic_year: str) -> Module:
        module = Module(
            id=self._new_id(),
            name=name,
            academic_year=academic_year,
            criteria=[dict(c) for c in DEFAULT_CRITERIA],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.modules[module.id] = module
        self.save()
        return module

    def update_module_docs(
        self,
        module_id: str,
        *,
        rubric_text: str | None = None,
        module_guide_text: str | None = None,
        criteria: list[dict] | None = None,
    ) -> Module | None:
        module = self.modules.get(module_id)
        if not module:
            return None
        if rubric_text is not None:
            module.rubric_text = rubric_text
        if module_guide_text is not None:
            module.module_guide_text = module_guide_text
        if criteria is not None:
            module.criteria = criteria
        self.save()
        return module

    def create_project(self, module_id: str, name: str) -> Project | None:
        module = self.modules.get(module_id)
        if not module:
            return None
        project = Project(id=self._new_id(), name=name, phase="configure")
        module.projects.append(project)
        self.save()
        return project

    def add_student(
        self,
        module_id: str,
        project_id: str,
        name: str,
        student_number: str = "",
    ) -> Student | None:
        project = self._find_project(module_id, project_id)
        if not project:
            return None
        student = Student(
            id=self._new_id(),
            name=name.strip(),
            student_number=student_number.strip(),
        )
        project.students.append(student)
        self.save()
        return student

    def remove_student(
        self,
        module_id: str,
        project_id: str,
        student_id: str,
    ) -> Student | None:
        project = self._find_project(module_id, project_id)
        if not project:
            return None
        removed: Student | None = None
        kept: list[Student] = []
        for s in project.students:
            if s.id == student_id:
                removed = s
            else:
                kept.append(s)
        if not removed:
            return None
        for ev in removed.evidence:
            self._evidence_content.pop(ev.id, None)
        project.students = kept
        self.chat_history = [c for c in self.chat_history if c.get("student_id") != student_id]
        if not project.students:
            project.phase = "configure"
        self.save()
        return removed

    def get_analysis_job(self, module_id: str, project_id: str) -> dict:
        self.reload_if_changed()
        key = self._analysis_job_key(module_id, project_id)
        job = self._analysis_jobs.get(key)
        if job:
            return job
        return {"status": "idle", "step": "", "progress": 0, "error": None}

    def start_analysis_job(self, module_id: str, project_id: str) -> bool:
        self.reload_if_changed()
        key = self._analysis_job_key(module_id, project_id)
        current = self._analysis_jobs.get(key)
        if current and current.get("status") == "running":
            return False
        self._analysis_jobs[key] = {
            "status": "running",
            "step": "Starting analysis…",
            "progress": 0,
            "error": None,
            "module_id": module_id,
            "project_id": project_id,
        }
        self.save()
        return True

    def update_analysis_job(
        self,
        module_id: str,
        project_id: str,
        *,
        step: str,
        progress: int,
    ) -> None:
        key = self._analysis_job_key(module_id, project_id)
        job = self._analysis_jobs.get(key)
        if not job:
            return
        job["step"] = step
        job["progress"] = min(99, max(0, progress))
        self.save()

    def complete_analysis_job(
        self,
        module_id: str,
        project_id: str,
        *,
        processing: str = "",
    ) -> None:
        key = self._analysis_job_key(module_id, project_id)
        self._analysis_jobs[key] = {
            "status": "completed",
            "step": "Analysis complete",
            "progress": 100,
            "error": None,
            "processing": processing,
        }
        self.save()

    def fail_analysis_job(self, module_id: str, project_id: str, error: str) -> None:
        key = self._analysis_job_key(module_id, project_id)
        self._analysis_jobs[key] = {
            "status": "failed",
            "step": "Analysis failed",
            "progress": 0,
            "error": error,
        }
        self.save()

    def add_evidence(
        self,
        module_id: str,
        project_id: str,
        student_id: str,
        filename: str,
        content: str,
        file_type: str,
    ) -> EvidenceFile | None:
        student = self._find_student(module_id, project_id, student_id)
        if not student:
            return None
        evidence = EvidenceFile(
            id=self._new_id(),
            filename=filename,
            content_preview=content[:500],
            uploaded_at=datetime.now(timezone.utc).isoformat(),
            file_type=file_type,
        )
        student.evidence.append(evidence)
        self._evidence_content[evidence.id] = content
        project = self._find_project(module_id, project_id)
        if project:
            project.phase = "ingest"
        self.save()
        return evidence

    def get_evidence_content(self, evidence_id: str) -> str:
        return self._evidence_content.get(evidence_id, "")

    def remove_evidence(
        self,
        module_id: str,
        project_id: str,
        student_id: str,
        evidence_id: str,
    ) -> EvidenceFile | None:
        student = self._find_student(module_id, project_id, student_id)
        if not student:
            return None
        removed: EvidenceFile | None = None
        kept: list[EvidenceFile] = []
        for e in student.evidence:
            if e.id == evidence_id:
                removed = e
            else:
                kept.append(e)
        if not removed:
            return None
        student.evidence = kept
        self._evidence_content.pop(evidence_id, None)
        student.analysis = None
        student.draft_form = []
        if student.phase in ("prepare", "grade"):
            student.phase = "ingest"
        self.save()
        return removed

    def clear_rubric(self, module_id: str) -> Module | None:
        module = self.modules.get(module_id)
        if not module:
            return None
        module.rubric_text = ""
        module.criteria = [dict(c) for c in DEFAULT_CRITERIA]
        self.save()
        return module

    def clear_module_guide(self, module_id: str) -> Module | None:
        module = self.modules.get(module_id)
        if not module:
            return None
        module.module_guide_text = ""
        self.save()
        return module

    def get_student_evidence_text(self, student: Student) -> str:
        parts: list[str] = []
        for ev in student.evidence:
            full = self._evidence_content.get(ev.id, ev.content_preview)
            parts.append(f"[{ev.filename}]\n{full}")
        return "\n\n".join(parts)

    def criterion_titles(self, module: Module) -> list[str]:
        return [c.get("title", c.get("description", "Criterion")) for c in module.criteria]

    def _find_project(self, module_id: str, project_id: str) -> Project | None:
        module = self.modules.get(module_id)
        if not module:
            return None
        for project in module.projects:
            if project.id == project_id:
                return project
        return None

    def _find_student(
        self, module_id: str, project_id: str, student_id: str
    ) -> Student | None:
        project = self._find_project(module_id, project_id)
        if not project:
            return None
        for student in project.students:
            if student.id == student_id:
                return student
        return None


store = PlatformStore()
