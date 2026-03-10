# 🏥 SecureRAG-Health

**Secure, Role-Aware, Multi-Tenant Retrieval-Augmented Generation (RAG) for Hospital Management**

SecureRAG-Health is a production-ready system that enables hospital staff to query medical documents using natural language while enforcing strict access controls. Each role (Physician, Nurse, Radiologist, etc.) only retrieves information they are authorized to see, with enforcement at every layer of the stack.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│                    (REST API — JSON over HTTPS)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      AUTHENTICATION LAYER                           │
│            JWT Token Verification (python-jose)                     │
│         Claims: user_id, email, role_name, tenant_id                │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      AUTHORIZATION LAYER                            │
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │  SpiceDB ReBAC   │    │  Pre-Filter by   │    │  Role→DocType │  │
│  │  (CheckPermission│    │  LookupResources │    │  Mapping      │  │
│  │   LookupResources│    │  authorized IDs  │    │  (fail-closed)│  │
│  └─────────────────┘    └──────────────────┘    └───────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                       RETRIEVAL LAYER                               │
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Query Embedding  │    │  pgvector HNSW   │    │  PostgreSQL   │  │
│  │ (MiniLM-L6-v2)  │    │  Cosine Search   │    │  RLS Policies │  │
│  │  384 dimensions  │    │  + Pre-filter    │    │  (SET LOCAL)  │  │
│  └─────────────────┘    └──────────────────┘    └───────────────┘  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                       GENERATION LAYER                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │  Anthropic Claude (claude-sonnet-4-20250514)                         │    │
│  │  System prompt enforces context-only answers                 │    │
│  │  No raw chunks/IDs in response — only titles & scores        │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                        AUDIT LAYER                                  │
│              Async fire-and-forget audit logging                    │
│        (user, role, query, retrieved IDs, latency)                  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- An Anthropic API key

### Setup

```bash
# 1. Clone and configure
cd securerag-health
cp .env.example .env
# Edit .env → fill in ANTHROPIC_API_KEY

# 2. Start all services
docker compose up -d

# 3. Run database migrations
docker compose exec api alembic upgrade head

# 4. Seed demo data (roles, users, documents)
docker compose exec api python -m app.seed

# 5. Verify the API is running
curl http://localhost:8000/health
# → {"status":"ok","version":"1.0.0"}
```

### Try a Query

```bash
# Login as a physician
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dr.smith@hospital.com","password":"Demo@1234"}' \
  | jq -r .access_token)

# Query the RAG system
curl -X POST http://localhost:8000/rag/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are the latest lab results?","top_k":5}'
```

---

## 📡 API Endpoints

| Method | Path                | Auth     | Description                                |
|--------|---------------------|----------|--------------------------------------------|
| POST   | `/auth/register`    | None     | Register a new user                        |
| POST   | `/auth/login`       | None     | Login and receive JWT                      |
| POST   | `/documents/upload` | Bearer   | Upload and ingest a document               |
| GET    | `/documents/list`   | Bearer   | List documents visible to current role     |
| POST   | `/rag/query`        | Bearer   | Query the RAG system                       |
| GET    | `/health`           | None     | Health check                               |

---

## 🔐 Role Permission Matrix

| Document Type            | Physician | Nurse | Radiologist | Pharmacist | Patient | Lab Tech | Admin | Compliance |
|--------------------------|:---------:|:-----:|:-----------:|:----------:|:-------:|:--------:|:-----:|:----------:|
| EHR                      |     ✅     |       |             |            |         |          |       |            |
| CLINICAL_NOTES           |     ✅     |  ✅   |             |            |         |          |       |            |
| LAB_RESULTS              |     ✅     |       |             |            |         |          |       |            |
| PRESCRIPTIONS            |     ✅     |       |             |            |         |          |       |            |
| DISCHARGE_SUMMARY        |     ✅     |       |             |            |         |          |       |            |
| RADIOLOGY_REPORT         |     ✅     |       |      ✅      |            |         |          |       |            |
| PATIENT_CARE_PLAN        |           |  ✅   |             |            |         |          |       |            |
| MEDICATION_SCHEDULE      |           |  ✅   |             |            |         |          |       |            |
| VITALS                   |           |  ✅   |             |            |         |          |       |            |
| DICOM_METADATA           |           |       |      ✅      |            |         |          |       |            |
| IMAGING_PROTOCOL         |           |       |      ✅      |            |         |          |       |            |
| DRUG_FORMULARY           |           |       |             |     ✅      |         |          |       |            |
| PRESCRIPTION_ORDER       |           |       |             |     ✅      |         |          |       |            |
| DRUG_INTERACTION_ALERT   |           |       |             |     ✅      |         |          |       |            |
| OWN_EHR_SUMMARY          |           |       |             |            |    ✅    |          |       |            |
| DISCHARGE_NOTES          |           |       |             |            |    ✅    |          |       |            |
| APPOINTMENT_RECORD       |           |       |             |            |    ✅    |          |  ✅   |            |
| LAB_ORDER                |           |       |             |            |         |    ✅     |       |            |
| SPECIMEN_REPORT          |           |       |             |            |         |    ✅     |       |            |
| REFERENCE_RANGES         |           |       |             |            |         |    ✅     |       |            |
| BILLING_RECORD           |           |       |             |            |         |          |  ✅   |            |
| INSURANCE_AUTH           |           |       |             |            |         |          |  ✅   |            |
| HR_DOCUMENT              |           |       |             |            |         |          |  ✅   |            |
| AUDIT_LOG                |           |       |             |            |         |          |       |     ✅      |
| REGULATORY_FILING        |           |       |             |            |         |          |       |     ✅      |
| POLICY_DOCUMENT          |           |       |             |            |         |          |       |     ✅      |
| ALL_ANONYMIZED           |           |       |             |            |         |          |       |     ✅      |

---

## 🛡️ Security Architecture

### Triple-Layer Enforcement

1. **SpiceDB Pre-Filter (Layer 1)**: Before any database query, SpiceDB's `LookupResources` RPC returns the set of document IDs the user is authorized to access. If SpiceDB is unavailable, the system returns HTTP 503 (fail-closed).

2. **PostgreSQL Row-Level Security (Layer 2)**: RLS policies on `documents` and `document_chunks` tables enforce tenant isolation, role-based access, and patient ownership checks using `SET LOCAL` session variables. The application connects as `rag_app_user` (non-superuser) so RLS is never bypassed.

3. **Application-Level Mapping (Layer 3)**: The `ROLE_DOCUMENT_TYPE_MAP` provides a deterministic mapping of which document types each role can access, used during both document ingestion and query validation.

### Key Security Properties

- **Tenant Isolation**: All queries are scoped to the user's tenant via RLS.
- **Patient Data Ownership**: PATIENT role users can only see documents where `owner_patient_id` matches their user ID.
- **No Data Leakage in Responses**: API responses never include raw chunk text, embedding vectors, or internal UUIDs. Only document titles, types, and similarity scores are returned.
- **Audit Trail**: Every RAG query is logged with full context for compliance review.
- **RLS Superuser Warning**: The PostgreSQL superuser (`postgres`) bypasses RLS. The application must always connect as `rag_app_user`.

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/test_auth.py -v
pytest tests/test_rag_isolation.py -v
pytest tests/test_ingestion.py -v
```

---

## 📦 Tech Stack

| Component       | Technology                               |
|-----------------|------------------------------------------|
| Runtime         | Python 3.11                              |
| Framework       | FastAPI (async)                          |
| Vector Store    | PostgreSQL 16 + pgvector (HNSW)          |
| Auth DB         | PostgreSQL 16                            |
| Authorization   | SpiceDB (ReBAC)                          |
| Cache           | Redis 7                                  |
| LLM             | Anthropic Claude (claude-sonnet-4-20250514)       |
| Embeddings      | sentence-transformers (all-MiniLM-L6-v2) |
| Identity        | JWT (python-jose)                        |
| Migrations      | Alembic                                  |
| Containers      | Docker + Docker Compose                  |
| Testing         | pytest + httpx (async)                   |
| Linting         | ruff + black                             |

---

## 📁 Project Structure

```
securerag-health/
├── docker-compose.yml          # All services
├── Dockerfile                  # API container
├── .env.example                # Environment template
├── pyproject.toml              # Dependencies
├── alembic/                    # Database migrations
├── app/
│   ├── main.py                 # FastAPI app + startup
│   ├── config.py               # pydantic-settings
│   ├── dependencies.py         # Shared dependencies
│   ├── seed.py                 # Demo data seeder
│   ├── auth/                   # Authentication (JWT)
│   ├── authz/                  # Authorization (SpiceDB)
│   ├── documents/              # Document management
│   ├── rag/                    # RAG pipeline
│   ├── audit/                  # Audit logging
│   └── db/                     # Database session + RLS
├── spicedb/
│   └── schema.zed              # SpiceDB authorization schema
└── tests/                      # Integration tests
```

---

## License

MIT
