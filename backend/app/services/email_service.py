"""
Email Service

Handles email sending via SMTP with template support.
Supports async sending for non-blocking operations.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import logging
from ..config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""
    
    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.SMTP_FROM_EMAIL
        self.from_name = settings.SMTP_FROM_NAME
        self.enabled = settings.EMAIL_ENABLED
    
    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None
    ) -> bool:
        """
        Send an email to one or more recipients.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            body_html: HTML version of email body
            body_text: Plain text version (optional, falls back to HTML)
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.info(f"Email disabled. Would send to {to_emails}: {subject}")
            return False
        
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not configured. Cannot send email.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            
            # Attach plain text and HTML versions
            if body_text:
                part1 = MIMEText(body_text, 'plain')
                msg.attach(part1)
            
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_emails}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_emails}: {str(e)}")
            return False
    
    def send_timetable_generated_notification(
        self,
        to_email: str,
        user_name: str,
        timetable_name: str,
        timetable_id: int
    ) -> bool:
        """
        Send notification when timetable generation is complete.
        
        Args:
            to_email: Recipient email
            user_name: Name of the user
            timetable_name: Name of the generated timetable
            timetable_id: ID of the timetable
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"Timetable Generated: {timetable_name}"
        
        body_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #1976d2; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f5f5f5; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #1976d2; 
                          color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>TABLESYS</h1>
                </div>
                <div class="content">
                    <h2>Timetable Generation Complete</h2>
                    <p>Hello {user_name},</p>
                    <p>The timetable <strong>{timetable_name}</strong> has been successfully generated and is now ready for review.</p>
                    <p>You can view and export the timetable from the system.</p>
                    <a href="{settings.FRONTEND_URL or 'http://localhost:3002'}/timetables" class="button">View Timetable</a>
                </div>
                <div class="footer">
                    <p>This is an automated message from the TABLESYS Timetable Management System.</p>
                    <p>&copy; 2026 TABLESYS</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        TABLESYS Timetable Management System
        
        Timetable Generation Complete
        
        Hello {user_name},
        
        The timetable {timetable_name} has been successfully generated and is now ready for review.
        
        You can view and export the timetable from the system at:
        {settings.FRONTEND_URL or 'http://localhost:3002'}/timetables
        
        ---
        This is an automated message from the TABLESYS Timetable Management System.
        © 2026 TABLESYS
        """
        
        return self.send_email([to_email], subject, body_html, body_text)
    
    def send_version_restored_notification(
        self,
        to_email: str,
        user_name: str,
        timetable_name: str,
        version_number: int
    ) -> bool:
        """
        Send notification when a timetable version is restored.
        
        Args:
            to_email: Recipient email
            user_name: Name of the user
            timetable_name: Name of the timetable
            version_number: Version number that was restored
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"Timetable Restored: {timetable_name} (Version {version_number})"
        
        body_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #ff9800; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f5f5f5; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #ff9800; 
                          color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>TABLESYS</h1>
                </div>
                <div class="content">
                    <h2>Timetable Version Restored</h2>
                    <p>Hello {user_name},</p>
                    <p>The timetable <strong>{timetable_name}</strong> has been restored to version {version_number}.</p>
                    <p>A backup of the previous state was automatically created before restoration.</p>
                    <a href="{settings.FRONTEND_URL or 'http://localhost:3002'}/timetables" class="button">View Timetable</a>
                </div>
                <div class="footer">
                    <p>This is an automated message from the TABLESYS Timetable Management System.</p>
                    <p>&copy; 2026 TABLESYS</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        TABLESYS Timetable Management System
        
        Timetable Version Restored
        
        Hello {user_name},
        
        The timetable {timetable_name} has been restored to version {version_number}.
        
        A backup of the previous state was automatically created before restoration.
        
        View the timetable at:
        {settings.FRONTEND_URL or 'http://localhost:3002'}/timetables
        
        ---
        This is an automated message from the TABLESYS Timetable Management System.
        © 2026 TABLESYS
        """
        
        return self.send_email([to_email], subject, body_html, body_text)
    
    def send_weekly_digest_to_hod(
        self,
        to_email: str,
        hod_name: str,
        department_name: str,
        stats: dict
    ) -> bool:
        """
        Send weekly digest email to HOD with department statistics.
        
        Args:
            to_email: HOD email
            hod_name: Name of the HOD
            department_name: Name of the department
            stats: Dictionary containing statistics
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"Weekly Timetable Digest - {department_name}"
        
        body_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4caf50; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f5f5f5; }}
                .stat-box {{ background-color: white; padding: 15px; margin: 10px 0; border-left: 4px solid #4caf50; }}
                .stat-label {{ font-weight: bold; color: #666; }}
                .stat-value {{ font-size: 24px; color: #4caf50; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Weekly Timetable Digest</h1>
                    <p>{department_name}</p>
                </div>
                <div class="content">
                    <p>Hello {hod_name},</p>
                    <p>Here's your weekly summary of timetable activities for {department_name}:</p>
                    
                    <div class="stat-box">
                        <div class="stat-label">Total Courses</div>
                        <div class="stat-value">{stats.get('total_courses', 0)}</div>
                    </div>
                    
                    <div class="stat-box">
                        <div class="stat-label">Active Lecturers</div>
                        <div class="stat-value">{stats.get('total_lecturers', 0)}</div>
                    </div>
                    
                    <div class="stat-box">
                        <div class="stat-label">Student Groups</div>
                        <div class="stat-value">{stats.get('total_groups', 0)}</div>
                    </div>
                    
                    <div class="stat-box">
                        <div class="stat-label">Room Utilization</div>
                        <div class="stat-value">{stats.get('room_utilization', 0):.1f}%</div>
                    </div>
                    
                    <p style="margin-top: 20px;">
                        <strong>Validation Issues:</strong><br>
                        Errors: {stats.get('validation_errors', 0)}<br>
                        Warnings: {stats.get('validation_warnings', 0)}
                    </p>
                </div>
                <div class="footer">
                    <p>This is an automated weekly digest from the TABLESYS Timetable Management System.</p>
                    <p>&copy; 2026 TABLESYS</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        TABLESYS Timetable Management System - Weekly Digest
        {department_name}
        
        Hello {hod_name},
        
        Here's your weekly summary of timetable activities:
        
        Total Courses: {stats.get('total_courses', 0)}
        Active Lecturers: {stats.get('total_lecturers', 0)}
        Student Groups: {stats.get('total_groups', 0)}
        Room Utilization: {stats.get('room_utilization', 0):.1f}%
        
        Validation Issues:
        - Errors: {stats.get('validation_errors', 0)}
        - Warnings: {stats.get('validation_warnings', 0)}
        
        ---
        This is an automated weekly digest from the TABLESYS Timetable Management System.
        © 2026 TABLESYS
        """
        
        return self.send_email([to_email], subject, body_html, body_text)

    def send_new_user_welcome_email(
        self,
        to_email: str,
        user_name: str,
        username: str,
        password: str,
        role: str
    ) -> bool:
        """
        Send a welcome email to a new user containing their credentials.
        
        Args:
            to_email: Recipient email
            user_name: Name of the user
            username: Username for login
            password: Password for login
            role: The role assigned to the user
            
        Returns:
            bool: True if sent successfully
        """
        subject = "Welcome to TABLESYS - Your Account Details"
        
        body_html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2e7d32; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 20px; background-color: #f5f5f5; }}
                .credentials {{ background-color: white; padding: 15px; margin: 20px 0; border: 1px solid #ddd; border-left: 4px solid #2e7d32; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #2e7d32; 
                          color: white; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to TABLESYS</h1>
                </div>
                <div class="content">
                    <h2>Your Account is Ready</h2>
                    <p>Hello {user_name},</p>
                    <p>You have been added to the TABLESYS Timetable Management System as a <strong>{role}</strong>.</p>
                    <p>Here are your temporary login credentials. Please log in and change your password as soon as possible.</p>
                    
                    <div class="credentials">
                        <p><strong>Username:</strong> {username}</p>
                        <p><strong>Password:</strong> {password}</p>
                    </div>
                    
                    <a href="{settings.FRONTEND_URL or 'http://localhost:3002'}/login" class="button">Log In Now</a>
                </div>
                <div class="footer">
                    <p>This is an automated message from the TABLESYS Timetable Management System.</p>
                    <p>&copy; 2026 TABLESYS</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        body_text = f"""
        TABLESYS Timetable Management System
        
        Welcome to TABLESYS
        
        Hello {user_name},
        
        You have been added to the system as a {role}.
        
        Here are your login credentials:
        Username: {username}
        Password: {password}
        
        Please log in and change your password as soon as possible at:
        {settings.FRONTEND_URL or 'http://localhost:3002'}/login
        
        ---
        This is an automated message from the TABLESYS Timetable Management System.
        © 2026 TABLESYS
        """
        
        return self.send_email([to_email], subject, body_html, body_text)
