"""Initialize the local SQLite database used by the FastAPI app."""

from __future__ import annotations

from agent_overseas_report.database import (
    SQLAlchemyEnterpriseRepository,
    create_database_engine,
    create_session_factory,
    get_database_url,
    initialize_database,
    seed_demo_data,
)


def main() -> None:
    """Create tables and seed demo enterprise/product rows."""

    database_url = get_database_url()
    engine = create_database_engine(database_url)
    initialize_database(engine)
    seed_demo_data(SQLAlchemyEnterpriseRepository(create_session_factory(engine)))
    print(f"Initialized database: {database_url}")


if __name__ == "__main__":
    main()
