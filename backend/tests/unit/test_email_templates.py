from app.core.utils.email_templates import get_parent_invitation_email_html


def test_email_template_uses_image_free_brand_mark() -> None:
    html = get_parent_invitation_email_html(
        school_name="Weave Test School",
        student_name="Ada Student",
        invite_link="https://app.example.com/parent-invitations/token",
    )

    assert "<img" not in html
    assert "weave-email-icon.png" not in html
    assert ">W</span>" in html
    assert "School Management" in html
