
from __future__ import annotations

from math import cos, isfinite, radians
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.cores.db import get_session
from app.models import Location
from app.models.enums import LocationType
from app.schemas.location import (
    LocationPage,
    LocationPublic,
    LocationTree,
    NearbyLocationPage,
)

from app.services.location import location_service as service

locations_router = APIRouter(
    prefix="/locations",
    tags=["Géographie"],
)


@locations_router.get("", response_model=LocationPage)
async def list_locations(
    q: str | None = Query(default=None, min_length=2, max_length=150),
    location_type: LocationType | None = Query(default=None, alias="type"),
    country_code: str | None = Query(default=None, min_length=2, max_length=2),
    parent_id: UUID | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    filters = [Location.is_active.is_(True)]

    if location_type is not None:
        filters.append(Location.type == location_type)

    if country_code is not None:
        filters.append(
            Location.country_code == service.normalize_code(country_code)
        )

    if parent_id is not None:
        filters.append(Location.parent_id == parent_id)

    if q is not None:
        term = service.escape_like(q.strip())
        filters.append(
            Location.name.ilike(f"%{term}%", escape="\\")
        )

    count_result = await session.execute(
        select(func.count(Location.id)).where(*filters)
    )

    result = await session.execute(
        select(Location)
        .where(*filters)
        .order_by(Location.name, Location.id)
        .offset(offset)
        .limit(limit)
    )

    return {
        "items": [
            service.public_location(item)
            for item in result.scalars().all()
        ],
        "total": count_result.scalar_one(),
        "limit": limit,
        "offset": offset,
    }


@locations_router.get("/nearby", response_model=NearbyLocationPage)
async def nearby_locations(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    radius_km: float = Query(default=25, gt=0, le=100),
    limit: int = Query(default=20, ge=1, le=100),
    location_type: LocationType | None = Query(default=None, alias="type"),
    session: AsyncSession = Depends(get_session),
):
    if not all(isfinite(v) for v in (latitude, longitude, radius_km)):
        raise HTTPException(
            status_code=422,
            detail="Les coordonnées et le rayon doivent être finis.",
        )

    lat_delta = radius_km / 110.574
    lon_scale = max(abs(cos(radians(latitude))), 0.01)
    lon_delta = radius_km / (111.320 * lon_scale)

    filters = [
        Location.is_active.is_(True),
        Location.latitude.isnot(None),
        Location.longitude.isnot(None),
        Location.latitude.between(
            max(-90, latitude - lat_delta),
            min(90, latitude + lat_delta),
        ),
    ]

    if lon_delta < 180:
        west, east = longitude - lon_delta, longitude + lon_delta

        if west < -180:
            filters.append(
                or_(
                    Location.longitude >= west + 360,
                    Location.longitude <= east,
                )
            )
        elif east > 180:
            filters.append(
                or_(
                    Location.longitude >= west,
                    Location.longitude <= east - 360,
                )
            )
        else:
            filters.append(Location.longitude.between(west, east))

    if location_type is not None:
        filters.append(Location.type == location_type)

    cosine = (
        func.sin(func.radians(latitude))
        * func.sin(func.radians(Location.latitude))
        + func.cos(func.radians(latitude))
        * func.cos(func.radians(Location.latitude))
        * func.cos(
            func.radians(Location.longitude) - func.radians(longitude)
        )
    )

    distance = 6371.0088 * func.acos(
        func.least(1.0, func.greatest(-1.0, cosine))
    )

    result = await session.execute(
        select(Location, distance.label("distance_km"))
        .where(*filters, distance <= radius_km)
        .order_by(distance, Location.id)
        .limit(limit)
    )

    return {
        "items": [
            {
                **service.public_location(location),
                "distance_km": round(distance_km, 3),
            }
            for location, distance_km in result.all()
        ],
        "limit": limit,
        "radius_km": radius_km,
    }


@locations_router.get("/countries", response_model=list[LocationPublic])
async def list_countries(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Location)
        .where(
            Location.type == LocationType.COUNTRY,
            Location.parent_id.is_(None),
            Location.is_active.is_(True),
        )
        .order_by(Location.name, Location.id)
    )
    return [service.public_location(x) for x in result.scalars().all()]

