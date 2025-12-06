import uuid

from fastapi import APIRouter, Depends, HTTPException, Path, Header

from models import RouteCreateRequest, RouteUpdateRequest, RouteModel
from shared.redis_client import redis_set_json, redis_get_json, redis_scan_json, redis_client
from config import settings

router = APIRouter(prefix="/routes", tags=["routes"])


def require_admin(x_admin_token: str = Header(..., alias="X-Admin-Token")):
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return True


@router.post("", response_model=RouteModel)
async def create_route(
    body: RouteCreateRequest,
    _: bool = Depends(require_admin),
):
    route_id = f"route_{uuid.uuid4().hex}"
    data = {
        "route_id": route_id,
        "source_chat": body.source_chat,
        "target_chat": body.target_chat,
        "transform_type": body.transform_type,
        "enabled": body.enabled,
    }
    await redis_set_json(f"tg:route:{route_id}", data)
    return RouteModel(**data)


@router.get("", response_model=list[RouteModel])
async def list_routes(
    _: bool = Depends(require_admin),
):
    raw_routes = await redis_scan_json("tg:route:route_*")
    return [RouteModel(**r) for r in raw_routes]


@router.patch("/{route_id}", response_model=RouteModel)
async def update_route(
    route_id: str = Path(...),
    body: RouteUpdateRequest = None,
    _: bool = Depends(require_admin),
):
    key = f"tg:route:{route_id}"
    existing = await redis_get_json(key)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")

    data = existing.copy()

    if body.enabled is not None:
        data["enabled"] = body.enabled
    if body.transform_type is not None:
        data["transform_type"] = body.transform_type
    if body.source_chat is not None:
        data["source_chat"] = body.source_chat
    if body.target_chat is not None:
        data["target_chat"] = body.target_chat

    await redis_set_json(key, data)
    return RouteModel(**data)


@router.delete("/{route_id}")
async def delete_route(
    route_id: str = Path(...),
    _: bool = Depends(require_admin),
):
    key = f"tg:route:{route_id}"
    existing = await redis_get_json(key)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")

    # delete raw key
    await redis_client.delete(key)

    return {"ok": True}
