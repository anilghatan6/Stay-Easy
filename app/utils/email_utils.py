# import os 
# from email.message import EmailMessage

# import aiosmtplib
# from fastapi.templating import Jinja2Templates
# from app.utils.exceptions import EmailDeliveryError
# from app.utils.logging import LoggerFactory
# from dotenv import load_dotenv

# templates = Jinja2Templates(directory="app/templates")
# load_dotenv()

# logger = LoggerFactory.get_logger(__name__)

# async def send_email(
#     to_email: str,
#     subject: str,
#     plain_text: str,
#     html_content: str | None = None,
# ) -> None:
#     message = EmailMessage()
#     message["From"] = os.getenv("MAIL_FROM")
#     message["To"] = to_email
#     message["Subject"] = subject

#     message.set_content(plain_text)

#     if html_content:
#         message.add_alternative(html_content, subtype="html")
    
#     try:
#         await aiosmtplib.send(
#             message,
#             hostname=os.getenv("MAIL_SERVER"),
#             port=os.getenv("MAIL_PORT"),
#             username=os.getenv("MAIL_USERNAME"),
#             password=os.getenv("MAIL_PASSWORD"),
#             start_tls=os.getenv("MAIL_USE_TLS"),
#         )
#     except Exception as e:
#         logger.error(f"Failed to send email: {e}")
#         raise EmailDeliveryError(user_message= "Failed to send email", internal_detail=str(e))


# async def send_password_reset_email(to_email: str, username: str, token: str) -> None:
#     reset_url = f"{os.getenv('FRONTEND_URL')}/reset-password?token={token}"

#     template = templates.env.get_template("password_reset.html")
#     html_content = template.render(reset_url=reset_url, username=username)

#     plain_text = f"""Hi {username},

# You requested to reset your password. Click the link below to set a new password:

# {reset_url}

# This link will expire in {os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES")} minutes.

# If you didn't request this, you can safely ignore this email.

# Best regards,
# StayEasy Team
# """
#     try:
#         await send_email(
#             to_email=to_email,
#             subject="Reset Your Password - StayEasy",
#             plain_text=plain_text,
#             html_content=html_content,
#         )
#     except EmailDeliveryError:
#         raise  # re-raise to let caller handle