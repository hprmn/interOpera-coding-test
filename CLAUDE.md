# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Fund Performance Analysis System - an AI-powered platform that processes PDF fund reports, extracts structured data (capital calls, distributions, adjustments), and enables LPs to query fund metrics using natural language via RAG (Retrieval Augmented Generation).

**Tech Stack:**
- Backend: FastAPI (Python 3.11+) with SQLAlchemy ORM
- Frontend: Next.js 14 (App Router) with TypeScript, TailwindCSS, shadcn/ui
- Database: PostgreSQL 15+ with pgvector extension
- Vector Store: pgvector (not FAISS as mentioned in older docs)
- LLM: OpenAI GPT-4 for chat, text-embedding-3-small for embeddings
- Task Queue: Celery + Redis
- Deployment: Docker Compose

## Essential Commands

### Docker (Primary Development Method)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f
docker-compose logs -f backend
docker-compose logs -f frontend

# Rebuild after changes
docker-compose up --build

# Stop all services
docker-compose down

# Reset database (WARNING: destroys data)
docker-compose down -v
```

### Backend Development
```bash
cd backend

# Initialize database
docker-compose exec backend python app/db/init_db.py

# Run backend tests
docker-compose exec backend pytest tests/ -v

# Run tests with coverage
docker-compose exec backend pytest --cov=app tests/

# Test specific file
docker-compose exec backend pytest tests/test_metrics.py -v

# Access Python shell with DB connection
docker-compose exec backend python
```

### Frontend Development
```bash
cd frontend

# Install dependencies (if developing locally)
npm install

# Run dev server (via Docker)
docker-compose up frontend

# Build for production
npm run build

# Lint
npm run lint
```

### Database Access
```bash
# Connect to PostgreSQL via Docker
docker-compose exec postgres psql -U funduser -d funddb

# Common SQL queries
SELECT * FROM funds;
SELECT * FROM capital_calls WHERE fund_id = 1;
SELECT * FROM distributions WHERE fund_id = 1;
SELECT * FROM adjustments WHERE fund_id = 1;
SELECT * FROM documents;
```

### API Testing
```bash
# Health check
curl http://localhost:8000/health

# Upload document
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@files/sample.pdf" \
  -F "fund_id=1"

# Chat query
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the current DPI?", "fund_id": 1}'

# Get fund metrics
curl http://localhost:8000/api/funds/1/metrics

# Get detailed metrics breakdown
curl http://localhost:8000/api/metrics/funds/1/metrics?metric=dpi
```

## Architecture Overview

### Backend Structure (FastAPI)
```
backend/app/
├── api/endpoints/          # API route handlers
│   ├── documents.py        # Document upload/status endpoints
│   ├── funds.py           # Fund CRUD and metrics endpoints
│   ├── chat.py            # RAG query endpoints
│   └── metrics.py         # Detailed metrics breakdown endpoints
├── core/
│   └── config.py          # Settings and environment config
├── db/
│   ├── session.py         # Database session management
│   └── init_db.py         # Database initialization script
├── models/                # SQLAlchemy ORM models
│   ├── fund.py           # Fund model
│   ├── transaction.py     # CapitalCall, Distribution, Adjustment models
│   └── document.py        # Document metadata model
├── schemas/               # Pydantic validation schemas
├── services/              # Business logic
│   ├── metrics_calculator.py  # DPI, IRR, PIC calculations (FULLY IMPLEMENTED)
│   ├── document_processor.py  # PDF parsing skeleton (NEEDS IMPLEMENTATION)
│   ├── vector_store.py        # pgvector integration (PARTIAL - needs embedding generation)
│   └── query_engine.py        # RAG pipeline (NEEDS IMPLEMENTATION)
└── main.py                # FastAPI app initialization
```

### Frontend Structure (Next.js)
```
frontend/
├── app/                   # Next.js 14 App Router
│   ├── page.tsx          # Home page
│   ├── upload/           # Document upload page
│   ├── chat/             # Chat interface page
│   ├── funds/            # Fund list and detail pages
│   └── documents/        # Document management
├── components/           # React components
│   └── ui/              # shadcn/ui components
└── lib/
    ├── api.ts           # API client utilities
    └── utils.ts         # Helper functions
```

### Data Model

**Key Tables:**
- `funds`: Fund master data (name, GP, vintage year)
- `capital_calls`: Capital call transactions (date, amount, description)
- `distributions`: Distribution transactions (date, amount, is_recallable)
- `adjustments`: Rebalancing entries (date, amount, type, category)
- `documents`: Uploaded PDF metadata (file_path, parsing_status)

**Important**: The system uses `pgvector` extension for vector storage, NOT FAISS. Vectors are stored directly in PostgreSQL using the `vector` column type.

## Critical Implementation Notes

### Metrics Calculation (FULLY IMPLEMENTED ✅)
The metrics calculator in `backend/app/services/metrics_calculator.py` is complete and tested:

- **PIC (Paid-In Capital)**: `Total Capital Calls - Adjustments`
- **DPI (Distribution to Paid-In)**: `Total Distributions / PIC`
- **IRR (Internal Rate of Return)**: Uses `numpy_financial.irr()` with proper cash flow ordering

**Features:**
- Detailed calculation breakdowns available via `/api/metrics/funds/{id}/metrics?metric=dpi`
- Shows all transactions (capital calls, distributions, adjustments) used in calculations
- Handles edge cases (zero PIC, missing data, IRR convergence failures)
- Cash flow timeline for IRR debugging

**Important Methods:**
- `calculate_all_metrics(fund_id)` - Returns all metrics at once
- `get_calculation_breakdown(fund_id, metric)` - Returns detailed breakdown with all transactions

### Document Processing (SKELETON ONLY ⚠️)
`backend/app/services/document_processor.py` is a skeleton. Key TODOs:

1. **PDF Parsing**: Integrate pdfplumber (already in requirements.txt)
   ```python
   import pdfplumber
   with pdfplumber.open(file_path) as pdf:
       for page in pdf.pages:
           tables = page.extract_tables()
           text = page.extract_text()
   ```

2. **Table Classification**: Identify table types by headers
   - Look for keywords: "Capital Call", "Distribution", "Adjustment"
   - Parse date columns and amount columns
   - Handle various date formats (YYYY-MM-DD, MM/DD/YYYY, etc.)

3. **Data Mapping**: Create SQLAlchemy model instances
   ```python
   # Example for capital calls
   capital_call = CapitalCall(
       fund_id=fund_id,
       call_date=parsed_date,
       amount=parsed_amount,
       call_type="Investment",  # or "Management Fee"
       description=row_description
   )
   db.add(capital_call)
   ```

4. **Text Chunking**: Extract non-table text for vector storage
   - Use settings.CHUNK_SIZE (1000) and settings.CHUNK_OVERLAP (200)
   - Preserve paragraph boundaries
   - Include metadata (page_number, document_id, fund_id)

5. **Error Handling**: Update document status
   - Set `parsing_status = "processing"` at start
   - Set `parsing_status = "completed"` on success
   - Set `parsing_status = "failed"` and store error_message on failure

**Note**: TableParser class is referenced but doesn't exist - you'll need to implement table parsing logic directly in DocumentProcessor or create the TableParser class.

### Vector Store (PARTIAL IMPLEMENTATION ⚠️)
`backend/app/services/vector_store.py` has pgvector infrastructure but needs completion:

**Already Implemented:**
- ✅ pgvector extension initialization
- ✅ `document_embeddings` table creation with vector column
- ✅ IVFFlat index for fast similarity search
- ✅ Embedding model initialization (OpenAI or HuggingFace fallback)

**Needs Implementation:**
1. **Fix `add_document()` method**: Currently has async/await issues
   - The embedding generation needs proper async handling
   - JSON serialization for metadata needs fixing

2. **Fix `similarity_search()` method**:
   - SQL query syntax needs correction
   - Vector casting needs proper format
   - Result parsing needs adjustment

3. **Add batch operations**:
   ```python
   async def add_documents_batch(self, documents: List[Dict]):
       # Batch insert for better performance
   ```

**pgvector Operators:**
- `<->` - L2 distance (Euclidean)
- `<#>` - Inner product (negative dot product)
- `<=>` - Cosine distance (1 - cosine similarity)

**Important**: This project uses pgvector, NOT FAISS. The `FAISS_INDEX_PATH` in config.py is obsolete and should be ignored.

### RAG Query Engine (MOSTLY IMPLEMENTED ✅)
`backend/app/services/query_engine.py` is surprisingly complete!

**Already Implemented:**
- ✅ Intent classification with keyword matching
- ✅ Vector similarity search integration
- ✅ Metrics calculation integration
- ✅ LangChain prompt engineering
- ✅ Response formatting with sources
- ✅ Conversation history support
- ✅ OpenAI/Ollama fallback support

**Query Flow:**
1. User query → `process_query()`
2. Classify intent: calculation, definition, retrieval, or general
3. Vector search for relevant context
4. Calculate metrics if needed
5. Generate LLM response with context + metrics
6. Return formatted response with sources

**May Need Adjustments:**
- Intent classification might need refinement based on testing
- Prompt engineering may need tuning for better responses
- Error handling could be more robust

## Development Guidelines

### When Adding New Features

1. **Backend API changes:**
   - Add endpoint to appropriate router in `api/endpoints/`
   - Define Pydantic schema in `schemas/`
   - Update API documentation in `docs/API.md`
   - Test with curl or `/docs` interactive UI

2. **Database schema changes:**
   - Modify models in `models/`
   - Update `db/init_db.py` if needed
   - Document in `docs/ARCHITECTURE.md`

3. **Frontend changes:**
   - Follow Next.js 14 App Router conventions
   - Use shadcn/ui components for consistency
   - Use TanStack Query for API calls
   - Implement proper loading and error states

### Database Models Reference

**Fund Model** (`backend/app/models/fund.py`):
- Relationships: capital_calls, distributions, adjustments, documents
- All transactions link back to Fund via `fund_id` foreign key

**Transaction Models** (`backend/app/models/transaction.py`):
- `CapitalCall`: Contains call_date, amount, call_type, description
- `Distribution`: Contains distribution_date, amount, distribution_type, is_recallable, description
- `Adjustment`: Contains adjustment_date, amount, adjustment_type, category, is_contribution_adjustment, description

**Important**: All amount fields use `Numeric(15, 2)` for precision. All dates use `Date` type (not DateTime).

### Configuration Reference

All settings in `backend/app/core/config.py`:
- `CHUNK_SIZE = 1000` - Text chunk size for embeddings
- `CHUNK_OVERLAP = 200` - Overlap between chunks
- `TOP_K_RESULTS = 5` - Number of similar documents to retrieve
- `SIMILARITY_THRESHOLD = 0.7` - Minimum similarity score
- `MAX_UPLOAD_SIZE = 52428800` - 50MB file upload limit

### Testing Strategy

- **Metrics calculations**: Use sample data in `files/` directory
- **Document parsing**: Test with provided `ILPA based Capital Accounting...pdf`
- **RAG queries**: Test with questions from README.md "Sample Questions" section
- **API integration**: Use pytest fixtures with test database

### Environment Variables

Required in `.env`:
```bash
OPENAI_API_KEY=sk-...           # Required for embeddings and LLM
DATABASE_URL=postgresql://...    # Auto-configured in Docker
REDIS_URL=redis://...            # Auto-configured in Docker
```

Optional (for local LLM alternatives):
```bash
LLM_PROVIDER=ollama              # For free local LLM
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

**Note**: In Docker, DATABASE_URL and REDIS_URL are automatically set via docker-compose.yml environment variables. Only OPENAI_API_KEY needs to be in your `.env` file.

## Common Tasks

### Add a New Fund Metric

1. Add calculation method to `MetricsCalculator` class in `metrics_calculator.py`
   ```python
   def calculate_tvpi(self, fund_id: int) -> Optional[float]:
       """Calculate TVPI (Total Value to Paid-In)"""
       pic = self.calculate_pic(fund_id)
       distributions = self.calculate_total_distributions(fund_id)
       nav = self._get_nav(fund_id)  # Need to implement NAV tracking

       if not pic or pic == 0:
           return 0.0

       return float(distributions + nav) / float(pic)
   ```

2. Update `calculate_all_metrics()` to include new metric
3. Add breakdown logic to `get_calculation_breakdown()`
4. Update schema in `schemas/fund.py`
5. Document formula in `docs/CALCULATIONS.md`

### Implement Document Parsing (Step-by-Step)

**Step 1: Basic PDF Parsing**
```python
async def process_document(self, file_path: str, document_id: int, fund_id: int):
    import pdfplumber
    from app.models.document import Document

    # Update status
    doc = db.query(Document).filter(Document.id == document_id).first()
    doc.parsing_status = "processing"
    db.commit()

    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    await self._process_table(table, fund_id, page_num)

                # Extract text
                text = page.extract_text()
                if text:
                    await self._process_text(text, document_id, fund_id, page_num)

        doc.parsing_status = "completed"
        db.commit()
    except Exception as e:
        doc.parsing_status = "failed"
        doc.error_message = str(e)
        db.commit()
        raise
```

**Step 2: Table Classification**
```python
def _classify_table(self, table: List[List[str]]) -> str:
    """Classify table type based on headers"""
    if not table or not table[0]:
        return "unknown"

    header = " ".join([str(cell).lower() for cell in table[0]])

    if "capital call" in header or "contribution" in header:
        return "capital_call"
    elif "distribution" in header:
        return "distribution"
    elif "adjustment" in header or "rebalance" in header:
        return "adjustment"

    return "unknown"
```

**Step 3: Parse Table Rows**
```python
async def _process_table(self, table: List[List[str]], fund_id: int, page_num: int):
    table_type = self._classify_table(table)

    if table_type == "capital_call":
        for row in table[1:]:  # Skip header
            if len(row) >= 3:  # Expect: date, amount, description
                call = CapitalCall(
                    fund_id=fund_id,
                    call_date=self._parse_date(row[0]),
                    amount=self._parse_amount(row[1]),
                    description=row[2] if len(row) > 2 else None
                )
                db.add(call)

    db.commit()
```

**Step 4: Helper Methods**
```python
def _parse_date(self, date_str: str) -> date:
    """Parse various date formats"""
    from dateutil import parser
    try:
        return parser.parse(date_str).date()
    except:
        return None

def _parse_amount(self, amount_str: str) -> Decimal:
    """Parse amount strings like '$1,000,000.00'"""
    import re
    cleaned = re.sub(r'[^\d.]', '', str(amount_str))
    return Decimal(cleaned) if cleaned else Decimal(0)
```

### Implement RAG Pipeline (Already Mostly Done!)

**What's Already Working:**
- `query_engine.py` has intent classification ✅
- LangChain prompt templates configured ✅
- Metrics integration complete ✅

**What Needs Fixing:**
1. In `vector_store.py`, fix the async embedding generation:
   ```python
   async def _get_embedding(self, text: str) -> np.ndarray:
       # OpenAI embeddings are sync, not async
       if hasattr(self.embeddings, 'embed_query'):
           embedding = self.embeddings.embed_query(text)  # Remove await
       else:
           embedding = self.embeddings.encode(text)
       return np.array(embedding, dtype=np.float32)
   ```

2. Fix vector casting in `similarity_search()`:
   ```python
   # Change from:
   embedding <=> :query_embedding::vector
   # To:
   embedding <=> CAST(:query_embedding AS vector)
   ```

3. Test end-to-end with sample queries:
   ```bash
   curl -X POST http://localhost:8000/api/chat/query \
     -H "Content-Type: application/json" \
     -d '{"query": "What is DPI?", "fund_id": 1}'
   ```

### Debug Calculation Issues

If calculations seem wrong, use the detailed breakdown endpoint:
```bash
# Get full breakdown with all transactions
curl http://localhost:8000/api/metrics/funds/1/metrics?metric=dpi

# This returns:
# - All capital calls with dates and amounts
# - All distributions with dates and amounts
# - All adjustments
# - Step-by-step calculation
```

### Add Missing TableParser Class

The DocumentProcessor references `TableParser` but it doesn't exist. Create it:

```python
# backend/app/services/table_parser.py
class TableParser:
    """Parse tables from PDF documents"""

    def parse_table(self, table: List[List[str]], fund_id: int) -> Dict[str, Any]:
        """Parse a table and return structured data"""
        table_type = self._classify_table(table)

        if table_type == "capital_call":
            return self._parse_capital_calls(table, fund_id)
        elif table_type == "distribution":
            return self._parse_distributions(table, fund_id)
        elif table_type == "adjustment":
            return self._parse_adjustments(table, fund_id)

        return {"type": "unknown", "data": []}
```

## Troubleshooting

### "Document parsing failed"
- Check backend logs: `docker-compose logs backend`
- Verify PDF is not corrupted or password-protected
- Ensure pdfplumber/Docling is properly installed
- Check file size (max 50MB)
- **Note**: Document processing is NOT implemented yet - this is expected to fail

### "OpenAI API key not found"
- Ensure `.env` exists in root directory
- Verify `OPENAI_API_KEY` is set
- Restart backend: `docker-compose restart backend`
- Check format: Must start with `sk-`

### "IRR returns NaN" or "IRR is None"
- Verify cash flows have both negative (calls) and positive (distributions) values
- Check for missing/null dates
- Ensure at least 2 cash flows exist
- Use detailed breakdown: `/api/metrics/funds/{id}/metrics?metric=irr`
- IRR calculation requires alternating cash flows (negative then positive)

### "pgvector extension error"
Database connection errors or vector-related issues:
- Ensure PostgreSQL is healthy: `docker-compose ps`
- Check logs: `docker-compose logs postgres`
- Manually enable extension:
  ```bash
  docker-compose exec postgres psql -U funduser -d funddb -c "CREATE EXTENSION IF NOT EXISTS vector;"
  ```
- Verify pgvector image: Should use `pgvector/pgvector:pg15` in docker-compose.yml

### "No module named 'numpy_financial'"
Backend dependency issues:
```bash
# Rebuild backend container
docker-compose up --build backend

# Or install locally
cd backend
pip install numpy-financial
```

### "Conversation not found" in chat
- Conversations are stored in-memory and lost on restart
- Create new conversation: `POST /api/chat/conversations`
- Or query without conversation_id

### Frontend cannot connect to backend
- Verify backend is running: `curl http://localhost:8000/health`
- Check CORS settings in `backend/app/main.py` (should allow localhost:3000)
- Verify `NEXT_PUBLIC_API_URL=http://localhost:8000` in frontend
- Check both services are in same Docker network

### "Table 'document_embeddings' does not exist"
Vector store table not created:
```bash
# Access database
docker-compose exec postgres psql -U funduser -d funddb

# Run these SQL commands:
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER,
    fund_id INTEGER,
    content TEXT NOT NULL,
    embedding vector(1536),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS document_embeddings_embedding_idx
ON document_embeddings USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Async/Await Errors in vector_store.py
The embedding generation methods are synchronous, not async:
- Remove `await` from `self.embeddings.embed_query()` calls
- Keep `async def` on public methods for API compatibility
- Call sync methods directly within async functions

### "Permission denied" on uploads directory
```bash
# Fix permissions
docker-compose exec backend chmod 777 /app/uploads

# Or recreate volume
docker-compose down -v
docker-compose up -d
```

## Important Implementation Details

### Conversation Storage
**Current Implementation**: In-memory dictionary in `backend/app/api/endpoints/chat.py`
- Conversations stored in Python dict: `conversations: Dict[str, Dict[str, Any]] = {}`
- **Lost on server restart** - not persistent
- For production: Move to Redis or database table

### File Upload Flow
1. File uploaded via `POST /api/documents/upload`
2. Saved to `UPLOAD_DIR` with timestamp prefix: `20241020_120000_filename.pdf`
3. Document record created in database with `parsing_status = "pending"`
4. `process_document()` should be called asynchronously (not yet implemented)
5. Status updated to "processing" → "completed" or "failed"

### Vector Embeddings Dimensions
- **OpenAI text-embedding-3-small**: 1536 dimensions
- **HuggingFace all-MiniLM-L6-v2**: 384 dimensions
- Table schema must match: `embedding vector(1536)` or `embedding vector(384)`

### LangChain Integration
The query engine uses LangChain's `ChatOpenAI` with:
- Temperature: 0 (deterministic responses)
- Model: `gpt-4-turbo-preview` (from config)
- System prompt defines assistant as "financial analyst"
- User prompt includes: context, metrics, history, query

### Transaction Type Guidelines
Based on model schemas:

**CapitalCall.call_type** (examples):
- "Investment" - Capital for new investments
- "Management Fee" - GP management fees
- "Follow-on" - Additional capital for existing investments

**Distribution.distribution_type** (examples):
- "Return of Capital" - Principal returned
- "Dividend" - Income distribution
- "Realized Gain" - Profit from exits

**Adjustment.adjustment_type** (examples):
- "Rebalance of Distribution" - Clawback
- "Rebalance of Capital Call" - Refund
- Category field provides additional classification

### Performance Considerations

**Database Queries:**
- Metrics calculations use aggregate functions (SUM, COUNT)
- Consider adding database indexes on `fund_id` and date columns
- Current implementation: No caching (add Redis for production)

**Vector Search:**
- IVFFlat index requires lists parameter (currently 100)
- Recommended: 100 lists for < 1M vectors
- Trade-off: Speed vs accuracy

**Document Processing:**
- Large PDFs (50MB) may take 1-2 minutes
- Consider background task queue (Celery + Redis)
- Currently: Synchronous processing blocks API

## Code Patterns & Conventions

### Database Sessions
Always use dependency injection for database sessions:
```python
from app.db.session import get_db

@router.get("/endpoint")
def endpoint(db: Session = Depends(get_db)):
    # db session automatically closed after request
```

### Error Responses
Use FastAPI's HTTPException:
```python
from fastapi import HTTPException

if not fund:
    raise HTTPException(status_code=404, detail="Fund not found")
```

### Decimal Precision
Always use `Decimal` for financial amounts:
```python
from decimal import Decimal

amount = Decimal("1000.50")  # Not float!
```

### Date Handling
Use `date` objects, not `datetime`:
```python
from datetime import date

call_date = date(2024, 10, 20)  # Not datetime.now()
```

## API Endpoint Patterns

### Standard CRUD Pattern
```python
# List (with pagination)
@router.get("/", response_model=List[Schema])
def list_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = db.query(Model).offset(skip).limit(limit).all()
    return items

# Get by ID
@router.get("/{id}", response_model=Schema)
def get_item(id: int, db: Session = Depends(get_db)):
    item = db.query(Model).filter(Model.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Not found")
    return item

# Create
@router.post("/", response_model=Schema)
def create_item(item: SchemaCreate, db: Session = Depends(get_db)):
    db_item = Model(**item.dict())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

# Delete
@router.delete("/{id}")
def delete_item(id: int, db: Session = Depends(get_db)):
    db.query(Model).filter(Model.id == id).delete()
    db.commit()
    return {"message": "Deleted successfully"}
```

## Additional Resources

- **API Documentation**: http://localhost:8000/docs (interactive Swagger UI)
- **API Redoc**: http://localhost:8000/redoc (alternative docs UI)
- **Architecture Diagram**: `docs/ARCHITECTURE.md`
- **Metrics Formulas**: `docs/CALCULATIONS.md`
- **Setup Instructions**: `SETUP.md`
- **Troubleshooting Guide**: `TROUBLESHOOTING.md`
- **Sample PDFs**: `files/` directory

## Quick Reference

### URLs
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Database: localhost:5432 (funduser/fundpass/funddb)
- Redis: localhost:6379

### File Locations
- Backend: `./backend/app/`
- Frontend: `./frontend/app/`
- Models: `./backend/app/models/`
- Services: `./backend/app/services/`
- API Endpoints: `./backend/app/api/endpoints/`
- Frontend Pages: `./frontend/app/*/page.tsx`

## Project Status

**Completed:**
- ✅ Docker infrastructure setup
- ✅ Database schema and models with relationships
- ✅ Basic API endpoints (CRUD operations)
- ✅ Metrics calculation (DPI, IRR, PIC) with detailed breakdowns
- ✅ Frontend boilerplate with routing and layouts
- ✅ RAG query engine skeleton (mostly complete)
- ✅ Vector store infrastructure (pgvector setup)
- ✅ LangChain integration with prompt templates

**In Progress / Needs Implementation:**
- ⚠️ Document parsing pipeline (skeleton exists, needs pdfplumber implementation)
- ⚠️ Vector store embedding generation (minor async/await fixes needed)
- ⚠️ TableParser class (referenced but doesn't exist)
- ⚠️ Text chunking implementation
- ⚠️ End-to-end document upload → parse → RAG flow
- ⚠️ Frontend-backend integration (upload, chat, metrics display)

**Not Started:**
- ❌ Background task processing with Celery
- ❌ Conversation persistence (currently in-memory)
- ❌ TVPI, RVPI metrics (require NAV tracking)
- ❌ Authentication and authorization
- ❌ Rate limiting
- ❌ Comprehensive test coverage
- ❌ Production deployment configuration

**Key Implementation Focus:**
When working on this codebase, prioritize:
1. **Document processing**: Implement pdfplumber parsing and table classification
2. **Vector store fixes**: Fix async/await issues in embedding generation
3. **Create TableParser**: Referenced but missing class
4. **End-to-end testing**: Test full flow from upload to RAG query

The metrics calculation foundation is solid and complete - build on top of it rather than modifying it.
- to memorize
- to memorize
- to memorize
- to
- to memorize