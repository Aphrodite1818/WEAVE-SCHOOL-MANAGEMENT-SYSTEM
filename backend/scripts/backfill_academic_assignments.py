#!/usr/bin/env python3
"""Backfill class_subjects, teacher_assignments, and score FKs from legacy tables.

Run against staging first. Produces migration_report.json and unmatched_teacher_subjects.csv.

Usage (from backend/):
    python -m scripts.backfill_academic_assignments [--tenant-id UUID] [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import uuid
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.modules import import_model_modules
from app.modules.student_academics.models import (
    ClassSubject,
    ClassSubjectTeacher,
    StudentSubjectResult,
    TeacherAssignment,
)
from app.modules.teachers.models import TeacherSubject


REPORT_PATH = Path("migration_report.json")
UNMATCHED_CSV_PATH = Path("unmatched_teacher_subjects.csv")


async def backfill(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID | None,
    dry_run: bool,
) -> dict:
    import_model_modules()

    cst_filters = []
    if tenant_id is not None:
        cst_filters.append(ClassSubjectTeacher.tenant_id == tenant_id)

    legacy_rows = (
        await db.execute(
            select(ClassSubjectTeacher).where(*cst_filters).order_by(ClassSubjectTeacher.created_at)
        )
    ).scalars().all()

    ts_filters = []
    if tenant_id is not None:
        ts_filters.append(TeacherSubject.tenant_id == tenant_id)
    teacher_subject_rows = (
        await db.execute(select(TeacherSubject).where(*ts_filters))
    ).scalars().all()

    result_rows_preview = (
        await db.execute(
            select(StudentSubjectResult).where(
                *([StudentSubjectResult.tenant_id == tenant_id] if tenant_id else [])
            )
        )
    ).scalars().all()

    counts_before = {
        "class_subject_teachers": len(legacy_rows),
        "teacher_subjects": len(teacher_subject_rows),
        "student_subject_results": len(result_rows_preview),
        "class_subjects": len(
            (
                await db.execute(
                    select(ClassSubject).where(
                        *([ClassSubject.tenant_id == tenant_id] if tenant_id else [])
                    )
                )
            ).scalars().all()
        ),
        "teacher_assignments": len(
            (
                await db.execute(
                    select(TeacherAssignment).where(
                        *([TeacherAssignment.tenant_id == tenant_id] if tenant_id else [])
                    )
                )
            ).scalars().all()
        ),
    }

    cst_to_ta: dict[uuid.UUID, uuid.UUID] = {}
    orphaned_results: list[dict] = []
    duplicate_active: list[dict] = []

    for row in legacy_rows:
        class_subject = (
            await db.execute(
                select(ClassSubject).where(
                    ClassSubject.tenant_id == row.tenant_id,
                    ClassSubject.class_id == row.class_id,
                    ClassSubject.subject_id == row.subject_id,
                )
            )
        ).scalar_one_or_none()

        if class_subject is None:
            class_subject = ClassSubject(
                tenant_id=row.tenant_id,
                class_id=row.class_id,
                subject_id=row.subject_id,
                is_core=row.is_core,
                is_active=row.is_active,
            )
            db.add(class_subject)
            await db.flush()

        teacher_assignment = (
            await db.execute(
                select(TeacherAssignment).where(
                    TeacherAssignment.tenant_id == row.tenant_id,
                    TeacherAssignment.class_subject_id == class_subject.id,
                    TeacherAssignment.teacher_membership_id == row.teacher_membership_id,
                )
            )
        ).scalar_one_or_none()

        if teacher_assignment is None:
            teacher_assignment = TeacherAssignment(
                tenant_id=row.tenant_id,
                class_subject_id=class_subject.id,
                teacher_membership_id=row.teacher_membership_id,
                is_active=row.is_active,
                effective_from=row.created_at.date() if row.created_at else date.today(),
                effective_to=None if row.is_active else date.today(),
            )
            db.add(teacher_assignment)
            await db.flush()

        cst_to_ta[row.id] = teacher_assignment.id

    result_rows = result_rows_preview

    for result in result_rows:
        mapped_id = cst_to_ta.get(result.class_subject_teacher_id)
        if mapped_id is None:
            orphaned_results.append(
                {
                    "result_id": str(result.id),
                    "class_subject_teacher_id": str(result.class_subject_teacher_id),
                    "student_id": str(result.student_id),
                    "status": result.status.value if hasattr(result.status, "value") else str(result.status),
                }
            )
            continue
        if result.teacher_assignment_id is None:
            result.teacher_assignment_id = mapped_id

    # Flag duplicate active teacher assignments per class_subject.
    active_assignments = (
        await db.execute(
            select(TeacherAssignment).where(
                TeacherAssignment.is_active.is_(True),
                *([TeacherAssignment.tenant_id == tenant_id] if tenant_id else []),
            )
        )
    ).scalars().all()
    by_class_subject: dict[uuid.UUID, list[TeacherAssignment]] = {}
    for assignment in active_assignments:
        by_class_subject.setdefault(assignment.class_subject_id, []).append(assignment)
    for class_subject_id, assignments in by_class_subject.items():
        if len(assignments) > 1:
            duplicate_active.append(
                {
                    "class_subject_id": str(class_subject_id),
                    "active_assignment_ids": [str(item.id) for item in assignments],
                }
            )

    submitted_without_ta = [
        {
            "result_id": str(row.id),
            "status": row.status.value if hasattr(row.status, "value") else str(row.status),
        }
        for row in result_rows
        if (row.status.value if hasattr(row.status, "value") else str(row.status)) == "submitted"
        and row.teacher_assignment_id is None
    ]

    counts_after = {
        "class_subjects": len(
            (
                await db.execute(
                    select(ClassSubject).where(
                        *([ClassSubject.tenant_id == tenant_id] if tenant_id else [])
                    )
                )
            ).scalars().all()
        ),
        "teacher_assignments": len(
            (
                await db.execute(
                    select(TeacherAssignment).where(
                        *([TeacherAssignment.tenant_id == tenant_id] if tenant_id else [])
                    )
                )
            ).scalars().all()
        ),
        "results_with_teacher_assignment_id": sum(
            1 for row in result_rows if row.teacher_assignment_id is not None
        ),
    }

    report = {
        "dry_run": dry_run,
        "tenant_id": str(tenant_id) if tenant_id else None,
        "counts_before": counts_before,
        "counts_after": counts_after,
        "legacy_to_new_mapping_count": len(cst_to_ta),
        "orphaned_results": orphaned_results,
        "duplicate_active_teacher_assignments": duplicate_active,
        "submitted_without_teacher_assignment_id": submitted_without_ta,
        "validation": {
            "all_submitted_have_teacher_assignment_id": len(submitted_without_ta) == 0,
            "no_duplicate_active_assignments": len(duplicate_active) == 0,
        },
    }

    with REPORT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)

    with UNMATCHED_CSV_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["tenant_id", "teacher_id", "subject_id", "teacher_subject_id"],
        )
        writer.writeheader()
        for row in teacher_subject_rows:
            writer.writerow(
                {
                    "tenant_id": str(row.tenant_id),
                    "teacher_id": str(row.teacher_id),
                    "subject_id": str(row.subject_id),
                    "teacher_subject_id": str(row.id),
                }
            )

    if dry_run:
        await db.rollback()
    else:
        await db.commit()

    return report


async def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill academic assignment consolidation data.")
    parser.add_argument("--tenant-id", type=uuid.UUID, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        report = await backfill(db, tenant_id=args.tenant_id, dry_run=args.dry_run)
        print(json.dumps(report, indent=2))
        print(f"\nWrote {REPORT_PATH} and {UNMATCHED_CSV_PATH}")

    if not report["validation"]["all_submitted_have_teacher_assignment_id"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
