# Deployment Setup Guide

## Backend (Render)

### 1. Create PostgreSQL Database on Render
1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "PostgreSQL"
3. Set name: `well-completion-db`
4. Choose a region close to your users
5. Click "Create Database"
6. Copy the `Internal Database URL` (you'll need this)

### 2. Deploy Backend to Render
1. Push code to GitHub (ensure `render.yaml` and `requirements.txt` are committed)
2. Go to Render Dashboard → "New +" → "Web Service"
3. Connect your GitHub repository
4. Set the following:
   - **Name**: `well-completion-backend`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Root Directory**: `backend`

5. Add Environment Variables:
   ```
   DATABASE_URL=<paste your PostgreSQL internal URL from step 1>
   GEMINI_API_KEY=<your Google Gemini API key>
   FRONTEND_URL=https://<your-vercel-app>.vercel.app
   ```

6. Click "Create Web Service" and wait for deployment

7. Copy your Render service URL (e.g., `https://well-completion-backend.onrender.com`)

### 3. Initialize Database on Render
The `init_db()` function runs automatically on app startup and creates tables from `schema.sql`.

---

## Frontend (Vercel)

### 1. Deploy Frontend to Vercel
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click "Add New" → "Project"
3. Import your GitHub repository
4. Set the following:
   - **Framework**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

5. Add Environment Variables:
   ```
   VITE_API_URL=https://well-completion-backend.onrender.com
   ```
   (Use the Render backend URL from above)

6. Click "Deploy"

---

## Testing the Connection

1. Visit your Vercel frontend URL
2. Open browser DevTools (F12) → Console
3. You should see: `Using Backend URL: https://well-completion-backend.onrender.com`
4. Try uploading a file - check Network tab to verify API calls are going to the Render URL

---

## Troubleshooting

### Backend Issues
- **Check logs**: Render Dashboard → your service → "Logs"
- **Database connection fails**: Verify `DATABASE_URL` is correct
- **Missing GEMINI_API_KEY**: Add to Render environment variables

### Frontend Issues
- **API calls to localhost**: Check that `VITE_API_URL` is set in Vercel
- **CORS errors**: Backend CORS is configured for Vercel frontend
- **Build fails**: Ensure `npm run build` works locally first

### Quick Debug
- Backend: Visit `https://well-completion-backend.onrender.com/` - should show JSON message
- Frontend: Check browser console for API URL being used
