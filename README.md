# Well Completion Extractor & Database Validator

## Overview
This application is designed to digitize and validate ONGC Well Completion Reports. It allows users to extract structured data from PDF reports or images, compare it against an existing database to identify duplicates or new records, and ensure data quality before saving.

## Key Features

### 1. Data Extraction
- **Snipping Tool:** Manually select regions on a PDF page to extract tables or key-value pairs.
- **AI Extraction:** Toggle between robust manual parsing and AI-powered extraction using Google Gemini for complex or unstructured data.
- **Image Support:** Works with both digital PDFs and scanned image files.
- **Smart Fallback:** Automatically falls back to OCR or manual parsing if AI extraction fails.

### 2. Database Validation
- **🔍 Check Existence:** Compares extracted data against the database (using Primary Keys like UWI) to identify existing vs. new records.
- **⚠️ Find Missing Values:** Scans extracted rows for empty or incomplete fields to ensure data quality.
- **📄 Scan PDF Matches:** Automatically scans an entire PDF file to find all records and checks their status in the database (Matches vs. New).

### 3. Data Management
- **Save to Database:** Persist validated data into the system (PostgreSQL in production, SQLite in dev).
- **Export:** Download extracted data as CSV or generate PDF reports.
- **Schema Mapping:** Intelligent column mapping using LLM when PDF headers don't match database columns exactly.

## User Workflows

### Workflow 1: Check Incoming Report
1. **Upload:** Upload a PDF Report.
2. **Extract:** Use the Snipping Tool to select data.
3. **Check:** Click "🔍 Check Existence".
4. **Review:** See which records exist and which are new.
5. **Action:** Save new data or skip duplicates.

### Workflow 2: Quality Assurance
1. **Extract:** Snip data from the PDF.
2. **Validate:** Click "⚠️ Find Missing Values".
3. **Review:** Identify rows with missing fields.
4. **Fix:** Ensure data is complete before saving.

### Workflow 3: Bulk Report Validation
1. **Upload:** Upload a comprehensive PDF report.
2. **Scan:** Click "📄 Scan PDF Matches" (no manual extraction needed).
3. **Analyze:** View a summary of all records in the PDF vs. the Database.
4. **Identify:** See which pages contain new data vs. existing data.

## Tech Stack

### Frontend
- **Framework:** React with TypeScript
- **Styling:** Tailwind CSS
- **PDF Handling:** react-pdf
- **State Management:** React Hooks

### Backend
- **Framework:** FastAPI (Python)
- **Database:** PostgreSQL (Production), SQLite (Development)
- **ORM:** SQLAlchemy
- **AI/OCR:** Google Gemini API, Tesseract OCR, pdfplumber, Pillow

## Setup Instructions

### Prerequisites
- Python 3.8+
- Node.js 16+
- Tesseract OCR (optional, for local OCR fallback)

### Backend Setup
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   python main.py
   ```
   The server runs on `http://127.0.0.1:9000`.

### Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/extract` | Extract data from a selected region (Manual/AI). |
| `POST` | `/check-existence` | Check if extracted rows exist in the DB. |
| `POST` | `/save` | Save validated data to the database. |
| `POST` | `/upload` | Upload a PDF file for processing. |
| `POST` | `/export` | Export valid rows to CSV. |

## Database Schema
The application supports the following ONGC tables:
- `WCR_WELLHEAD`
- `WCR_CASING`
- `WCR_LOGSRECORD`
- `WCR_DIRSRVY`
- `WCR_SWC`
- `WCR_HCSHOWS`

## Deployment

### Backend (Render)
- Push changes to GitHub.
- Render automatically deploys the `backend` directory.
- Environment Variables: `DATABASE_URL`, `GEMINI_API_KEY`.

### Frontend (Vercel)
- Push changes to GitHub.
- Vercel automatically builds and deploys the `frontend` directory.

---
*Built for ONGC Well Completion Report digitization.*