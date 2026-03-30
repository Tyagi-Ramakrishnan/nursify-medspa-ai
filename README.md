# Nursify MedSpa AI — MVP

Automated daily financial reporting for med spas. Connects to QuickBooks, stores transactions, and emails a daily report at 11 PM.

## Stack

- **Backend**: Python 3.11, FastAPI, PostgreSQL, Celery + Redis
- **Frontend**: React (Next.js), Tailwind CSS
- **Infrastructure**: Railway (backend + DB + Redis), Vercel or WordPress embed (frontend)

## Repo structure

```
nursify-medspa-ai/
├── backend/
│   ├── app/
│   │   ├── api/routes/      # FastAPI route handlers
│   │   ├── core/            # Config, security, settings
│   │   ├── db/              # Database connection + migrations
│   │   ├── models/          # SQLAlchemy models
│   │   ├── services/        # QuickBooks, report logic
│   │   └── tasks/           # Celery scheduled jobs
│   ├── tests/
│   ├── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/      # Dashboard UI components
│   │   ├── pages/           # Next.js pages
│   │   └── lib/             # API client, auth helpers
│   ├── package.json
│   └── Dockerfile
├── .github/workflows/       # CI/CD
├── docker-compose.yml       # Local dev
└── .env.example
```

## Quick start

```bash
cp .env.example .env
# Fill in your QuickBooks credentials and DB URL
docker-compose up
```

Backend runs at `http://localhost:8000`  
Frontend runs at `http://localhost:3000`

## MVP scope

- [x] QuickBooks OAuth 2.0 connection
- [x] Transaction sync + deduplication
- [x] Daily report email (11 PM scheduled job)
- [x] Simple dashboard (today + last 7 days)
- [x] Basic JWT login

## Environment variables

See `.env.example` for all required variables.
