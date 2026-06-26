#!/usr/bin/env python3

import json
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


def _draft_json(beoordeling: str) -> str:
    return json.dumps({"criteria": {"beoordeling": beoordeling}})


def _final_json(grade: str, name: str) -> str:
    g = float(grade)
    if g >= 9.0:
        summary = (
            f"Uitstekende prestatie. {name} heeft het project op hoog niveau afgerond "
            f"met sterke technische bijdragen en voorbeeldige documentatie."
        )
    elif g >= 8.0:
        summary = (
            f"Goede prestatie. {name} heeft het project degelijk uitgewerkt met "
            f"heldere documentatie en een nette codebase."
        )
    elif g >= 7.0:
        summary = (
            f"Ruim voldoende prestatie. {name} heeft de kern van het project adequaat "
            f"uitgewerkt, met enkele verbeterpunten in uitwerking of documentatie."
        )
    else:
        summary = (
            f"Voldoende prestatie. {name} heeft aan de basisvereisten voldaan maar "
            f"toont merkbare tekortkomingen in diepgang of afwerking."
        )
    return json.dumps({"grade": grade, "samenvatting": summary})


def build_seed_database(seed_path: str) -> None:
    os.makedirs(os.path.dirname(seed_path), exist_ok=True)
    if os.path.exists(seed_path):
        os.remove(seed_path)

    engine = create_engine(f"sqlite:///{seed_path}")
    session_cls = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    session = session_cls()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # -------------------------------------------------------------------------
    # Departments
    # -------------------------------------------------------------------------
    departments = [
        Department(
            id=uid("dept-informatica"),
            name="Informatica",
            created_at=now - timedelta(days=400),
        ),
        Department(
            id=uid("dept-datasci"),
            name="Data Science & AI",
            created_at=now - timedelta(days=380),
        ),
        Department(
            id=uid("dept-se"),
            name="Software Engineering",
            created_at=now - timedelta(days=360),
        ),
    ]
    session.add_all(departments)

    # -------------------------------------------------------------------------
    # Teachers
    # -------------------------------------------------------------------------
    teachers = [
        Teacher(
            id=uid("teacher-jeroen"),
            name="Jeroen van der Berg",
            email="j.vandenberg@nhlstenden.com",
            password_hash=hash_password("password123"),
            is_admin=False,
            is_seed=False,
            department_id=uid("dept-informatica"),
            created_at=now - timedelta(days=280),
            last_login=now - timedelta(hours=4),
        ),
        Teacher(
            id=uid("teacher-marieke"),
            name="Marieke de Boer",
            email="m.deboer@nhlstenden.com",
            password_hash=hash_password("password123"),
            is_admin=False,
            is_seed=False,
            department_id=uid("dept-datasci"),
            created_at=now - timedelta(days=275),
            last_login=now - timedelta(hours=12),
        ),
        Teacher(
            id=uid("teacher-thomas"),
            name="Thomas Bakker",
            email="t.bakker@nhlstenden.com",
            password_hash=hash_password("password123"),
            is_admin=False,
            is_seed=False,
            department_id=uid("dept-se"),
            created_at=now - timedelta(days=260),
            last_login=now - timedelta(days=1),
        ),
    ]
    session.add_all(teachers)

    # -------------------------------------------------------------------------
    # Modules
    # Modules marked "no groups" use a single project with group_name=None so
    # all students appear directly under the module without a sub-group label.
    # -------------------------------------------------------------------------
    modules = [
        # --- with groups ---
        Module(
            id=uid("module-oop-2026"),
            teacher_id=uid("teacher-jeroen"),
            name="Object Georiënteerd Programmeren",
            academic_year="2025-2026",
            deadline="2026-07-04",
            created_at=now - timedelta(days=220),
            status=ModuleStatus.active,
        ),
        Module(
            id=uid("module-databases-2026"),
            teacher_id=uid("teacher-marieke"),
            name="Databases",
            academic_year="2025-2026",
            deadline="2026-06-27",
            created_at=now - timedelta(days=215),
            status=ModuleStatus.active,
        ),
        Module(
            id=uid("module-webdev-2026"),
            teacher_id=uid("teacher-thomas"),
            name="Webontwikkeling",
            academic_year="2025-2026",
            deadline="2026-07-11",
            created_at=now - timedelta(days=210),
            status=ModuleStatus.active,
        ),
        Module(
            id=uid("module-algds-2026"),
            teacher_id=uid("teacher-jeroen"),
            name="Algoritmen & Datastructuren",
            academic_year="2025-2026",
            deadline="2026-07-18",
            created_at=now - timedelta(days=205),
            status=ModuleStatus.active,
        ),
        # --- no groups (single project per module) ---
        Module(
            id=uid("module-linux-2026"),
            teacher_id=uid("teacher-thomas"),
            name="Linux & Netwerken",
            academic_year="2025-2026",
            deadline="2026-06-20",
            created_at=now - timedelta(days=200),
            status=ModuleStatus.active,
        ),
        # --- archived ---
        Module(
            id=uid("module-sep-2024"),
            teacher_id=uid("teacher-jeroen"),
            name="Software Engineering Project",
            academic_year="2023-2024",
            deadline="2024-06-15",
            created_at=now - timedelta(days=600),
            status=ModuleStatus.archived,
        ),
        Module(
            id=uid("module-agile-2025"),
            teacher_id=uid("teacher-marieke"),
            name="Agile Projectmanagement",
            academic_year="2024-2025",
            deadline="2025-06-13",
            created_at=now - timedelta(days=420),
            status=ModuleStatus.archived,
        ),
    ]
    session.add_all(modules)

    # -------------------------------------------------------------------------
    # Projects  (key, display name, group_name or None, module key, status)
    # group_name=None  →  module has no sub-group structure
    # -------------------------------------------------------------------------
    project_specs = [
        # Object Georiënteerd Programmeren – 3 groepen (15 students)
        ("oop-groep-1", "CLI Taakbeheerder in Python",     "Groep 1", "module-oop-2026",       ProjectStatus.active),
        ("oop-groep-2", "Algoritme Visualizer",             "Groep 2", "module-oop-2026",       ProjectStatus.active),
        ("oop-groep-3", "Bibliotheekbeheer Applicatie",    "Groep 3", "module-oop-2026",       ProjectStatus.completed),
        # Databases – 3 groepen (15 students)
        ("db-groep-1",  "Ontwerp Studenten Volgsysteem",   "Groep 1", "module-databases-2026", ProjectStatus.active),
        ("db-groep-2",  "E-commerce Rapportage Database",  "Groep 2", "module-databases-2026", ProjectStatus.active),
        ("db-groep-3",  "Normalisatie en Data Migratie",   "Groep 3", "module-databases-2026", ProjectStatus.completed),
        # Webontwikkeling – 2 groepen (10 students)
        ("web-groep-1", "Portfolio Platform met Next.js",  "Groep 1", "module-webdev-2026",    ProjectStatus.active),
        ("web-groep-2", "REST API voor Evenementenbeheer", "Groep 2", "module-webdev-2026",    ProjectStatus.active),
        # Algoritmen & Datastructuren – 2 groepen (10 students)
        ("algds-groep-1", "Sorteeralgoritmen Implementatie", "Groep 1", "module-algds-2026",   ProjectStatus.active),
        ("algds-groep-2", "Grafentheorie Visualisatie",      "Groep 2", "module-algds-2026",   ProjectStatus.active),
        # Linux & Netwerken – geen groepen (8 students)
        ("linux-klas",  "Linux & Netwerken",                None,      "module-linux-2026",    ProjectStatus.active),
        # Software Engineering Project (archief) – 1 groep (4 students)
        ("sep-groep-1", "Campus Service Applicatie",       "Groep 1", "module-sep-2024",       ProjectStatus.archived),
        # Agile Projectmanagement (archief) – geen groepen (6 students)
        ("agile-klas",  "Agile Projectmanagement",         None,      "module-agile-2025",     ProjectStatus.archived),
    ]
    projects = []
    for idx, (key, name, group_name, module_key, status) in enumerate(project_specs):
        projects.append(
            Project(
                id=uid(f"project-{key}"),
                module_id=uid(module_key),
                name=name,
                group_name=group_name,
                created_at=now - timedelta(days=180 - idx * 4),
                status=status,
            )
        )
    session.add_all(projects)

    project_by_key = {
        key: proj
        for (key, _, _, _, _), proj in zip(project_specs, projects)
    }

    # -------------------------------------------------------------------------
    # Students  (name, student_number, project_key, consent_given, status)
    # Max 15 students per module.
    # -------------------------------------------------------------------------
    student_specs = [
        # OOP Groep 1 – CLI Taakbeheerder in Python (5)
        ("Liam de Vries",       "2100001", "oop-groep-1",   True,  StudentStatus.active),
        ("Sophie Jansen",       "2100002", "oop-groep-1",   True,  StudentStatus.active),
        ("Noah van den Berg",   "2100003", "oop-groep-1",   False, StudentStatus.active),
        ("Emma Bakker",         "2100004", "oop-groep-1",   True,  StudentStatus.active),
        ("Lucas Meijer",        "2100005", "oop-groep-1",   True,  StudentStatus.active),
        # OOP Groep 2 – Algoritme Visualizer (5)
        ("Olivia Smit",         "2100006", "oop-groep-2",   True,  StudentStatus.active),
        ("Milan Visser",        "2100007", "oop-groep-2",   True,  StudentStatus.active),
        ("Iris van der Laan",   "2100008", "oop-groep-2",   False, StudentStatus.active),
        ("Finn Mulder",         "2100009", "oop-groep-2",   True,  StudentStatus.active),
        ("Julia Dekker",        "2100010", "oop-groep-2",   True,  StudentStatus.inactive),
        # OOP Groep 3 – Bibliotheekbeheer Applicatie (5, afgerond)
        ("Daan Bos",            "2100011", "oop-groep-3",   True,  StudentStatus.active),
        ("Lotte Peters",        "2100012", "oop-groep-3",   True,  StudentStatus.active),
        ("Sam Hendriks",        "2100013", "oop-groep-3",   True,  StudentStatus.active),
        ("Nora van Dijk",       "2100014", "oop-groep-3",   False, StudentStatus.active),
        ("Max Vermeer",         "2100015", "oop-groep-3",   True,  StudentStatus.active),
        # Databases Groep 1 – Ontwerp Studenten Volgsysteem (5)
        ("Lisa Brouwer",        "2100016", "db-groep-1",    True,  StudentStatus.active),
        ("Tom Kuipers",         "2100017", "db-groep-1",    True,  StudentStatus.active),
        ("Amber van Leeuwen",   "2100018", "db-groep-1",    False, StudentStatus.active),
        ("Jesse Willems",       "2100019", "db-groep-1",    True,  StudentStatus.active),
        ("Fleur Jacobs",        "2100020", "db-groep-1",    True,  StudentStatus.active),
        # Databases Groep 2 – E-commerce Rapportage Database (5)
        ("Lars Kok",            "2100021", "db-groep-2",    True,  StudentStatus.active),
        ("Roos Peeters",        "2100022", "db-groep-2",    True,  StudentStatus.active),
        ("Dylan Arends",        "2100023", "db-groep-2",    True,  StudentStatus.active),
        ("Nathalie Boer",       "2100024", "db-groep-2",    False, StudentStatus.active),
        ("Bram Scholten",       "2100025", "db-groep-2",    True,  StudentStatus.inactive),
        # Databases Groep 3 – Normalisatie en Data Migratie (5, afgerond)
        ("Manon Kroeze",        "2100026", "db-groep-3",    True,  StudentStatus.active),
        ("Sander Post",         "2100027", "db-groep-3",    True,  StudentStatus.active),
        ("Bo Steenbeek",        "2100028", "db-groep-3",    True,  StudentStatus.active),
        ("Kevin Verhoeven",     "2100029", "db-groep-3",    True,  StudentStatus.active),
        ("Jolien Manders",      "2100030", "db-groep-3",    False, StudentStatus.active),
        # Webontwikkeling Groep 1 – Portfolio Platform met Next.js (5)
        ("Ruben van Kaam",      "2100031", "web-groep-1",   True,  StudentStatus.active),
        ("Sofie Haan",          "2100032", "web-groep-1",   True,  StudentStatus.active),
        ("Pieter Vogel",        "2100033", "web-groep-1",   False, StudentStatus.active),
        ("Anna de Groot",       "2100034", "web-groep-1",   True,  StudentStatus.active),
        ("Thijs van Ommen",     "2100035", "web-groep-1",   True,  StudentStatus.active),
        # Webontwikkeling Groep 2 – REST API voor Evenementenbeheer (5)
        ("Mila van der Berg",   "2100036", "web-groep-2",   True,  StudentStatus.active),
        ("Stefan Verburg",      "2100037", "web-groep-2",   True,  StudentStatus.active),
        ("Femke Graaf",         "2100038", "web-groep-2",   False, StudentStatus.active),
        ("Jasper de Jong",      "2100039", "web-groep-2",   True,  StudentStatus.active),
        ("Nienke Hoekstra",     "2100040", "web-groep-2",   True,  StudentStatus.active),
        # Software Engineering Project (archief) – Groep 1 (4)
        ("Mathias Kuijpers",    "2100041", "sep-groep-1",   True,  StudentStatus.active),
        ("Demi Langbroek",      "2100042", "sep-groep-1",   True,  StudentStatus.active),
        ("Wouter van Beek",     "2100043", "sep-groep-1",   True,  StudentStatus.active),
        ("Claudia Roos",        "2100044", "sep-groep-1",   True,  StudentStatus.active),
        # Algoritmen & Datastructuren Groep 1 – Sorteeralgoritmen (5)
        ("Kai Vermeulen",       "2100045", "algds-groep-1", True,  StudentStatus.active),
        ("Zoë van der Meer",    "2100046", "algds-groep-1", True,  StudentStatus.active),
        ("Tim de Graaf",        "2100047", "algds-groep-1", False, StudentStatus.active),
        ("Hannah Willems",      "2100048", "algds-groep-1", True,  StudentStatus.active),
        ("Victor Prins",        "2100049", "algds-groep-1", True,  StudentStatus.active),
        # Algoritmen & Datastructuren Groep 2 – Grafentheorie (5)
        ("Rens Hoogenbosch",    "2100050", "algds-groep-2", True,  StudentStatus.active),
        ("Eline van Beek",      "2100051", "algds-groep-2", True,  StudentStatus.active),
        ("Stef Bogaard",        "2100052", "algds-groep-2", False, StudentStatus.active),
        ("Lena Wolters",        "2100053", "algds-groep-2", True,  StudentStatus.active),
        ("Joost van Mil",       "2100054", "algds-groep-2", True,  StudentStatus.active),
        # Linux & Netwerken – geen groepen (8)
        ("Chris de Haas",       "2100055", "linux-klas",    True,  StudentStatus.active),
        ("Sara Oosterbeek",     "2100056", "linux-klas",    True,  StudentStatus.active),
        ("Mikkel Lindqvist",    "2100057", "linux-klas",    False, StudentStatus.active),
        ("Petra Engel",         "2100058", "linux-klas",    True,  StudentStatus.active),
        ("Floris de Bruin",     "2100059", "linux-klas",    True,  StudentStatus.active),
        ("Merel Kuiper",        "2100060", "linux-klas",    True,  StudentStatus.active),
        ("Bart Lammers",        "2100061", "linux-klas",    True,  StudentStatus.active),
        ("Sanne Vink",          "2100062", "linux-klas",    False, StudentStatus.active),
        # Agile Projectmanagement – geen groepen (6, archief 2024-2025)
        ("Timo Bergstra",       "2100063", "agile-klas",    True,  StudentStatus.active),
        ("Lisanne Hartman",     "2100064", "agile-klas",    True,  StudentStatus.active),
        ("Joëlle Pijnenburg",   "2100065", "agile-klas",    True,  StudentStatus.active),
        ("Alex Kooistra",       "2100066", "agile-klas",    True,  StudentStatus.active),
        ("Celine Hordijk",      "2100067", "agile-klas",    True,  StudentStatus.active),
        ("David van Beekum",    "2100068", "agile-klas",    False, StudentStatus.active),
    ]

    sn_to_project_key = {sn: key for _, sn, key, _, _ in student_specs}

    students = []
    for name, student_number, project_key, consent_given, status in student_specs:
        s = Student(
            name=name,
            student_number=student_number,
            status=status,
            consent_given=consent_given,
        )
        s.projects.append(project_by_key[project_key])
        students.append(s)
    session.add_all(students)
    session.flush()

    module_by_id = {m.id: m for m in modules}

    # -------------------------------------------------------------------------
    # Assessments
    # Value is (status, grade_or_None, draft_note, created_at); None = skip.
    # -------------------------------------------------------------------------
    assessment_specs = {
        # OOP Groep 1 (actief)
        "2100001": (AssessmentStatus.final,    "8.5", "Sterke implementatie, goede documentatie",                    now - timedelta(days=10)),
        "2100002": (AssessmentStatus.reviewed, None,  "Goede structuur, testen nog onvolledig",                      now - timedelta(days=5)),
        "2100003": (AssessmentStatus.draft,    None,  "Analyse aanwezig, implementatie gestart",                     now - timedelta(days=2)),
        "2100004": (AssessmentStatus.draft,    None,  "Solide basisimplementatie, documentatie mist nog",            now - timedelta(days=3)),
        "2100005": None,
        # OOP Groep 2 (actief)
        "2100006": (AssessmentStatus.draft,    None,  "Goed begrip van OOP-concepten, verdere uitwerking nodig",     now - timedelta(days=4)),
        "2100007": (AssessmentStatus.reviewed, None,  "Consistente aanpak, minor feedback gegeven",                  now - timedelta(days=6)),
        "2100008": None,
        "2100009": (AssessmentStatus.draft,    None,  "Algoritme correct geïmplementeerd, efficiëntie te verbeteren", now - timedelta(days=1)),
        "2100010": (AssessmentStatus.draft,    None,  "Basis aanwezig, beperkte deelname door afwezigheid",          now - timedelta(days=8)),
        # OOP Groep 3 (afgerond)
        "2100011": (AssessmentStatus.final,    "7.5", "Correct opgezet, voldoende documentatie",                     now - timedelta(days=45)),
        "2100012": (AssessmentStatus.final,    "8.0", "Goed afgerond project, nette en leesbare code",               now - timedelta(days=40)),
        "2100013": (AssessmentStatus.reviewed, None,  "Sterke bijdrage aan het groepsproject, eindoordeel volgt",    now - timedelta(days=35)),
        "2100014": (AssessmentStatus.draft,    None,  "Concept aanwezig, verdere uitwerking was mager",              now - timedelta(days=30)),
        "2100015": (AssessmentStatus.final,    "9.0", "Uitstekende prestatie, voorbeeldige codebase en tests",       now - timedelta(days=42)),
        # Databases Groep 1 (actief)
        "2100016": (AssessmentStatus.draft,    None,  "ERD goed opgesteld, SQL-queries deels correct",               now - timedelta(days=3)),
        "2100017": (AssessmentStatus.draft,    None,  "Normalisatie begrepen, query-optimalisatie ontbreekt",        now - timedelta(days=2)),
        "2100018": None,
        "2100019": (AssessmentStatus.reviewed, None,  "Solide databaseontwerp, documentatie compleet",               now - timedelta(days=7)),
        "2100020": (AssessmentStatus.draft,    None,  "Basis aanwezig, JOIN-queries bevatten nog fouten",            now - timedelta(days=4)),
        # Databases Groep 2 (actief)
        "2100021": (AssessmentStatus.reviewed, None,  "Goed begrip van normaalvormen en relationeel ontwerp",        now - timedelta(days=6)),
        "2100022": (AssessmentStatus.draft,    None,  "Schema klopt, rapportages nog incompleet",                    now - timedelta(days=3)),
        "2100023": (AssessmentStatus.draft,    None,  "Actief betrokken, queries kunnen efficiënter",                now - timedelta(days=2)),
        "2100024": None,
        "2100025": (AssessmentStatus.draft,    None,  "Beperkte bijdrage, basiskennis aantoonbaar aanwezig",         now - timedelta(days=9)),
        # Databases Groep 3 (afgerond)
        "2100026": (AssessmentStatus.final,    "8.0", "Goed genormaliseerde database, nette en correcte queries",    now - timedelta(days=55)),
        "2100027": (AssessmentStatus.final,    "7.5", "Correct eindproduct, gedegen en gestructureerde aanpak",      now - timedelta(days=50)),
        "2100028": (AssessmentStatus.final,    "9.0", "Technisch sterk, innovatieve en goed gedocumenteerde aanpak", now - timedelta(days=52)),
        "2100029": (AssessmentStatus.reviewed, None,  "Goede bijdrage aan het eindproduct, afronding in behandeling", now - timedelta(days=48)),
        "2100030": (AssessmentStatus.final,    "6.5", "Voldoende, enkele fouten en onvolledigheden in eindproduct",  now - timedelta(days=58)),
        # Webontwikkeling Groep 1 (actief)
        "2100031": (AssessmentStatus.draft,    None,  "Frontend solide opgezet, backend-integratie loopt nog",       now - timedelta(days=2)),
        "2100032": (AssessmentStatus.reviewed, None,  "Mooie en toegankelijke UI, code review volgt nog",            now - timedelta(days=5)),
        "2100033": (AssessmentStatus.draft,    None,  "Basis HTML/CSS aanwezig, JavaScript nog te verdiepen",        now - timedelta(days=1)),
        "2100034": (AssessmentStatus.draft,    None,  "Actief en betrokken, Next.js-concepten goed begrepen",        now - timedelta(days=3)),
        "2100035": None,
        # Webontwikkeling Groep 2 (actief)
        "2100036": (AssessmentStatus.draft,    None,  "API-endpoints aanwezig, inputvalidatie ontbreekt nog",        now - timedelta(days=4)),
        "2100037": (AssessmentStatus.reviewed, None,  "Goede architectuurkeuzes, RESTful structuur klopt",           now - timedelta(days=6)),
        "2100038": (AssessmentStatus.draft,    None,  "REST-principes begrepen, implementatie gedeeltelijk",         now - timedelta(days=2)),
        "2100039": (AssessmentStatus.draft,    None,  "Solide backend, frontend nog te realiseren",                  now - timedelta(days=3)),
        "2100040": None,
        # Software Engineering Project (archief)
        "2100041": (AssessmentStatus.final,    "8.0", "Goede samenwerking, sterke deliverables geleverd",            now - timedelta(days=380)),
        "2100042": (AssessmentStatus.final,    "7.5", "Solide bijdrage, projectmanagement op orde",                  now - timedelta(days=375)),
        "2100043": (AssessmentStatus.final,    "8.5", "Technisch sterk, helder gecommuniceerd in het team",          now - timedelta(days=370)),
        "2100044": (AssessmentStatus.final,    "9.0", "Uitstekende kwaliteit, nam initiatief als projectleider",     now - timedelta(days=372)),
        # Algoritmen & Datastructuren Groep 1 (actief)
        "2100045": (AssessmentStatus.draft,    None,  "Goed begrip van recursie, implementatie gestart",             now - timedelta(days=4)),
        "2100046": (AssessmentStatus.reviewed, None,  "Nette implementatie, tijdcomplexiteitsanalyse ontbreekt",     now - timedelta(days=7)),
        "2100047": None,
        "2100048": (AssessmentStatus.draft,    None,  "Basis datastructuren correct toegepast",                      now - timedelta(days=3)),
        "2100049": (AssessmentStatus.draft,    None,  "Algoritmen begrepen, code nog niet geoptimaliseerd",          now - timedelta(days=2)),
        # Algoritmen & Datastructuren Groep 2 (actief)
        "2100050": (AssessmentStatus.reviewed, None,  "Grafenalgoritmen goed geïmplementeerd, testen uitbreiden",    now - timedelta(days=8)),
        "2100051": (AssessmentStatus.draft,    None,  "Visualisatie aanwezig, correctheid nog te verifiëren",        now - timedelta(days=4)),
        "2100052": None,
        "2100053": (AssessmentStatus.draft,    None,  "Solide aanpak, documentatie ontbreekt nog",                   now - timedelta(days=2)),
        "2100054": (AssessmentStatus.draft,    None,  "BFS en DFS correct, complexere algoritmen nog niet geïmpl.", now - timedelta(days=5)),
        # Linux & Netwerken (geen groepen, actief)
        "2100055": (AssessmentStatus.draft,    None,  "Basis Linux-commando's beheerst, scripting te verdiepen",     now - timedelta(days=3)),
        "2100056": (AssessmentStatus.reviewed, None,  "Server correct geconfigureerd, monitoringscript opgesteld",   now - timedelta(days=6)),
        "2100057": None,
        "2100058": (AssessmentStatus.draft,    None,  "Goede voortgang, firewallconfiguratie nog incompleet",        now - timedelta(days=2)),
        "2100059": (AssessmentStatus.reviewed, None,  "Bash-scripts functioneel en robuust opgezet",                 now - timedelta(days=5)),
        "2100060": (AssessmentStatus.draft,    None,  "Installaties gedaan, configuratiedocumentatie mist",          now - timedelta(days=3)),
        "2100061": None,
        "2100062": (AssessmentStatus.draft,    None,  "Basis netwerkinzicht aangetoond, verdere verdieping nodig",   now - timedelta(days=4)),
        # Agile Projectmanagement (geen groepen, archief 2024-2025)
        "2100063": (AssessmentStatus.final,    "8.0", "Actieve deelname in scrumteam, sterke retrospectives",        now - timedelta(days=380)),
        "2100064": (AssessmentStatus.final,    "7.5", "Goede bijdrage als teamlid, procesafspraken nageleefd",       now - timedelta(days=375)),
        "2100065": (AssessmentStatus.final,    "9.0", "Uitstekend scrummaster, team effectief gecoacht",             now - timedelta(days=370)),
        "2100066": (AssessmentStatus.final,    "7.0", "Voldoende bijdrage, backlogbeheer voor verbetering vatbaar",  now - timedelta(days=372)),
        "2100067": (AssessmentStatus.final,    "8.5", "Sterke product owner, heldere user stories opgesteld",        now - timedelta(days=368)),
        "2100068": (AssessmentStatus.final,    "7.5", "Goede retrospective-inbreng, samenwerking soepel verlopen",   now - timedelta(days=365)),
    }

    student_by_number = {s.student_number: s for s in students}

    assessments = []
    for student_number, spec in assessment_specs.items():
        if spec is None:
            continue

        status, grade, draft_note, created_at = spec
        student = student_by_number[student_number]
        project = project_by_key[sn_to_project_key[student_number]]
        module = module_by_id[project.module_id]

        consent_status = (
            ConsentStatus.accepted if student.consent_given else ConsentStatus.pending
        )
        consent_confirmed_at = (
            (created_at - timedelta(days=5)) if student.consent_given else None
        )
        consent_confirmed_by = module.teacher_id if student.consent_given else None

        final_form = None
        completed_at = None
        if status == AssessmentStatus.final and grade:
            final_form = _final_json(grade, student.name)
            completed_at = created_at + timedelta(days=3)

        assessments.append(
            Assessment(
                id=uid(f"assessment-{student_number}"),
                student_id=student_number,
                teacher_id=module.teacher_id,
                module_id=module.id,
                status=status,
                draft_form_json=_draft_json(draft_note),
                final_form_json=final_form,
                consent_status=consent_status,
                consent_confirmed_at=consent_confirmed_at,
                consent_confirmed_by=consent_confirmed_by,
                created_at=created_at,
                completed_at=completed_at,
            )
        )
    session.add_all(assessments)

    session.commit()

    print(f"Seed database created: {seed_path}")
    print(f"  departments : {session.query(Department).count()}")
    print(f"  teachers    : {session.query(Teacher).count()}")
    print(f"  modules     : {session.query(Module).count()}")
    print(f"  projects    : {session.query(Project).count()}")
    print(f"  students    : {session.query(Student).count()}")
    print(f"  assessments : {session.query(Assessment).count()}")

    session.close()


if __name__ == "__main__":
    build_seed_database(resolve_output_path())
