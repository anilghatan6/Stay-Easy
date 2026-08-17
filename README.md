# ServerIQ API

A multi-tenant **property-management & booking backend** built with **FastAPI**.

It powers two broad use cases:

- **Property Management System (PMS)** — admins/tenants manage properties, rooms (room types, bed types), special offers, discount codes, staff, and image uploads.
- **Guest-facing booking flow** — guests register, search properties, create reservations, apply discounts/coupons, and pay through multiple payment gateways.

> **Note:** `document.md` contains an exhaustive project reference (endpoints, data model, DFD, migration history). This README is a condensed quick-start guide.

## Features

- **Multi-tenancy** — users own tenants; tenants own properties, staff, offers, discount codes, and loyalty profiles
- **Authentication** — guest/user registration with email OTP (Resend), login, JWT access/refresh tokens, Argon2 password hashing
- **Property management** — properties, rooms, room/bed types, amenities, localization, brand visuals, activation toggling
- **Guest booking flow** — destination search with availability & pricing, nearby-property search, reservations, coupon/discount application
- **Payments** — Stripe, Razorpay, Khalti (with NRB forex conversion), and a Dummy gateway selected via a strategy/factory pattern
- **Reliability** — Redis-backed idempotency keys, Redis soft-locks to prevent double-booking, background stale-booking expiry loop
- **Caching** — Redis caching for popular destination searches and forex rates (fail-open)
- **Image handling** — bulk uploads with mime checks, webp conversion, local disk or Cloudinary storage (strategy pattern)

## Tech Stack

| Category | Technology |
|---|---|
| Web framework | FastAPI, Uvicorn |
| ORM | SQLAlchemy 2.0 (async), GeoAlchemy2 |
| Database | PostgreSQL (`psycopg`), SQLite + `aiosqlite` for tests |
| Migrations | Alembic |
| Cache / sessions | Redis (async) |
| Auth & security | PyJWT, pwdlib (Argon2) |
| Payments | Stripe SDK, Razorpay SDK, Khalti via `httpx`, NRB forex API |
| Email | Resend |
| Validation | Pydantic v2 |
| Testing | pytest, pytest-asyncio, fakeredis, httpx |

## Architecture

Modular monolith with a clean layered pattern:

```
Router (HTTP) → Dependency (injection) → Service (business logic) → Repository (SQL) → ORM Model
```

All API responses use a standard envelope:

```json
{
  "success": true,
  "data": { ... },
  "meta": { "total": 0, "skip": 0, "limit": 10, "has_more": false }
}
```

## Project Structure

```
stay-easy/
├── app/
│   ├── main.py                      # FastAPI app, lifespan (expiry job), router mounting
│   ├── config/
│   │   ├── database_config.py       # async engine, session factory, Base, get_db
│   │   └── redis_config.py          # Redis connection pool + get_redis_client
│   ├── middlewares/                 # CORS, correlation ID, rate limiter
│   ├── utils/                       # cache, exceptions, forex, image utils, expiry_loop, ...
│   └── modules/
│       ├── auth/                    # users, guests, login, password reset
│       ├── pms/                     # tenants, properties, rooms, images, offers, discount codes, search
│       ├── booking/                 # bookings, payment strategies (stripe/razorpay/khalti/dummy)
│       └── staff_mgmt/              # staff CRUD
├── alembic/                         # Alembic migrations
├── tests/                           # pytest suite (SQLite + fakeredis)
├── alembic.ini
├── pyproject.toml
├── pytest.ini
└── requirements.txt
```

## Quick Start

```bash
# 1. Environment
# Create a .env file (see "Configuration" below). Note: no .env.example is committed;
# copy your secrets from document.md section 9 or from existing tools/env.

# 2. Install dependencies
uv sync
# or
pip install -r requirements.txt

# 3. Run database migrations
alembic upgrade head

# 4. Start the server
uvicorn app.main:app --reload
```

- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- Root route: <http://localhost:8000/> → `{"message": "Welcome to the ServerIQ API"}`

## Configuration (`.env`)

| Group | Keys |
|---|---|
| Database / cache | `DATABASE_URL`, `REDIS_URL` |
| Auth | `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` |
| Email | `SENDER_EMAIL`, `RESEND_API_KEY` |
| Environment | `ENVIRONMENT` (`development` disables real email/OTP), `DEVELOPMENT_MASTER_OTP`, `OTP_EXPIRATION_SECONDS` |
| Image storage | `IMAGE_STORAGE_PROVIDER` (`local` \| `cloudinary`), `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `CLOUDINARY_BASE` |
| CORS | `ALLOWED_ORIGINS` |
| Bookings | `SOFT_LOCK_TTL_SECONDS` |
| Payments | `STRIPE_SECRET_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `KHALTI_SECRET_KEY`, `KHALTI_RETURN_URL`, `KHALTI_WEBSITE_URL` |

## API Overview (prefix `/api/v1`)

| Module | Description |
|---|---|
| `/auth` | User & guest register (OTP), verify/resend OTP, refresh tokens, `/me`, login |
| `/tenants` | Tenant CRUD (user-owned) |
| `/properties` | Property CRUD, location, photos/amenities, localization, brand visual, activation toggle, floors, bookings, public view |
| `/properties/{id}/rooms` | Room CRUD, bulk create, room/bed types, available rooms by date range |
| `/properties/{id}/images` | Bulk/single image uploads (property, room, staff) |
| `/properties/{id}/special-offers` | Special offer CRUD |
| `/properties/{id}/discount-codes` | Discount code CRUD (FIXED/PERCENTAGE) |
| `/properties/{id}/staffs` | Staff CRUD |
| `/search` | Destination search (availability + pricing, Redis-cached), nearby properties with radius & lowest rate |
| `/bookings` | Create booking, payment intent, confirm (idempotent), apply discount, guest bookings list/detail |

## Tests

```bash
pytest
```

Suite features (100+ test functions):

- In-memory SQLite with PostgreSQL ARRAY/JSONB patched to JSON
- Shared `fakeredis` session; `get_db` / `get_redis_client` overridden via dependency injection
- External calls (Resend, random OTP) mocked; OTP pinned to `123456`
- Coverage: auth, tenants, properties, rooms, offers, discount codes, staff, search, images, bookings, payment-intent/confirm flows, Khalti strategy

See `document.md` for the full test breakdown.

## License

Private/internal project — no license specified.