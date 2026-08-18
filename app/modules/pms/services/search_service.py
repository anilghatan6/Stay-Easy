# service/search_service.py

import math
import uuid
from collections import defaultdict
from datetime import date

from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.utils.exceptions import RepositoryException, ServiceException
from app.utils.cache import build_cache_key, get_cached, set_cached

from app.utils.logging import LoggerFactory
from typing import Optional
import redis.asyncio as aioredis

logger = LoggerFactory.get_logger(__name__)

SEARCH_CACHEABLE_DESTINATIONS={"pokhara","kathmandu"}
SEARCH_CACHE_TTL_SECONDS=600

class SearchService:
    def __init__(
        self,
        property_repo: PropertyRepository,
        room_repo: RoomRepository,
        redis_client: Optional[aioredis.Redis] = None,
    ):
        self.property_repo = property_repo
        self.room_repo = room_repo
        self.redis = redis_client
        
    async def search(
        self,
        destination: str,
        check_in: date,
        check_out: date,
        adults: int,
        children: int,
        rooms_needed: int,
        skip: int,
        limit: int,
    ):
        logger.info(
            f"[SearchService] Initiationg searching for destination: {destination}"
        )
        normalized_destination = destination.strip().lower()
        is_cacheable = self.redis is not None and normalized_destination in SEARCH_CACHEABLE_DESTINATIONS

        cache_key = None
        if is_cacheable:
            try:
                cache_key = build_cache_key(
                    "property_search",
                    destination=normalized_destination,
                    check_in=check_in.isoformat(),
                    check_out=check_out.isoformat(),
                    adults=adults,
                    children=children,
                    rooms=rooms_needed,
                    skip=skip,
                    limit=limit,
                )

            except ValueError as e:
                logger.error(f"[SearchService] Failed to build cache key: {e}")
                cache_key = None

            if cache_key:
                cached = await get_cached(self.redis, cache_key)
                if cached is not None:
                    logger.info(f"[SearchService] Retrieved search results from cache for key: {cache_key}")
                    return cached
                logger.info(f"[SearchService] Cache MISS: {cache_key}")
        try:
            nights = (check_out - check_in).days

            adults_per_room = math.ceil(adults / rooms_needed)
            children_per_room = math.ceil(children / rooms_needed)

            # 1. Fuzzy destination match — now returns (Property, score) pairs
            matched = await self.property_repo.search_by_destination(query=destination)
            if not matched:
                return {
                    "data": {
                        "adults": adults,
                        "children": children,
                        "rooms": rooms_needed,
                        "results": [],
                    },
                    "meta": {
                        "total": 0,
                        "skip": skip,
                        "limit": limit,
                        "has_more": False,
                    },
                }

            property_score_map = {prop.id: score for prop, score in matched}
            property_ids = list(property_score_map.keys())

            # 2. Availability-filtered rooms for the date range
            available_rooms = await self.room_repo.get_available_rooms(
                property_ids, check_in, check_out
            )

            rooms_by_property: dict[uuid.UUID, list] = defaultdict(list)
            for r in available_rooms:
                rooms_by_property[r.property_id].append(r)

            all_candidates = []
            for property_id, rooms in rooms_by_property.items():
                candidates = [
                    r
                    for r in rooms
                    if r.max_adults >= adults_per_room
                    and r.max_children >= children_per_room
                ]
                candidates.sort(key=lambda r: r.base_rate)
                selected = candidates[:rooms_needed]

                if len(selected) < rooms_needed:
                    continue

                total_price = sum(r.base_rate for r in selected) * nights
                all_candidates.append(
                    {
                        "property_id": property_id,
                        "total_price": total_price,
                        "nights": nights,
                        "match_score": property_score_map[property_id],
                    }
                )

            # 3. Rank: best match first, then cheapest within similar relevance
            all_candidates.sort(key=lambda x: (-x["match_score"], x["total_price"]))

            # --- PAGINATION CALCULATIONS ---


            # Slice the valid results according to skip & limit parameters
            paginated_candidates = all_candidates[skip : skip + limit]

            enriched_properties = await self._attach_property_details(
                results=paginated_candidates
            )
            total_count = len(all_candidates)
            has_more = skip + len(paginated_candidates) < total_count


            response =  {
                "data": {
                    "adults": adults,
                    "children": children,
                    "rooms": rooms_needed,
                    "results": enriched_properties,
                },
                "meta": {
                    "total": total_count,
                    "skip": skip,
                    "limit": limit,
                    "has_more": has_more,
                },
            }
            if is_cacheable and cache_key:
                await set_cached(self.redis, cache_key, response, SEARCH_CACHE_TTL_SECONDS)
                logger.info(f"[SearchService] Cached search results for key: {cache_key}")

            return response
        except RepositoryException:
            raise

        except Exception as e:
            logger.error("[SearchService] Error searching for given query")
            raise ServiceException(internal_detail=f"Failed to search for {str(e)}")

    async def _attach_property_details(self, results: list):
        logger.info("Attaching property details")
        if not results:
            return []

        try:
            property_ids = [r["property_id"] for r in results]
            properties = {
                p.id: p
                for p in await self.property_repo.get_by_ids(property_ids=property_ids)
            }

            enriched = []
            for r in results:
                prop = properties.get(r["property_id"])
                if not prop:
                    continue

                amenity_ids = (prop.system_amenity_ids or [])[:5]
                amenities = (
                    await self.property_repo.get_amenities_by_ids(
                        amenity_ids=amenity_ids
                    )
                    if amenity_ids
                    else []
                )

                enriched.append(
                    {
                        "property_id": prop.id,
                        "name": prop.name,
                        "country": prop.country,
                        "state": prop.state,
                        "city": prop.city,
                        "address": prop.address,
                        "type":str(prop.type),
                        "cover_photo": str(prop.photos.get("cover"))
                        if prop.photos
                        else None,
                        "amenities": [a.name for a in amenities],
                        "description":prop.description,
                        "currency": prop.currency,
                        "total_price": float(r["total_price"]),
                        "nights": r["nights"],
                    }
                )
            return enriched

        except RepositoryException:
            raise
        except Exception as e:
            logger.error("[SearchService] Error attaching property details")
            raise ServiceException(
                internal_detail=f"Failed to attach property details: {str(e)}"
            )

    async def get_nearby_properties(self, lat: float, lon: float,limit: int ):
        logger.info(
            f"[SearchService] Getting nearby properties for lat: {lat}, lon: {lon}"
        )
        try:
            rows, radius_used_m = await self.property_repo.get_nearby_properties(
                lat, lon,  limit
            )

            results = [
                {
                    "property_id": row.id,
                    "name": row.name,
                    "type": row.type,
                    "country": row.country,
                    "state": row.state,
                    "city": row.city,
                    "address": row.address,
                    "currency": row.currency,
                    "cover_photo": row.cover_photo,
                    "distance_km": round(row.distance_m / 1000, 2),
                    "lowest_rate": (
                        float(row.min_base_rate)
                        if row.min_base_rate is not None
                        else None
                    ),
                }
                for row in rows
            ]
            return {
                "search_radius_km": round(radius_used_m / 1000),
                "count": len(results),
                "results": results,
            }
        except RepositoryException:
            raise
        except Exception as e:
            logger.error(
                f"[PropertyService] Unexpected error fetching nearby properties: {e}"
            )
            raise ServiceException(
                "Could not fetch nearby properties. Please try again."
            )
