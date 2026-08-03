#======================================#
#       core/utils/email_templates.py  #
#======================================#

from datetime import datetime
from html import escape

BRAND_NAME = "Weave"
BRAND_SUBTITLE = "School Management"


def _html(value: object) -> str:
    """Escape values before placing them into email HTML."""
    return escape(str(value), quote=True)


def _brand_mark() -> str:
    """Return an image-free brand mark that renders reliably in email clients."""

    return f"""
                        <table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse: collapse;">
                            <tr>
                                <td width="48" height="48" style="width: 48px; height: 48px; text-align: center; vertical-align: middle; background-color: #1E344D; background-image: linear-gradient(145deg, #263F5F 0%, #142235 100%); border-radius: 15px; box-shadow: inset 0 1px 0 rgba(255,255,255,0.08), 0 14px 28px rgba(2, 6, 23, 0.28);">
                                    <span style="display: inline-block; font-size: 23px; line-height: 48px; font-weight: 900; color: #DDE4FF; font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">W</span>
                                </td>
                            </tr>
                        </table>
"""


def _email_shell(title: str, eyebrow: str, body: str) -> str:
    """Return the shared Weave branded email shell."""
    year = datetime.now().year
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_html(title)}</title>
</head>
<body style="font-family: Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 40px 20px; color: #0F172A;">
    <div style="max-width: 600px; margin: 0 auto;">
        <div style="padding: 0 0 18px 0;">
            <table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse: collapse;">
                <tr>
                    <td style="vertical-align: middle; padding: 0 12px 0 0;">
{_brand_mark()}
                    </td>
                    <td style="vertical-align: middle; padding: 0;">
                        <p style="margin: 0; font-size: 20px; line-height: 1.1; font-weight: 800; color: #0F172A;">{BRAND_NAME}</p>
                        <p style="margin: 3px 0 0 0; font-size: 12px; line-height: 1.4; color: #64748B;">{BRAND_SUBTITLE}</p>
                    </td>
                </tr>
            </table>
        </div>

        <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 18px; overflow: hidden; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 20px 50px rgba(15, 23, 42, 0.07);">
            <div style="background-color: #EEF1FF; padding: 30px;">
                <p style="margin: 0 0 10px 0; font-size: 12px; font-weight: 800; letter-spacing: 0.12em; text-transform: uppercase; color: #416F91;">{_html(eyebrow)}</p>
                <h1 style="margin: 0; font-size: 26px; line-height: 1.25; font-weight: 800; color: #070B14;">{_html(title)}</h1>
            </div>

            <div style="padding: 34px 30px;">
                {body}
            </div>

            <div style="background-color: #F8FAFC; padding: 22px 30px; border-top: 1px solid #E2E8F0;">
                <p style="margin: 0; font-size: 13px; line-height: 1.6; color: #64748B;">
                    &copy; {year} {BRAND_NAME}. Premium school management operations.
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def _action_button(label: str, href: str, variant: str = "primary") -> str:
    """Return an email-safe action button."""
    background = "#2563EB" if variant == "primary" else "#4F46E5"
    border = "#1D4ED8" if variant == "primary" else "#4338CA"
    return f"""
            <div style="text-align: center; margin: 30px 0;">
                <a href="{_html(href)}" style="display: inline-block; background-color: {background}; border: 1px solid {border}; color: #FFFFFF; padding: 13px 22px; border-radius: 12px; text-decoration: none; font-size: 14px; line-height: 1.4; font-weight: 700; box-shadow: 0 8px 18px rgba(37, 99, 235, 0.22);">{_html(label)}</a>
            </div>
"""


def _fallback_link(link: str) -> str:
    """Return a fallback link block for email clients that do not render buttons."""
    safe_link = _html(link)
    return f"""
            <div style="margin-top: 28px; padding: 16px; border-radius: 14px; background-color: #F8FAFC; border: 1px solid #E2E8F0;">
                <p style="margin: 0 0 8px 0; font-size: 13px; line-height: 1.6; color: #64748B;">If the button does not work, copy and paste this link into your browser:</p>
                <p style="margin: 0; font-size: 13px; line-height: 1.6; color: #334155; word-break: break-all;">{safe_link}</p>
            </div>
"""


def get_otp_email_html(code: str, purpose: str, expiration_minutes: int) -> str:
    """Return otp email html."""
    purpose_text = "account verification" if purpose == "verification" else "password reset"
    body = f"""
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 20px 0; color: #334155;">Hello,</p>
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 30px 0; color: #334155;">
                You requested a one-time code for <strong>{_html(purpose_text)}</strong>. Use the code below to complete your request.
            </p>

            <div style="text-align: center; margin: 35px 0;">
                <span style="display: inline-block; font-size: 36px; line-height: 1; font-weight: 800; letter-spacing: 8px; color: #1E3A8A; background-color: #EFF6FF; padding: 22px 38px; border-radius: 14px; border: 1px solid #BFDBFE;">
                    {_html(code)}
                </span>
            </div>

            <p style="font-size: 15px; line-height: 1.6; margin: 30px 0 0 0; color: #64748B; background-color: #FFFBEB; border: 1px solid #FDE68A; border-radius: 14px; padding: 14px 16px;">
                This code will expire in <strong>{_html(expiration_minutes)} minutes</strong>. If you did not request this, you can safely ignore and delete this email.
            </p>
"""
    return _email_shell("Check your email", "Secure access", body)


def get_teacher_onboarding_email_html(
    teacher_name: str,
    school_name: str,
    setup_link: str,
) -> str:
    """Return teacher onboarding email html."""
    safe_school_name = _html(school_name)
    body = f"""
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 20px 0; color: #334155;">Hello {_html(teacher_name)},</p>
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 30px 0; color: #334155;">
                Your teacher account has been created for <strong>{safe_school_name}</strong>. Complete your profile to start using the school workspace.
            </p>
            {_action_button("Set up your account", setup_link)}
            {_fallback_link(setup_link)}
"""
    return _email_shell(f"Welcome to {school_name}", "Teacher onboarding", body)


def get_teacher_invitation_email_html(
    school_name: str,
    invite_link: str,
) -> str:
    """Return the canonical teacher invitation email HTML."""
    safe_school_name = _html(school_name or "your school")
    body = f"""
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 18px 0; color: #334155;">Hello,</p>
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 24px 0; color: #334155;">
                You have been invited to join <strong>{safe_school_name}</strong> as a teacher on Weave.
            </p>

            <div style="margin: 0 0 28px 0; padding: 18px; border-radius: 14px; background-color: #F8FAFC; border: 1px solid #E2E8F0;">
                <p style="margin: 0 0 8px 0; font-size: 14px; line-height: 1.6; font-weight: 700; color: #0F172A;">What happens next</p>
                <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #475569;">
                    Review the invitation, create or sign in to your teacher account, then complete your staff profile for the school workspace.
                </p>
            </div>

            {_action_button("Review invitation", invite_link)}
            {_fallback_link(invite_link)}
            <p style="font-size: 14px; line-height: 1.6; margin: 24px 0 0 0; color: #64748B;">
                This invitation is personal to your email address. If you were not expecting it, you can ignore this message.
            </p>
"""
    return _email_shell(f"Join {school_name} on Weave", "Teacher invitation", body)


def get_parent_invitation_email_html(
    school_name: str,
    student_name: str,
    invite_link: str,
    admission_number: str | None = None,
) -> str:
    """Return the canonical parent invitation email HTML."""
    safe_school_name = _html(school_name or "your school")
    safe_student_name = _html(student_name or "a student")
    admission_number_row = (
        f"""
                <p style="margin: 10px 0 0 0; font-size: 14px; line-height: 1.6; color: #475569;">
                    Admission number: <strong style="color: #0F172A;">{_html(admission_number)}</strong>
                </p>
"""
        if admission_number
        else ""
    )
    body = f"""
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 18px 0; color: #334155;">Hello,</p>
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 24px 0; color: #334155;">
                <strong>{safe_school_name}</strong> invited you to connect with <strong>{safe_student_name}</strong> on Weave.
            </p>

            <div style="margin: 0 0 28px 0; padding: 18px; border-radius: 14px; background-color: #F8FAFC; border: 1px solid #E2E8F0;">
                <p style="margin: 0 0 8px 0; font-size: 14px; line-height: 1.6; font-weight: 700; color: #0F172A;">Student details</p>
                <p style="margin: 0; font-size: 14px; line-height: 1.6; color: #475569;">
                    Student: <strong style="color: #0F172A;">{safe_student_name}</strong>
                </p>
                {admission_number_row}
            </div>

            <div style="margin: 0 0 28px 0; padding: 18px; border-radius: 14px; background-color: #F8FAFC; border: 1px solid #E2E8F0;">
                <p style="margin: 0 0 8px 0; font-size: 14px; line-height: 1.6; font-weight: 700; color: #0F172A;">Before access is granted</p>
                <p style="margin: 0; font-size: 14px; line-height: 1.7; color: #475569;">
                    Review the prefilled student details. The student or school administrator must approve the link request before records become available.
                </p>
            </div>

            {_action_button("Review invitation", invite_link)}
            {_fallback_link(invite_link)}
            <p style="font-size: 14px; line-height: 1.6; margin: 24px 0 0 0; color: #64748B;">
                This link is for the invited parent or guardian only. If this message was sent to you by mistake, no action is needed.
            </p>
"""
    return _email_shell(f"Connect with {student_name}", "Parent invitation", body)


def get_superadmin_invite_email_html(
    user_name: str,
    school_name: str,
    setup_link: str,
) -> str:
    """Return superadmin invite email html."""
    safe_school_name = _html(school_name)
    body = f"""
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 20px 0; color: #334155;">Hello {_html(user_name)},</p>
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 30px 0; color: #334155;">
                You were invited to administer <strong>{safe_school_name}</strong>. Confirm your email address and set your password to continue.
            </p>
            {_action_button("Set up your account", setup_link)}
            {_fallback_link(setup_link)}
"""
    return _email_shell(f"Welcome to {school_name}", "Superadmin invite", body)


def get_tenant_invite_email_html(school_name: str, invite_link: str) -> str:
    """Return tenant invite email html."""
    safe_school_name = _html(school_name)
    body = f"""
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 20px 0; color: #334155;">Hello,</p>
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 30px 0; color: #334155;">
                <strong>{safe_school_name}</strong> has been registered. Complete your administrator profile to activate the school workspace.
            </p>
            {_action_button("Complete your setup", invite_link, variant="accent")}
            {_fallback_link(invite_link)}
"""
    return _email_shell(school_name, "Workspace activation", body)


def get_security_alert_email_html(title: str, rows: dict[str, object]) -> str:
    """Return security alert email html."""
    row_markup = "".join(
        f"<tr><td style='padding:12px 16px;color:#64748B;font-weight:600;border-bottom:1px solid #E2E8F0'>{_html(key)}</td>"
        f"<td style='padding:12px 16px;color:#0F172A;border-bottom:1px solid #E2E8F0'>{_html(value)}</td></tr>"
        for key, value in rows.items()
        if value is not None and value != ""
    )
    body = f"""
            <p style="font-size: 16px; line-height: 1.6; margin: 0 0 24px 0; color: #334155;">
                A high-signal Weave security event was detected. Please review the details below.
            </p>
            <table style="width:100%;border-collapse:collapse;border:1px solid #E2E8F0;border-radius:12px;overflow:hidden;background-color:#F8FAFC">
                <tbody>
                    {row_markup}
                </tbody>
            </table>
            <p style="font-size: 15px; line-height: 1.6; margin: 24px 0 0 0; color: #64748B;">
                If immediate action is required, log into the Superadmin dashboard to manage platform controls.
            </p>
"""
    return _email_shell(title, "Security Alert", body)
