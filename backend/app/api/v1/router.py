from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    assessment_questions,
    assessments,
    auth,
    evidence,
    evidence_matches,
    github,
    health,
    modules,
    projects,
    recordings,
    reports,
    rubric_scores,
    students,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(modules.router, prefix="/modules", tags=["Modules"])
api_router.include_router(projects.router, prefix="/projects", tags=["Projects"])
api_router.include_router(students.router, prefix="/students", tags=["Students"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["Evidence"])
api_router.include_router(
    evidence_matches.router, prefix="/students", tags=["Evidence Matching"]
)
api_router.include_router(
    assessment_questions.router, prefix="/students", tags=["Assessment Questions"]
)
api_router.include_router(
    rubric_scores.router, prefix="/students", tags=["Rubric Scores"]
)
api_router.include_router(recordings.router, tags=["Recording"])
api_router.include_router(assessments.router, tags=["Assessment"])
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
api_router.include_router(github.router, prefix="/github", tags=["GitHub"])
