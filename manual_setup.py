import psycopg2

# Database connection parameters
max_attempts = 10
attempts = 0
while True:
    db_url = input("[?] Please Input the DataBase secret url (type help for help): ")
    if db_url == "help":
        print("[-] The URL format starts with `postgres://` it should include the password, username etc")
    try:
        # Establish the connection
        conn = psycopg2.connect(db_url)
        break
    except Exception:
        print("[x] Error connecting to the database, please try again")
    attempts += 1
    if attempts >= max_attempts:
        exit("[x] Maximum number of attempts has been reached")

cursor = conn.cursor()


try:
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_name VARCHAR(100) PRIMARY KEY,
                password TEXT NOT NULL,
                ip_address TEXT
            );
    """)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS item (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                price INT NOT NULL,
                stock INT NOT NULL,
                image TEXT
            );
    """)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS receipt (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                item_id INT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES item(id)
            );
    """)
    cursor.execute("""
            CREATE TABLE IF NOT EXISTS missions (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT NOT NULL,
                scraps INT NOT NULL
            );
    """)
finally:
    # Close the cursor and connection
    cursor.close()
    conn.close()
