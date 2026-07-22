import os

from fastapi import APIRouter, Depends, HTTPException, Response, status

from auth import COOKIE_NAME, User, authenticate, create_session, require_user
from models.schemas import LoginRequest, UserOut
from storage import get_manifest

router = APIRouter(prefix="/auth", tags=["Authentication"])


async def _user_out(user: User) -> dict:
    manifest = await get_manifest(user.id)
    resumes = [item for item in manifest["templates"] if item["kind"] == "resume"]
    covers = [item for item in manifest["templates"] if item["kind"] == "cover_letter"]
    return {"id": user.id, "name": user.name, "email": user.email, "resume_count": len(resumes), "has_cover_letter": bool(covers), "setup_complete": bool(resumes and covers)}


@router.post("/login", response_model=UserOut)
async def login(payload: LoginRequest, response: Response) -> dict:
    """Authenticate one of the four configured users and set a secure cookie."""
    user = authenticate(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    response.set_cookie(
        COOKIE_NAME, create_session(user), max_age=604800, httponly=True,
        secure=os.getenv("VERCEL") == "1", samesite="lax", path="/",
    )
    return await _user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    """Clear the active ResumeForge session cookie."""
    response.delete_cookie(COOKIE_NAME, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
async def current_user(user: User = Depends(require_user)) -> dict:
    """Return the authenticated user and template-setup status."""
    return await _user_out(user)
