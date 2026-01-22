import sqlite3
import os
from sqlalchemy import create_engine, MetaData, text

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Support both SQLite (local) and PostgreSQL (production)
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Production: Use PostgreSQL from environment variable
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    IS_POSTGRES = True
else:
    # Development: Use SQLite
    DB_PATH = os.path.join(BASE_DIR, "oilgas.db")
    DB_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
    IS_POSTGRES = False

metadata = MetaData()

def init_db():
    # Load the schema.sql file to initialize the DB
    with open(os.path.join(BASE_DIR, "schema.sql"), "r") as f:
        sql_script = f.read()
    
    if IS_POSTGRES:
        # For PostgreSQL, execute via SQLAlchemy connection
        with engine.connect() as conn:
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql_script.split(';') if s.strip()]
            for statement in statements:
                try:
                    conn.execute(text(statement))
                except Exception as e:
                    # Table might already exist, continue
                    pass
            conn.commit()
    else:
        # For SQLite, use sqlite3 directly
        DB_PATH = os.path.join(BASE_DIR, "oilgas.db")
        with sqlite3.connect(DB_PATH) as conn:
            conn.executescript(sql_script)

def get_table_schema(table_name: str):
    """Reflects the database to get strict column definitions."""
    metadata.clear() # Clear cache to ensure fresh reflection
    metadata.reflect(bind=engine)
    if table_name not in metadata.tables:
        raise ValueError(f"Table '{table_name}' not found in SQL schema.")
    
    table = metadata.tables[table_name]
    # Return a dict of {column_name: type}
    return {col.name: str(col.type) for col in table.columns}
