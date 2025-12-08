from fastapi import APIRouter, Depends, HTTPException

from backend.core.models import UserCreateRequest, UserModel
from backend.database import create_user, get_user_by_username, list_users, delete_user
from backend.auth.password import hash_password
from backend.auth import get_current_admin

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserModel)
async def create_new_user(
    body: UserCreateRequest,
    _: str = Depends(get_current_admin),
):
    """
    Create a new user with hashed password.
    Requires admin authentication.
    """
    # Check if user already exists
    existing_user = await get_user_by_username(body.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # Hash the password
    hashed_password = hash_password(body.password)

    # Create the user
    user = await create_user(body.username, hashed_password)

    return UserModel(
        id=user.id,
        username=user.username,
        created_at=user.createdAt.isoformat(),
        updated_at=user.updatedAt.isoformat()
    )


@router.get("", response_model=list[UserModel])
async def get_users(
    _: str = Depends(get_current_admin),
):
    """
    List all users.
    Requires admin authentication.
    """
    users = await list_users()
    return [
        UserModel(
            id=user.id,
            username=user.username,
            created_at=user.createdAt.isoformat(),
            updated_at=user.updatedAt.isoformat()
        )
        for user in users
    ]


@router.delete("/{username}")
async def delete_user_by_username(
    username: str,
    _: str = Depends(get_current_admin),
):
    """
    Delete a user by username.
    Requires admin authentication.
    """
    user = await get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await delete_user(username)
    return {"ok": True}
