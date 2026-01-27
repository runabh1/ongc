import os
import shutil
import json
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager
from collections import defaultdict
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
import pytesseract
import re
import google.generativeai as genai

from database import init_db, get_table_schema, engine
from sqlalchemy import inspect

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("DEBUG: Server starting up...")
    try:
        init_db()
        print("[OK] Database initialized")
    except Exception as e:
        print(f"[ERROR] Database init failed: {e}")
        import traceback
        traceback.print_exc()
    
    yield  # Server is running
    
    # Shutdown
    print("DEBUG: Server shutting down...")

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
    # Percentage based (Legacy/Default)
    x_pct: Optional[float] = 0.0
    y_pct: Optional[float] = 0.0
    w_pct: Optional[float] = 0.0
    h_pct: Optional[float] = 0.0
    # Pixel based (Snip Tool)
    x: Optional[float] = 0.0
    y: Optional[float] = 0.0
    width: Optional[float] = 0.0
    height: Optional[float] = 0.0
    view_width: Optional[float] = 0.0
    view_height: Optional[float] = 0.0
    label: str    # e.g., "CASING"
    use_ai: bool = False

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

# Configure pytesseract (handle common Windows/Linux/macOS installation paths)
TESSERACT_AVAILABLE = False

def setup_pytesseract():
    """Set up pytesseract path for different OS environments."""
    global TESSERACT_AVAILABLE
    if os.name == 'nt':  # Windows
        tesseract_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\Public\Tesseract-OCR\tesseract.exe"
        ]
        for path in tesseract_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                TESSERACT_AVAILABLE = True
                print(f"[OK] Tesseract found at: {path}")
                return
        print("[WARNING] Tesseract not found in common Windows paths")
    else:
        # Linux/macOS - check if tesseract is in PATH
        try:
            pytesseract.get_tesseract_version()
            TESSERACT_AVAILABLE = True
            print("[OK] Tesseract found in PATH")
        except pytesseract.TesseractNotFoundError:
            TESSERACT_AVAILABLE = False
            print("[WARNING] Tesseract not found in PATH")

setup_pytesseract()

# --- GEMINI LLM CONFIGURATION ---
GEMINI_API_KEY = "AIzaSyCQkOOEJRBnZIvh1YdEC8bedRFLxJ4f0NE"
genai.configure(api_key=GEMINI_API_KEY)

def parse_with_gemini(text: str, label: str) -> List[Dict]:
    """
    Uses Gemini LLM to parse unstructured text into structured JSON 
    matching the target table schema.
    """
    print(f"DEBUG: Parsing text with Gemini for label: {label}")
    table_name = LABEL_TO_TABLE.get(label)
    if not table_name:
        return []
        
    try:
        # Get schema to guide the LLM
        try:
            schema = get_table_schema(table_name)
            columns = ", ".join(schema.keys())
        except Exception:
            columns = "Infer columns from text"

        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        You are a data extraction assistant. Extract structured data from the following text.
        Target Table: {table_name}
        Expected Columns: {columns}
        
        Text Content:
        {text}
        
        Instructions:
        1. Return a JSON array of objects.
        2. Map extracted values to the expected columns where possible.
        3. If the text represents a table, extract all rows.
        4. If the text is key-value pairs, extract as a single object in the array.
        5. Return ONLY the JSON array. No markdown formatting.
        """
        
        response = model.generate_content(prompt)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(cleaned_text)
        return data if isinstance(data, list) else [data]
        
    except Exception as e:
        print(f"ERROR: Gemini parsing failed: {e}")
        return []

def parse_text_manually(text: str) -> List[Dict]:
    """
    Manually parse text into key-value pairs or table rows based on spacing.
    Used when AI extraction is disabled.
    """
    data = []
    lines = text.split('\n')
    kv_data = {}
    table_rows = []
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # Try to parse as key-value pair
        if ':' in line and len(line) < 100:
            parts = line.split(':', 1)
            k = parts[0].strip()
            v = parts[1].strip()
            if k and v and len(k) < 50:
                kv_data[k.lower().replace(" ", "_")] = v
        else:
            # Collect lines that might be table rows
            if len(line) > 5:
                table_rows.append(line)
    
    if kv_data:
        data.append(kv_data)
    
    if table_rows:
        for row_text in table_rows:
            # Split by multiple spaces to separate columns
            cells = [cell.strip() for cell in re.split(r'\s{2,}|\t', row_text) if cell.strip()]
            if len(cells) >= 2:
                row_dict = {f"col_{i}": cell for i, cell in enumerate(cells)}
                data.append(row_dict)
                
    return data

def get_canonical_bbox(
    page_w: float, page_h: float,
    view_w: float, view_h: float,
    sel_x: float, sel_y: float, sel_w: float, sel_h: float
) -> tuple:
    """
    Canonical function to convert UI pixel coordinates to Backend (PDF/Image) coordinates.
    
    CRITICAL LOGIC EXPLANATION:
    1. Coordinate Systems:
       - PDF Native: Origin is Bottom-Left.
       - pdfplumber/Image: Origin is Top-Left (abstracted).
       - Browser/UI: Origin is Top-Left.
       - We map UI (Top-Left) -> pdfplumber (Top-Left). 
       - Y-axis inversion is NOT performed manually because pdfplumber's .crop() 
         expects Top-Left coordinates (x0, top, x1, bottom).
    
    2. Trust Width Scaling:
       - Browsers often report incorrect view_height due to scrollbars, UI chrome, or CSS.
       - view_width is typically constrained by the container and is reliable.
       - If the calculated X and Y scales differ by > 2%, we assume the Y scale is 
         distorted and force it to match the X scale to preserve the selection's aspect ratio.
    """
    # 1. Validate View Dimensions
    if view_w <= 0 or view_h <= 0:
        # Fallback for legacy calls without view dims (assume 1:1 or percentage)
        return (0, 0, 0, 0)

    # 2. Calculate Scales
    scale_x = page_w / view_w
    scale_y = page_h / view_h

    # 3. Trust Width Logic (Override Height Scale if mismatch > 2%)
    if abs(scale_x - scale_y) / scale_x > 0.02:
        print(f"DEBUG: Scale mismatch (X: {scale_x:.4f}, Y: {scale_y:.4f}). Trusting Width.")
        scale_y = scale_x

    # 4. Transform Coordinates (Top-Left -> Top-Left)
    x0 = sel_x * scale_x
    top = sel_y * scale_y
    x1 = (sel_x + sel_w) * scale_x
    bottom = (sel_y + sel_h) * scale_y

    # 5. Clamp to Page Dimensions (Ensure valid bbox)
    x0 = max(0.0, min(x0, page_w))
    top = max(0.0, min(top, page_h))
    x1 = max(x0, min(x1, page_w))
    bottom = max(top, min(bottom, page_h))

    return (x0, top, x1, bottom)

def extract_with_ocr(pdf_path: str, sel: RegionSelection) -> List[Dict]:
    """Extract data from PDF using OCR with pytesseract - converts pages to images and applies OCR."""
    data = []
    try:
        print(f"DEBUG: Starting OCR extraction from {pdf_path}")
        
        # Check if tesseract is available
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError:
            print("WARNING: Tesseract not found - OCR extraction disabled, will fall back to pdfplumber")
            return []
        
        # USE PDFPLUMBER FOR CROPPING (Better coordinate handling)
        with pdfplumber.open(pdf_path) as pdf:
            if sel.page_number < 1 or sel.page_number > len(pdf.pages):
                print(f"DEBUG: Page {sel.page_number} out of range")
                return []
                
            page = pdf.pages[sel.page_number - 1]
            width, height = float(page.width), float(page.height)
            
            # Use Canonical Coordinate Transformation
            if sel.view_width and sel.view_width > 0:
                bbox = get_canonical_bbox(width, height, float(sel.view_width), float(sel.view_height),
                                          sel.x, sel.y, sel.width, sel.height)
            else:
                # Legacy Percentage Fallback
                bbox = (sel.x_pct * width, sel.y_pct * height, 
                        (sel.x_pct + sel.w_pct) * width, (sel.y_pct + sel.h_pct) * height)

            print(f"DEBUG: PDF Dimensions: {width}x{height}")
            print(f"DEBUG: Cropping bbox: {bbox}")
            
            if bbox[2] - bbox[0] <= 0 or bbox[3] - bbox[1] <= 0:
                return []
            
            # Crop the image to the selected region
            try:
                cropped_page = page.crop(bbox)
                # Convert crop to image (high res for OCR)
                # Resolution 600 provides better detail for small text/tables
                img = cropped_page.to_image(resolution=600).original # PIL Image

                # DEBUG: Save crop to verify alignment
                img.save("DEBUG_CROP.png")

                # --- Advanced Image Preprocessing for OCR ---
                # 1. Convert to grayscale
                img = img.convert('L')
                # 2. Upscale 2x using LANCZOS
                new_size = (img.width * 2, img.height * 2)
                img = img.resize(new_size, getattr(Image, 'Resampling', Image).LANCZOS)
            except Exception as e:
                print(f"DEBUG: Error cropping/converting page: {e}")
                return []
            
            # Apply OCR to the cropped image using pytesseract
            print("DEBUG: Applying pytesseract OCR to cropped region")
            # Config: OEM 3 (Default), PSM 6 (Block of text), Preserve spacing
            custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
            extracted_text = pytesseract.image_to_string(img, config=custom_config)
            
            if not extracted_text or not extracted_text.strip():
                print("DEBUG: No text extracted from OCR")
                return []
            
            print(f"DEBUG: OCR extracted text ({len(extracted_text)} chars)")
            
            if sel.use_ai:
                # Use Gemini for intelligent parsing
                gemini_data = parse_with_gemini(extracted_text, sel.label)
                if gemini_data:
                    print(f"DEBUG: Gemini extracted {len(gemini_data)} records from OCR text")
                    data.extend(gemini_data)
            else:
                # Use Manual parsing
                manual_data = parse_text_manually(extracted_text)
                if manual_data:
                    data.extend(manual_data)

            if not data:
                # Return empty so we can fallback to pdfplumber (which is better at tables)
                pass
    except Exception as e:
        print(f"OCR extraction error: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    return data

def extract_from_image(image_path: str, sel: RegionSelection, use_raw_headers: bool = False) -> List[Dict]:
    """Extract data from an image using pytesseract OCR."""
    data = []
    try:
        print(f"DEBUG: Starting image OCR extraction from {image_path}")
        
        # Check if tesseract is available
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError:
            print("WARNING: Tesseract not found - OCR extraction disabled for images")
            return []
        
        image = Image.open(image_path)
        width, height = image.size
        
        # Use Canonical Coordinate Transformation
        if sel.view_width and sel.view_width > 0:
            bbox = get_canonical_bbox(float(width), float(height), float(sel.view_width), float(sel.view_height),
                                      sel.x, sel.y, sel.width, sel.height)
        else:
            bbox = (sel.x_pct * width, sel.y_pct * height, 
                    (sel.x_pct + sel.w_pct) * width, (sel.y_pct + sel.h_pct) * height)
        
        x0, y0, x1, y1 = bbox
        
        print(f"DEBUG: Image dimensions: {width}x{height}")
        print(f"DEBUG: Crop box: ({x0}, {y0}, {x1}, {y1})")
        
        if x1 - x0 <= 0 or y1 - y0 <= 0:
            return []
        
        # Crop the image to the selected region
        cropped_image = image.crop((x0, y0, x1, y1))
        
        # DEBUG: Save crop
        cropped_image.save("DEBUG_CROP.png")

        # --- Advanced Image Preprocessing for OCR ---
        # 1. Convert to grayscale
        cropped_image = cropped_image.convert('L')
        # 2. Upscale 2x using LANCZOS
        new_size = (cropped_image.width * 2, cropped_image.height * 2)
        resample_method = getattr(Image, 'Resampling', Image).LANCZOS
        cropped_image = cropped_image.resize(new_size, resample_method)
        
        # Run pytesseract OCR on the cropped image
        print("DEBUG: Applying pytesseract OCR to image region")
        custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
        extracted_text = pytesseract.image_to_string(cropped_image, config=custom_config)
        
        if not extracted_text or not extracted_text.strip():
            print("DEBUG: No text extracted from OCR")
            return []
        
        print(f"DEBUG: OCR extracted text ({len(extracted_text)} chars)")
        
        if sel.use_ai:
            # Use Gemini for intelligent parsing
            gemini_data = parse_with_gemini(extracted_text, sel.label)
            if gemini_data:
                print(f"DEBUG: Gemini extracted {len(gemini_data)} records from Image")
                data.extend(gemini_data)
        else:
            # Use Manual parsing
            manual_data = parse_text_manually(extracted_text)
            if manual_data:
                data.extend(manual_data)
            else:
                data.append({"extracted_text": extracted_text[:1000], "_source": "ocr_raw"})
            
    except Exception as e:
        print(f"Image extraction error: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    return data

def extract_from_region(pdf_path: str, sel: RegionSelection, use_raw_headers: bool = False) -> List[Dict]:
    """Extract tables from ONLY the cropped region you selected."""
    data = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[sel.page_number - 1]
        width, height = page.width, page.height
        
        print(f"DEBUG: Page dimensions: {width}x{height}")
        
        # Use Canonical Coordinate Transformation
        if sel.view_width and sel.view_width > 0:
            bbox = get_canonical_bbox(float(width), float(height), float(sel.view_width), float(sel.view_height),
                                      sel.x, sel.y, sel.width, sel.height)
        else:
            bbox = (sel.x_pct * width, sel.y_pct * height, 
                    (sel.x_pct + sel.w_pct) * width, (sel.y_pct + sel.h_pct) * height)

        x0, top, x1, bottom = bbox
        print(f"DEBUG: Cropped bbox (clamped): ({x0}, {top}, {x1}, {bottom})")
        
        if x1 - x0 <= 1 or bottom - top <= 1:
            print("DEBUG: Selection too small")
            return []
        
        # Crop page and extract tables ONLY from that region
        cropped = page.crop(bbox)
        
        tables = []
        
        # 🎯 STRATEGY 1: Clustering (The "Industry-Grade" Fix for Casing)
        # Only apply if label suggests it's a casing table (or similar complex table)
        if "CASING" in sel.label.upper():
            try:
                print("DEBUG: Attempting specialized deterministic extraction for CASING")
                words = cropped.extract_words(use_text_flow=True, keep_blank_chars=False)
                
                if words:
                    # 🔧 Step 1: Lock column boundaries ONCE
                    # sort words by x center
                    words_sorted = sorted(words, key=lambda w: (w["x0"] + w["x1"]) / 2)
                    
                    # expected number of columns
                    NUM_COLS = 9
                    
                    if len(words_sorted) >= NUM_COLS:
                        # split into 9 roughly equal vertical slices
                        columns = [[] for _ in range(NUM_COLS)]
                        
                        for i, w in enumerate(words_sorted):
                            columns[i * NUM_COLS // len(words_sorted)].append(w)
                        
                        # compute column boundaries
                        col_bounds = []
                        for col in columns:
                            if col:
                                xs = [w["x0"] for w in col] + [w["x1"] for w in col]
                                col_bounds.append((min(xs), max(xs)))
                            else:
                                col_bounds.append((-1, -1))

                        # 🔧 Step 2: Assign every word to EXACTLY one column
                        def assign_column(word, col_bounds):
                            cx = (word["x0"] + word["x1"]) / 2
                            for i, (x0, x1) in enumerate(col_bounds):
                                if x0 == -1: continue
                                if x0 - 2 <= cx <= x1 + 2:
                                    return i
                            return None

                        for w in words:
                            w["col"] = assign_column(w, col_bounds)
                            
                        # 🔧 Step 3: Build rows using vertical overlap
                        def same_row(w1, w2, tol=4):
                            return not (
                                w1["bottom"] < w2["top"] - tol or
                                w2["bottom"] < w1["top"] - tol
                            )

                        rows = []
                        # Sort by top to process top-down
                        for w in sorted(words, key=lambda w: w["top"]):
                            placed = False
                            for row in rows:
                                if same_row(w, row[0]):
                                    row.append(w)
                                    placed = True
                                    break
                            if not placed:
                                rows.append([w])
                                
                        # 🔧 Step 4: Reconstruct rows column-by-column
                        # Sort rows by vertical position
                        rows.sort(key=lambda r: r[0]["top"])
                        
                        for row in rows:
                            row_cells = [""] * NUM_COLS
                            for col in range(NUM_COLS):
                                cell_words = [w for w in row if w.get("col") == col]
                                # Sort words in cell by x position
                                cell_words.sort(key=lambda w: w["x0"])
                                row_cells[col] = " ".join([w["text"] for w in cell_words]).strip()
                            table_data.append(row_cells)
                        
                        if table_data:
                            tables = [table_data]
                            print(f"DEBUG: Deterministic extraction found table with {len(table_data)} rows")
                    else:
                        print("DEBUG: Not enough words for column estimation")
            except Exception as e:
                print(f"DEBUG: Deterministic extraction failed: {e}")
                import traceback
                traceback.print_exc()

        # 🎯 STRATEGY 2: Standard pdfplumber extraction (Fallback)
        if not tables:
            try:
                tables = cropped.extract_tables(table_settings={
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "snap_tolerance": 5,
                    "min_words_vertical": 2,
                    "intersection_x_tolerance": 10
                })
                print(f"DEBUG: Found {len(tables) if tables else 0} tables in cropped region")
            except Exception as e:
                print(f"DEBUG: Error extracting tables: {e}")
                tables = []
        
        # Extract from first table found
        if tables:
            for table_idx, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue
                
                print(f"DEBUG: Processing table {table_idx}: {len(table)} rows x {len(table[0])} cols")
                
                # Get headers from first row
                header_row = table[0]
                headers = {}
                for col_idx, cell in enumerate(header_row):
                    if cell and str(cell).strip():
                        text = str(cell).strip()
                        headers[col_idx] = text if use_raw_headers else text.lower().replace(" ", "_").replace(".", "")
                
                print(f"DEBUG: Headers: {list(headers.values())}")
                
                if len(headers) < 2:
                    continue
                
                # Extract data rows
                for row in table[1:]:
                    row_dict = {}
                    for col_idx, cell in enumerate(row):
                        if col_idx in headers and cell and str(cell).strip():
                            row_dict[headers[col_idx]] = str(cell).strip()
                    
                    if row_dict:
                        data.append(row_dict)
                
                print(f"DEBUG: Extracted {len(data)} rows from table {table_idx}")
                
                if data:
                    return data
        
        # Fallback to text
        print("DEBUG: No tables in cropped region, trying text extraction")
        # layout=True preserves visual spacing better, crucial for regex splitting
        text = cropped.extract_text(layout=True)
        
        if text and text.strip():
            if sel.use_ai:
                # Use Gemini for intelligent parsing of the text region
                gemini_data = parse_with_gemini(text, sel.label)
                if gemini_data:
                    print(f"DEBUG: Gemini extracted {len(gemini_data)} records from PDF text")
                    data.extend(gemini_data)
            else:
                # Use Manual parsing
                manual_data = parse_text_manually(text)
                if manual_data:
                    data.extend(manual_data)
                else:
                    data.append({"raw_text": text[:2000], "_warning": "No table found - extracted text"})
    
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
            
            # 2. Fuzzy Match (Substring) - check if key contains SQL column name
            if not real_col_name:
                for sql_norm, sql_orig in sql_cols_normalized:
                    # Check if SQL column is inside Extracted Header (e.g. "FIELD" in "FIELDNAME")
                    if sql_norm in norm_key and len(sql_norm) > 2: 
                        real_col_name = sql_orig
                        break
            
            # 3. Smart semantic matching for common patterns
            if not real_col_name:
                key_lower = key.lower()
                # Pattern-based matching for common renamings
                if "type" in key_lower and ("casing" in schema.keys() or any("CASING_TYPE" in c for c in schema.keys())):
                    real_col_name = "CASING_TYPE"
                elif ("depth" in key_lower or "bottom" in key_lower) and "CASING_BOTTOM" in schema.keys():
                    real_col_name = "CASING_BOTTOM"
                elif ("top" in key_lower) and "CASING_TOP" in schema.keys():
                    real_col_name = "CASING_TOP"
                elif ("diameter" in key_lower or "od" in key_lower) and "OUTER_DIAMETER" in schema.keys():
                    real_col_name = "OUTER_DIAMETER"
                elif ("length" in key_lower or "grade" in key_lower) and "STEEL_GRADE" in schema.keys():
                    real_col_name = "STEEL_GRADE"
                elif ("material" in key_lower or "grade" in key_lower) and "MATERIAL_TYPE" in schema.keys():
                    real_col_name = "MATERIAL_TYPE"
            
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
        # Try native PDF extraction first (Best for tables in digital PDFs)
        print(f"DEBUG: Attempting native pdfplumber extraction")
        raw_data = extract_from_region(file_path, sel_obj, use_raw_headers=True)

        # Evaluate Native Result
        native_quality_low = False
        if not raw_data or len(raw_data) == 0:
            native_quality_low = True
        elif "_warning" in raw_data[0] or "_error" in raw_data[0]:
            # Fix 2: Only OCR if PDF has NO TEXT LAYER
            # If we have substantial text, assume digital PDF and accept the text result (don't OCR)
            raw_text = raw_data[0].get("raw_text", "")
            if len(raw_text.strip()) > 50:
                native_quality_low = False
            else:
                native_quality_low = True
        elif len(raw_data[0].keys()) < 2:
            # If we only found 1 column, native extraction probably failed to split columns
            native_quality_low = True
        
        # Fallback to OCR if native extraction yields nothing
        if not raw_data or len(raw_data) == 0:
            print(f"DEBUG: Native extraction returned no data, trying OCR")
            raw_data = extract_with_ocr(file_path, sel_obj)
        # Fallback to OCR if native extraction was poor
        if native_quality_low:
            print(f"DEBUG: Native extraction quality low, trying OCR")
            ocr_data = extract_with_ocr(file_path, sel_obj)
            # Use OCR data if it found something
            if ocr_data and len(ocr_data) > 0:
                raw_data = ocr_data
    
    if not raw_data:
        msg = "No data found in selection"
        if not TESSERACT_AVAILABLE:
            msg += " (OCR unavailable: Tesseract not found on server)"
        return {"message": msg, "raw_data": [], "sql_data": [], "schema": []}

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
    uvicorn.run(app, host="127.0.0.1", port=9000)
