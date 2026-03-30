from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi import Depends
from app.core.config import settings
from app.core.security import verify_password, hash_password, create_access_token

router = APIRouter()

# MVP: single hardcoded admin user
# Replace with a users table when you add multi-tenant support
ADMIN_HASH = hash_password(settings.ADMIN_PASSWORD)


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    if form.username != settings.ADMIN_EMAIL:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(form.password, ADMIN_HASH):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({"sub": form.username, "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
def me(user: dict = Depends(lambda: None)):
    # Protected by get_current_user in real routes — placeholder
    return {"email": settings.ADMIN_EMAIL, "role": "admin"}
