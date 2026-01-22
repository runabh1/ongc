import os
import shutil
import json
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import pdfplumber
import pandas as pd
from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import google.generativeai as genai
from dotenv import load_dotenv

from database import init_db, get_table_schema, engine

# Load environment variables from .env file in development
load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Well Completion Extractor", lifespan=lifespan)

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# CORS Setup - Allow Vercel frontend and localhost for development
allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://localhost:5173",
    "https://ongc-yb42.vercel.app",  # Your Vercel frontend
]
# Add production frontend URL if specified
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in allowed_origins:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"message": "Backend is running successfully. Use /docs for API documentation."}

# --- MODELS ---
class RegionSelection(BaseModel):
    page_number: int
    x_pct: float  # Normalized coordinates (0.0 to 1.0)
    y_pct: float
    w_pct: float
    h_pct: float
    label: str    # e.g., "CASING"
    use_ai: bool = False

# --- CONFIGURATION ---
LABEL_TO_TABLE = {
    "WELL_HEADER": "WCR_WELLHEAD",
    "WCR_WELLHEAD": "WCR_WELLHEAD",
    "CASING": "WCR_CASING",
    "WCR_CASING": "WCR_CASING",
    "LOGS": "WCR_LOGSRECORD",
    "WCR_LOGSRECORD": "WCR_LOGSRECORD",
    "DIRSRVY": "WCR_DIRSRVY",
    "WCR_DIRSRVY": "WCR_DIRSRVY",
    "SWC": "WCR_SWC",
    "WCR_SWC": "WCR_SWC",
    "HCSHOWS": "WCR_HCSHOWS",
    "WCR_HCSHOWS": "WCR_HCSHOWS"
}

# --- LOGIC ---

def extract_from_region(pdf_path: str, sel: RegionSelection, use_raw_headers: bool = False) -> List[Dict]:
    data = []
    with pdfplumber.open(pdf_path) as pdf:
        # pdfplumber pages are 0-indexed
        page = pdf.pages[sel.page_number - 1]
        width, height = page.width, page.height
        
        # Convert normalized percentages to PDF points and clamp to page bounds
        x0 = max(0, min(sel.x_pct * width, width))
        top = max(0, min(sel.y_pct * height, height))
        x1 = max(x0, min((sel.x_pct + sel.w_pct) * width, width))
        bottom = max(top, min((sel.y_pct + sel.h_pct) * height, height))
        
        bbox = (x0, top, x1, bottom)
        
        if x1 - x0 <= 0 or bottom - top <= 0:
            return []
        
        cropped = page.crop(bbox)
        
        # Try Table Extraction
        tables = cropped.extract_tables()
        table_extracted = False
        
        if tables:
            for table in tables:
                if not table: continue
                # Assume first row is header
                header_row = table[0]
                valid_headers = {} # index -> cleaned_name
                for idx, h in enumerate(header_row):
                    if h:
                        if use_raw_headers:
                            valid_headers[idx] = str(h)
                        else:
                            valid_headers[idx] = str(h).lower().replace(" ", "_").replace(".", "")

                for row in table[1:]:
                    row_data = {}
                    for idx, val in enumerate(row):
                        if idx in valid_headers:
                            row_data[valid_headers[idx]] = val
                    if row_data:
                        data.append(row_data)
                        table_extracted = True
        
        if not table_extracted:
            # Fallback: Raw text (simple key-value heuristic could go here)
            text = cropped.extract_text()
            
            # Attempt simple KV parsing (e.g. "Field: Mumbai High")
            kv_data = {}
            if text:
                lines = text.split('\n')
                for line in lines:
                    # Split by first colon
                    if ':' in line:
                        parts = line.split(':', 1)
                        k = parts[0].strip()
                        v = parts[1].strip()
                        if k and v:
                            kv_data[k] = v
            
            if kv_data:
                data.append(kv_data)
            else:
                data.append({"raw_text": text, "_warning": "No table structure detected"})
            
    return data

def extract_with_gemini(text: str, table_name: str) -> List[Dict]:
    """Uses Gemini Pro to parse unstructured text into SQL-compatible JSON."""
    try:
        schema = get_table_schema(table_name)
        columns = [k for k in schema.keys() if k.upper() not in IGNORED_COLUMNS]
        
        model = genai.GenerativeModel('gemini-3-flash-preview')
        
        prompt = f"""
        You are a data extraction assistant for Oil & Gas reports.
        Extract data from the following text into a JSON list of objects.
        
        Target SQL Table: {table_name}
        Target Columns: {", ".join(columns)}
        
        Rules:
        1. Return ONLY a valid JSON list. No markdown formatting, no explanations.
        2. Map the text values to the Target Columns best suited for them.
        3. Convert values to appropriate types (numbers for depths, YYYY-MM-DD for dates if possible).
        4. If a column is not found in text, omit it or set to null.
        
        Input Text:
        {text}
        """
        
        response = model.generate_content(prompt)
        cleaned_response = response.text.replace("```json", "").replace("```", "").strip()
        
        data = json.loads(cleaned_response)
        if isinstance(data, dict):
            data = [data]
        return data
        
    except Exception as e:
        print(f"Gemini Extraction Error: {e}")
        return []

# System columns to ignore during validation/display so we don't flag them as missing
IGNORED_COLUMNS = {
    "ID", "MODEL", "INSERT_DATE", "MATCH_PERCENT", 
    "VECTOR_IDS", "PAGE_NUMBERS", "MATCH_ID"
}

def validate_data(data: List[Dict], table_name: str):
    try:
        schema = get_table_schema(table_name)
    except ValueError as e:
        return {"error": f"Table {table_name} not defined in SQL: {str(e)}"}
    except Exception as e:
        print(f"Schema reflection error for {table_name}: {str(e)}")
        # Fallback: Create schema from extracted data
        if not data:
            return {"error": "No data to validate"}
        schema = {k: "TEXT" for k in data[0].keys() if not k.startswith("_")}
        print(f"Using fallback schema with {len(schema)} columns")

    validated_rows = []
    
    # Helper to normalize keys for robust matching (remove spaces, underscores, dots)
    def normalize_key(k):
        # Remove all non-alphanumeric characters for stricter matching (e.g. "Field:" -> "FIELD")
        return "".join(c for c in str(k).upper() if c.isalnum())

    # Create a map of the schema: NORMALIZED -> Original
    schema_map = {normalize_key(k): k for k in schema.keys()}
    # Also create a list for fuzzy substring matching
    sql_cols_normalized = [(normalize_key(k), k) for k in schema.keys()]
    
    # Filter schema for display/validation (exclude system columns)
    display_columns = [k for k in schema.keys() if k.upper() not in IGNORED_COLUMNS]
    
    for row in data:
        row_status = "VALID"
        errors = []
        clean_row = {}
        
        # 1. Map extracted data to SQL columns and check for unknown columns
        for key, val in row.items():
            if key.startswith("_"): continue # Skip internal flags
            norm_key = normalize_key(key)
            
            real_col_name = None
            
            # 1. Exact Normalized Match
            if norm_key in schema_map:
                real_col_name = schema_map[norm_key]
            
            # 2. Fuzzy Match (Substring)
            if not real_col_name:
                for sql_norm, sql_orig in sql_cols_normalized:
                    # Check if SQL column is inside Extracted Header (e.g. "FIELD" in "FIELDNAME")
                    if sql_norm in norm_key and len(sql_norm) > 2: 
                        real_col_name = sql_orig
                        break
            
            if real_col_name:
                clean_row[real_col_name] = val
            else:
                errors.append(f"Unknown column: {key}")
                row_status = "INVALID"
        
        # 2. Check for Missing Columns (Compare against SQL Schema)
        for col in display_columns:
            if col not in clean_row or clean_row[col] is None or clean_row[col] == "":
                clean_row[col] = None
                errors.append(f"Missing: {col}")
                row_status = "INVALID"
        
        clean_row["_status"] = row_status
        clean_row["_errors"] = "; ".join(errors)
        validated_rows.append(clean_row)
        
    return {"schema": display_columns, "data": validated_rows}

# --- ENDPOINTS ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    path = os.path.join(UPLOAD_DIR, file.filename)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename}

@app.post("/extract")
async def extract(
    filename: str = Form(...),
    selection: str = Form(...)
):
    try:
        sel_dict = json.loads(selection)
        sel_obj = RegionSelection(**sel_dict)
        
        # Security: Ensure filename is just the name, not a path
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        
        table_name = LABEL_TO_TABLE.get(sel_obj.label)
        if not table_name:
            raise HTTPException(status_code=400, detail="Label not mapped to SQL table")
            
        # 1. Extract
        if sel_obj.use_ai:
            # AI Extraction Path
            with pdfplumber.open(file_path) as pdf:
                page = pdf.pages[sel_obj.page_number - 1]
                width, height = page.width, page.height
                x0 = max(0, min(sel_obj.x_pct * width, width))
                top = max(0, min(sel_obj.y_pct * height, height))
                x1 = max(x0, min((sel_obj.x_pct + sel_obj.w_pct) * width, width))
                bottom = max(top, min((sel_obj.y_pct + sel_obj.h_pct) * height, height))
                
                cropped = page.crop((x0, top, x1, bottom))
                text_content = cropped.extract_text()
                
            if not text_content or len(text_content.strip()) < 5:
                 return {"message": "Region is empty or unreadable", "raw_data": [], "sql_data": [], "schema": []}
                 
            raw_data = extract_with_gemini(text_content, table_name)
        else:
            # Standard Extraction Path
            raw_data = extract_from_region(file_path, sel_obj, use_raw_headers=True)
        
        if not raw_data:
            return {"message": "No data found in selection", "raw_data": [], "sql_data": [], "schema": []}

        # 2. Validate
        result = validate_data(raw_data, table_name)
        
        if "error" in result:
            return {"error": result["error"], "raw_data": raw_data, "sql_data": [], "schema": []}
        
        return {
            "raw_data": raw_data,
            "sql_data": result["data"],
            "schema": result["schema"]
        }
    except Exception as e:
        print(f"Extract endpoint error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@app.post("/save")
async def save_to_db(
    data: str = Form(...), 
    table_name: str = Form(...)
):
    try:
        rows = json.loads(data)
        if not rows:
             return {"message": "No data to save"}
             
        # Convert to DataFrame
        df = pd.DataFrame(rows)
        
        # Remove internal fields (_status, _errors)
        cols_to_drop = [c for c in df.columns if c.startswith("_")]
        df = df.drop(columns=cols_to_drop)
        
        # Insert into DB (append mode)
        df.to_sql(table_name, engine, if_exists='append', index=False, method='multi')
        
        return {"message": f"Successfully saved {len(df)} rows to {table_name}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

@app.post("/export")
async def export_csv(data: str = Form(...), table_name: str = Form(...)):
    """Exports ONLY valid rows to CSV matching SQL schema"""
    rows = json.loads(data)
    
    # Filter valid rows
    valid_rows = [r for r in rows if r.get('_status') == 'VALID']
    
    if not valid_rows:
        raise HTTPException(status_code=400, detail="No valid rows to export")
        
    df = pd.DataFrame(valid_rows)
    
    # Drop internal columns
    cols_to_drop = [c for c in df.columns if c.startswith("_")]
    df = df.drop(columns=cols_to_drop)
    
    # Ensure column order matches SQL schema
    schema = get_table_schema(table_name)
    # Add missing columns as empty
    for col in schema.keys():
        if col not in df.columns:
            df[col] = None
            
    # Reorder
    df = df[list(schema.keys())]
    
    output_path = os.path.join(UPLOAD_DIR, f"{table_name}_export.csv")
    df.to_csv(output_path, index=False)
    
    return FileResponse(output_path, filename=f"{table_name}.csv")

@app.post("/generate-template")
async def generate_template(table_name: str = Form(...)):
    """Generates a perfect PDF template for the given SQL table"""
    try:
        schema = get_table_schema(table_name)
        # Filter system columns
        cols = [k for k in schema.keys() if k.upper() not in IGNORED_COLUMNS]
        
        output_path = os.path.join(UPLOAD_DIR, f"{table_name}_template.pdf")
        doc = SimpleDocTemplate(output_path, pagesize=landscape(letter))
        elements = []
        
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Sample Report for {table_name}", styles['Title']))
        elements.append(Spacer(1, 20))
        
        # Create Dummy Data
        data = [cols] # Header
        dummy_row = [f"Test {c}" for c in cols] # Row 1
        data.append(dummy_row)
        
        t = Table(data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(t)
        
        doc.build(elements)
        return FileResponse(output_path, filename=f"{table_name}_template.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ========== NEW: DATABASE COMPARISON ENDPOINTS ==========

@app.post("/check-existence")
async def check_existence(data: str = Form(...), table_name: str = Form(...)):
    """Check if extracted data already exists in the database"""
    try:
        rows = json.loads(data)
        if not rows:
            return {"exists": [], "missing": rows, "message": "No data to check"}
        
        table_label = LABEL_TO_TABLE.get(table_name, table_name)
        
        # Get table schema
        schema = get_table_schema(table_label)
        
        # Primary keys to check
        from sqlalchemy import inspect, select
        insp = inspect(engine)
        pk_columns = insp.get_pk_constraint(table_label)['constrained_columns']
        
        exists_list = []
        missing_list = []
        
        with engine.connect() as conn:
            for row in rows:
                # Build WHERE clause for primary keys
                filter_dict = {col: row.get(col.upper()) or row.get(col) for col in pk_columns}
                
                # Query database
                from sqlalchemy import text
                where_clause = " AND ".join([f"{col} = '{filter_dict[col]}'" for col in pk_columns if filter_dict[col]])
                
                if where_clause:
                    query = f"SELECT * FROM {table_label} WHERE {where_clause}"
                    result = conn.execute(text(query))
                    db_row = result.fetchone()
                    
                    if db_row:
                        exists_list.append({"pdf_data": row, "db_data": dict(db_row._mapping)})
                    else:
                        missing_list.append(row)
                else:
                    missing_list.append(row)
        
        return {
            "exists": exists_list,
            "missing": missing_list,
            "total_checked": len(rows),
            "found_count": len(exists_list),
            "missing_count": len(missing_list)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/find-missing-values")
async def find_missing_values(data: str = Form(...), table_name: str = Form(...)):
    """Find missing/empty values in extracted data"""
    try:
        rows = json.loads(data)
        if not rows:
            return {"missing_values": {}}
        
        table_label = LABEL_TO_TABLE.get(table_name, table_name)
        schema = get_table_schema(table_label)
        
        missing_analysis = {}
        
        for idx, row in enumerate(rows):
            row_missing = {}
            for col in schema.keys():
                col_upper = col.upper()
                col_lower = col.lower()
                
                value = row.get(col_upper) or row.get(col_lower) or row.get(col)
                
                if not value or str(value).strip() == "":
                    row_missing[col] = "MISSING"
            
            if row_missing:
                missing_analysis[f"row_{idx}"] = row_missing
        
        return {
            "table": table_label,
            "total_rows": len(rows),
            "rows_with_missing": len(missing_analysis),
            "missing_details": missing_analysis
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scan-pdf-matches")
async def scan_pdf_matches(file: UploadFile = File(...), table_name: str = Form(...)):
    """Scan entire PDF and find all matches with database"""
    try:
        # Save file
        filename = file.filename
        file_path = os.path.join(UPLOAD_DIR, filename)
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        table_label = LABEL_TO_TABLE.get(table_name, table_name)
        
        # Get all data from PDF
        all_pdf_data = []
        with pdfplumber.open(file_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if not table:
                            continue
                        header_row = table[0]
                        valid_headers = {}
                        for idx, h in enumerate(header_row):
                            if h:
                                valid_headers[idx] = str(h).lower().replace(" ", "_").replace(".", "")
                        
                        for row in table[1:]:
                            row_data = {}
                            for idx, val in enumerate(row):
                                if idx in valid_headers:
                                    row_data[valid_headers[idx]] = val
                            if row_data:
                                row_data['_page'] = page_idx + 1
                                all_pdf_data.append(row_data)
        
        # Compare with database
        schema = get_table_schema(table_label)
        from sqlalchemy import inspect
        insp = inspect(engine)
        pk_columns = insp.get_pk_constraint(table_label)['constrained_columns']
        
        matches = []
        no_matches = []
        
        with engine.connect() as conn:
            for pdf_row in all_pdf_data:
                filter_dict = {col: pdf_row.get(col.upper()) or pdf_row.get(col) for col in pk_columns}
                where_clause = " AND ".join([f"{col} = '{filter_dict[col]}'" for col in pk_columns if filter_dict[col]])
                
                if where_clause:
                    from sqlalchemy import text
                    query = f"SELECT * FROM {table_label} WHERE {where_clause}"
                    result = conn.execute(text(query))
                    db_row = result.fetchone()
                    
                    if db_row:
                        matches.append({
                            "page": pdf_row.get('_page'),
                            "pdf_data": pdf_row,
                            "db_data": dict(db_row._mapping),
                            "status": "FOUND IN DATABASE"
                        })
                    else:
                        no_matches.append({
                            "page": pdf_row.get('_page'),
                            "data": pdf_row,
                            "status": "NOT IN DATABASE"
                        })
                else:
                    no_matches.append({
                        "page": pdf_row.get('_page'),
                        "data": pdf_row,
                        "status": "INCOMPLETE DATA"
                    })
        
        return {
            "filename": filename,
            "table": table_label,
            "total_records_found": len(all_pdf_data),
            "database_matches": len(matches),
            "no_matches": len(no_matches),
            "matches": matches,
            "no_matches_data": no_matches
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export-pdf")
async def export_pdf(data: str = Form(...), table_name: str = Form(...)):
    """Exports extraction results to a PDF report"""
    rows = json.loads(data)
    if not rows:
        raise HTTPException(status_code=400, detail="No data to export")
        
    output_path = os.path.join(UPLOAD_DIR, f"{table_name}_report.pdf")
    doc = SimpleDocTemplate(output_path, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    
    elements.append(Paragraph(f"Extraction Report: {table_name}", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Prepare Table Data
    # Get all keys from first row (schema)
    headers = [k for k in rows[0].keys() if not k.startswith("_")]
    table_data = [headers]
    
    for row in rows:
        table_data.append([str(row.get(k, "")) for k in headers])
        
    t = Table(table_data, repeatRows=1)
    t.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(t)
    doc.build(elements)
    return FileResponse(output_path, filename=f"{table_name}_report.pdf")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
