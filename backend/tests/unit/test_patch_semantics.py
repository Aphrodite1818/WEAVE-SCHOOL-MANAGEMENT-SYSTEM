from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.attendance.schemas import AttendanceSettingsUpdate, SchoolGeofenceUpdate
from app.modules.classes.models import AcademicCategory
from app.modules.classes.schemas import (
    AcademicLevelUpdate,
    ArmLabelUpdate,
    ClassRoomUpdate,
)
from app.modules.communications.schemas import AnnouncementUpdate
from app.modules.report_cards.schemas import ReportCardCommentsUpdate
from app.modules.school_calendar.calendar_enums import (
    SchoolCalendarEventAudience,
    SchoolCalendarEventType,
)
from app.modules.school_calendar.schemas import (
    SchoolCalendarConfigurationUpdate,
    SchoolCalendarDayUpdate,
    SchoolCalendarEventUpdate,
)
from app.modules.student_academics.assessment_schemas import AssessmentComponentUpdate
from app.modules.student_academics.curriculum_v2_schemas import CurriculumSubjectUpdate
from app.modules.student_academics.models import AcademicTermName
from app.modules.student_academics.schemas import (
    AcademicSessionUpdate,
    AcademicTermUpdate,
    GradingScaleUpdate,
)
from app.modules.tenant_branding.schemas import TenantBrandingUpdate
from app.modules.user_guides.schemas import UserGuideStateUpdate
from app.tenant_management.schemas import TenantUpdate


def _assert_invalid(factory, **values) -> None:
    with pytest.raises(ValidationError):
        factory(**values)


def test_academic_structure_patch_rejects_null_non_clearable_fields() -> None:
    _assert_invalid(AcademicLevelUpdate, name=None)
    _assert_invalid(AcademicLevelUpdate, category=None)
    _assert_invalid(AcademicLevelUpdate, position=None)
    _assert_invalid(ArmLabelUpdate, label=None)
    _assert_invalid(ArmLabelUpdate, is_active=None)
    _assert_invalid(ClassRoomUpdate, academic_level_id=None)
    _assert_invalid(ClassRoomUpdate, arm_label_id=None)


def test_academic_structure_patch_preserves_clearable_teacher_assignment() -> None:
    payload = ClassRoomUpdate(teacher_membership_id=None)
    assert payload.model_fields_set == {"teacher_membership_id"}
    assert payload.model_dump(exclude_unset=True) == {"teacher_membership_id": None}


def test_curriculum_patch_requires_real_boolean_changes() -> None:
    _assert_invalid(CurriculumSubjectUpdate, is_elective=None)
    _assert_invalid(CurriculumSubjectUpdate, is_active=None)
    _assert_invalid(CurriculumSubjectUpdate)
    payload = CurriculumSubjectUpdate(is_elective=True)
    assert payload.model_dump(exclude_unset=True) == {"is_elective": True}


def test_assessment_component_patch_distinguishes_clearable_code() -> None:
    _assert_invalid(AssessmentComponentUpdate, name=None)
    _assert_invalid(AssessmentComponentUpdate, maximum_score=None)
    payload = AssessmentComponentUpdate(code=None)
    assert payload.model_dump(exclude_unset=True) == {"code": None}


def test_period_patch_distinguishes_omitted_and_clearable_nulls() -> None:
    _assert_invalid(AcademicSessionUpdate, name=None)
    _assert_invalid(AcademicTermUpdate, name=None)

    session = AcademicSessionUpdate(start_date=None, next_academic_session_id=None)
    assert session.model_dump(exclude_unset=True) == {
        "start_date": None,
        "next_academic_session_id": None,
    }

    term = AcademicTermUpdate(end_date=None)
    assert term.model_dump(exclude_unset=True) == {"end_date": None}


def test_grading_scale_patch_preserves_clearable_remark() -> None:
    _assert_invalid(GradingScaleUpdate, grade=None)
    _assert_invalid(GradingScaleUpdate, min_score=None)
    _assert_invalid(GradingScaleUpdate, max_score=None)
    payload = GradingScaleUpdate(remark=None)
    assert payload.model_dump(exclude_unset=True) == {"remark": None}


def test_branding_patch_rejects_null_and_empty_updates() -> None:
    _assert_invalid(TenantBrandingUpdate, palette_key=None)
    _assert_invalid(TenantBrandingUpdate, is_enabled=None)
    _assert_invalid(TenantBrandingUpdate)
    assert TenantBrandingUpdate(is_enabled=False).model_dump(exclude_unset=True) == {
        "is_enabled": False
    }


def test_user_guide_patch_preserves_clearable_fields_only() -> None:
    _assert_invalid(UserGuideStateUpdate, status=None)
    _assert_invalid(UserGuideStateUpdate, skipped_steps=None)
    _assert_invalid(UserGuideStateUpdate)

    payload = UserGuideStateUpdate(current_step=None, remind_after=None)
    assert payload.model_dump(exclude_unset=True) == {
        "current_step": None,
        "remind_after": None,
    }


def test_tenant_patch_rejects_null_core_identity_but_allows_optional_clears() -> None:
    _assert_invalid(TenantUpdate, school_name=None)
    _assert_invalid(TenantUpdate, email=None)
    _assert_invalid(TenantUpdate, country=None)
    _assert_invalid(TenantUpdate, timezone=None)
    _assert_invalid(TenantUpdate, language=None)

    payload = TenantUpdate(phone=None, address=None, institution_type=None)
    assert payload.model_dump(exclude_unset=True) == {
        "phone": None,
        "address": None,
        "institution_type": None,
    }


def test_calendar_configuration_patch_separates_clearable_times() -> None:
    _assert_invalid(SchoolCalendarConfigurationUpdate, timezone=None)
    _assert_invalid(SchoolCalendarConfigurationUpdate, instructional_weekdays=None)
    _assert_invalid(
        SchoolCalendarConfigurationUpdate,
        default_student_attendance_required=None,
    )

    payload = SchoolCalendarConfigurationUpdate(
        default_open_time=None,
        default_close_time=None,
    )
    assert payload.model_dump(exclude_unset=True) == {
        "default_open_time": None,
        "default_close_time": None,
    }


def test_calendar_day_patch_allows_only_intentional_clears() -> None:
    _assert_invalid(SchoolCalendarDayUpdate, day_type=None)
    _assert_invalid(SchoolCalendarDayUpdate, school_open=None)
    payload = SchoolCalendarDayUpdate(
        title=None,
        description=None,
        opens_at=None,
        closes_at=None,
    )
    assert payload.model_dump(exclude_unset=True) == {
        "title": None,
        "description": None,
        "opens_at": None,
        "closes_at": None,
    }


def test_calendar_event_patch_allows_description_and_location_to_clear() -> None:
    _assert_invalid(SchoolCalendarEventUpdate, title=None)
    _assert_invalid(SchoolCalendarEventUpdate, event_type=None)
    _assert_invalid(SchoolCalendarEventUpdate, starts_at=None)
    _assert_invalid(SchoolCalendarEventUpdate, ends_at=None)
    _assert_invalid(SchoolCalendarEventUpdate, is_all_day=None)
    _assert_invalid(SchoolCalendarEventUpdate, audience=None)

    payload = SchoolCalendarEventUpdate(description=None, location=None)
    assert payload.model_dump(exclude_unset=True) == {
        "description": None,
        "location": None,
    }


def test_announcement_patch_rejects_null_core_fields_and_keeps_clearable_schedule() -> None:
    _assert_invalid(AnnouncementUpdate)
    _assert_invalid(AnnouncementUpdate, title=None)
    _assert_invalid(AnnouncementUpdate, body=None)
    _assert_invalid(AnnouncementUpdate, category=None)
    _assert_invalid(AnnouncementUpdate, priority=None)
    _assert_invalid(AnnouncementUpdate, is_pinned=None)
    _assert_invalid(AnnouncementUpdate, audiences=None)

    payload = AnnouncementUpdate(publish_at=None, expires_at=None)
    assert payload.model_dump(exclude_unset=True) == {
        "publish_at": None,
        "expires_at": None,
    }


def test_report_card_comment_patch_supports_intentional_clear_only() -> None:
    _assert_invalid(ReportCardCommentsUpdate)
    payload = ReportCardCommentsUpdate(class_teacher_comment=None)
    assert payload.model_dump(exclude_unset=True) == {"class_teacher_comment": None}


def test_attendance_settings_update_rejects_null_config_and_allows_time_clear() -> None:
    _assert_invalid(AttendanceSettingsUpdate)
    _assert_invalid(AttendanceSettingsUpdate, timezone=None)
    _assert_invalid(AttendanceSettingsUpdate, require_geofence_for_workforce=None)
    _assert_invalid(AttendanceSettingsUpdate, geofence_accuracy_threshold_m=None)

    payload = AttendanceSettingsUpdate(
        student_marking_opens_at=None,
        student_marking_closes_at=None,
    )
    assert payload.model_dump(exclude_unset=True) == {
        "student_marking_opens_at": None,
        "student_marking_closes_at": None,
    }


def test_geofence_patch_rejects_null_core_fields_and_allows_description_clear() -> None:
    _assert_invalid(SchoolGeofenceUpdate)
    _assert_invalid(SchoolGeofenceUpdate, name=None)
    _assert_invalid(SchoolGeofenceUpdate, latitude=None)
    _assert_invalid(SchoolGeofenceUpdate, longitude=None)
    _assert_invalid(SchoolGeofenceUpdate, radius_m=None)
    _assert_invalid(SchoolGeofenceUpdate, is_primary=None)

    payload = SchoolGeofenceUpdate(description=None)
    assert payload.model_dump(exclude_unset=True) == {"description": None}


def test_valid_non_null_patch_values_remain_accepted() -> None:
    level = AcademicLevelUpdate(
        name="JSS 1",
        category=AcademicCategory.JUNIOR_SECONDARY,
        position=1,
    )
    assert set(level.model_fields_set) == {"name", "category", "position"}

    component = AssessmentComponentUpdate(
        name="CA 1",
        maximum_score=Decimal("20"),
    )
    assert component.model_dump(exclude_unset=True)["name"] == "CA 1"

    event = SchoolCalendarEventUpdate(
        title="Open Day",
        event_type=SchoolCalendarEventType.OTHER,
        starts_at=datetime(2026, 8, 20, 9, 0),
        ends_at=datetime(2026, 8, 20, 12, 0),
        is_all_day=False,
        audience=SchoolCalendarEventAudience.ALL,
    )
    assert event.model_dump(exclude_unset=True)["title"] == "Open Day"

    term = AcademicTermUpdate(name=AcademicTermName.FIRST_TERM)
    assert term.model_dump(exclude_unset=True)["name"] == AcademicTermName.FIRST_TERM
