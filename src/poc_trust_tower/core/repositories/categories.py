"""Repo des catégories."""

from poc_trust_tower.core.model import Category
from poc_trust_tower.core.schemas import CategoryCreateSchema

from ._base import ConflictError, _add, _find, _name_taken, _next_id, _remove, _save

repoCategories: list[Category] = [
    Category(id=index, name=name)
    for index, name in enumerate(["Finance", "RH", "Operations", "Risques", "Conformite"], start=1)
]

def get_category(category_id: int) -> Category | None:
    return next((c for c in repoCategories if c.id == category_id), None)

def create_category(payload: CategoryCreateSchema) -> Category:
    if _name_taken(repoCategories, payload.name):
        raise ConflictError(f"category '{payload.name}' already exists")
    category = Category(id=_next_id(repoCategories), name=payload.name)
    return _add("repoCategories", category)


def update_category(category_id: int, payload: CategoryCreateSchema) -> Category:
    category = _find(repoCategories, category_id, "category")
    if _name_taken(repoCategories, payload.name, exclude=category):
        raise ConflictError(f"category '{payload.name}' already exists")
    category.name = payload.name
    return _save("repoCategories", category)


def delete_category(category_id: int) -> None:
    from .indicators import repoIndicators  # import paresseux : évite un cycle

    category = _find(repoCategories, category_id, "category")
    if any(i.category is category for i in repoIndicators):
        raise ConflictError(f"category {category_id} is used by indicators")
    _remove("repoCategories", category)
