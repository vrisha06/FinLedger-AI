# FinLedger-AI — Local Setup Script (Windows)
# Run from repository root: .\scripts\setup_postgres_local.ps1
# Requires PostgreSQL 16+ running locally, Python 3.12+ and Node.js 20+.
# Safe to re-run: every step is idempotent.

$ErrorActionPreference = 'Stop'

function Invoke-Step([string]$Label, [scriptblock]$Command) {
    Write-Host $Label -ForegroundColor Yellow
    & $Command
    # Native tools report failure through exit codes, which -ErrorAction does not catch
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  -> Failed (exit code $LASTEXITCODE). Fix the error above and re-run." -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " FinLedger-AI Local Setup" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Environment file
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[1/8] Created .env from .env.example." -ForegroundColor Yellow
    Write-Host "  -> Set DB_PASSWORD and SECRET_KEY in .env, then re-run this script." -ForegroundColor Yellow
    exit 1
}
Write-Host "[1/8] Found .env." -ForegroundColor Green

# 2. Python virtual environment
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Invoke-Step "[2/8] Creating Python virtual environment in .venv..." { python -m venv .venv }
} else {
    Write-Host "[2/8] Virtual environment ready." -ForegroundColor Green
}

# 3. Backend dependencies
Invoke-Step "[3/8] Installing backend dependencies..." { .\.venv\Scripts\pip.exe install -r backend\requirements.txt --quiet }

# 4. Databases must exist before migrations; seeding must wait until tables exist
Invoke-Step "[4/8] Creating finledger and finledger_test databases if missing..." { .\.venv\Scripts\python.exe backend\scripts\init_db.py --create-only }

# 5. Schema, triggers and constraints on both databases
Invoke-Step "[5/8] Running Alembic migrations (development)..." { .\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head }
Invoke-Step "[5/8] Running Alembic migrations (test)..." { .\.venv\Scripts\alembic.exe -c backend\alembic.ini -x db=test upgrade head }

# 6. Clearing account, demo users and product catalogue
Invoke-Step "[6/8] Seeding clearing account..." { .\.venv\Scripts\python.exe backend\scripts\init_db.py --seed-only }
Invoke-Step "[6/8] Seeding demo users..." { .\.venv\Scripts\python.exe backend\scripts\seed_users.py }
Invoke-Step "[6/8] Seeding financial products..." { .\.venv\Scripts\python.exe backend\scripts\seed_products.py }

# 7. Fraud model (the trained artifact is not committed; without it scoring uses the rule baseline)
Push-Location backend
try {
    if (Test-Path "ml\artifacts\model.joblib") {
        Write-Host "[7/8] Fraud model already trained (backend\ml\artifacts\model.joblib)." -ForegroundColor Green
    } else {
        Invoke-Step "[7/8] Training the Random Forest fraud model (about a minute)..." { ..\.venv\Scripts\python.exe -m ml.train --count 10000 }
    }
} finally {
    Pop-Location
}

# 8. Frontend dependencies
Push-Location frontend
try {
    Invoke-Step "[8/8] Installing frontend dependencies..." { npm install --no-fund --no-audit }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Setup complete." -ForegroundColor Green
Write-Host "  API:      cd backend; ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000" -ForegroundColor Green
Write-Host "  Frontend: cd frontend; npm run dev   (http://localhost:5173)" -ForegroundColor Green
Write-Host "  Sign in:  rahul_sharma / priya_investigator / admin_system, password Password123!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
