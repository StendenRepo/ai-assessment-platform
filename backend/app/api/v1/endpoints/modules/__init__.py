"""Module endpoints package."""
from .router import router
from . import crud, templates, documents, groups, students, overlap, export  # noqa: F401

__all__ = ["router"]
