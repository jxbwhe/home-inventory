import sqlite3

def migrate():
    conn = sqlite3.connect('data/inventory.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE items ADD COLUMN family_id INTEGER REFERENCES families(id)")
        print("Successfully added family_id to items.")
    except sqlite3.OperationalError as e:
        print(f"Migration error (already exists?): {e}")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate()
