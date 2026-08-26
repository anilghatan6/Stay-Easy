import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5433/StayEasy")
cur = conn.cursor()

# Migration 1: Payment method and status columns
print("Running migration 1: Payment columns...")

cur.execute("""
DO $$ BEGIN
    CREATE TYPE paymentmethod AS ENUM ('ONLINE', 'ADVANCE', 'PAY_ON_ARRIVAL');
EXCEPTION WHEN duplicate_object THEN null;
END $$;
""")

cur.execute("""
DO $$ BEGIN
    CREATE TYPE paymentstatus AS ENUM ('UNPAID', 'PARTIAL', 'PAID');
EXCEPTION WHEN duplicate_object THEN null;
END $$;
""")

cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS payment_method paymentmethod NOT NULL DEFAULT 'ONLINE'")
cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS payment_status paymentstatus NOT NULL DEFAULT 'UNPAID'")
cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS amount_paid NUMERIC(10,2) NOT NULL DEFAULT 0.00")
cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS amount_due NUMERIC(10,2) NOT NULL DEFAULT 0.00")
cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS advance_amount NUMERIC(10,2)")
cur.execute("UPDATE bookings SET amount_due = total_amount WHERE amount_due = 0")
conn.commit()
print("  Done!")

# Migration 2: Check-in/out timestamps and reviews
print("Running migration 2: Timestamps and reviews...")

cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ")
cur.execute("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS checked_out_at TIMESTAMPTZ")
cur.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS average_rating NUMERIC(3,2) DEFAULT 0.00")
cur.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS total_reviews INTEGER DEFAULT 0")

cur.execute("""
CREATE TABLE IF NOT EXISTS reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    guest_id UUID NOT NULL REFERENCES guests(id) ON DELETE CASCADE,
    booking_id UUID NOT NULL REFERENCES bookings.id ON DELETE CASCADE,
    rating INTEGER NOT NULL,
    comment VARCHAR(2000),
    is_edited BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_review_per_booking UNIQUE (booking_id),
    CONSTRAINT chk_review_rating_range CHECK (rating >= 1 AND rating <= 5)
)
""")
cur.execute("CREATE INDEX IF NOT EXISTS ix_reviews_property_id ON reviews(property_id)")
cur.execute("CREATE INDEX IF NOT EXISTS ix_reviews_guest_id ON reviews(guest_id)")
cur.execute("CREATE INDEX IF NOT EXISTS ix_reviews_booking_id ON reviews(booking_id)")
conn.commit()
print("  Done!")

# Migration 3: Allow pay on arrival and advance percentage
print("Running migration 3: Pay on arrival settings...")

cur.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS allow_pay_on_arrival BOOLEAN NOT NULL DEFAULT true")
cur.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS min_advance_percentage INTEGER DEFAULT 10")
cur.execute("ALTER TABLE properties ADD COLUMN IF NOT EXISTS max_advance_percentage INTEGER DEFAULT 50")
conn.commit()
print("  Done!")

# Verify
print("\nVerifying columns...")
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'bookings' 
    AND column_name IN ('payment_method', 'payment_status', 'amount_paid', 'amount_due', 'advance_amount', 'checked_in_at', 'checked_out_at')
    ORDER BY column_name
""")
print("Bookings columns:", [r[0] for r in cur.fetchall()])

cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'properties' 
    AND column_name IN ('allow_pay_on_arrival', 'min_advance_percentage', 'max_advance_percentage', 'average_rating', 'total_reviews')
    ORDER BY column_name
""")
print("Properties columns:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'reviews')")
print("Reviews table exists:", cur.fetchone()[0])

cur.close()
conn.close()
print("\nAll migrations complete!")
