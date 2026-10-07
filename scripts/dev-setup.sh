#!/usr/bin/env bash
# =============================================================================
# scripts/dev-setup.sh
# Developer setup script for local development
# =============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🏭 Multi-Agent Document Processing Factory — Dev Setup"
echo "======================================================="

# ---- Step 1: Copy .env.example to .env if not present ---------------------
if [ ! -f ".env" ]; then
    echo "📋 Copying .env.example → .env"
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env and fill in your secrets before proceeding."
else
    echo "✅ .env already exists — skipping copy."
fi

# ---- Step 2: Create backend virtual environment ---------------------------
if [ ! -d "backend/.venv" ]; then
    echo "🐍 Creating Python virtual environment in backend/.venv"
    python3 -m venv backend/.venv
    echo "✅ Virtual environment created."
else
    echo "✅ Python virtual environment already exists."
fi

# ---- Step 3: Install backend dependencies ---------------------------------
echo "📦 Installing backend Python dependencies..."
backend/.venv/bin/pip install --upgrade pip --quiet
backend/.venv/bin/pip install -r backend/requirements.txt --quiet
echo "✅ Backend dependencies installed."

# ---- Step 4: Install frontend dependencies --------------------------------
echo "📦 Installing frontend Node.js dependencies..."
cd frontend && npm install --silent && cd ..
echo "✅ Frontend dependencies installed."

# ---- Step 5: Print next steps --------------------------------------------
echo ""
echo "======================================================="
echo "✅ Setup complete! Next steps:"
echo ""
echo "  Option A — Run everything with Docker:"
echo "    docker-compose up -d"
echo ""
echo "  Option B — Run services individually:"
echo "    # Terminal 1 (backend):"
echo "    cd backend && .venv/Scripts/activate  # Windows"
echo "    cd backend && source .venv/bin/activate  # macOS/Linux"
echo "    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "    # Terminal 2 (frontend):"
echo "    cd frontend && npm run dev"
echo ""
echo "  Run backend tests:"
echo "    cd backend && .venv/Scripts/pytest tests/ -v  # Windows"
echo "    cd backend && .venv/bin/pytest tests/ -v      # macOS/Linux"
echo ""
echo "  API available at: http://localhost:8000"
echo "  API docs at:      http://localhost:8000/docs"
echo "  Frontend at:      http://localhost:5173"
echo "======================================================="
