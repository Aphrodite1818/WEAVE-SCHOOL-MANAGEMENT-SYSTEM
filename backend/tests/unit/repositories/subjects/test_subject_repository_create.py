# from app.modules.subjects.repository import SubjectRepository
# from sqlalchemy.ext.asyncio import AsyncSession
# from app.tenant_management.models import Tenant
# from app.modules.subjects.models import Subject
# import pytest


# """this test is actually creating an object and passing it to repository"""
# @pytest.mark.asyncio #tells pytest this function is async run in an async event loop
# async def test_create_subject(
#     db_session: AsyncSession,
#     tenant: Tenant,
# ) -> None:
#     subject = Subject(
#         tenant_id=tenant.id,
#         name="English",
#         code="ENG",
#         description="English subject",
#         is_active=True,
#     )

#     created_subject = await SubjectRepository.create_subject(
#         db=db_session,
#         subject=subject,
#     )

#     assert created_subject.id is not None
#     assert created_subject.name == "English"
