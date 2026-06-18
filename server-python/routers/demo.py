import logging
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from database import get_db_connection

logger = logging.getLogger(__name__)
router = APIRouter(tags=["demo"])

class DemoRequest(BaseModel):
    name: str
    email: str
    company: str = ""
    message: str = ""

@router.post("/api/demo-request")
async def submit_demo_request(req: DemoRequest):
    """Store demo request in DB and send email notification."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS demo_requests (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                company TEXT DEFAULT '',
                message TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Insert the request
        cur.execute(
            """
            INSERT INTO demo_requests (name, email, company, message)
            VALUES (%s, %s, %s, %s)
            RETURNING id, created_at
            """,
            (req.name, req.email, req.company, req.message)
        )
        row = cur.fetchone()
        conn.commit()

        # Send email notification
        try:
            _send_demo_email(req, row[0], row[1])
        except Exception as email_err:
            logger.warning(f"Demo email notification failed (request still saved): {email_err}")

        return {"success": True, "message": "Demo request submitted successfully!", "id": row[0]}

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Demo request failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if conn:
            conn.close()


def _send_demo_email(req: DemoRequest, request_id: int, created_at):
    """Send email notification about new demo request."""
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    notify_email = "techmate.ed@gmail.com"

    if not smtp_user or not smtp_pass:
        logger.warning("SMTP not configured, skipping demo email notification")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚀 New Demo Request from {req.name} — BlinkBot"
    msg["From"] = f"BlinkBot <{smtp_user}>"
    msg["To"] = notify_email

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 0 auto; padding: 32px; background: #f9fafb; border-radius: 16px;">
        <div style="background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 24px 32px; border-radius: 12px; margin-bottom: 24px;">
            <h1 style="color: white; margin: 0; font-size: 22px;">🚀 New Demo Request</h1>
            <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0;">Someone wants to see BlinkBot in action!</p>
        </div>
        
        <div style="background: white; padding: 24px; border-radius: 12px; border: 1px solid #e5e7eb;">
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; font-weight: 600; color: #374151; width: 120px;">Name</td>
                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #6b7280;">{req.name}</td>
                </tr>
                <tr>
                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; font-weight: 600; color: #374151;">Email</td>
                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #6b7280;"><a href="mailto:{req.email}" style="color: #6366f1;">{req.email}</a></td>
                </tr>
                <tr>
                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; font-weight: 600; color: #374151;">Company</td>
                    <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; color: #6b7280;">{req.company or 'Not specified'}</td>
                </tr>
                <tr>
                    <td style="padding: 12px 0; font-weight: 600; color: #374151; vertical-align: top;">Message</td>
                    <td style="padding: 12px 0; color: #6b7280;">{req.message or 'No message provided'}</td>
                </tr>
            </table>
        </div>
        
        <p style="text-align: center; color: #9ca3af; font-size: 12px; margin-top: 24px;">
            Request #{request_id} • {created_at.strftime('%B %d, %Y at %I:%M %p') if created_at else 'Just now'}
        </p>
    </div>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, notify_email, msg.as_string())

    logger.info(f"Demo request email sent to {notify_email}")
