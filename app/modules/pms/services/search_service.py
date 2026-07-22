# service/search_service.py

import math
import uuid
from collections import defaultdict
from datetime import date

from app.modules.pms.repositories.properties_repo import PropertyRepository
from app.modules.pms.repositories.room_repo import RoomRepository
from app.utils.exceptions import RepositoryException, ServiceException

from app.utils.logging import LoggerFactory

logger = LoggerFactory.get_logger(__name__)


class SearchService:
    def __init__(
        self,
        property_repo: PropertyRepository,
        room_repo: RoomRepository,
    ):
        self.property_repo = property_repo
        self.room_repo = room_repo

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
            total_count = len(all_candidates)

            # Slice the valid results according to skip & limit parameters
            paginated_candidates = all_candidates[skip : skip + limit]
            has_more = skip + len(paginated_candidates) < total_count

            enriched_properties = await self._attach_property_details(
                results=paginated_candidates
            )

            return {
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
                        "amenities": [a.name for a in amenities],
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
