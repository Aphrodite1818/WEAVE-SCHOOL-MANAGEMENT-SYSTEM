#======================================#
#             __init__.py              #
#======================================#


def import_model_modules() -> None:
    """Import SQLAlchemy models so string relationships and FKs can resolve."""
    import app.modules.auth.models  # noqa: F401
    import app.modules.auth_identity.models  # noqa: F401
    import app.modules.announcements.models  # noqa: F401
    import app.modules.classes.models  # noqa: F401
    import app.modules.parents.models  # noqa: F401
    import app.modules.students.models  # noqa: F401
    import app.modules.subjects.models  # noqa: F401
    import app.modules.student_academics.models  # noqa: F401
    import app.modules.report_cards.models  # noqa: F401
    import app.modules.subscriptions.models  # noqa: F401
    import app.modules.superadmin.models  # noqa: F401
    import app.modules.teachers.models  # noqa: F401
    import app.modules.tenant_admins.models  # noqa: F401
    import app.tenant_management.models  # noqa: F401
