"""Repo des utilisateurs (mots de passe hachés)."""

from poc_trust_tower.core.model import ROLE, User
from poc_trust_tower.core.schemas import PasswordChangeSchema, UserCreateSchema, UserUpdateSchema
from poc_trust_tower.core.security import DEMO_ROUNDS, hash_password, verify_password

from ._base import ConflictError, ForbiddenError, _add, _find, _next_id, _remove, _save
from .business_units import _BU_SEED, get_business_unit, repoBusinessUnits

def _demo_hash(password: str) -> str:
    return hash_password(password, rounds=DEMO_ROUNDS)


def _build_users() -> list[User]:
    users = [
        User(id=1, email="admin@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[0], role=ROLE.ADMIN),
        User(id=2, email="cfo@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[1], role=ROLE.CFO),
        User(id=3, email="bu@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[2], role=ROLE.BU),
        User(id=4, email="buHead@trust-tower.example", password=_demo_hash("aaa"), business_unit=repoBusinessUnits[3], role=ROLE.BU_HEAD),
    ]
    next_id = len(users) + 1
    for (slug, _), bu in zip(_BU_SEED, repoBusinessUnits):
        users.append(User(id=next_id, email=f"bu.{slug}@trust-tower.example", password=_demo_hash("bu"), business_unit=bu, role=ROLE.BU))
        users.append(User(id=next_id + 1, email=f"bu-head.{slug}@trust-tower.example", password=_demo_hash("bu-head"), business_unit=bu, role=ROLE.BU_HEAD))
        next_id += 2
    return users


repoUsers: list[User] = _build_users()

def get_user(user_id: int) -> User:
    return _find(repoUsers, user_id, "user")

def create_user(payload: UserCreateSchema) -> User:
    if any(u.email == payload.email for u in repoUsers):
        raise ConflictError(f"user {payload.email} already exists")
    user = User(
        id=_next_id(repoUsers),
        email=payload.email,
        password=hash_password(payload.password),
        business_unit=get_business_unit(payload.business_unit_id),
        role=payload.role,
    )
    return _add("repoUsers", user)


def update_user(user_id: int, payload: UserUpdateSchema) -> User:
    user = get_user(user_id)
    if any(u.email == payload.email and u is not user for u in repoUsers):
        raise ConflictError(f"user {payload.email} already exists")
    user.email = payload.email
    user.business_unit = get_business_unit(payload.business_unit_id)
    user.role = payload.role
    if payload.password:
        user.password = hash_password(payload.password)
    return _save("repoUsers", user)


def change_password(user: User, payload: PasswordChangeSchema) -> None:
    """Change le mot de passe de l'utilisateur après vérification de l'actuel."""
    if not verify_password(payload.current_password, user.password):
        raise ForbiddenError("current password is incorrect")
    user.password = hash_password(payload.new_password)
    _save("repoUsers", user)


def delete_user(user_id: int) -> None:
    _remove("repoUsers", get_user(user_id))
