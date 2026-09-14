"""Authoritative institution-aware academic category metadata."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.classes.models import AcademicCategory
from app.tenant_management.models import InstitutionType


@dataclass(frozen=True, slots=True)
class AcademicCategoryDefinition:
    value: AcademicCategory
    label: str
    position: int
    supports_departments: bool = False


CATEGORY_CATALOG: dict[InstitutionType, tuple[AcademicCategoryDefinition, ...]] = {
    InstitutionType.PRIMARY_SCHOOL: (
        AcademicCategoryDefinition(AcademicCategory.KINDERGARTEN, "Kindergarten", 1),
        AcademicCategoryDefinition(AcademicCategory.NURSERY, "Nursery", 2),
        AcademicCategoryDefinition(AcademicCategory.PRIMARY, "Primary", 3),
    ),
    InstitutionType.SECONDARY_SCHOOL: (
        AcademicCategoryDefinition(AcademicCategory.JUNIOR_SECONDARY, "Junior Secondary", 1),
        AcademicCategoryDefinition(
            AcademicCategory.SENIOR_SECONDARY,
            "Senior Secondary",
            2,
            supports_departments=True,
        ),
    ),
}


def categories_for(institution_type: InstitutionType) -> tuple[AcademicCategoryDefinition, ...]:
    return CATEGORY_CATALOG[institution_type]


def category_definition(
    institution_type: InstitutionType,
    category: AcademicCategory,
) -> AcademicCategoryDefinition | None:
    return next(
        (item for item in categories_for(institution_type) if item.value == category),
        None,
    )


def category_supports_departments(
    institution_type: InstitutionType,
    category: AcademicCategory,
) -> bool:
    definition = category_definition(institution_type, category)
    return bool(definition and definition.supports_departments)
