# Production Deployment Guide: Vercel + Render
### Multi-Agent Document Processing Factory

This guide covers the public cloud deployment of the Multi-Agent Document Processing Factory:
- **Frontend SPA:** Deployed on **Vercel** (Free Tier)
- **Backend API:** Deployed on **Render** (Free Web Service)
- **Source Control:** **GitHub**

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │             Vercel Edge              │
                      │   React + TypeScript + Vite SPA     │
                      │     (Public HTTPS User Access)       │
                      └──────────────────┬───────────────────┘
                                         │
                         HTTPS API Calls │ VITE_API_BASE_URL
                                         ▼
                      ┌──────────────────────────────────────┐
                      │              Render                  │
                      │    FastAPI Application Container     │
                      │   - Tesseract OCR Engine             │
                      │   - LangGraph Multi-Agent Workflows  │
                      │   - Health & Document APIs           │
                      └──────────────┬───────────────┬───────┘
                                     │               │
                     Managed Postgres│               │ HTTPS API
                   (Render / Neon /  │               │
                       Supabase)     ▼               ▼
                           ┌──────────────┐   ┌──────────────┐
                           │  PostgreSQL  │   │  OpenAI API  │
                           │  + pgvector  │   │   (Cloud LLM │
                           │              │   │ & Embeddings)│
                           └──────────────┘   └──────────────┘
```

---

## Comparison: Local Docker vs. Public Cloud Deployment

| Component | Local Docker Compose | Public Vercel + Render Deployment |
| :--- | :--- | :--- |
| **Frontend** | Nginx container on `http://localhost:5173` | Vercel SPA on `https://<your-app>.vercel.app` |
| **Backend** | FastAPI container on `http://localhost:8000` | Render Docker Web Service on `https://<your-app>.onrender.com` |
| **Database** | Docker container `pgvector/pgvector:pg16` | Cloud PostgreSQL (Render Managed DB, Neon, or Supabase) |
| **LLM Provider** | Local Ollama (`llama3.2:3b`) on host | Cloud OpenAI (`LLM_PROVIDER=openai`) |
| **Orchestration** | Temporal + Redis local containers | Modular FastAPI workflows / Cloud endpoints |

---

## Step-by-Step Deployment Instructions

### Step 1: Push Repository to GitHub

1. Initialize git and commit your files (if not already done):
   ```bash
   git init
   git add .
   git commit -m "feat: prepare repository for Vercel and Render deployment"
   ```
2. Create a GitHub repository and push your branch:
   ```bash
   git remote add origin https://github.com/<your-username>/multi-agent-document-processing-factory.git
   git branch -M main
   git push -u origin main
   ```

---

### Step 2: Deploy Backend on Render

1. Log into your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** $\rightarrow$ **Web Service**.
3. Connect your GitHub repository.
4. Configure the Web Service:
   - **Name:** `docfactory-backend` (or your preferred name)
   - **Region:** Choose the region closest to your users (e.g., Oregon or Frankfurt).
   - **Runtime / Environment:** **Docker**
   - **Dockerfile Path:** `./backend/Dockerfile`
   - **Docker Context:** `./backend`
   - **Instance Type:** **Free**
   - **Health Check Path:** `/health`
5. Alternatively, if using the Render Blueprint:
   - Click **New +** $\rightarrow$ **Blueprint** and select your repository. Render will automatically read [render.yaml](file:///c:/Users/yogya/OneDrive/Documents/multi-agent-document-processing-factory/render.yaml).

---

### Step 3: Configure Render Environment Variables

In your Render service settings, configure the following environment variables:

| Environment Variable | Recommended Value | Description |
| :--- | :--- | :--- |
| `APP_ENV` | `production` | Enables production mode and structured logging. |
| `LOG_LEVEL` | `INFO` | Application log verbosity. |
| `SECRET_KEY` | *(Generate a 32+ character random string)* | Cryptographic signing key. |
| `LLM_PROVIDER` | `openai` | Switches from local Ollama to cloud OpenAI provider. |
| `OPENAI_API_KEY` | `sk-...` | Your OpenAI API key for classification, extraction, and RAG. |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host/db` | Connection string from your managed PostgreSQL instance. |
| `REDIS_URL` | *(Optional / Leave blank)* | Cloud Redis URL. If omitted, status caching falls back to Postgres. |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed origins (will be augmented with Vercel URL in Step 6). |
| `CORS_ORIGIN_REGEX`| `https://.*\.vercel\.app` | Permits all Vercel production and preview deployments. |

Click **Save Changes** and allow Render to build and deploy your container.

---

### Step 4: Deploy Frontend on Vercel

1. Log into your [Vercel Dashboard](https://vercel.com).
2. Click **Add New...** $\rightarrow$ **Project**.
3. Import your GitHub repository.
4. Configure Project Settings:
   - **Framework Preset:** **Vite**
   - **Root Directory:** Click **Edit** and select `frontend`.
   - **Build Command:** `npm run build` (or `tsc -b && vite build`)
   - **Output Directory:** `dist`
   - **Install Command:** `npm install`
5. Configure Environment Variables:
   - Name: `VITE_API_BASE_URL`
   - Value: `https://<your-render-service-name>.onrender.com` *(your Render backend URL from Step 3, without trailing slash)*
6. Click **Deploy**.

---

### Step 5: Finalize Backend CORS Configuration

Once Vercel assigns your production URL (e.g. `https://multi-agent-factory.vercel.app`):
1. Return to your Render Dashboard $\rightarrow$ **docfactory-backend** $\rightarrow$ **Environment**.
2. Add or update:
   ```env
   FRONTEND_URL=https://multi-agent-factory.vercel.app
   ```
   *(Or append to `CORS_ORIGINS`: `http://localhost:5173,https://multi-agent-factory.vercel.app`)*
3. Render will automatically redeploy the backend with the new allowed origin.

---

### Step 6: Post-Deployment Verification

1. **Verify Backend Liveness:**
   ```bash
   curl -i https://<your-render-service-name>.onrender.com/health
   ```
   Expected response: `HTTP/2 200 OK` with `{"status":"healthy"}`.
2. **Verify Frontend Application:**
   Open `https://<your-app>.vercel.app` in your browser.
   - Confirm the Document Factory Dashboard loads.
   - Verify the health badge or status indicator connects cleanly without CORS errors in the browser console.
   - Upload a test PDF document (invoice, certificate, receipt) and verify OCR and multi-agent extraction pipeline execution.
