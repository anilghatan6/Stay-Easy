# ServerIQ Restful API — Project Report
*Repository: `stay-easy` · Live API root: `/api/v1`*

## 1. Brief Overview
ServerIQ is a full-stack-as-a-service — a **multi-tenant hotel Property Management System (PMS)** delivered as a FastAPI REST API. Every hotel on the platform gets its own isolated tenant workspace (properties, rooms, staff, bookings, folios) while sharing one codebase and one database schema scoped by `tenant_id`. Three actor types are supported — **Guests** (self-service booking, payments, folio, reviews, favorites), **Staff** (front-desk, housekeeping, maintenance… with dedicated web and mobile flows), and **Super Admins** (platform management, subscriptions, feature flags, audits). The API enforces global and per-route rate limiting, role-based access control, JWT authentication, async SQLAlchemy on PostgreSQL (Neon), Redis caching/locks, pluggable payment gateways, and email via Resend.

## 2. Tech Stack and Key Dependencies
| Category | Technology |
|---|---|
| Language | Python ≥ 3.12 |
| Web framework | FastAPI (`fastapi[standard]`), Uvicorn |
| ORM | SQLAlchemy 2.0.x (async) + Greenlet driver |
| Database | PostgreSQL (psycopg async, Neon) · GeoAlchemy2 (PostGIS) |
| Migrations | Alembic (38 version files) |
| Cache / rate-limit / locks | Redis (async, connection pool) |
| Auth | PyJWT + pwdlib (Argon2) |
| Validation | Pydantic v2 (settings via pydantic-settings) |
| Payments | Stripe, Razorpay, Khalti (HTTPX), eSewa, Dummy (Strategy pattern) |
| Email | Resend API |
| Media | Cloudinary (images), Pillow, aiofiles |
| Testing | pytest, pytest-asyncio, aiosqlite, fakeredis |
| Utilities | asgi-correlation-id, httpx (NRB forex rates) |

## 3. Architecture and Project Structure
```
serveriq/
├── app/
│   ├── main.py                 # App factory, router mounting, startup expiry job
│   ├── config/                 # settings_config (env), database_config (async engine,
│   │                           #   sessionmaker expire_on_commit=False), redis_config (pool)
│   ├── middlewares/            # auth_middlewares (CurrentUser/Staff/Guest/SuperAdmin),
│   │                           #   rate_limiter (global 150/min + per-route scopes), cors
│   ├── Images/                 # image_routers (Cloudinary uploads, temp-file cleanup)
│   ├── templates/              # Email templates (Resend)
│   ├── utils/                  # exceptions, exception_handlers, logging, mail_services,
│   │                           #   security, schemas, validation, cache, forex,
│   │                           #   refund_calculator, expiry_loop, url_validation, timestamp
│   └── modules/                # Feature modules (each: models / schemas / repositories /
│       │                       #   services / routers)
│       ├── auth/               # users, guests, password reset
│       ├── pms/                # tenants, properties, rooms, images, offers, discount
│       │                       #   codes, reviews, search, activity logs
│       ├── staff_mgmt/         # staff CRUD
│       ├── booking/            # bookings, folio, favourites, payment strategies
│       ├── dashboard/          # dashboard aggregates
│       ├── house_keeping/      # web housekeeping (tasks)
│       ├── housekeeping_mobile/# mobile housekeeping (cleaning submissions, schedules,
│       │                       #   shift swaps, leave, maintenance)
│       ├── notifications/      # targeted notification delivery
│       ├── staff_operations/   # staff back-office ops
│       ├── superadmin/         # platform mgmt, subscription plans/flag, audits
│       └── subscription/       # plan limits + feature flags on tenant workspaces
├── alembic/versions/           # 38 migrations
└── tests/                      # module-scoped pytest suites (aiosqlite + fakeredis)
```
**Cross-cutting behaviour**
- Response envelope: `{"success": true, "data": ..., "meta": ...}`; errors → `{"success": false, "error": ...}` handled centrally by custom exception handlers.
- Auth dependencies read JWT `sub/role/exp`; `STAFF_ROLES = {admin, manager, front_desk, housekeeping, maintenance, waiter, kitchen}`; a `must_change_password` gate forces a password change on first login / invites.
- Global rate limit 150 req/min per identity+path; sensitive endpoints add stricter sliding-window scopes.
- A background loop auto-expires stale booking soft-locks and dirty bookings (10-min TTL).

## 4. Modules and Endpoints
> Each module lists its endpoints, then a few notes on how users/guests interact with that feature.

### 4.1 Authentication (auth)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/register` | Guest | Register a new guest account |
| POST | `/auth/login` | – | OAuth2 login → access + refresh JWT |
| POST | `/auth/refresh` | – | Rotate refresh token |
| POST | `/auth/forgot-password` | – | Email reset link (10-min token) |
| POST | `/auth/reset-password` | – | Reset password with token |
| POST | `/auth/change-password` | Staff | Change own password |
| GET | `/auth/users/me` | All | Current user profile |
| PUT | `/auth/users/me` | All | Update own profile |
| POST | `/auth/users/invite` | Staff (admin) | Invite staff with temp password |
| GET/PUT/DELETE | `/auth/users/{id}` | Staff (admin) | Manage users |
| GET | `/auth/guests/me` | Guest | Guest profile |
| GET/PUT | `/auth/guests/{id}` | Staff | View/edit guest details |

- Guests self-register, log in with OAuth2, and manage their own profile; staff must complete a mandatory password change on first login (invite flow).
- Admins invite new staff with an expiring temporary password; users rotate tokens seamlessly via refresh endpoint.

### 4.2 Tenants (pms)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/tenants` | Staff (admin) | Create tenant (unique slug) |
| GET | `/tenants` | Staff | List tenants |
| GET | `/tenants/{tenant_id}` | Staff | Tenant details |
| PUT | `/tenants/{tenant_id}` | Staff (admin) | Update tenant |
| DELETE | `/tenants/{tenant_id}` | Staff (superadmin) | Delete tenant |

- Tenant onboarding auto-creates a globally unique slug from the hotel name and assigns a free-trial subscription plan (feature flags + limits).
- All other modules scope their queries by the caller's tenant, so staff only ever see their own hotel's data.

### 4.3 Properties (pms)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/properties` | Staff (admin) | Register property |
| GET | `/properties` | Guest/Staff | List properties (+ filters, pagination) |
| GET | `/properties/{property_id}` | Guest/Staff | Property detail |
| PUT | `/properties/{property_id}` | Staff (admin) | Update property |
| DELETE | `/properties/{property_id}` | Staff (admin) | Soft-delete property |
| POST | `/properties/{property_id}/images` | Staff (admin) | Upload property images |
| GET | `/properties/nearby` | Guest | Geo search by lat/lng (radius ≤ 20) |

- Guests browse/search the public property feed and open detail pages; staff manage their hotel's properties and imagery.
- Nearby search converts coordinates to PostGIS geography for radius filtering, returning distance for each result.

### 4.4 Rooms (pms)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/rooms` | Staff (admin) | Add room under a property |
| GET | `/rooms` | Guest/Staff | List rooms (filters: price, beds, floor, amenities) |
| GET | `/rooms/{room_id}` | Guest/Staff | Room detail |
| PUT | `/rooms/{room_id}` | Staff (admin) | Update room |
| DELETE | `/rooms/{room_id}` | Staff (admin) | Remove room |
| GET | `/rooms/{room_id}/availability` | Guest | Check date-range availability |
| GET | `/pms/rooms/availability/calendar` | Staff | Availability calendar |

- Guests check live availability for any date range before booking; the system soft-locks rooms during checkout to prevent double booking.
- Staff manage the inventory, room types/beds/amenities (seeded defaults), pricing and per-room flooring.

### 4.5 Images (Images module)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/images/upload` | Staff (admin) | Upload image (max 5) |
| DELETE | `/images/{image_id}` | Staff (admin) | Remove image |
| GET | `/images/property/{property_id}` | Guest/Staff | List property images |

- Uploads enforce `image/*` MIME, `webp` conversion via Pillow, and Cloudinary storage; temporary files are cleaned up by a background job.
- Guests see optimized, cached property galleries rendered on property detail pages.

### 4.6 Special Offers (pms)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/offers` | Staff (admin) | Create offer |
| GET | `/offers` | Guest/Staff | List active offers |
| GET | `/offers/{offer_id}` | Guest/Staff | Offer detail |
| PUT | `/offers/{offer_id}` | Staff (admin) | Update offer |
| DELETE | `/offers/{offer_id}` | Staff (admin) | Delete offer |
| POST | `/offers/{offer_id}/apply` | Guest | Apply offer to cart/booking |

- Guests see active promotional offers on listing pages and apply them at checkout to get discounted rates.
- Staff author these deals with validity windows and apply rules; bookkeeping snapshots the discount at confirmation.

### 4.7 Discount Codes (pms)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/discount-codes` | Staff (admin) | Create code (FIXED/PERCENTAGE) |
| GET | `/discount-codes` | Staff | List codes |
| PUT | `/discount-codes/{code_id}` | Staff (admin) | Update code |
| DELETE | `/discount-codes/{code_id}` | Staff (admin) | Delete code |
| POST | `/discount-codes/validate` | Guest | Validate a code during checkout |

- Guests enter a promo code at payment; validation enforces min-booking amount, usage caps and expiry before a percentage or fixed amount is applied.
- Staff control issuance, usage limits, and validity; applied discounts are stored on the booking record.

### 4.8 Staff Management (staff_mgmt)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/staffs` | Admin | Create staff profile (links to auth user) |
| GET | `/staffs` | Admin | List staff |
| GET | `/staffs/{staff_id}` | Admin | Staff detail |
| PUT | `/staffs/{staff_id}` | Admin | Update staff (role, shift) |
| DELETE | `/staffs/{staff_id}` | Admin | Deactivate staff |

- Hotel admins onboard the front-desk, housekeeping, and maintenance crew with roles that map to the `STAFF_ROLES` permission set and each staff member's assigned shift.
- Role assignments directly control which API surface each staff account may call.

### 4.9 Search (pms)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/search` | Guest/Staff | Fuzzy search (type/name/city/state/country, cached) |
| GET | `/search/nearby` | Guest | Radius search with geo ordering |

- Guests type partial names or cities and receive fuzzy-matched, Redis-cached results for fast autocomplete-style browsing.
- Staff reuse the search across the dashboard to jump between properties, rooms, or guests; results are keyed and cached per query for performance.

### 4.10 Bookings and Payments (booking)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/bookings` | Guest/Staff | Create booking (idempotency key) |
| GET | `/bookings` | Staff/Guest | List bookings |
| GET | `/bookings/{booking_id}` | Owner/Staff | Booking detail |
| PUT | `/bookings/{booking_id}` | Staff (front_desk) | Update booking |
| DELETE | `/bookings/{booking_id}` | Owner/Staff | Cancel booking |
| POST | `/bookings/{booking_id}/payment` | Guest | Initiate gateway payment |
| POST | `/bookings/payment/webhook` | Gateway | Payment callback (verifies signature) |
| POST | `/bookings/{booking_id}/checkout` | Guest | Complete payment (hosted redirect) |
| GET | `/bookings/{booking_id}/receipt` | Guest | Download booking receipt |
| POST | `/bookings/{booking_id}/modify` | Guest/Staff | Change dates/rooms (logged) |
| GET | `/bookings/walkin` + POST | Staff (front_desk) | Walk-in booking flow |

- Guests run the full journey: pick dates → 10-minute soft-lock → apply offer/discount → pay via preferred gateway → get reference `BK-XXXX`, receipt, and email confirmation. Idempotency keys prevent duplicate charges from retries.
- Guests can modify or cancel per the property's cancellation policy, which computes refunds via the refund calculator; every modification is logged for audit.
- Front-desk staff create walk-in bookings for walk-up guests and can book on a guest's behalf.

### 4.11 Folio (booking)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/folios` | Staff (front_desk) | Open folio for guest stay |
| GET | `/folios/{folio_id}` | Staff/Guests | Folio transactions |
| POST | `/folios/{folio_id}/charges` | Staff | Add incidental charges |
| POST | `/folios/{folio_id}/payments` | Staff | Settle payments |
| GET | `/folios/guest/{guest_id}` | Staff | Guest folio summary |

- Front-desk staff log incidental charges (minibar, laundry) and settle them to the guest's folio throughout the stay.
- Guests see an itemized, running folio of charges and payments for transparency at check-out, while settlement hooks into the same gateway strategies.

### 4.12 Favorites (booking)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/favorites` | Guest | My favorite properties |
| POST | `/favorites/{property_id}` | Guest | Add to favorites |
| DELETE | `/favorites/{property_id}` | Guest | Remove from favorites |

- Guests save properties they like during browsing; the favorites list persists across sessions and surfaces one-tap rebooking shortcuts.

### 4.13 Dashboard (dashboard)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/dashboard/overview` | Staff | KPIs: occupancy, revenue, arrivals |
| GET | `/dashboard/occupancy` | Staff | Occupancy trend |
| GET | `/dashboard/revenue` | Staff | Revenue breakdown by source |
| GET | `/dashboard/arrivals` | Staff | Today/upcoming arrivals |
| GET | `/dashboard/departures` | Staff | Today departures |
| GET | `/dashboard/alerts` | Staff | Operational alerts (maintenance, stayovers) |

- Hotel staff land on a dashboard aggregating live occupancy, revenue and arrivals so they can prioritize front-desk and housekeeping action.

### 4.14 Housekeeping Web (house_keeping)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/housekeeping/tasks` | Housekeeping admin | Create cleaning task |
| GET | `/housekeeping/tasks` | Housekeeping | Task list by status |
| PUT | `/housekeeping/tasks/{task_id}` | Housekeeping | Update task status (assigned/done) |

- Housekeeping staff pull a task queue per floor and flip tasks between pending / in-progress / clean; completed tasks trigger guest-ready room status updates.

### 4.15 Housekeeping Mobile (housekeeping_mobile)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/mobile/cleaning-submissions` | Housekeeping (mobile) | Submit cleaning proof & report |
| GET | `/mobile/tasks` | Housekeeping | Today's assigned tasks |
| GET/POST | `/mobile/schedules` | Housekeeping | My shift schedule |
| POST | `/mobile/shift-swap/request` | Housekeeping | Request shift swap |
| GET | `/mobile/leave/requests` | Housekeeping | Submit leave request |
| GET/POST | `/mobile/maintenance/reports` | Housekeeping | Report a maintenance issue |
| GET | `/mobile/dashboard` | Housekeeping | Mobile summary view |

- Housekeeping crews work from a mobile app: see only their assigned tasks and schedule, submit cleaning completion with evidence, request shift swaps or leave, and report maintenance issues that stream into the staff dashboard alerts.

### 4.16 Notifications (notifications)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/notifications` | All | List my notifications |
| GET | `/notifications/unread-count` | All | Unread badge count |
| PUT | `/notifications/{id}/read` | All | Mark single as read |
| PUT | `/notifications/read-all` | All | Mark all read |
| POST | `/notifications` | Staff (admin) | Push notification (email/in-app) |

- Guests receive booking confirmations, cancellation updates and payment receipts (email + in-app); staff get housekeeping/maintenance and booking alerts scoped to their role/tenant.

### 4.17 Staff Operations (staff_operations)
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/operations/checkin` | Staff (front_desk) | Guest check-in |
| POST | `/operations/checkout` | Staff (front_desk) | Guest check-out + folio settle |
| POST | `/operations/room-assign` | Staff | Assign/reassign rooms |
| GET | `/operations/stayovers` | Staff | Stayover guests |

- Front-desk staff run the physical guest journey — check-in, room assignment, and check-out with final folio settlement — all logged per actor and tenant.

### 4.18 Superadmin (superadmin)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET/POST | `/superadmin/tenants` | SuperAdmin | List/onboard tenants (assign free trial) |
| GET/PUT | `/superadmin/tenants/{id}/subscription` | SuperAdmin | Change plan/state |
| GET/POST | `/superadmin/plans` | SuperAdmin | Manage subscription plans |
| POST | `/superadmin/announcements` | SuperAdmin | Broadcast announcements |
| GET | `/superadmin/audit-logs` | SuperAdmin | Platform audit trail |
| GET/POST | `/superadmin/feature-flags` | SuperAdmin | Enable/disable features per tenant |

- Platform operators manage the whole ecosystem from a single console: onboarding new hotels on the free trial, upgrading plans, toggling feature flags, broadcasting announcements, and auditing every cross-tenant action.

### 4.19 Subscription (subscription)
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/subscription/plan` | Staff (admin) | Current plan + limits |
| GET | `/subscription/feature-flags` | Staff | Enabled features |
| POST | `/subscription/limits/check` | Staff | Check rooms/bookings limits before create |

- New hotels start on an auto-assigned free-trial plan; the subscription middleware enforces hard limits (room count, booking volume) and feature flags before resource creation, giving admins a clear upgrade prompt when they hit a ceiling.

## 5. Payment Integration
| Gateway | Service | Mode |
|---|---|---|
| Stripe | `stripe_strategy.py` | Card/iDEAL hosted checkout, webhook verification |
| Razorpay | `razorpay_strategy.py` | Indian card/netbanking/UPI hosted checkout |
| Khalti | `khalti_strategy.py` | Nepal: hosted checkout via `return_url`, `paisa` conversion |
| eSewa | `esewa_strategy.py` | Nepal: hosted checkout, signature-signed callbacks |
| Dummy | `dummy_strategy.py` | Local/sandbox testing |
| FX conversion | `utils/forex.py` | Live NRB rates via HTTPX (NPR ↔ currency) |

- Payments flow through a strategy factory: creating a booking returns a gateway-specific hosted session; the gateway POSTs a signed webhook that the API verifies before releasing/confirming the booking, with full refund calculation on cancellation.

## 6. Conclusion
ServerIQ condenses a hotel's entire operations — guest-facing booking and payments, staff housekeeping and front-desk flows, operational dashboards, notifications, and platform-level subscription management — into one multi-tenant API. Strict tenant isolation, role-gated auth, Redis-backed rate limiting and caching, idempotent async booking logic, and pluggable payment strategies make it both a production-grade PMS core and an extensible platform for future modules.