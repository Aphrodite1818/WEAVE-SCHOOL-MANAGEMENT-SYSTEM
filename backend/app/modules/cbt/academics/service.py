"""Build a consistent v2 CBT bootstrap from the same domain concepts used by sync."""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import AsyncSessionLocal
from app.modules.cbt.academics.schemas import *
from app.modules.cbt.auth.schemas import AuthenticatedCBTServer
from app.modules.cbt.models import CBTServer
from app.modules.cbt.sync.repository import CBTSyncRepository
from app.modules.classes.models import AcademicLevel, ArmLabel, ClassRoom, Department
from app.modules.student_academics.curriculum_models import ClassTermDepartmentAssignment, Curriculum, CurriculumOffering, CurriculumSubject
from app.modules.student_academics.models import AcademicSession, AcademicTerm, AssessmentComponent, AssessmentScheme, AssessmentSchemeStatus, LevelSubject, TeacherAssignment
from app.modules.students.models import AcademicStatus, Student, StudentEnrollment
from app.modules.subjects.models import Subject
from app.modules.teachers.models import TeacherAccount, TeacherMembership
from app.tenant_management.models import Tenant


class CBTAcademicSyncService:
    @staticmethod
    async def build_bootstrap(_request_db: AsyncSession, *, current_server: AuthenticatedCBTServer) -> CBTAcademicBootstrapResponse:
        # Authentication may already have used the request session. Use a dedicated
        # REPEATABLE READ snapshot so domain rows and the returned cursor describe
        # one MVCC boundary: a concurrent domain+sync commit is seen entirely or not at all.
        async with AsyncSessionLocal() as db:
            await db.connection(execution_options={"isolation_level":"REPEATABLE READ"})
            return await CBTAcademicSyncService._build(db, current_server=current_server)

    @staticmethod
    async def _build(db: AsyncSession, *, current_server: AuthenticatedCBTServer) -> CBTAcademicBootstrapResponse:
        tenant_id=current_server.tenant_id
        tenant=(await db.execute(select(Tenant).where(Tenant.id==tenant_id))).scalar_one()
        server=(await db.execute(select(CBTServer).where(CBTServer.id==current_server.server_id,CBTServer.tenant_id==tenant_id))).scalar_one()
        sessions=list((await db.execute(select(AcademicSession).where(AcademicSession.tenant_id==tenant_id).order_by(AcademicSession.created_at))).scalars().all())
        terms=list((await db.execute(select(AcademicTerm).where(AcademicTerm.tenant_id==tenant_id).order_by(AcademicTerm.created_at))).scalars().all())
        levels=list((await db.execute(select(AcademicLevel).where(AcademicLevel.tenant_id==tenant_id,AcademicLevel.is_active.is_(True),AcademicLevel.archived_at.is_(None)).order_by(AcademicLevel.category,AcademicLevel.position))).scalars().all())
        arms=list((await db.execute(select(ArmLabel).where(ArmLabel.tenant_id==tenant_id,ArmLabel.is_active.is_(True),ArmLabel.archived_at.is_(None)).order_by(ArmLabel.label))).scalars().all())
        departments=list((await db.execute(select(Department).where(Department.tenant_id==tenant_id,Department.is_active.is_(True),Department.archived_at.is_(None)).order_by(Department.name))).scalars().all())
        classes=list((await db.execute(select(ClassRoom).where(ClassRoom.tenant_id==tenant_id,ClassRoom.is_active.is_(True),ClassRoom.archived_at.is_(None)))).scalars().all())
        class_terms=list((await db.execute(select(ClassTermDepartmentAssignment).where(ClassTermDepartmentAssignment.tenant_id==tenant_id))).scalars().all())
        subjects=list((await db.execute(select(Subject).where(Subject.tenant_id==tenant_id,Subject.is_active.is_(True),Subject.archived_at.is_(None)).order_by(Subject.name))).scalars().all())
        curricula=list((await db.execute(select(Curriculum).where(Curriculum.tenant_id==tenant_id))).scalars().all())
        curriculum_subjects=list((await db.execute(select(CurriculumSubject).where(CurriculumSubject.tenant_id==tenant_id,CurriculumSubject.is_active.is_(True)))).scalars().all())
        offerings=list((await db.execute(select(CurriculumOffering).where(CurriculumOffering.tenant_id==tenant_id))).scalars().all())
        schemes=list((await db.execute(select(AssessmentScheme).where(AssessmentScheme.tenant_id==tenant_id,AssessmentScheme.status==AssessmentSchemeStatus.ACTIVE))).scalars().all())
        scheme_ids=[row.id for row in schemes]
        components=list((await db.execute(select(AssessmentComponent).where(AssessmentComponent.tenant_id==tenant_id,AssessmentComponent.assessment_scheme_id.in_(scheme_ids),AssessmentComponent.is_active.is_(True)).order_by(AssessmentComponent.position))).scalars().all()) if scheme_ids else []
        enrollment_rows=list((await db.execute(select(StudentEnrollment,Student).join(Student,Student.id==StudentEnrollment.student_id).where(StudentEnrollment.tenant_id==tenant_id,StudentEnrollment.is_current.is_(True),Student.status==AcademicStatus.ACTIVE,Student.is_archived.is_(False)))).all())

        specialization={(row.class_id,row.academic_term_id):row.department_id for row in class_terms}
        curricula_by_id={row.id:row for row in curricula}; cs_by_id={row.id:row for row in curriculum_subjects}
        eligible_by_offering:dict[uuid.UUID,list[uuid.UUID]]={}
        for offering in offerings:
            cs=cs_by_id.get(offering.curriculum_subject_id); curriculum=curricula_by_id.get(cs.curriculum_id) if cs else None
            eligible=[]
            if curriculum:
                for enrollment,_student in enrollment_rows:
                    if enrollment.academic_level_id!=curriculum.academic_level_id: continue
                    if offering.department_id is None:
                        eligible.append(enrollment.id); continue
                    if enrollment.class_id and specialization.get((enrollment.class_id,offering.academic_term_id))==offering.department_id: eligible.append(enrollment.id)
            eligible_by_offering[offering.id]=eligible

        # Translate existing class-subject teacher assignments to the v2 curriculum
        # identifier by matching the old subject identity against the class level.
        legacy_assignments=list((await db.execute(select(TeacherAssignment,LevelSubject,ClassRoom).join(LevelSubject,LevelSubject.id==TeacherAssignment.level_subject_id).join(ClassRoom,ClassRoom.id==TeacherAssignment.class_id).where(TeacherAssignment.tenant_id==tenant_id,TeacherAssignment.is_active.is_(True)))).all())
        cs_lookup={(curricula_by_id[cs.curriculum_id].academic_level_id,cs.subject_id):cs.id for cs in curriculum_subjects if cs.curriculum_id in curricula_by_id}
        assignment_payload=[]; teacher_ids=set()
        for assignment,level_subject,classroom in legacy_assignments:
            cs_id=cs_lookup.get((classroom.academic_level_id,level_subject.subject_id))
            if not cs_id: continue
            teacher_ids.add(assignment.teacher_membership_id)
            assignment_payload.append(CBTTeacherAssignmentSnapshot(id=assignment.id,teacher_membership_id=assignment.teacher_membership_id,class_id=assignment.class_id,curriculum_subject_id=cs_id,is_active=assignment.is_active))
        teacher_rows=list((await db.execute(select(TeacherMembership,TeacherAccount).join(TeacherAccount,TeacherAccount.id==TeacherMembership.teacher_account_id).where(TeacherMembership.tenant_id==tenant_id,TeacherMembership.id.in_(teacher_ids)))).all()) if teacher_ids else []

        cursor=await CBTSyncRepository.get_latest_cursor(db,tenant_id=tenant_id)
        return CBTAcademicBootstrapResponse(
            metadata=CBTSyncMetadata(snapshot_id=uuid.uuid4(),generated_at=datetime.now(timezone.utc),cursor=cursor),
            school=CBTSchoolSnapshot(id=tenant.id,name=tenant.school_name,institution_type=tenant.institution_type.value if tenant.institution_type else None,timezone=tenant.timezone),
            server=CBTServerSnapshot(id=server.id,name=server.name),
            sessions=[CBTAcademicSessionSnapshot(id=x.id,name=x.name,status=x.status.value,is_current=x.is_current) for x in sessions],
            terms=[CBTAcademicTermSnapshot(id=x.id,academic_session_id=x.academic_session_id,name=x.name.value,status=x.status.value,is_current=x.is_current) for x in terms],
            levels=[CBTAcademicLevelSnapshot(id=x.id,name=x.name,category=x.category.value,position=x.position) for x in levels],
            arm_labels=[CBTArmLabelSnapshot(id=x.id,label=x.label) for x in arms],
            departments=[CBTDepartmentSnapshot(id=x.id,academic_level_id=x.academic_level_id,name=x.name) for x in departments],
            classes=[CBTClassSnapshot(id=x.id,academic_level_id=x.academic_level_id,arm_label_id=x.arm_label_id,display_name=x.display_name,is_active=x.is_active) for x in classes],
            class_term_departments=[CBTClassTermDepartmentSnapshot.model_validate(x) for x in class_terms],
            subjects=[CBTSubjectSnapshot(id=x.id,name=x.name,code=x.code,is_active=x.is_active) for x in subjects],
            curricula=[CBTCurriculumSnapshot.model_validate(x) for x in curricula],
            curriculum_subjects=[CBTCurriculumSubjectSnapshot.model_validate(x) for x in curriculum_subjects],
            offerings=[CBTCurriculumOfferingSnapshot(id=x.id,curriculum_subject_id=x.curriculum_subject_id,academic_term_id=x.academic_term_id,department_id=x.department_id,eligible_enrollment_ids=eligible_by_offering[x.id]) for x in offerings],
            assessment_schemes=[CBTAssessmentSchemeSnapshot(id=x.id,name=x.name,status=x.status.value) for x in schemes],
            assessment_components=[CBTAssessmentComponentSnapshot.model_validate(x) for x in components],
            teachers=[CBTTeacherSnapshot(id=m.id,teacher_account_id=m.teacher_account_id,first_name=a.first_name,last_name=a.last_name,staff_id=m.staff_id,status=m.status.value) for m,a in teacher_rows],
            teacher_assignments=assignment_payload,
            student_enrollments=[CBTStudentEnrollmentSnapshot(id=e.id,student_id=s.id,admission_number=s.admission_number,first_name=s.first_name,last_name=s.last_name,academic_level_id=e.academic_level_id,class_id=e.class_id,academic_session_id=e.academic_session_id,is_current=e.is_current,student_status=s.status.value) for e,s in enrollment_rows],
        )
