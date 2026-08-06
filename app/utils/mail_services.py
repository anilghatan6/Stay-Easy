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


async def send_transactional_email(
    to_email: str, subject: str, html_content: str
) -> None:
    """
    Non-blocking worker task to dispatch emails instantly via HTTP/2.
    """
    logger.info("[MailService] Sending email")
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": SENDER_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_content,
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

        await send_transactional_email(
            to_email,
            "StayEasy - Verify Your Email Address",
            html_content or plain_content,
        )
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
        await send_transactional_email(
            to_email, "StayEasy - Reset Your Password", html_content or plain_text
        )
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        raise ServiceException(str(e))


async def send_booking_confirmed_guest_email(
    to_email: str, guest_name: str, booking, property_obj, room_units: list
) -> None:
    template = templates.env.get_template("booking_confirmed_guest.html")
    map_url = f"https://www.google.com/maps?q={property_obj.latitude},{property_obj.longitude}"

    html_content = template.render(
        guest_name=guest_name,
        ref_number=booking.ref_number,
        property_name=property_obj.name,
        property_email=property_obj.email,
        property_phone_number=property_obj.phone_number,
        property_address=property_obj.address,
        property_zip_code=property_obj.zip_code,
        property_city=property_obj.city,
        property_state=property_obj.state,
        property_country=property_obj.country,
        checkin_date=booking.checkin_date.strftime("%B %d, %Y"),
        checkout_date=booking.checkout_date.strftime("%B %d, %Y"),
        adults=booking.number_of_adults,
        children=booking.number_of_children,
        rooms=[
            {
                "room_name": r.room_name,
                "room_type": r.room_type.room_type_name,
                "base_rate": f"{r.base_rate:.2f}",
                "currency": property_obj.currency,
            }
            for r in room_units
        ],
        currency=property_obj.currency,
        subtotal=f"{booking.subtotal:.2f}",
        special_offer_discount=f"{booking.special_offer_discount:.2f}",
        coupon_code=booking.coupon_code,
        coupon_discount=f"{booking.coupon_discount:.2f}",
        total_amount=f"{booking.total_amount:.2f}",
        map_url=map_url,
    )

    plain_text = f"Your booking {booking.ref_number} at {property_obj.name} is confirmed. Total: {property_obj.currency} {booking.total_amount:.2f}"

    await send_transactional_email(
        to_email=to_email,
        subject=f"Booking Confirmed - {booking.ref_number} | StayEasy",
        html_content=html_content or plain_text,
    )


async def send_booking_confirmed_owner_email(
    to_email: str,
    owner_name: str,
    guest_name: str,
    guest_email: str,
    guest_phone: str,
    guest_nationality: str,
    booking,
    property_obj,
    room_units: list,
) -> None:
    template = templates.env.get_template("booking_confirmed_owner.html")

    html_content = template.render(
        owner_name=owner_name,
        guest_name=guest_name,
        guest_email=guest_email,
        guest_phone=guest_phone,
        guest_nationality=guest_nationality,
        ref_number=booking.ref_number,
        property_name=property_obj.name,
        checkin_date=booking.checkin_date.strftime("%B %d, %Y"),
        checkout_date=booking.checkout_date.strftime("%B %d, %Y"),
        rooms=[{"room_name": r.room_name} for r in room_units],
        currency=property_obj.currency,
        total_amount=f"{booking.total_amount:.2f}",
    )

    await send_transactional_email(
        to_email=to_email,
        subject=f"New Reservation - {booking.ref_number} | {property_obj.name}",
        html_content=html_content,
    )

async def send_staff_welcome_email(
    to_email: str,
    full_name: str,
    job_role: str,
    temp_password: str,
    property_name: str,
    login_url: str = os.getenv("FRONTEND_LOGIN_URL"),
) -> None:
    template = templates.env.get_template("staff_welcome.html")

    html_content = template.render(
        full_name=full_name,
        email=to_email,
        job_role=job_role,
        temp_password=temp_password,
        property_name=property_name,
        login_url=login_url,
    )

    plain_text = (
        f"Welcome to StayEasy, {full_name}!\n\n"
        f"Your staff account at {property_name} has been created.\n"
        f"Role: {job_role}\n"
        f"Email: {to_email}\n"
        f"Temporary Password: {temp_password}\n\n"
        f"Please log in and update your password."
    )

    await send_transactional_email(
        to_email=to_email,
        subject=f"Welcome to the Team - Account Credentials | {property_name}",
        html_content=html_content or plain_text,
    )