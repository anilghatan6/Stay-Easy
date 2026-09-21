"""
Usage: python -m app.modules.superadmin.create_superadmin <email> <password> <full_name>

Creates a superadmin user in the database.
"""
import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Import all models so SQLAlchemy can resolve relationships
from app.modules.auth.models import *
from app.modules.pms.models import *
from app.modules.booking.models import *
from app.modules.staff_mgmt.models import *
from app.modules.house_keeping.models import *
from app.modules.notifications.models import *
from app.modules.superadmin.models import *

from app.config.database_config import AsyncSessionLocal
from app.modules.auth.services.auth_services import AuthService
from app.modules.auth.models.users_model import User
from sqlalchemy import select
import uuid


async def create_superadmin(email: str, password: str, full_name: str):
    auth_service = AuthService()
    hashed_password = auth_service.get_password_hash(password)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()
        if existing:
            print(f"User with email {email} already exists (role: {existing.role})")
            print("Updating role to superadmin...")
            existing.role = "superadmin"
            existing.is_active = True
            await db.commit()
            print(f"User {email} is now a superadmin.")
            return

        user = User(
            id=uuid.uuid4(),
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role="superadmin",
            is_active=True,
            must_change_password=False,
        )
        db.add(user)
        await db.commit()
        print(f"SuperAdmin created successfully!")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")
        print(f"  Name:     {full_name}")
        print(f"  Role:     superadmin")
        print(f"  User ID:  {user.id}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python -m app.modules.superadmin.create_superadmin <email> <password> <full_name>")
        print('Example: python -m app.modules.superadmin.create_superadmin adminanil@123 aniladmin@123 "Anil Admin"')
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    full_name = sys.argv[3]

    asyncio.run(create_superadmin(email, password, full_name))
