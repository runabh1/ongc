import sqlite3
import os
from sqlalchemy import create_engine, MetaData

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "oilgas.db")

# Using SQLite for easy local setup.
DB_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
metadata = MetaData()

def init_db():
    # Load the schema.sql file to initialize the DB
    with open(os.path.join(BASE_DIR, "schema.sql"), "r") as f:
        sql_script = f.read()
    
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
