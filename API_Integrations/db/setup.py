import pyodbc
from typing import Generator

# SQL Server connection string
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS;"
    "DATABASE=nexus_agent_db;"
    "Trusted_Connection=yes;"
)


def get_db_connection():
    """
    Create and return a new database connection.
    """
    try:
        conn = pyodbc.connect(CONNECTION_STRING)
        return conn
    except Exception as e:
        raise RuntimeError(f"Database connection failed: {e}")


def get_db() -> Generator:
    """
    FastAPI dependency that provides a DB connection
    and automatically closes it after request.
    """
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()


def test_connection():
    """
    Quick check to verify DB connectivity.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT DB_NAME()")
    db_name = cursor.fetchone()[0]

    print(f"✅ Connected to database: {db_name}")

    conn.close()


if __name__ == "__main__":
    test_connection()
