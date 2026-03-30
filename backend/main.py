from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import auth, quickbooks, transactions, reports

app = FastAPI(
    title="Nursify MedSpa AI",
    description="Automated financial reporting for med spas",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only create tables if DATABASE_URL is configured
if settings.DATABASE_URL:
    try:
        from app.db.database import engine, Base
        from app.models import models  # noqa
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"[startup] DB init skipped: {e}")

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(quickbooks.router, prefix="/api/v1/quickbooks", tags=["quickbooks"])
app.include_router(transactions.router, prefix="/api/v1/transactions", tags=["transactions"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
