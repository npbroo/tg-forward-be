import uuid

from fastapi import APIRouter, Depends, HTTPException, Path

from models import RouteCreateRequest, RouteUpdateRequest, RouteModel
from database import create_route as db_create_route, get_route, update_route as db_update_route, delete_route as db_delete_route, list_routes as db_list_routes
from events import emit_route_change
from auth_jwt import get_current_admin

router = APIRouter(prefix="/routes", tags=["routes"])
@router.post("", response_model=RouteModel)
async def create_route(
    body: RouteCreateRequest,
    _: str = Depends(get_current_admin),
):
    route_id = f"route_{uuid.uuid4().hex}"
    route = await db_create_route(
        route_id=route_id,
        source_chat=str(body.source_chat),
        target_chat=str(body.target_chat),
        transform_type=body.transform_type,
        enabled=body.enabled
    )
    await emit_route_change()
    return RouteModel(
        route_id=route.routeId,
        source_chat=route.sourceChat,
        target_chat=route.targetChat,
        transform_type=route.transformType,
        enabled=route.enabled
    )


@router.get("", response_model=list[RouteModel])
async def list_routes(
    _: str = Depends(get_current_admin),
):
    routes = await db_list_routes()
    return [RouteModel(
        route_id=r.routeId,
        source_chat=r.sourceChat,
        target_chat=r.targetChat,
        transform_type=r.transformType,
        enabled=r.enabled
    ) for r in routes]


@router.patch("/{route_id}", response_model=RouteModel)
async def update_route(
    body: RouteUpdateRequest,
    route_id: str = Path(...),
    _: str = Depends(get_current_admin),
):
    existing = await get_route(route_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")

    update_data = {}
    if body.enabled is not None:
        update_data["enabled"] = body.enabled
    if body.transform_type is not None:
        update_data["transformType"] = body.transform_type
    if body.source_chat is not None:
        update_data["sourceChat"] = str(body.source_chat)
    if body.target_chat is not None:
        update_data["targetChat"] = str(body.target_chat)

    route = await db_update_route(route_id, update_data)
    await emit_route_change()
    return RouteModel(
        route_id=route.routeId,
        source_chat=route.sourceChat,
        target_chat=route.targetChat,
        transform_type=route.transformType,
        enabled=route.enabled
    )


@router.delete("/{route_id}")
async def delete_route(
    route_id: str = Path(...),
    _: str = Depends(get_current_admin),
):
    existing = await get_route(route_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Route not found")

    await db_delete_route(route_id)
    await emit_route_change()

    return {"ok": True}
