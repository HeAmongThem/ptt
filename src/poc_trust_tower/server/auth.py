from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr

from poc_trust_tower.core import repository as repo
from poc_trust_tower.core.model import ROLE, User
from poc_trust_tower.core.security import verify_password
from poc_trust_tower.server.templating import templates

router = APIRouter(include_in_schema=False, tags=["auth"])

SESSION_USER_KEY = "user_id"


# Session ==============================================================
def get_current_user(request: Request) -> User | None:
    user_id = request.session.get(SESSION_USER_KEY)
    if user_id is None:
        return None
    try:
        return repo.get_user(user_id)
    except repo.NotFoundError:
        # Utilisateur supprimé entre-temps : on invalide la session.
        request.session.pop(SESSION_USER_KEY, None)
        return None


OptionalUserDep = Annotated[User | None, Depends(get_current_user)]


class NotAuthenticated(Exception):
    """Levée quand une page exige une session ; le handler redirige vers /login."""

    def __init__(self, next_url: str):
        super().__init__("Authentification requise")
        self.next_url = next_url


def require_user(request: Request, user: OptionalUserDep) -> User:
    if user is None:
        raise NotAuthenticated(request.url.path)
    return user


CurrentUserDep = Annotated[User, Depends(require_user)]


def require_role(*roles: ROLE):
    def _check(user: CurrentUserDep) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Accès réservé")
        return user

    return Depends(_check)


# Routes ===============================================================
class LoginSchema(BaseModel):
    email: EmailStr
    password: str


def _safe_next(target: str | None) -> str:
    # N'accepte que des chemins relatifs internes (anti open-redirect).
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return "/"


NextUrl = Annotated[str | None, Query(alias="next")]


@router.get("/login")
def login_form(request: Request, user: OptionalUserDep, next_url: NextUrl = None):
    if user is not None:
        return RedirectResponse(_safe_next(next_url), status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request, "login.html", {"title": "Connexion", "next": next_url, "error": None, "email": ""}
    )


@router.post("/login")
def login(request: Request, payload: Annotated[LoginSchema, Form()], next_url: NextUrl = None):
    user = next((u for u in repo.repoUsers if u.email.lower() == payload.email.lower()), None)
    if user is None or not verify_password(payload.password, user.password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"title": "Connexion", "next": next_url, "error": "Email ou mot de passe incorrect.", "email": payload.email},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id
    return RedirectResponse(_safe_next(next_url), status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
