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
from PIL import Image
import io
import base64

from database import init_db, get_table_schema, engine
from sqlalchemy import inspect

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Well Completion Extractor", lifespan=lifespan)

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# --- CONFIGURATION ---
LABEL_TO_TABLE = {
    "WELL_HEADER": "wcr_wellhead",
    "WCR_WELLHEAD": "wcr_wellhead",
    "CASING": "wcr_casing",
    "WCR_CASING": "wcr_casing",
    "LOGS": "wcr_logsrecord",
    "WCR_LOGSRECORD": "wcr_logsrecord",
    "DIRSRVY": "wcr_dirsrvy",
    "WCR_DIRSRVY": "wcr_dirsrvy",
    "SWC": "wcr_swc",
    "WCR_SWC": "wcr_swc",
    "HCSHOWS": "wcr_hcshows",
    "WCR_HCSHOWS": "wcr_hcshows"
}

# --- LOGIC ---

def extract_from_image(image_path: str, sel: RegionSelection, use_raw_headers: bool = False) -> List[Dict]:
    """Extract data from an image. Uses OCR if available, otherwise returns region info."""
    data = []
    try:
        image = Image.open(image_path)
        width, height = image.size
        
        # Convert normalized percentages to pixel coordinates
        x0 = max(0, min(int(sel.x_pct * width), width))
        y0 = max(0, min(int(sel.y_pct * height), height))
        x1 = max(x0, min(int((sel.x_pct + sel.w_pct) * width), width))
        y1 = max(y0, min(int((sel.y_pct + sel.h_pct) * height), height))
        
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            return []
        
        # Crop the image to the selected region
        cropped_image = image.crop((x0, y0, x1, y1))
        
        # Try OCR to extract text
        text = ""
        try:
            text = pytesseract.image_to_string(cropped_image)
        except Exception as ocr_error:
            # OCR failed - this is common if Tesseract is not installed
            print(f"OCR failed (Tesseract may not be installed): {ocr_error}")
            # Try to get text from image metadata or return a placeholder
            text = ""
        
        # If we got text from OCR, parse it
        if text and text.strip():
            # Try to parse as key-value pairs or tabular data
            kv_data = {}
            lines = text.split('\n')
            
            # First try to identify if it's a table (lines with multiple fields)
            is_table = False
            for line in lines:
                # Count separators that might indicate tabular data
                if '\t' in line or '  ' in line:
                    is_table = True
                    break
            
            if is_table:
                # Try to parse as table
                for line in lines:
                    if line.strip():
                        # Split by tabs or multiple spaces
                        parts = line.split('\t') if '\t' in line else line.split()
                        for i, part in enumerate(parts):
                            if part.strip():
                                kv_data[f"field_{i}"] = part.strip()
            else:
                # Parse as key-value pairs
                for line in lines:
                    if ':' in line:
                        parts = line.split(':', 1)
                        k = parts[0].strip()
                        v = parts[1].strip()
                        if k and v:
                            kv_data[k] = v
            
            if kv_data:
                data.append(kv_data)
            else:
                # No structured data found, return raw text
                data.append({"extracted_text": text})
        else:
            # No text extracted - return placeholder indicating region was empty
            data.append({"_warning": "No readable text found in selected region. Ensure the region contains visible text or use AI mode for better results."})
            
    except Exception as e:
        print(f"Image extraction error: {e}")
        data.append({"_error": f"Failed to process image: {str(e)}"})
    
    return data

def extract_from_region(pdf_path: str, sel: RegionSelection, use_raw_headers: bool = False) -> List[Dict]:
    data = []
    with pdfplumber.open(pdf_path) as pdf:
        # pdfplumber pages are 0-indexed
        page = pdf.pages[sel.page_number - 1]
        width, height = page.width, page.height
        
        print(f"DEBUG: Page dimensions: {width}x{height}")
        print(f"DEBUG: Selection (normalized): x_pct={sel.x_pct}, y_pct={sel.y_pct}, w_pct={sel.w_pct}, h_pct={sel.h_pct}")
        
        # Convert normalized percentages to PDF points and clamp to page bounds
        x0 = max(0, min(sel.x_pct * width, width))
        top = max(0, min(sel.y_pct * height, height))
        x1 = max(x0, min((sel.x_pct + sel.w_pct) * width, width))
        bottom = max(top, min((sel.y_pct + sel.h_pct) * height, height))
        
        bbox = (x0, top, x1, bottom)
        
        print(f"DEBUG: Cropped bbox: ({x0}, {top}, {x1}, {bottom})")
        print(f"DEBUG: Crop dimensions: {x1-x0} x {bottom-top}")
        
        if x1 - x0 <= 0 or bottom - top <= 0:
            return []
        
        # Crop the page to ONLY the selected region
        cropped = page.crop(bbox)
        
        # Get ONLY tables from the cropped region (not from full page)
        cropped_tables = cropped.extract_tables()
        
        print(f"DEBUG: Found {len(cropped_tables) if cropped_tables else 0} tables in cropped region")
        
        table_extracted = False
        
        if cropped_tables:
            # Process tables - prefer larger tables (more likely to be the main data)
            cropped_tables.sort(key=lambda t: len(t) * len(t[0]) if t and t[0] else 0, reverse=True)
            
            for table_idx, table in enumerate(cropped_tables):
                if not table or not table[0]: 
                    print(f"DEBUG: Skipping table {table_idx} - empty or no header")
                    continue
                
                print(f"DEBUG: Processing table {table_idx} with {len(table)} rows and {len(table[0])} cols")
                
                # Assume first row is header
                header_row = table[0]
                valid_headers = {} # index -> cleaned_name
                header_count = 0
                
                for idx, h in enumerate(header_row):
                    if h and str(h).strip():
                        if use_raw_headers:
                            valid_headers[idx] = str(h).strip()
                        else:
                            valid_headers[idx] = str(h).strip().lower().replace(" ", "_").replace(".", "")
                        header_count += 1
                
                print(f"DEBUG: Table {table_idx} has {header_count} valid headers")
                
                # Only process if we have reasonable headers (at least 2)
                if header_count < 2:
                    print(f"DEBUG: Skipping table {table_idx} - insufficient headers")
                    continue
                
                # Extract data rows
                rows_extracted = 0
                for row_idx, row in enumerate(table[1:]):
                    row_data = {}
                    for idx, val in enumerate(row):
                        if idx in valid_headers and val and str(val).strip():
                            row_data[valid_headers[idx]] = str(val).strip()
                    if row_data:
                        print(f"DEBUG: Extracted row {row_idx}: {row_data}")
                        data.append(row_data)
                        rows_extracted += 1
                        table_extracted = True
                
                print(f"DEBUG: Extracted {rows_extracted} rows from table {table_idx}")
                
                # If we successfully extracted data, use this table
                if rows_extracted > 0:
                    print(f"DEBUG: Using table {table_idx} - breaking out of loop")
                    break
        
        if not table_extracted:
            # Fallback: Extract text from cropped region only
            text = cropped.extract_text()
            
            print(f"DEBUG: No table found, attempting text extraction")
            print(f"DEBUG: Extracted text length: {len(text) if text else 0}")
            
            # Attempt simple KV parsing (e.g. "Field: Value")
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
                print(f"DEBUG: Found {len(kv_data)} key-value pairs")
                data.append(kv_data)
            else:
                print(f"DEBUG: No key-value pairs found, returning raw text warning")
                data.append({"raw_text": text if text else "No text found", "_warning": "No table structure detected in selected region"})
            
    return data

# System columns to ignore during validation/display so we don't flag them as missing
IGNORED_COLUMNS = {
    "ID", "MODEL", "INSERT_DATE", "MATCH_PERCENT", 
    "VECTOR_IDS", "PAGE_NUMBERS", "MATCH_ID"
}

def validate_data(data: List[Dict], table_name: str):
    try:
        schema = get_table_schema(table_name)
    except ValueError:
        return {"error": f"Table {table_name} not defined in SQL."}

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
        
        # Skip rows with only warnings or errors
        if "_warning" in row or "_error" in row:
            # Keep these special rows as-is
            clean_row = row.copy()
            clean_row["_status"] = "WARNING" if "_warning" in row else "ERROR"
            validated_rows.append(clean_row)
            continue
        
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
        
        # 2. Only mark as INVALID if we found actual data but have unknown columns
        # If we have data that maps to known columns, keep it as VALID
        # Missing columns should just be null
        if not clean_row and not errors:
            # Empty row
            row_status = "WARNING"
            errors.append("No data extracted")
        
        # Fill in missing columns with None
        for col in display_columns:
            if col not in clean_row:
                clean_row[col] = None
        
        clean_row["_status"] = row_status
        clean_row["_errors"] = "; ".join(errors) if errors else ""
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
    sel_dict = json.loads(selection)
    sel_obj = RegionSelection(**sel_dict)
    
    # Security: Ensure filename is just the name, not a path
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    table_name = LABEL_TO_TABLE.get(sel_obj.label)
    if not table_name:
        raise HTTPException(status_code=400, detail="Label not mapped to SQL table")
    
    # Determine if file is an image or PDF
    is_image = safe_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.tif', '.webp', '.bmp', '.gif'))
    
    # Extract based on file type
    if is_image:
        raw_data = extract_from_image(file_path, sel_obj, use_raw_headers=True)
    else:
        raw_data = extract_from_region(file_path, sel_obj, use_raw_headers=True)
    
    if not raw_data:
        return {"message": "No data found in selection", "raw_data": [], "sql_data": [], "schema": []}

    # Validate
    result = validate_data(raw_data, table_name)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return {
        "raw_data": raw_data,
        "sql_data": result["data"],
        "schema": result["schema"]
    }

@app.post("/check-existence")
async def check_existence(
    data: str = Form(...),
    table_name: str = Form(...)
):
    try:
        rows = json.loads(data)
        if not rows:
            return {"exists": [], "new": []}
            
        # Convert to DataFrame for easier handling
        input_df = pd.DataFrame(rows)
        # Drop internal columns
        input_df = input_df.drop(columns=[c for c in input_df.columns if c.startswith("_")], errors='ignore')
        
        if input_df.empty:
             return {"exists": [], "new": rows}

        with engine.connect() as conn:
            # Check if table exists
            inspector = inspect(engine)
            if not inspector.has_table(table_name):
                return {"exists": [], "new": rows}

            # Read existing data
            # Optimization: If UWI is present, filter by UWI to reduce data load
            query = f"SELECT * FROM {table_name}"
            if "UWI" in input_df.columns:
                unique_uwis = [str(u) for u in input_df["UWI"].unique() if u]
                if unique_uwis:
                    uwis_str = "', '".join(unique_uwis)
                    query += f" WHERE \"UWI\" IN ('{uwis_str}')"
            
            existing_df = pd.read_sql(query, conn)
            
        if existing_df.empty:
            return {"exists": [], "new": rows}

        # Identify common columns for comparison
        common_cols = list(set(existing_df.columns) & set(input_df.columns))
        if not common_cols:
             return {"exists": [], "new": rows}

        # Create signatures for comparison (concat all common values)
        existing_sigs = existing_df[common_cols].astype(str).agg('-'.join, axis=1)
        input_sigs = input_df[common_cols].astype(str).agg('-'.join, axis=1)
        
        exists_mask = input_sigs.isin(existing_sigs)
        
        exists_rows = []
        new_rows = []
        
        for i, is_exist in enumerate(exists_mask):
            if is_exist:
                exists_rows.append(rows[i])
            else:
                new_rows.append(rows[i])
                
        return {"exists": exists_rows, "new": new_rows}

    except Exception as e:
        print(f"Check Error: {e}")
        # Fallback: assume all new if check fails
        return {"exists": [], "new": json.loads(data)}

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
