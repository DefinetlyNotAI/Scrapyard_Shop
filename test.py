import os

import psycopg2

# Database connection parameters
db_url = os.getenv("DB_URL_AIVEN")

# Establish the connection
conn = psycopg2.connect(db_url)
cursor = conn.cursor()


def execute_query(query):
    cursor.execute(query)
    if query.strip().lower().startswith("select"):
        result = cursor.fetchall()
        for row in result:
            print(row)


try:

    execute_query("""
            CREATE TABLE IF NOT EXISTS teams (
                team_name VARCHAR(100) PRIMARY KEY,
                password TEXT NOT NULL,
                ip_address TEXT
            );
    """)
    execute_query("""
            CREATE TABLE IF NOT EXISTS item (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                price INT NOT NULL,
                stock INT NOT NULL,
                image TEXT
            );
    """)
    execute_query("""
            CREATE TABLE IF NOT EXISTS receipt (
                id SERIAL PRIMARY KEY,
                user_email VARCHAR(255) NOT NULL,
                item_id INT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES item(id)
            );
    """)
    execute_query("""
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
