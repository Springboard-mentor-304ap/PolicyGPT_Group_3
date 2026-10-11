"""Administrative user management under /admin/users.

Two rules drive every per-user handler here and are enforced in one place:

* nobody can act on their own account (a self-deactivate would lock the last
  administrator out of the platform), and
* nobody can act on a super admin — administrators included.

Each state change writes an audit row and, for deactivation, revokes the
target's refresh tokens so their sessions die immediately (`get_current_user`
rejects an inactive account on the very next request). Deactivation notifies
nobody, per spec.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.audit.service import client_ip, log_action
from backend.app.auth.dependencies import get_current_user
from backend.app.auth.refresh_tokens import revoke_user_refresh_tokens
from backend.app.db.database import get_db
from backend.app.models.user import User, UserRole
from backend.app.pagination import DEFAULT_LIMIT, clamp_limit

# Roles that may use /admin/users at all.
ADMIN_USER_ROLES = (
    UserRole.ADMINISTRATOR,
    UserRole.SUPER_ADMIN,
)

# What each administrative role is allowed to manage. A super admin adds
# administrators; nobody (super admin included) ever manages a super admin —
# that is checked separately, by target role.
MANAGEABLE_BY_ADMIN = frozenset({
    UserRole.CITIZEN,
    UserRole.RESEARCHER,
    UserRole.ORGANIZATION,
    UserRole.GOVERNMENT_OFFICIAL,
})
MANAGEABLE_BY_SUPER_ADMIN = MANAGEABLE_BY_ADMIN | {UserRole.ADMINISTRATOR}

# Audit trail actions (target table is always "users").
AUDIT_USER_DEACTIVATE = "admin.user_deactivate"
AUDIT_USER_REACTIVATE = "admin.user_reactivate"
AUDIT_USER_REVOKE_ROLE = "admin.user_revoke_role"

# SQL standard escape: the caller's own %, _ and \ are literals, not wildcards.
LIKE_ESCAPE = "\\"


def _escape_like(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


class AdminUserResponse(BaseModel):
    """Admin view of a user account.

    Deliberately an explicit allow-list: `password_hash` and the token columns
    exist on the model but are not declared here, so they can never be
    serialised into a response.
    """

    id: UUID
    full_name: str
    email: str
    phone: str | None = None
    role: UserRole
    is_active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


def require_admin_access(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ADMIN_USER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage users",
        )

    return current_user


def _load_target(db: Session, user_id: UUID) -> User:
    target = db.get(User, user_id)

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return target


def _ensure_may_manage(actor: User, target: User) -> None:
    """Permission matrix for every per-user admin action.

    Order matters: the self check runs first so an administrator acting on
    their own account gets the self message rather than a role message, and a
    super admin acting on themselves is still refused.
    """
    if target.id == actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot perform administrative actions on your own account",
        )

    if target.role == UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin accounts cannot be managed",
        )

    allowed = (
        MANAGEABLE_BY_SUPER_ADMIN
        if actor.role == UserRole.SUPER_ADMIN
        else MANAGEABLE_BY_ADMIN
    )

    if target.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage this user",
        )


router = APIRouter(
    prefix="/admin/users",
    tags=["Admin Users"],
    dependencies=[Depends(require_admin_access)],
)


@router.get("", response_model=list[AdminUserResponse])
def list_users(
    response: Response,
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_LIMIT, ge=1),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access),
):
    """List accounts with role / is_active / name-or-email filters.

    The search term is escaped before it is turned into an ILIKE pattern, so
    `%` and `_` typed by an operator match literally instead of widening the
    result set.
    """
    query = db.query(User)

    if role is not None:
        query = query.filter(User.role == role)

    if is_active is not None:
        query = query.filter(User.is_active.is_(is_active))

    if search is not None and search.strip():
        pattern = f"%{_escape_like(search.strip())}%"
        query = query.filter(
            or_(
                User.full_name.ilike(pattern, escape=LIKE_ESCAPE),
                User.email.ilike(pattern, escape=LIKE_ESCAPE),
            )
        )

    total = query.count()

    rows = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset(offset)
        .limit(clamp_limit(limit))
        .all()
    )

    response.headers["X-Total-Count"] = str(total)

    return rows


@router.get("/{user_id}", response_model=AdminUserResponse)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access),
):
    target = _load_target(db, user_id)
    _ensure_may_manage(current_user, target)

    return target


@router.post("/{user_id}/deactivate", response_model=AdminUserResponse)
def deactivate_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access),
):
    """Disable an account immediately and silently.

    No notification is sent, and every refresh token the account holds is
    revoked so its existing sessions cannot outlive the deactivation.
    """
    target = _load_target(db, user_id)
    _ensure_may_manage(current_user, target)

    target.is_active = False
    revoke_user_refresh_tokens(db, target.id)

    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_USER_DEACTIVATE,
        target_table="users",
        target_id=target.id,
        changes={"is_active": {"old": True, "new": False}},
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(target)

    return target


@router.post("/{user_id}/reactivate", response_model=AdminUserResponse)
def reactivate_user(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access),
):
    target = _load_target(db, user_id)
    _ensure_may_manage(current_user, target)

    target.is_active = True

    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_USER_REACTIVATE,
        target_table="users",
        target_id=target.id,
        changes={"is_active": {"old": False, "new": True}},
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(target)

    return target


@router.post("/{user_id}/revoke-role", response_model=AdminUserResponse)
def revoke_user_role(
    user_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_access),
):
    """Return an account to citizen and drop its government profile.

    The role claim inside any outstanding access token is irrelevant: every
    authorization check reads `current_user.role` from the database, so the
    demotion applies from the next request.
    """
    target = _load_target(db, user_id)
    _ensure_may_manage(current_user, target)

    old_role = target.role
    target.role = UserRole.CITIZEN

    profile = target.government_official_profile

    if profile is not None:
        db.delete(profile)

    log_action(
        db=db,
        actor_id=current_user.id,
        action=AUDIT_USER_REVOKE_ROLE,
        target_table="users",
        target_id=target.id,
        changes={
            "role": {
                "old": old_role.value,
                "new": UserRole.CITIZEN.value,
            }
        },
        ip_address=client_ip(request),
    )

    db.commit()
    db.refresh(target)

    return target
