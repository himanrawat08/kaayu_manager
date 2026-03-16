import os

from sqlalchemy import create_engine, text

from app.config import settings


def sync_contact(email: str, name: str | None) -> None:
    """Upsert client email into the email tool's contacts table. Best-effort — never raises."""
    if not email:
        return

    db_path = settings.EMAIL_TOOL_DB_PATH
    if not os.path.exists(db_path):
        return

    try:
        ext_engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        with ext_engine.connect() as conn:
            existing = conn.execute(
                text("SELECT id, name FROM contacts WHERE email = :email"),
                {"email": email},
            ).fetchone()

            if existing:
                # Update name only if currently blank
                if name and not existing[1]:
                    conn.execute(
                        text("UPDATE contacts SET name = :name WHERE email = :email"),
                        {"name": name, "email": email},
                    )
                    conn.commit()
            else:
                conn.execute(
                    text("INSERT INTO contacts (email, name) VALUES (:email, :name)"),
                    {"email": email, "name": name or None},
                )
                conn.commit()

        ext_engine.dispose()
    except Exception:
        pass  # Best-effort — never crash the main app
