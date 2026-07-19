"""
Email Notification Service

Sends transactional email notifications (e.g. timetable activation).
SMTP credentials are read from environment variables:

    SMTP_HOST   - SMTP server hostname (default: localhost)
    SMTP_PORT   - SMTP server port    (default: 587)
    SMTP_USER   - SMTP login username
    SMTP_PASS   - SMTP login password
    SMTP_FROM   - Sender address      (default: noreply@tablesys.com)

If SMTP_HOST is not configured, all send calls are silently skipped and
a warning is written to the application log. This ensures that missing
SMTP configuration never breaks a core workflow (e.g. timetable activation).
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """
    Thin wrapper around smtplib for sending plain-text and HTML notifications.

    All methods fail silently when SMTP is not configured; errors are
    logged at WARNING level and never propagate to callers.
    """

    # ------------------------------------------------------------------
    # Public notification methods
    # ------------------------------------------------------------------

    @staticmethod
    def send_timetable_activated(
        recipient: str,
        timetable_name: str,
        semester: str,
        year: str,
    ) -> bool:
        """
        Notify a user that a timetable has been activated.

        Args:
            recipient:       Recipient email address.
            timetable_name:  Human-readable name of the timetable.
            semester:        Semester label (e.g. "Semester 1").
            year:            Academic year string (e.g. "2026").

        Returns:
            True if the email was sent; False if skipped or failed.
        """
        subject = f"Timetable Activated: {timetable_name}"
        body_text = (
            f"Dear User,\n\n"
            f"The timetable '{timetable_name}' for {semester} {year} "
            f"has been activated and is now available for viewing.\n\n"
            f"Log in to TABLESYS to view or export the schedule.\n\n"
            f"TABLESYS Timetable Management System\n"
            f"Automated Scheduling Platform"
        )
        body_html = f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; padding: 40px 20px; margin: 0;">
  <table style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb; border-spacing: 0; width: 100%;">
    <tr>
      <td style="padding: 24px; text-align: center; border-bottom: 1px solid #e5e7eb;">
        <span style="color: #111827; font-size: 20px; font-weight: 800; letter-spacing: 1px;">TABLESYS</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 32px 40px;">
        <h2 style="color: #111827; font-size: 24px; font-weight: 700; margin-top: 0; margin-bottom: 16px;">Timetable Activated</h2>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 24px 0;">
          The timetable <strong>{timetable_name}</strong> for <strong>{semester} {year}</strong> has been successfully activated.
        </p>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 32px 0;">
          You can now log in to your dashboard to view, manage, or export the finalized schedule.
        </p>
      </td>
    </tr>
    <tr>
      <td style="background-color: #f9fafb; padding: 24px; text-align: center; border-top: 1px solid #e5e7eb;">
        <p style="color: #6b7280; font-size: 12px; margin: 0;">
          &copy; {year} TABLESYS Enterprise Scheduling
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""

        return EmailService._send(recipient, subject, body_text, body_html)

    @staticmethod
    def send_generation_complete(
        recipient: str,
        timetable_name: str,
    ) -> bool:
        """
        Notify a coordinator that timetable generation has finished.

        Args:
            recipient:       Recipient email address.
            timetable_name:  Name of the newly generated timetable.

        Returns:
            True if sent; False if skipped or failed.
        """
        subject = f"Timetable Generation Complete: {timetable_name}"
        body_text = (
            f"Timetable '{timetable_name}' has been generated successfully.\n"
            )
        return EmailService._send(recipient, subject, body_text)

    @staticmethod
    def send_registration_verification(
        recipient: str,
        organization_name: str,
        verification_link: str,
    ) -> bool:
        """
        Notify a new tenant admin to verify their email address.

        Args:
            recipient:         Recipient email address.
            organization_name: Name of the university/organization.
            verification_link: Full URL for verification.

        Returns:
            True if sent; False if skipped or failed.
        """
        subject = f"Verify your TABLESYS account for {organization_name}"
        body_text = (
            f"Welcome to TABLESYS!\n\n"
            f"Please verify your email address to complete the registration for {organization_name}.\n"
            f"Click or copy the following link:\n{verification_link}\n\n"
            f"If you did not request this, please ignore this email."
        )
        body_html = f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; padding: 40px 20px; margin: 0;">
  <table style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb; border-spacing: 0; width: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);">
    <tr>
      <td style="padding: 32px 40px; text-align: center; border-bottom: 1px solid #e5e7eb;">
        <span style="color: #111827; font-size: 22px; font-weight: 800; letter-spacing: 1px;">TABLESYS</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 40px 40px;">
        <h2 style="color: #111827; font-size: 24px; font-weight: 700; margin-top: 0; margin-bottom: 16px; text-align: center;">Verify your email</h2>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 32px 0; text-align: center;">
          Welcome to TABLESYS! Please verify your email to securely provision the workspace for <strong>{organization_name}</strong>.
        </p>
        <table align="center" style="margin: 0 auto;">
          <tr>
            <td align="center">
              <a href="{verification_link}" style="display: inline-block; padding: 14px 28px; background-color: #111827; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Verify Email Address</a>
            </td>
          </tr>
        </table>
        <p style="color: #9ca3af; font-size: 13px; line-height: 20px; margin: 32px 0 0 0; text-align: center; word-break: break-all;">
          Or copy this link:<br>
          <a href="{verification_link}" style="color: #6366f1;">{verification_link}</a>
        </p>
      </td>
    </tr>
    <tr>
      <td style="background-color: #f9fafb; padding: 24px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
        <p style="color: #6b7280; font-size: 12px; margin: 0;">
          If you did not request this verification, you can safely ignore this email.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""
        return EmailService._send(recipient, subject, body_text, body_html)

    # ------------------------------------------------------------------
    # Internal send helper
    # ------------------------------------------------------------------

    @staticmethod
    def _send(
        recipient: str,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
    ) -> bool:
        """
        Construct and dispatch a MIME email via SMTP.

        Returns False without raising if SMTP is not configured or fails.
        """
        # Guard: respect the EMAIL_ENABLED flag
        email_enabled: bool = getattr(settings, "EMAIL_ENABLED", False)
        if not email_enabled:
            logger.warning(
                "EMAIL_ENABLED=false. Email to '%s' was skipped (subject: %s).",
                recipient,
                subject,
            )
            return False

        smtp_host: str = getattr(settings, "SMTP_HOST", "")
        smtp_port: int = int(getattr(settings, "SMTP_PORT", 587))
        smtp_user: str = getattr(settings, "SMTP_USER", "")
        # FIX: was incorrectly reading SMTP_PASS — the config field is SMTP_PASSWORD
        smtp_pass: str = getattr(settings, "SMTP_PASSWORD", "")
        # FIX: was reading non-existent SMTP_FROM — use the authenticated sender
        smtp_from: str = smtp_user if smtp_user else getattr(settings, "SMTP_FROM_EMAIL", "noreply@tablesys.com")

        if not smtp_host or not smtp_user or not smtp_pass:
            logger.warning(
                "SMTP credentials incomplete. Email to '%s' was skipped (subject: %s). "
                "Ensure SMTP_HOST, SMTP_USER, and SMTP_PASSWORD are all set.",
                recipient,
                subject,
            )
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = recipient

        msg.attach(MIMEText(body_text, "plain"))
        if body_html:
            msg.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [recipient], msg.as_string())

            logger.info("Email sent to '%s' (subject: %s).", recipient, subject)
            return True

        except Exception as exc:
            logger.error(
                "Failed to send email to '%s' (subject: %s): %s",
                recipient,
                subject,
                exc,
            )
            return False

    @staticmethod
    def send_new_user_welcome_email(
        recipient: str,
        user_name: str,
        username: str,
        password: str,
        role: str,
        organization_name: str = "TABLESYS",
    ) -> bool:
        """
        Notify a new user of their account credentials.

        Args:
            recipient:         Recipient email address.
            user_name:         Full name of the new user.
            username:          The assigned login username.
            password:          The assigned temporary password.
            role:              The user's assigned role.
            organization_name: Name of the university/organization.

        Returns:
            True if sent; False if skipped or failed.
        """
        subject = f"Welcome to TABLESYS - Your Account Details for {organization_name}"
        body_text = (
            f"Welcome to TABLESYS!\n\n"
            f"Hello {user_name},\n\n"
            f"You have been added to the system for {organization_name} as a {role}.\n\n"
            f"Here are your temporary login credentials:\n"
            f"Username: {username}\n"
            f"Password: {password}\n\n"
            f"Please log in and change your password as soon as possible.\n\n"
            f"TABLESYS Timetable Management System"
        )
        body_html = f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; padding: 40px 20px; margin: 0;">
  <table style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb; border-spacing: 0; width: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <tr>
      <td style="padding: 32px 40px; text-align: center; border-bottom: 1px solid #e5e7eb;">
        <span style="color: #111827; font-size: 22px; font-weight: 800; letter-spacing: 1px;">TABLESYS</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 40px 40px;">
        <h2 style="color: #111827; font-size: 24px; font-weight: 700; margin-top: 0; margin-bottom: 16px; text-align: center;">Account Details</h2>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 24px 0;">
          Hello <strong>{user_name}</strong>,
        </p>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 24px 0;">
          You have been securely added to the system for <strong>{organization_name}</strong>. Your assigned role is <strong>{role}</strong>.
        </p>
        <div style="background-color: #f3f4f6; border-left: 4px solid #4f46e5; padding: 16px; margin-bottom: 32px;">
            <p style="margin: 0 0 8px 0; color: #111827;"><strong>Username:</strong> {username}</p>
            <p style="margin: 0; color: #111827;"><strong>Password:</strong> {password}</p>
        </div>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 32px 0;">
          Please log in and change your password as soon as possible.
        </p>
        <table align="center" style="margin: 0 auto;">
          <tr>
            <td align="center">
              <a href="{getattr(settings, 'FRONTEND_URL', 'http://localhost:3002')}/login" style="display: inline-block; padding: 14px 28px; background-color: #4f46e5; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 16px;">Log In Now</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
    <tr>
      <td style="background-color: #f9fafb; padding: 24px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
        <p style="color: #6b7280; font-size: 12px; margin: 0;">
          This is an automated message from the TABLESYS Enterprise Scheduling platform.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>"""
        return EmailService._send(recipient, subject, body_text, body_html)

    @staticmethod
    def send_lecturer_welcome_email(
        recipient: str,
        user_name: str,
        staff_number: str,
        login_url: str,
        organization_name: str = "TABLESYS",
        assigned_courses: list = None,
    ) -> bool:
        """
        Notify a new lecturer of their portal access details.
        """
        subject = f"Welcome to TABLESYS - Your Lecturer Portal Access for {organization_name}"
        
        courses_text = ""
        courses_html = ""
        if assigned_courses:
            courses_text = "\nAssigned Courses:\n" + "\n".join(f"- {c}" for c in assigned_courses) + "\n"
            courses_html_list = "".join(f"<li style='margin-bottom: 4px; color: #111827;'>{c}</li>" for c in assigned_courses)
            courses_html = f"""
        <div style="background-color: #ffffff; border: 1px solid #e5e7eb; border-radius: 6px; padding: 16px; margin-bottom: 32px;">
            <h3 style="margin-top: 0; margin-bottom: 12px; color: #374151; font-size: 16px;">Assigned Courses</h3>
            <ul style="margin: 0; padding-left: 20px;">
                {courses_html_list}
            </ul>
        </div>
"""

        body_text = (
            f"Welcome to TABLESYS!\n\n"
            f"Hello {user_name},\n\n"
            f"You have been added to the system for {organization_name} as a Lecturer.\n\n"
            f"Here are your access details:\n"
            f"Staff Number: {staff_number}\n"
            f"Login Portal: {login_url}\n{courses_text}\n"
            f"Please log in to view your timetable.\n\n"
            f"TABLESYS Timetable Management System"
        )
        body_html = f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f9fafb; padding: 40px 20px; margin: 0;">
  <table style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e5e7eb; border-spacing: 0; width: 100%; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
    <tr>
      <td style="padding: 32px 40px; text-align: center; border-bottom: 1px solid #e5e7eb;">
        <span style="color: #111827; font-size: 22px; font-weight: 800; letter-spacing: 1px;">TABLESYS</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 40px 40px;">
        <h2 style="color: #111827; font-size: 24px; font-weight: 700; margin-top: 0; margin-bottom: 16px; text-align: center;">Lecturer Portal Access</h2>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 24px 0;">
          Hello <strong>{user_name}</strong>,
        </p>
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 24px 0;">
          You have been added to the system for <strong>{organization_name}</strong> as a Lecturer.
        </p>
        <div style="background-color: #f3f4f6; border-left: 4px solid #4f46e5; padding: 16px; margin-bottom: 24px;">
            <p style="margin: 0 0 8px 0; color: #111827;"><strong>Staff Number:</strong> {staff_number}</p>
            <p style="margin: 0; color: #111827;"><strong>Login Portal:</strong> <a href="{login_url}">{login_url}</a></p>
        </div>
{courses_html}
        <p style="color: #4b5563; font-size: 16px; line-height: 24px; margin: 0 0 32px 0;">
          Please log in to view your timetable.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""
        try:
            return EmailService._send(
                recipient=recipient,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error(f"Unexpected error formatting lecturer welcome email for {recipient}: {exc}")
            return False
