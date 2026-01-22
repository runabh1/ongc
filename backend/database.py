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

def get_postgres_schema():
    """Return PostgreSQL-compatible schema"""
    return """
    DROP TABLE IF EXISTS WCR_CASING CASCADE;
    DROP TABLE IF EXISTS WCR_LOGSRECORD CASCADE;
    DROP TABLE IF EXISTS WCR_DIRSRVY CASCADE;
    DROP TABLE IF EXISTS WCR_SWC CASCADE;
    DROP TABLE IF EXISTS WCR_HCSHOWS CASCADE;
    DROP TABLE IF EXISTS WCR_WELLHEAD CASCADE;

    CREATE TABLE WCR_WELLHEAD (
        UWI VARCHAR(64) PRIMARY KEY NOT NULL,
        WELL_NAME VARCHAR(255),
        FIELD VARCHAR(255),
        RELEASE_NAME VARCHAR(255),
        LOCATION_TYPE VARCHAR(128),
        BOTTOM_LONG FLOAT,
        BOTTOM_LAT FLOAT,
        SURFACE_LONG FLOAT,
        SURFACE_LAT FLOAT,
        CATEGORY VARCHAR(255),
        WELL_PROFILE VARCHAR(64),
        TARGET_DEPTH FLOAT,
        DRILLED_DEPTH FLOAT,
        LOGGERS_DEPTH FLOAT,
        K_B FLOAT,
        G_L FLOAT,
        RIG VARCHAR(255),
        SPUD_DATE VARCHAR(11),
        HERMETICAL_TEST_DATE VARCHAR(11),
        DRILLING_COMPLETED_DATE VARCHAR(11),
        RIG_RELEASED_DATE VARCHAR(11),
        FORMATION_AT_TD VARCHAR(255),
        RELEASE_ORDER_NO VARCHAR(255),
        OBJECTIVE TEXT,
        STATUS TEXT,
        ID INTEGER,
        MODEL VARCHAR(25),
        INSERT_DATE DATE,
        MATCH_PERCENT FLOAT,
        VECTOR_IDS VARCHAR(100),
        PAGE_NUMBERS VARCHAR(100)
    );

    CREATE TABLE WCR_CASING (
        UWI VARCHAR(64) NOT NULL,
        CASING_TYPE VARCHAR(255),
        CASING_LINER_NAME VARCHAR(255),
        CASING_START_DATE DATE,
        CASING_TOP FLOAT,
        CASING_BOTTOM FLOAT,
        OUTER_DIAMETER FLOAT,
        CASING_SHOE_LENGTH FLOAT,
        FLOAT_COLLAR FLOAT,
        MATERIAL_TYPE VARCHAR(64),
        WEIGHT VARCHAR(64),
        STEEL_GRADE VARCHAR(64),
        REMARKS TEXT,
        ID INTEGER PRIMARY KEY,
        MODEL VARCHAR(25),
        INSERT_DATE DATE,
        MATCH_PERCENT FLOAT,
        VECTOR_IDS VARCHAR(100),
        PAGE_NUMBERS VARCHAR(100),
        MATCH_ID INTEGER
    );

    CREATE TABLE WCR_LOGSRECORD (
        UWI VARCHAR(64) NOT NULL,
        TOP FLOAT,
        BOTTOM FLOAT,
        LOG_RECORDED VARCHAR(255),
        LOG_DATE VARCHAR(11),
        LOGGED_BY VARCHAR(64),
        ID INTEGER PRIMARY KEY,
        MODEL VARCHAR(25),
        INSERT_DATE DATE,
        MATCH_PERCENT FLOAT,
        VECTOR_IDS VARCHAR(100),
        PAGE_NUMBERS VARCHAR(100),
        MATCH_ID INTEGER
    );

    CREATE TABLE WCR_DIRSRVY (
        ID INTEGER PRIMARY KEY,
        UWI VARCHAR(64),
        MD FLOAT,
        ANGLE_INCLINATION FLOAT,
        AZIMUTH FLOAT,
        NS FLOAT,
        EW FLOAT,
        NET_DRIFT FLOAT,
        NET_DIRECTION_ANGLE FLOAT,
        VERTICAL_SHORTENING FLOAT,
        MODEL VARCHAR(25),
        INSERT_DATE DATE,
        MATCH_PERCENT FLOAT,
        VECTOR_IDS VARCHAR(100),
        PAGE_NUMBERS VARCHAR(100),
        MATCH_ID VARCHAR(100)
    );

    CREATE TABLE WCR_SWC (
        DEPTH FLOAT,
        RECOVERED_LENGTH FLOAT,
        LITHOLOGY VARCHAR(255),
        LITHOLOGY_DESCRIPTION TEXT,
        HCSHOW VARCHAR(255),
        REMARKS VARCHAR(255),
        ID INTEGER PRIMARY KEY,
        UWI VARCHAR(64),
        MODEL VARCHAR(25),
        INSERT_DATE DATE,
        MATCH_PERCENT FLOAT,
        VECTOR_IDS VARCHAR(100),
        PAGE_NUMBERS VARCHAR(100),
        MATCH_ID INTEGER
    );

    CREATE TABLE WCR_HCSHOWS (
        ID INTEGER PRIMARY KEY,
        UWI VARCHAR(64),
        TOP_DEPTH FLOAT,
        BOTTOM_DEPTH FLOAT,
        TOTAL_GAS VARCHAR(255),
        LITHOLOGY VARCHAR(255),
        HCSHOW VARCHAR(255),
        MODEL VARCHAR(25),
        INSERT_DATE DATE,
        MATCH_PERCENT FLOAT,
        VECTOR_IDS VARCHAR(100),
        PAGE_NUMBERS VARCHAR(100),
        MATCH_ID INTEGER
    );
    """

def init_db():
    # Load the schema.sql file to initialize the DB
    if IS_POSTGRES:
        sql_script = get_postgres_schema()
    else:
        with open(os.path.join(BASE_DIR, "schema.sql"), "r") as f:
            sql_script = f.read()
    
    if IS_POSTGRES:
        # For PostgreSQL, execute via SQLAlchemy connection
        try:
            with engine.connect() as conn:
                # First check which tables already exist
                from sqlalchemy import inspect
                inspector = inspect(engine)
                existing_tables = set(inspector.get_table_names())
                print(f"✓ Existing tables in database: {existing_tables}")
                
                # Split by semicolon and execute each statement
                statements = [s.strip() for s in sql_script.split(';') if s.strip()]
                created_count = 0
                for statement in statements:
                    try:
                        # Skip if it's a DROP or CREATE for an existing table
                        if statement.startswith("DROP"):
                            conn.execute(text(statement))
                            print(f"✓ Dropped table: {statement[20:50]}...")
                        elif statement.startswith("CREATE"):
                            conn.execute(text(statement))
                            created_count += 1
                            # Extract table name for logging
                            table_name = statement.split("(")[0].replace("CREATE TABLE", "").strip()
                            print(f"✓ Created table: {table_name}")
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "already exists" in error_msg or "duplicate" in error_msg:
                            print(f"⊘ Table already exists (skipped)")
                        else:
                            print(f"✗ Error: {statement[:50]}... -> {str(e)}")
                            raise
                
                conn.commit()
                print(f"✓ Database initialized: {created_count} tables created/updated")
                
                # Verify tables were created
                inspector = inspect(engine)
                final_tables = set(inspector.get_table_names())
                print(f"✓ Final tables in database: {final_tables}")
                
        except Exception as e:
            print(f"✗ Database initialization error: {e}")
            import traceback
            traceback.print_exc()
            raise
    else:
        # For SQLite, use sqlite3 directly
        DB_PATH = os.path.join(BASE_DIR, "oilgas.db")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.executescript(sql_script)
                print("✓ SQLite database initialized successfully")
        except Exception as e:
            print(f"✗ SQLite initialization error: {e}")
            raise


def get_table_schema(table_name: str):
    """Reflects the database to get strict column definitions."""
    # Clear cache and re-reflect to get fresh data
    metadata.clear()
    
    # For fresh reflection, create a new connection
    if IS_POSTGRES:
        # Force a fresh connection for PostgreSQL
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        print(f"Available tables in database: {tables}")
        
        if table_name not in tables:
            raise ValueError(f"Table '{table_name}' not found. Available tables: {tables}")
        
        # Get columns
        columns = inspector.get_columns(table_name)
        return {col['name']: str(col['type']) for col in columns}
    else:
        # SQLite
        metadata.reflect(bind=engine)
        if table_name not in metadata.tables:
            raise ValueError(f"Table '{table_name}' not found in SQL schema.")
        
        table = metadata.tables[table_name]
        return {col.name: str(col.type) for col in table.columns}

