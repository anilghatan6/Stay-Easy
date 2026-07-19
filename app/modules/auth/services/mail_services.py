import httpx
from app.utils.logging import LoggerFactory
from app.utils.exceptions import ServiceException
from dotenv import load_dotenv
import os

load_dotenv()

logger = LoggerFactory.get_logger(__name__)

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
    
    # Use httpx.AsyncClient to prevent blocking the async event loop
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
    is_dev = os.getenv("ENVIRONMENT") == "development"
    
    if is_dev:
        # Bypasses Resend entirely and outputs the credentials directly to your terminal
        logger.info(f"\n"
                    f"========================================================\n"
                    f"[MailService][DEV MODE] Intercepted outbound email\n"
                    f"TO: {to_email}\n"
                    f"SUBJECT: StayEasy - Verify Your Email Address\n"
                    f"DEVELOPMENT OTP CODE: {verification_code}\n"
                    f"========================================================")
        return
    try:
        html_content = f"""
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
        await send_transactional_email(to_email, "StayEasy - Verify Your Email Address", html_content)
    except Exception as e:
        logger.error(f"Error sending verification email: {str(e)}")
        raise ServiceException(str(e))

        