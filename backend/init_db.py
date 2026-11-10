"""Database existence check and bootstrap script for PRAMAN on port 1234."""
import psycopg
from backend.app.core.config import settings
from backend.app.core.database import engine, Base
from backend.app.models import (
    Farmer,
    Device,
    Farm,
    BoundaryVertex,
    BoundaryHistory,
    Evidence,
    AuditLog,
    AIAssessment,
    ReviewDecision,
    MerkleBatch,
    PublicToken,
)


def init_database():
    """Ensures database exists and creates all required tables and immutability triggers."""
    # 1. Connect to default maintenance database if postgresql
    if settings.DATABASE_URL.startswith("postgresql"):
        print(f"Checking database '{settings.POSTGRES_DB}' on port {settings.POSTGRES_PORT}...")
        try:
            conn = psycopg.connect(
                host=settings.POSTGRES_SERVER,
                port=settings.POSTGRES_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                dbname="postgres",
                autocommit=True,
            )
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings.POSTGRES_DB,))
            if not cur.fetchone():
                print(f"Creating database {settings.POSTGRES_DB} on port {settings.POSTGRES_PORT}...")
                cur.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
            else:
                print(f"Database {settings.POSTGRES_DB} already exists on port {settings.POSTGRES_PORT}.")
            cur.close()
            conn.close()
        except Exception as e:
            print(f"Warning: Postgres maintenance check encountered: {e}")

    # 2. Create tables via SQLAlchemy metadata
    print(f"Connecting to database: {engine.url}")
    print("Creating all tables (farmers, devices, farms, boundary_vertices, boundary_history, evidence, audit_log)...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

    # 3. If PostgreSQL, create audit_log immutability triggers
    if engine.dialect.name == "postgresql":
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("""
                    CREATE OR REPLACE FUNCTION audit_log_prohibit_update()
                    RETURNS trigger AS $$
                    BEGIN
                        RAISE EXCEPTION 'Audit log records are immutable and cannot be updated';
                    END;
                    $$ LANGUAGE plpgsql;

                    CREATE OR REPLACE FUNCTION audit_log_prohibit_delete()
                    RETURNS trigger AS $$
                    BEGIN
                        RAISE EXCEPTION 'Audit log records are append-only and cannot be deleted';
                    END;
                    $$ LANGUAGE plpgsql;

                    DROP TRIGGER IF EXISTS prohibit_audit_update ON audit_log;
                    CREATE TRIGGER prohibit_audit_update
                    BEFORE UPDATE ON audit_log
                    FOR EACH ROW EXECUTE FUNCTION audit_log_prohibit_update();

                    DROP TRIGGER IF EXISTS prohibit_audit_delete ON audit_log;
                    CREATE TRIGGER prohibit_audit_delete
                    BEFORE DELETE ON audit_log
                    FOR EACH ROW EXECUTE FUNCTION audit_log_prohibit_delete();
                """)
                connection.commit()
                print("Audit immutability triggers created successfully.")
        except Exception as e:
            print(f"Warning: Creating triggers encountered: {e}")


if __name__ == "__main__":
    init_database()
