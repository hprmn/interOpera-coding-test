# Setup Guide - Fund Performance Analysis System

Complete guide for configuring and running the Fund Performance Analysis System.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [Docker Setup](#docker-setup)
4. [Running the Application](#running-the-application)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)
7. [Development Workflow](#development-workflow)

---

## Prerequisites

### Required Software

1. **Docker & Docker Compose**
   - Docker Desktop 20.10+ (recommended)
   - Docker Compose v2.0+

   **Installation:**
   - **Mac**: `brew install --cask docker`
   - **Windows**: Download from [docker.com](https://www.docker.com/products/docker-desktop/)
   - **Linux**:
     ```bash
     curl -fsSL https://get.docker.com -o get-docker.sh
     sh get-docker.sh
     ```

2. **Git**
   ```bash
   # Verify installation
   git --version
   ```

3. **OpenAI API Key** (or alternative LLM provider)
   - Get from: https://platform.openai.com/api-keys
   - Alternative: Use Google Gemini (free tier) - see [Free LLM Options](#alternative-llm-providers)

### System Requirements

- **RAM**: Minimum 8GB (16GB recommended)
- **Disk Space**: 5GB free space
- **OS**: macOS, Windows 10+, or Linux (Ubuntu 20.04+)

---

## Environment Setup

### Step 1: Clone Repository

```bash
git clone <your-repo-url>
cd interOpera-coding-test
```

### Step 2: Create Environment File

Create a `.env` file in the project root:

```bash
# Copy from example (if exists)
cp .env.example .env

# Or create manually
touch .env
```

### Step 3: Configure Environment Variables

Edit `.env` file with your settings:

```env
# === REQUIRED: LLM API Keys ===
OPENAI_API_KEY=sk-your-openai-api-key-here

# === OPTIONAL: Alternative LLM Providers ===
# Uncomment if using Google Gemini instead of OpenAI
# GOOGLE_API_KEY=your-gemini-api-key-here
# LLM_PROVIDER=gemini

# === Database Configuration (Auto-configured by Docker) ===
# These are set automatically in docker-compose.yml
# DATABASE_URL=postgresql://funduser:fundpass@postgres:5432/funddb
# REDIS_URL=redis://redis:6379/0

# === Application Settings ===
# Upload directory (auto-created)
UPLOAD_DIR=/app/uploads

# Maximum upload file size (50MB)
MAX_UPLOAD_SIZE=52428800

# === Vector Store Settings ===
# Embedding model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Text chunking
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Similarity search
TOP_K_RESULTS=5
SIMILARITY_THRESHOLD=0.7

# === LLM Settings ===
LLM_MODEL=gpt-4-turbo-preview
LLM_TEMPERATURE=0

# === Development Settings ===
# Set to "development" for auto-reload
ENVIRONMENT=development
```

### Step 4: Verify Configuration

```bash
# Check .env file exists
ls -la .env

# View contents (without exposing keys)
grep -v "API_KEY" .env
```

---

## Docker Setup

### Architecture Overview

The application uses 4 Docker containers:

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│  Frontend (Next.js)          Backend (FastAPI)     │
│  Port: 3000                  Port: 8000            │
│                                                     │
└──────────────┬──────────────────────┬───────────────┘
               │                      │
       ┌───────▼──────┐      ┌───────▼──────┐
       │              │      │              │
       │  PostgreSQL  │      │    Redis     │
       │  (pgvector)  │      │  (Optional)  │
       │  Port: 5432  │      │  Port: 6379  │
       │              │      │              │
       └──────────────┘      └──────────────┘
```

### Container Details

1. **postgres** (pgvector/pgvector:pg15)
   - PostgreSQL 15 with pgvector extension
   - Stores: Funds, Transactions, Documents, Vector Embeddings
   - Volume: `postgres_data` (persistent)

2. **redis** (redis:7-alpine)
   - In-memory cache and task queue
   - Used for: Conversation history (future), Task queue (future)
   - Volume: `redis_data` (persistent)

3. **backend** (FastAPI)
   - Python 3.11+ with FastAPI
   - Automatic reload on code changes
   - Volume: `./backend:/app` (live code sync)

4. **frontend** (Next.js 14)
   - Node.js with Next.js App Router
   - Automatic reload on code changes
   - Volume: `./frontend:/app` (live code sync)

### Build Process

Docker will automatically:
1. Build images from Dockerfiles
2. Install dependencies (Python packages, npm packages)
3. Initialize database with pgvector extension
4. Create database tables
5. Start all services

---

## Running the Application

### Quick Start (Recommended)

```bash
# Start all services
docker-compose up -d

# View logs (all services)
docker-compose logs -f

# View logs (specific service)
docker-compose logs -f backend
```

**First Run:** Initial build takes 3-5 minutes (downloads images, installs dependencies).

### Step-by-Step Start

1. **Start Database First (Optional)**
   ```bash
   docker-compose up -d postgres redis

   # Wait for healthy status
   docker-compose ps
   ```

2. **Start Backend**
   ```bash
   docker-compose up -d backend

   # Check logs
   docker-compose logs -f backend

   # Wait for: "Application startup complete"
   ```

3. **Start Frontend**
   ```bash
   docker-compose up -d frontend

   # Check logs
   docker-compose logs -f frontend

   # Wait for: "ready - started server on 0.0.0.0:3000"
   ```

### Alternative: Run with Build

Force rebuild images (use after dependency changes):

```bash
docker-compose up --build -d
```

### Stopping the Application

```bash
# Stop all services (preserves data)
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

---

## Verification

### 1. Check Service Health

```bash
# View running containers
docker-compose ps

# Expected output:
# NAME            STATUS        PORTS
# fund-postgres   Up (healthy)  0.0.0.0:5432->5432/tcp
# fund-redis      Up (healthy)  0.0.0.0:6379->6379/tcp
# fund-backend    Up            0.0.0.0:8000->8000/tcp
# fund-frontend   Up            0.0.0.0:3000->3000/tcp
```

### 2. Test Backend API

```bash
# Health check
curl http://localhost:8000/health

# Expected: {"status":"healthy"}

# API documentation
open http://localhost:8000/docs
```

### 3. Test Frontend

```bash
# Open in browser
open http://localhost:3000

# Expected: Homepage with navigation
```

### 4. Test Database Connection

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U funduser -d funddb

# Inside psql:
\dt                    # List tables
SELECT * FROM funds;   # Query funds table
\q                     # Exit
```

### 5. Test End-to-End Upload

```bash
# Create a test fund
curl -X POST http://localhost:8000/api/funds \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Fund", "gp_name": "Test GP", "vintage_year": 2023}'

# Upload sample PDF
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@files/Sample_Fund_Performance_Report1.pdf" \
  -F "fund_id=1"

# Expected: {"document_id": 1, "status": "pending", ...}

# Wait 10-15 seconds for processing

# Check status
curl http://localhost:8000/api/documents/1/status

# Expected: {"status": "completed", ...}
```

---

## Troubleshooting

### Common Issues

#### 1. Port Already in Use

**Error:** `Bind for 0.0.0.0:3000 failed: port is already allocated`

**Solution:**
```bash
# Check what's using the port
lsof -i :3000
lsof -i :8000
lsof -i :5432

# Kill the process (replace PID)
kill -9 <PID>

# Or change port in docker-compose.yml
```

#### 2. Database Connection Failed

**Error:** `could not connect to server: Connection refused`

**Solution:**
```bash
# Check postgres is healthy
docker-compose ps postgres

# Restart postgres
docker-compose restart postgres

# Check logs
docker-compose logs postgres

# Manually initialize pgvector
docker-compose exec postgres psql -U funduser -d funddb -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 3. Backend Won't Start

**Error:** `ModuleNotFoundError: No module named 'fastapi'`

**Solution:**
```bash
# Rebuild backend
docker-compose up --build backend

# Check Dockerfile
cat backend/Dockerfile

# Manually install in running container
docker-compose exec backend pip install -r requirements.txt
```

#### 4. Frontend Build Errors

**Error:** `Module not found: Can't resolve '@/lib/api'`

**Solution:**
```bash
# Rebuild frontend
docker-compose up --build frontend

# Clear Next.js cache
docker-compose exec frontend rm -rf .next

# Reinstall dependencies
docker-compose exec frontend npm install
```

#### 5. File Upload Fails

**Error:** `Permission denied: /app/uploads`

**Solution:**
```bash
# Fix permissions
docker-compose exec backend mkdir -p /app/uploads
docker-compose exec backend chmod 777 /app/uploads

# Check volume
docker volume inspect interopera-coding-test_backend_uploads
```

#### 6. OpenAI API Errors

**Error:** `AuthenticationError: Incorrect API key`

**Solution:**
```bash
# Verify .env file
cat .env | grep OPENAI_API_KEY

# Format should be: OPENAI_API_KEY=sk-...

# Restart backend to load new env
docker-compose restart backend

# Alternative: Use free Gemini API
# Add to .env:
# GOOGLE_API_KEY=your-key
# LLM_PROVIDER=gemini
```

#### 7. pgvector Extension Missing

**Error:** `extension "vector" does not exist`

**Solution:**
```bash
# Initialize manually
docker-compose exec postgres psql -U funduser -d funddb

# In psql:
CREATE EXTENSION IF NOT EXISTS vector;
\dx  # Verify extension installed
\q

# Or use init script
docker-compose exec backend python -c "
from app.services.vector_store import VectorStore
from app.db.session import SessionLocal
vs = VectorStore(SessionLocal())
print('Vector store initialized')
"
```

### Performance Issues

#### Slow Document Processing

**Symptom:** PDF upload takes > 30 seconds

**Solutions:**
```bash
# Check resource usage
docker stats

# Increase Docker resources (Docker Desktop > Settings > Resources)
# Recommended: 4 CPU, 8GB RAM

# Check backend logs for errors
docker-compose logs backend | grep -i error

# Monitor processing
docker-compose logs -f backend | grep "Document processing"
```

#### Slow Chat Responses

**Symptom:** Chat queries take > 10 seconds

**Solutions:**
```bash
# Check LLM provider performance
# OpenAI: Usually fast (1-3s)
# Gemini: Free tier can be slow

# Switch to faster model in .env:
LLM_MODEL=gpt-3.5-turbo  # Faster than gpt-4

# Check vector search performance
curl http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "fund_id": 1}' \
  -w "\nTime: %{time_total}s\n"
```

### Debugging Tools

#### View Container Logs

```bash
# All logs
docker-compose logs

# Last 100 lines
docker-compose logs --tail=100

# Follow logs (real-time)
docker-compose logs -f backend

# Search logs
docker-compose logs backend | grep -i error
```

#### Access Container Shell

```bash
# Backend (Python)
docker-compose exec backend bash
python -c "from app.db.session import SessionLocal; print('DB OK')"

# Frontend (Node)
docker-compose exec frontend sh
npm list next

# Database (PostgreSQL)
docker-compose exec postgres psql -U funduser -d funddb
```

#### Inspect Volumes

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect interopera-coding-test_postgres_data

# Backup volume
docker run --rm -v interopera-coding-test_postgres_data:/data \
  -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz /data
```

---

## Development Workflow

### Making Code Changes

#### Backend Changes (Python)

1. **Edit files** in `./backend/app/`
2. **Auto-reload** happens automatically (uvicorn --reload)
3. **No restart needed** for most changes

```bash
# Edit a service
nano backend/app/services/query_engine.py

# Watch logs for reload
docker-compose logs -f backend

# Expected: "Detected file change, reloading..."
```

**When to restart:**
- Changed `requirements.txt` → `docker-compose up --build backend`
- Changed environment variables → `docker-compose restart backend`
- Changed Dockerfile → `docker-compose up --build backend`

#### Frontend Changes (TypeScript/React)

1. **Edit files** in `./frontend/app/` or `./frontend/components/`
2. **Auto-reload** happens automatically (Next.js dev server)
3. **No restart needed**

```bash
# Edit a page
nano frontend/app/chat/page.tsx

# Browser auto-refreshes
```

**When to restart:**
- Changed `package.json` → `docker-compose exec frontend npm install && docker-compose restart frontend`
- Changed `next.config.js` → `docker-compose restart frontend`

#### Database Schema Changes

```bash
# 1. Edit model
nano backend/app/models/fund.py

# 2. Drop and recreate tables (DEVELOPMENT ONLY - deletes data!)
docker-compose exec backend python -c "
from app.db.base import Base
from app.db.session import engine
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
print('Database reset complete')
"

# 3. Or use Alembic migrations (PRODUCTION)
# (Not configured yet - would need setup)
```

### Running Tests

```bash
# Backend tests
docker-compose exec backend pytest tests/ -v

# With coverage
docker-compose exec backend pytest --cov=app tests/

# Specific test file
docker-compose exec backend pytest tests/test_metrics.py -v

# Frontend tests (if configured)
docker-compose exec frontend npm test
```

### Accessing Services

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | - |
| Backend API | http://localhost:8000 | - |
| API Docs (Swagger) | http://localhost:8000/docs | - |
| API Docs (ReDoc) | http://localhost:8000/redoc | - |
| PostgreSQL | localhost:5432 | user: funduser, pass: fundpass, db: funddb |
| Redis | localhost:6379 | - |

### Database Management

#### Backup Database

```bash
# Dump database
docker-compose exec postgres pg_dump -U funduser funddb > backup.sql

# Restore database
cat backup.sql | docker-compose exec -T postgres psql -U funduser funddb
```

#### Reset Database

```bash
# WARNING: Deletes all data!
docker-compose down -v
docker-compose up -d
```

#### Query Database

```bash
# Via psql
docker-compose exec postgres psql -U funduser -d funddb

# Common queries:
\dt                                    # List tables
SELECT * FROM funds;                   # All funds
SELECT * FROM capital_calls LIMIT 10;  # Recent calls
SELECT COUNT(*) FROM document_embeddings;  # Vector count

# Via Python
docker-compose exec backend python
>>> from app.db.session import SessionLocal
>>> from app.models.fund import Fund
>>> db = SessionLocal()
>>> funds = db.query(Fund).all()
>>> for f in funds: print(f.name)
```

---

## Alternative LLM Providers

### Google Gemini (Free)

1. **Get API Key:** https://makersuite.google.com/app/apikey

2. **Update .env:**
   ```env
   GOOGLE_API_KEY=your-gemini-key
   LLM_PROVIDER=gemini
   ```

3. **Restart backend:**
   ```bash
   docker-compose restart backend
   ```

### Ollama (Local, Free)

1. **Install Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **Pull model:**
   ```bash
   ollama pull llama3.2
   ```

3. **Update .env:**
   ```env
   LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   OLLAMA_MODEL=llama3.2
   ```

4. **Restart backend:**
   ```bash
   docker-compose restart backend
   ```

---

## Production Deployment

### Preparation

1. **Update docker-compose.yml:**
   - Remove volume mounts (code in images)
   - Remove `--reload` flag
   - Add health checks
   - Use production WSGI server (gunicorn)

2. **Set environment:**
   ```env
   ENVIRONMENT=production
   ```

3. **Build production images:**
   ```bash
   docker-compose -f docker-compose.prod.yml build
   ```

### Security Checklist

- [ ] Change database password (not fundpass!)
- [ ] Use secrets manager for API keys
- [ ] Enable HTTPS/SSL
- [ ] Set CORS to specific origins
- [ ] Add authentication
- [ ] Enable rate limiting
- [ ] Set up monitoring (Sentry, DataDog)
- [ ] Configure backups

### Recommended Deployment Platforms

- **Backend + DB:** Railway, Render, AWS ECS
- **Frontend:** Vercel, Netlify
- **Database:** Neon, Supabase (with pgvector)

---

## Support

### Getting Help

- **Documentation:** `README.md`, `CLAUDE.md`
- **API Reference:** http://localhost:8000/docs
- **Logs:** `docker-compose logs -f`
- **GitHub Issues:** [Your repo issues page]

### Useful Commands

```bash
# Quick reference
docker-compose up -d          # Start all services
docker-compose down           # Stop all services
docker-compose logs -f        # View logs
docker-compose ps             # List services
docker-compose restart        # Restart all
docker-compose exec <service> # Access shell

# Cleanup
docker system prune           # Remove unused containers/images
docker volume prune           # Remove unused volumes (WARNING: data loss!)
```

---

**Last Updated:** 2025-10-25
**Version:** 1.0
