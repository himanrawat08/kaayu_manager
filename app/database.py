from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _create_system_log_trigger():
    """
    FIFO cap: after every INSERT into system_logs, delete any rows that fall
    outside the most recent 100,000 records (ordered by id).
    Works with PostgreSQL using PL/pgSQL.
    """
    create_function = """
    CREATE OR REPLACE FUNCTION trim_system_log_fifo()
    RETURNS TRIGGER AS $$
    BEGIN
        DELETE FROM system_logs
        WHERE id NOT IN (
            SELECT id FROM system_logs ORDER BY id DESC LIMIT 100000
        );
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    drop_trigger = "DROP TRIGGER IF EXISTS trim_system_log_fifo ON system_logs;"
    create_trigger = """
    CREATE TRIGGER trim_system_log_fifo
    AFTER INSERT ON system_logs
    FOR EACH ROW EXECUTE FUNCTION trim_system_log_fifo();
    """
    with engine.connect() as conn:
        conn.execute(text(create_function))
        conn.execute(text(drop_trigger))
        conn.execute(text(create_trigger))
        conn.commit()


def _create_indexes():
    """Create indexes for frequently queried columns. Safe to run multiple times."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_projects_client_id    ON projects(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_projects_status        ON projects(status)",
        "CREATE INDEX IF NOT EXISTS idx_quotations_project_id  ON quotations(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_quotations_status      ON quotations(status)",
        "CREATE INDEX IF NOT EXISTS idx_quote_items_quote_id   ON quote_items(quote_id)",
        "CREATE INDEX IF NOT EXISTS idx_quote_sundries_quote_id ON quote_sundries(quote_id)",
        "CREATE INDEX IF NOT EXISTS idx_client_activities_client_id ON client_activities(client_id)",
        "CREATE INDEX IF NOT EXISTS idx_system_logs_created_at ON system_logs(created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_leads_stage            ON leads(stage)",
        "CREATE INDEX IF NOT EXISTS idx_design_files_project_id ON design_files(project_id)",
    ]
    with engine.connect() as conn:
        for sql in indexes:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass


def _migrate_schema():
    """Add new columns to existing tables without dropping data. Safe to run multiple times."""
    migrations = [
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS client_name VARCHAR(200)",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS client_address TEXT",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS contact_name VARCHAR(200)",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS contact_number VARCHAR(50)",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS payment_terms TEXT",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS payment_account_name VARCHAR(200)",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS payment_account_no VARCHAR(100)",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS payment_ifsc VARCHAR(20)",
        "ALTER TABLE quotations ADD COLUMN IF NOT EXISTS payment_bank_name VARCHAR(200)",
        "ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS material TEXT",
        "ALTER TABLE quote_items ADD COLUMN IF NOT EXISTS gst_percent FLOAT NOT NULL DEFAULT 0.0",
        "ALTER TABLE design_files ADD COLUMN IF NOT EXISTS finalized_at TIMESTAMP",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS order_number VARCHAR(20)",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS prod_design_name TEXT",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS prod_size VARCHAR(100)",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS prod_polish_stain VARCHAR(255)",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS prod_polish_type VARCHAR(255)",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS prod_veneer_type VARCHAR(255)",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS prod_design_page INTEGER DEFAULT 1",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass
    _backfill_order_numbers()


def _backfill_order_numbers():
    """Assign order numbers to existing projects that have a final design but no order number.
    Projects are ordered by creation date so earlier projects get lower numbers."""
    with engine.connect() as conn:
        try:
            # Find projects with a final design file but no order number, ordered by creation date
            rows = conn.execute(text("""
                SELECT DISTINCT p.id
                FROM projects p
                JOIN design_files df ON df.project_id = p.id AND df.is_final = TRUE
                WHERE p.order_number IS NULL
                ORDER BY p.id ASC
            """)).fetchall()

            if not rows:
                return

            # Find current max order number
            max_row = conn.execute(text(
                "SELECT order_number FROM projects WHERE order_number IS NOT NULL"
            )).fetchall()
            max_num = 0
            for (num_str,) in max_row:
                try:
                    max_num = max(max_num, int(num_str.split("/")[-1]))
                except (ValueError, AttributeError):
                    pass

            for (project_id,) in rows:
                max_num += 1
                conn.execute(text(
                    "UPDATE projects SET order_number = :num WHERE id = :id"
                ), {"num": f"KS/{max_num:04d}", "id": project_id})
            conn.commit()
        except Exception:
            pass


def init_db():
    from app.models import client, project, design, activity, project_files, task, social_post, quotation, user, system_log, lead, yarn  # noqa: F401
    from app.models.quotation import QuoteSundry  # noqa: F401 — ensure table is created
    Base.metadata.create_all(bind=engine)
    _migrate_schema()
    _create_indexes()
    _create_system_log_trigger()
