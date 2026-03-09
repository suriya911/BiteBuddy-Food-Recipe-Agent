import psycopg
dsn = "postgresql://bitebuddy:bitebuddy@127.0.0.1:5432/bitebuddy"
with psycopg.connect(dsn) as conn:
    with conn.cursor() as cur:
        cur.execute("select user_id, username, email, email_verified from users where email='admin@local'")
        print(cur.fetchall())
