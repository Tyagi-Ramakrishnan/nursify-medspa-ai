from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from app.core.config import settings
from app.core.security import verify_password, hash_password, create_access_token

router = APIRouter()

# Hash is computed lazily on first login — not at import time
# This avoids bcrypt crashing before the server starts
_admin_hash: str | None = None

def get_admin_hash() -> str:
    global _admin_hash
    if _admin_hash is None:
        _admin_hash = hash_password(settings.ADMIN_PASSWORD)
    return _admin_hash


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    if form.username != settings.ADMIN_EMAIL:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(form.password, get_admin_hash()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": form.username, "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me():
    return {"email": settings.ADMIN_EMAIL, "role": "admin"}
