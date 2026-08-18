"""Build a consistent v3 CBT bootstrap with bulk canonical projection."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.modules.cbt.academics.schemas import (
    CBTAcademicBootstrapResponse,
    CBTSchoolSnapshot,
    CBTServerSnapshot,
    CBTSyncMetadata,
)
from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.models import CBTServer
from app.modules.cbt.sync.projectors.bootstrap import build_bootstrap_sections
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.tenant_management.models import Tenant


class CBTAcademicSyncService:
    @staticmethod
    async def build_bootstrap(
        _request_db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
    ) -> CBTAcademicBootstrapResponse:
        # Authentication may already have used the request session. A dedicated
        # REPEATABLE READ transaction guarantees projected rows and cursor come
        # from exactly the same MVCC snapshot.
        async with AsyncSessionLocal() as db:
            await db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            return await CBTAcademicSyncService._build(
                db,
                current_server=current_server,
            )

    @staticmethod
    async def _build(
        db: AsyncSession,
        *,
        current_server: AuthenticatedCBTServer,
    ) -> CBTAcademicBootstrapResponse:
        tenant_id = current_server.tenant_id
        tenant = (await db.execute(select(Tenant).where(Tenant.id == tenant_id))).scalar_one()
        server = (
            await db.execute(
                select(CBTServer).where(
                    CBTServer.id == current_server.server_id,
                    CBTServer.tenant_id == tenant_id,
                )
            )
        ).scalar_one()

        sections = await db.run_sync(
            lambda sync_session: build_bootstrap_sections(
                sync_session,
                tenant_id=tenant_id,
            )
        )

        # Read after all projections while still inside the same repeatable-read
        # transaction. A concurrent mutation therefore belongs either entirely to
        # this snapshot/cursor boundary or entirely to a later incremental page.
        cursor = await CBTSyncRepository.get_latest_cursor(db, tenant_id=tenant_id)
        return CBTAcademicBootstrapResponse(
            metadata=CBTSyncMetadata(
                snapshot_id=uuid.uuid4(),
                generated_at=datetime.now(timezone.utc),
                cursor=cursor,
            ),
            school=CBTSchoolSnapshot(
                id=tenant.id,
                name=tenant.school_name,
                institution_type=(
                    tenant.institution_type.value if tenant.institution_type else None
                ),
                timezone=tenant.timezone,
            ),
            server=CBTServerSnapshot(id=server.id, name=server.name),
            sessions=sections["sessions"],
            terms=sections["terms"],
            levels=sections["levels"],
            arm_labels=sections["arm_labels"],
            departments=sections["departments"],
            classes=sections["classes"],
            class_term_departments=sections["class_term_departments"],
            subjects=sections["subjects"],
            curricula=sections["curricula"],
            curriculum_subjects=sections["curriculum_subjects"],
            offerings=sections["offerings"],
            assessment_schemes=sections["assessment_schemes"],
            assessment_components=sections["assessment_components"],
            admins=sections["admins"],
            teachers=sections["teachers"],
            teacher_assignments=sections["teacher_assignments"],
            student_enrollments=sections["student_enrollments"],
        )
