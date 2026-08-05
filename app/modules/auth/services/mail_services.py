import httpx
from app.utils.logging import LoggerFactory
from app.utils.exceptions import ServiceException
from fastapi.templating import Jinja2Templates

from dotenv import load_dotenv
import os

load_dotenv()

logger = LoggerFactory.get_logger(__name__)
templates = Jinja2Templates(directory="app/templates")

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

async def send_transactional_email(to_email: str, subject: str, html_content: str) -> None:
    """
    Non-blocking worker task to dispatch emails instantly via HTTP/2.
    """
    logger.info("[MailService] Sending email")
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        }
    except Exception as e:
        logger.error(f"Error creating email payload: {str(e)}")
        raise ServiceException(str(e))
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"Failed to dispatch email to {to_email}: {response.text}")
            else:
                logger.info(f"Email successfully dispatched to {to_email}")
        except Exception as e:
            logger.critical(f"Email gateway unreachable. Exception: {str(e)}")


async def send_verification_email(to_email: str, verification_code: str) -> None:
    """
    Sends a verification email to the specified email address.
    """
    logger.info("[MailService] Sending verification email")

    try:
        plain_content = f"""
        <html>
        <body>
            <h1>Verify Your Email Address</h1>
            <p>Thank you for registering with StayEasy. Please use the code below to verify your email address:</p>
            <p><strong>{verification_code}</strong></p>
            <p>This code will expire in 10 minutes.</p>
            <p>If you did not register with StayEasy, please ignore this email.</p>
        </body>
        </html>
        """

        template = templates.env.get_template("verify_email.html")
        html_content = template.render(verification_code=verification_code)

        await send_transactional_email(to_email, "StayEasy - Verify Your Email Address", html_content or plain_content)
    except Exception as e:
        logger.error(f"Error sending verification email: {str(e)}")
        raise ServiceException(str(e))


async def send_password_reset_email(to_email: str, username: str, token: str) -> None:
    reset_url = f"{os.getenv('FRONTEND_URL')}/reset-password?token={token}"

    template = templates.env.get_template("password_reset.html")
    html_content = template.render(reset_url=reset_url, username=username)

    plain_text = f"""Hi {username},

    You requested to reset your password. Click the link below to set a new password:

    {reset_url}

    This link will expire in {os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES")} minutes.

    If you didn't request this, you can safely ignore this email.

    Best regards,
    StayEasy Team
    """
    try:
        await send_transactional_email(to_email, "StayEasy - Reset Your Password", html_content or plain_text)
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        raise ServiceException(str(e))