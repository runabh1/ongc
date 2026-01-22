# Pre-Deployment Checklist

## ✅ Code Changes Made

1. **Database Configuration** (`backend/database.py`)
   - Added support for PostgreSQL via `DATABASE_URL` environment variable
   - SQLite used as fallback for local development
   
2. **Render Configuration** (`backend/render.yaml`)
   - Set up deployment instructions for Python/FastAPI
   - Configured build and start commands
   
3. **Main Backend** (`backend/main.py`)
   - Added `python-dotenv` import for .env support
   - Updated CORS to allow Vercel frontend + localhost
   - Environment variable for `FRONTEND_URL` support
   
4. **Frontend Environment** (`.env.production`)
   - Template created for Vercel to use
   
5. **Requirements** (`backend/requirements.txt`)
   - Added `python-dotenv` for environment variable management

## 📋 What You Need To Do

### Step 1: Create PostgreSQL Database
- [ ] Go to https://dashboard.render.com
- [ ] Create a PostgreSQL database
- [ ] Copy the **Internal Database URL**

### Step 2: Deploy Backend to Render
- [ ] Push your code to GitHub (all changes are committed)
- [ ] Create a new Web Service on Render connected to your repo
- [ ] Set Root Directory to: `backend`
- [ ] Add environment variables:
  - `DATABASE_URL` = (from your PostgreSQL)
  - `GEMINI_API_KEY` = (your API key)
  - `FRONTEND_URL` = (your Vercel app URL - add after frontend is deployed)
- [ ] Deploy and get your backend URL

### Step 3: Deploy Frontend to Vercel
- [ ] Go to https://vercel.com/dashboard
- [ ] Import your GitHub repository
- [ ] Set Root Directory to: `frontend`
- [ ] Add environment variable:
  - `VITE_API_URL` = (your Render backend URL from Step 2)
- [ ] Deploy

### Step 4: Update Backend CORS (if needed)
- [ ] After frontend is deployed, add frontend URL to Render environment variable `FRONTEND_URL`

## 🧪 Testing

After deployment, test:
1. Visit your Vercel frontend URL
2. Open browser DevTools Console (F12)
3. Check that it says: `Using Backend URL: https://your-render-url.onrender.com`
4. Try uploading a PDF file
5. Check Network tab to verify API calls are working

## ❓ Common Issues

| Issue | Fix |
|-------|-----|
| Frontend stuck on localhost:8000 | Check `VITE_API_URL` env var in Vercel |
| Backend crashes on startup | Check `DATABASE_URL` is correct PostgreSQL string |
| CORS errors | Backend CORS configured for your Vercel domain |
| Database tables not created | Run Render build with PostgreSQL set up first |

See `DEPLOYMENT.md` for detailed troubleshooting.
