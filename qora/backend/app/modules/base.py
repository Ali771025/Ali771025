"""Module conventions [TECH — modular monolith boundary rules].

Each module owns: models.py, schemas.py, service.py, router.py.
Modules may import other modules' *service/schemas* (interfaces) but NEVER their
models or repositories. Cross-module data joins happen through service calls.
"""
from fastapi import APIRouter


class ModuleRouter(APIRouter):
    """APIRouter tagged with its module name for boundary tooling."""

    module_name: str = "base"
