import psycopg

conn = psycopg.connect("postgresql://postgres:postgres@localhost:5433/StayEasy")
cur = conn.cursor()

# Check which columns exist
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'bookings' 
    AND column_name IN ('payment_method', 'payment_status', 'amount_paid', 'amount_due', 'advance_amount', 'checked_in_at', 'checked_out_at')
""")
existing = [r[0] for r in cur.fetchall()]
print("Existing booking columns:", existing)

cur.close()
conn.close()
