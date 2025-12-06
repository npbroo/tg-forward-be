import uuid

from fastapi import APIRouter, Depends, HTTPException, Path

from models import RouteCreateRequest, RouteUpdateRequest, RouteModel
from shared.redis_client import redis_set_json, redis_get_json, redis_scan_json, redis_client
from shared.pubsub import notify_forwarder_reload
from auth_jwt import get_current_admin

router = APIRouter(prefix="/routes", tags=["routes"])
@router.post("", response_model=RouteModel)
async def create_route(
    body: RouteCreateRequest,
    _: str = Depends(get_current_admin),
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
    await notify_forwarder_reload("route_created")
    return RouteModel(**data)


@router.get("", response_model=list[RouteModel])
async def list_routes(
    _: str = Depends(get_current_admin),
):
    raw_routes = await redis_scan_json("tg:route:route_*")
    return [RouteModel(**r) for r in raw_routes]


@router.patch("/{route_id}", response_model=RouteModel)
async def update_route(
    body: RouteUpdateRequest,
    route_id: str = Path(...),
    _: str = Depends(get_current_admin),
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
    await notify_forwarder_reload("route_updated")
    return RouteModel(**data)


@router.delete("/{route_id}")
async def delete_route(
    route_id: str = Path(...),
    _: str = Depends(get_current_admin),
):
    key = f"tg:route:{route_id}"
    existing = await redis_get_json(key)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")

    # delete raw key
    await redis_client.delete(key)
    await notify_forwarder_reload("route_deleted")

    return {"ok": True}
