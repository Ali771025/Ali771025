# QORA — Consumer AI Service Network

A production-style full-stack marketplace where **consumers** discover, order and review AI
services from vetted **providers** — chatbots, computer vision, data & analytics, voice,
automation and more. Built as an advanced full-stack demo:

**Backend:** Python · FastAPI · SQLAlchemy 2.0 · Pydantic v2 · JWT auth · bcrypt
**Frontend:** React 18 · TypeScript · Vite · Tailwind CSS v4 · React Router · lucide-react
**Database:** SQLite by default (dev) — swap `DATABASE_URL` to PostgreSQL for production.

---

## Features

| Area | What's inside |
|---|---|
| **Auth & roles** | Register/login with JWT, roles: `consumer`, `provider`, `admin` |
| **Marketplace** | Service catalog with search, category filters, sorting (newest / rating / price) |
| **Orders** | Escrow-style flow: pay → accept → deliver → approve & pay · cancellations with full refunds |
| **Wallet** | Top-up (mock payments), protected balance, full transaction ledger (purchase / earning / refund) |
| **Reviews** | 1–5★ reviews on completed orders only, live rating aggregation on services |
| **Provider workspace** | Publish / edit / pause / delete services, fulfill orders, track earnings (90% payout, 10% platform fee) |
| **Admin console** | Platform stats (GMV, orders, ratings), user suspend/activate, order oversight |
| **AI Concierge** | Intent-based assistant that recommends matching services from the live catalog |
| **UI** | Dark glassmorphism design, responsive, skeletons/empty states, toasts & modals |

## Quick start

### 1 · Backend (FastAPI)

```bash
cd qora/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python seed.py                  # creates qora.db with demo data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: **http://localhost:8000/api/docs**

### 2 · Frontend (React)

```bash
cd qora/frontend
npm install
npm run dev                     # http://localhost:5173  (proxies /api → :8000)
```

### Demo logins

| Role | Email | Password |
|---|---|---|
| Consumer | `omar@qora.ai` | `consumer123` |
| Provider | `sarah@qora.ai` | `provider123` |
| Admin | `admin@qora.ai` | `admin123` |

## API overview

```
POST   /api/auth/register          create account (consumer|provider)
POST   /api/auth/login             → JWT access token
GET    /api/auth/me                current user
GET    /api/categories             capability categories
GET    /api/services               ?search= &category= &sort= &limit=
GET    /api/services/{id}          service detail
POST   /api/services               provider: create
PATCH  /api/services/{id}          provider: update / pause
DELETE /api/services/{id}          provider: delete
POST   /api/orders                 place order (wallet payment)
GET    /api/orders                 ?role=buyer|provider
PATCH  /api/orders/{id}/status     accept / deliver / complete / cancel
POST   /api/reviews                review a completed order
GET    /api/services/{id}/reviews  public reviews
GET    /api/wallet                 balance + transactions
POST   /api/wallet/topup           mock payment top-up
POST   /api/assistant/chat         AI Concierge (service matching)
GET    /api/stats                  public platform stats
GET    /api/admin/stats            admin: platform KPIs
GET    /api/admin/users            admin: user management
PATCH  /api/admin/users/{id}       admin: suspend / activate
GET    /api/admin/orders           admin: order oversight
```

## Architecture

```
qora/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, CORS, public stats
│   │   ├── core/              config (env), security (bcrypt + JWT)
│   │   ├── db/                SQLAlchemy models (User, Category, Service,
│   │   │                      Order, Review, Wallet, Transaction)
│   │   ├── schemas/           Pydantic v2 request/response schemas
│   │   └── api/               routers: auth · services · orders · wallet
│   │                          · assistant · admin + role guards
│   ├── seed.py                demo data (14 services, 6 users, orders, reviews)
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api/client.ts      fetch wrapper + money/date helpers
    │   ├── context/           AuthContext (JWT session)
    │   ├── components/        Navbar, Footer, ServiceCard, OrderCard, …
    │   └── pages/             Home, Services, ServiceDetail, Assistant,
    │                          Dashboard, Provider, Admin, Wallet, Login, Register
    └── vite.config.ts         dev server + /api proxy
```

### Order lifecycle

```
pending ──(provider accepts)──► in_progress ──(provider delivers)──► delivered
   │                                   │                                │
   └──(either side cancels)──► cancelled                                └──(buyer approves)──► completed
        └─ full refund to buyer wallet                                       └─ 90% to provider wallet
```

## Architecture & planning docs

The project follows a documented pipeline (PRD → Architecture → ERD → API Contract → Phasing →
Codex prompts → implementation):

| Doc | Content |
|---|---|
| [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Technical Architecture & Development Blueprint v1.0 — every decision tagged `[PRD]` vs `[TECH]` |
| [`docs/ERD.md`](./docs/ERD.md) | Full data model: 9 clusters, ~45 entities (identity → reward ledger) |
| [`docs/API_CONTRACT.md`](./docs/API_CONTRACT.md) | `/api/v1` REST contract + normative flow sequences |
| [`docs/PHASING.md`](./docs/PHASING.md) | Phases 0–5 with exit criteria + mapping of the current prototype to phases |
| [`docs/CODEX_PROMPTS.md`](./docs/CODEX_PROMPTS.md) | Ready-to-run implementation prompts per module |

> The current `backend/` + `frontend/` is the working **marketplace-style prototype** (Phase 0/1
> scaffold). It will be evolved toward the Personal-QORA architecture in the docs.

## Production notes

- **Database:** set `DATABASE_URL=postgresql+psycopg://…` (SQLAlchemy) — models are portable.
- **Secrets:** override `SECRET_KEY` via env / `.env` in `backend/`.
- **Payments:** `wallet/topup` is a mock gateway — plug in Stripe/PayPal there.
- **AI Concierge:** rule-based matching engine; swap the matching layer for an LLM
  (OpenAI-compatible) call in `app/api/assistant.py` without touching the frontend.
