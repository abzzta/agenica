"""
Dynamic Room Discovery, Resource Indexing & Batch Booking Engine for Google Workspace.
Scalable, zero-hardcoding architecture supporting multi-floor and global office buildings.
"""

import os
import re
import json
import logging
import zoneinfo
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Tuple, Any

from ..config import (
    PRINCIPAL_EMAIL,
    DEFAULT_TIMEZONE,
    OFFICE_LOCATION,
    OFFICE_PRIMARY_FLOOR,
    BUILDING_CODE,
)
from .auth_service import AuthService

logger = logging.getLogger("agenica.services.rooms")
SGT_TZ = zoneinfo.ZoneInfo(DEFAULT_TIMEZONE)

# Global Google Office Directory Mapping (City / Airport code -> Google Building Codes)
GLOBAL_OFFICE_MAP: Dict[str, List[str]] = {
    # APAC
    "sydney": ["AU-SYD-PIR", "AU-SYD-ODI", "SYD"],
    "melbourne": ["AU-MEL-MQT", "MEL"],
    "canberra": ["AU-CBR-NORTHB", "CBR"],
    "singapore": ["SG-SIN-MBC2", "SIN", "MBC2"],
    "tokyo": ["JP-TOK-STRM", "TOK", "STRM", "SHIBUYA", "ROPPONGI"],
    "seoul": ["KR-SEO-GFC", "SEO", "GFC"],
    "hong kong": ["HK-HKG-TW2", "HKG", "TW2"],
    "taipei": ["TW-TPE-101", "TPE", "101"],
    "kuala lumpur": ["MY-KUL-QIL7", "KUL"],
    "bangkok": ["TH-BKK-PVE", "BKK"],
    "jakarta": ["ID-CGK-PCP", "CGK"],
    "auckland": ["NZ-AKL-MAD10", "AKL"],
    "manila": ["PH-MNL-NETP", "MNL"],
    "bangalore": ["IN-BLR-ANANTA", "IN-BLR-BCPWK", "IN-BLR-RMZ", "BLR"],
    "bengaluru": ["IN-BLR-ANANTA", "IN-BLR-BCPWK", "IN-BLR-RMZ", "BLR"],
    "gurgaon": ["IN-GUR-SIGD", "IN-GUR-SIGB", "IN-GUR-TRILB", "GUR", "GGN"],
    "gurugram": ["IN-GUR-SIGD", "IN-GUR-SIGB", "IN-GUR-TRILB", "GUR", "GGN"],
    "mumbai": ["IN-MUM-FIFC", "MUM", "BOM"],
    "beijing": ["CN-PEK-RCB", "PEK"],
    "shanghai": ["CN-SHA-WFC", "SHA"],
    "shenzhen": ["CN-SZX-HUG5001", "SZX"],

    # EMEA
    "london": ["UK-LON-CSG", "UK-LON-6PS", "UK-LON-R7", "UK-LON-S2", "UK-LON-6PNC", "LON"],
    "dublin": ["IE-DUB-GRCQ1", "IE-DUB-DOC", "DUB"],
    "zurich": ["CH-ZRH-EURG", "CH-ZRH-EURD", "ZRH"],
    "paris": ["FR-PAR-RDL", "PAR"],
    "berlin": ["DE-BER-TSKY2", "BER"],
    "barcelona": ["ES-BCN-GRA", "BCN"],
    "helsinki": ["FI-HEL-ARK6", "HEL"],
    "dubai": ["AE-DXB-HUB2", "DXB"],
    "nairobi": ["KE-NBO-PROM", "NBO"],

    # AMER
    "mountain view": ["US-MTV", "MTV"],
    "sunnyvale": ["US-SVL-MP3", "SVL", "MP3", "MOFFETT"],
    "seattle": ["US-SEA-BRN", "SEA"],
    "chicago": ["US-CHI-CARP210", "CHI"],
    "new york": ["US-NYC", "NYC"],
    "toronto": ["CA-TOR-KING65", "TOR"],
    "ottawa": ["CA-OTT-QUEEN222", "OTT"],
    "sao paulo": ["BR-SAO-SPCT", "SAO"],
}


@dataclass
class RoomResource:
    """Standardized Google Calendar Room Resource Model."""
    email: str
    name: str
    clean_name: str
    building: str
    floor: Optional[int] = None
    capacity: int = 2
    type: str = "meeting_room"  # "meeting_room" | "phone_booth" | "focus_room"
    features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RoomService:
    """
    Dynamic Google Workspace Room Management Service.
    - Inverted indexing for microsecond lookups across floors, buildings, and names.
    - Global Office Resolution mapping cities/offices worldwide to Google Calendar room resources.
    - Dynamic calendar-based resource discovery fallback for unindexed rooms/buildings.
    - High-efficiency batch FreeBusy checks (single HTTP request for N rooms).
    """

    _instance = None

    def __init__(self, cache_file_path: Optional[str] = None):
        self.auth_service = AuthService.get_instance()
        self.cache_file = cache_file_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "tools", "extracted_rooms.json"
        )
        self._rooms: Dict[str, RoomResource] = {}
        self._by_building: Dict[str, List[RoomResource]] = {}
        self._by_building_floor: Dict[Tuple[str, int], List[RoomResource]] = {}
        self._by_name_tokens: Dict[str, Set[str]] = {}

        self._load_and_index()

    @classmethod
    def get_instance(cls) -> "RoomService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def resolve_target_buildings(location_str: Optional[str]) -> List[str]:
        """Resolve a city name, airport code, or office string to Google building codes."""
        if not location_str:
            return []

        clean_loc = location_str.lower().strip()

        # 1. Exact match in office map
        if clean_loc in GLOBAL_OFFICE_MAP:
            return GLOBAL_OFFICE_MAP[clean_loc]

        # 2. Token match (e.g. "Sydney office" -> "sydney")
        for city, codes in GLOBAL_OFFICE_MAP.items():
            if city in clean_loc or any(token == city for token in re.findall(r"[a-z0-9]+", clean_loc)):
                return codes

        # 3. Direct building code pattern (e.g. "AU-SYD", "UK-LON", "US-MTV")
        bldg_match = re.search(r"([A-Z]{2}-[A-Z0-9]+)", location_str, re.IGNORECASE)
        if bldg_match:
            return [bldg_match.group(1).upper()]

        return [location_str]

    @staticmethod
    def parse_room_name(full_name: str, email: str) -> RoomResource:
        """Dynamically extract building, floor, capacity, and clean room name from naming conventions."""
        clean_name = full_name.split("[")[0].strip()
        building = "OTHER"
        floor = None
        capacity = 2
        room_type = "meeting_room"

        # 1. Detect Building
        bldg_match = re.search(r"([A-Z]{2}-[A-Z0-9]+-[A-Z0-9]+)", full_name)
        if bldg_match:
            building = bldg_match.group(1)
        elif "MBC2" in full_name or "Mapletree" in full_name:
            building = "SG-SIN-MBC2"
        elif "SYD" in full_name or "Sydney" in full_name:
            building = "AU-SYD-PIR"
        elif "MEL" in full_name or "Melbourne" in full_name:
            building = "AU-MEL-MQT"
        elif "MTV" in full_name or "Mountain View" in full_name:
            building = "US-MTV"
        elif "LON" in full_name or "London" in full_name:
            building = "UK-LON-CSG"
        elif "TOK" in full_name or "Tokyo" in full_name:
            building = "JP-TOK-STRM"

        # 2. Detect Floor
        floor_match = re.search(r"(?:-|\bLevel\s*|\bFloor\s*|\bL)([0-9]{1,2})(?:-|\b)", full_name, re.IGNORECASE)
        if floor_match:
            try:
                floor = int(floor_match.group(1))
            except ValueError:
                pass

        # 3. Detect Capacity
        cap_match = re.search(r"\((\d{1,3})\)", full_name)
        if cap_match:
            try:
                capacity = int(cap_match.group(1))
            except ValueError:
                pass

        # 4. Detect Type
        name_lower = full_name.lower()
        if "phone" in name_lower or capacity <= 2:
            room_type = "phone_booth"
        elif "board" in name_lower or capacity >= 15:
            room_type = "boardroom"
        elif "focus" in name_lower:
            room_type = "focus_room"

        # 5. Extract human-readable clean room name
        tokens = re.sub(r"^[A-Z]{2}-[A-Z0-9]+-[A-Z0-9]+-?\d*-?", "", clean_name).strip()
        tokens = re.sub(r"\([0-9]+\)", "", tokens).strip()
        tokens = re.sub(r"^[A-Z0-9]-[A-Z0-9]+\s*", "", tokens).strip()
        tokens = re.sub(r"-External", "", tokens, flags=re.IGNORECASE).strip()
        tokens = re.sub(r"\s+", " ", tokens).strip()
        human_name = tokens if tokens else clean_name

        return RoomResource(
            email=email,
            name=clean_name,
            clean_name=human_name,
            building=building,
            floor=floor,
            capacity=capacity,
            type=room_type,
        )

    def _index_room(self, room: RoomResource):
        """Add room to multi-tiered in-memory indices."""
        self._rooms[room.email] = room
        self._by_building.setdefault(room.building, []).append(room)
        if room.floor is not None:
            self._by_building_floor.setdefault((room.building, room.floor), []).append(room)

        search_blob = f"{room.name} {room.clean_name} {room.building} floor {room.floor} level {room.floor}".lower()
        for token in re.findall(r"[a-z0-9]+", search_blob):
            self._by_name_tokens.setdefault(token, set()).add(room.email)

    def _load_and_index(self):
        """Load rooms from local persistent store and index in memory."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for email, r_data in data.items():
                    r = RoomResource(
                        email=email,
                        name=r_data.get("name") or r_data.get("full_name") or email,
                        clean_name=r_data.get("clean_name") or r_data.get("name") or email,
                        building=r_data.get("building") or "SG-SIN-MBC2",
                        floor=r_data.get("floor"),
                        capacity=r_data.get("capacity", 2),
                        type=r_data.get("type", "meeting_room"),
                    )
                    self._index_room(r)
            except Exception as e:
                logger.warning("Could not read room cache: %s", e)

    def dynamic_discovery(self, query: str) -> List[RoomResource]:
        """Dynamic on-demand discovery fallback searching Google Calendar history."""
        found: List[RoomResource] = []
        try:
            service = self.auth_service.get_calendar_service()
            now = datetime.now(timezone.utc)
            res = service.events().list(
                calendarId="primary",
                timeMin=(now - timedelta(days=180)).isoformat(),
                timeMax=(now + timedelta(days=180)).isoformat(),
                q=query,
                singleEvents=True,
                maxResults=50,
            ).execute()

            for event in res.get("items", []):
                for att in event.get("attendees", []):
                    email = att.get("email", "")
                    if "resource.calendar.google.com" in email:
                        if email not in self._rooms:
                            disp = att.get("displayName") or event.get("location") or email
                            new_room = self.parse_room_name(disp, email)
                            self._index_room(new_room)
                            found.append(new_room)
            if found:
                self._persist_cache()
        except Exception as ex:
            logger.warning("Dynamic room discovery warning for '%s': %s", query, ex)

        return found

    def _persist_cache(self):
        """Asynchronously save updated room index to cache."""
        try:
            dump = {email: r.to_dict() for email, r in self._rooms.items()}
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(dump, f, indent=2)
        except Exception as e:
            logger.warning("Failed to persist room cache: %s", e)

    def search_rooms(
        self,
        query: Optional[str] = None,
        building: Optional[str] = None,
        office: Optional[str] = None,
        location: Optional[str] = None,
        floor: Optional[int] = None,
        room_type: Optional[str] = None,
        min_capacity: int = 1,
        limit: int = 25,
    ) -> List[RoomResource]:
        """
        Global multi-office query over indexed room resources.
        Supports cities (Sydney, London, Tokyo, Melbourne), buildings, and floors worldwide.
        """
        candidates: List[RoomResource] = []

        # 1. Resolve target location / office / building
        loc_str = building or office or location

        # If loc_str is None, check if query itself mentions an office/city from GLOBAL_OFFICE_MAP
        if not loc_str and query:
            q_lower = query.lower()
            for city in GLOBAL_OFFICE_MAP:
                if city in q_lower:
                    loc_str = city
                    break

        target_building_codes: List[str] = []
        if loc_str:
            target_building_codes = self.resolve_target_buildings(loc_str)
        else:
            # Default to primary building (Singapore MBC2) ONLY if no location was specified
            target_building_codes = ["SG-SIN-MBC2"]

        # 2. Gather candidates from resolved building codes
        for code in target_building_codes:
            code_lower = code.lower()
            for b, rlist in self._by_building.items():
                if code_lower in b.lower():
                    candidates.extend(rlist)

        # 3. Apply floor filter
        if floor is not None:
            if candidates:
                floor_filtered = [r for r in candidates if r.floor == floor]
                if floor_filtered:
                    candidates = floor_filtered
            else:
                # Direct lookup in floor index
                for (b, f), rlist in self._by_building_floor.items():
                    if f == floor:
                        candidates.extend(rlist)

        # 4. Filter by specific room name query (if not just the city name)
        if query:
            q_clean = query.lower().strip()
            # If query is not just the resolved location name
            if not loc_str or q_clean != loc_str.lower():
                matched_emails = set()
                for token in re.findall(r"[a-z0-9]+", q_clean):
                    if token in self._by_name_tokens:
                        matched_emails.update(self._by_name_tokens[token])

                if matched_emails:
                    named = [self._rooms[e] for e in matched_emails if e in self._rooms]
                    if candidates:
                        refined = [r for r in candidates if r.email in matched_emails]
                        candidates = refined if refined else named
                    else:
                        candidates = named

        # 5. Dynamic Discovery Fallback if still empty
        if not candidates and (loc_str or query or floor is not None):
            disc_term = loc_str or query or f"Floor {floor}"
            candidates = self.dynamic_discovery(disc_term)

        # 6. Filter by capacity and room_type
        if room_type:
            rt_clean = room_type.lower()
            candidates = [r for r in candidates if rt_clean in r.type.lower() or rt_clean in r.name.lower()]

        if min_capacity > 1:
            candidates = [r for r in candidates if r.capacity >= min_capacity]

        # De-duplicate while preserving order
        seen = set()
        unique_candidates = []
        for r in candidates:
            if r.email not in seen:
                seen.add(r.email)
                unique_candidates.append(r)

        return unique_candidates[:limit]

    def check_availability(
        self,
        rooms: List[RoomResource],
        start_iso: str,
        end_iso: str,
    ) -> Dict[str, Any]:
        """
        High-efficiency BATCH FreeBusy availability check for multiple rooms.
        Performs 1 single network call to Google Calendar API regardless of number of rooms.
        """
        if not rooms:
            return {"available": [], "busy": [], "total_checked": 0}

        try:
            body = {
                "timeMin": start_iso,
                "timeMax": end_iso,
                "items": [{"id": r.email} for r in rooms],
            }
            res = self.auth_service.execute_call(
                "calendar", "v3",
                lambda s: s.freebusy().query(body=body).execute()
            )
            calendars = res.get("calendars", {})

            available: List[RoomResource] = []
            busy: List[RoomResource] = []

            for r in rooms:
                busy_slots = calendars.get(r.email, {}).get("busy", [])
                if len(busy_slots) == 0:
                    available.append(r)
                else:
                    busy.append(r)

            return {
                "available": available,
                "busy": busy,
                "total_checked": len(rooms),
            }
        except Exception as e:
            logger.error("Batch FreeBusy check error: %s", e)
            return {"available": [], "busy": rooms, "total_checked": len(rooms), "error": str(e)}

    def find_available_room(
        self,
        floor: Optional[int] = None,
        building: Optional[str] = None,
        office: Optional[str] = None,
        location: Optional[str] = None,
        room_name: Optional[str] = None,
        room_type: Optional[str] = None,
        min_capacity: int = 1,
        start_iso: str = "",
        end_iso: str = "",
    ) -> Optional[RoomResource]:
        """Find the first available room matching criteria using high-speed batch check."""
        candidate_rooms = self.search_rooms(
            query=room_name,
            building=building,
            office=office,
            location=location,
            floor=floor,
            room_type=room_type,
            min_capacity=min_capacity,
            limit=15,
        )

        if not candidate_rooms and floor is not None:
            candidate_rooms = self.search_rooms(
                building=building,
                office=office,
                location=location,
                floor=OFFICE_PRIMARY_FLOOR,
                room_type=room_type,
                min_capacity=min_capacity,
                limit=10,
            )

        if not candidate_rooms:
            return None

        result = self.check_availability(candidate_rooms, start_iso, end_iso)
        available = result.get("available", [])
        return available[0] if available else None

    def book_room(
        self,
        room: RoomResource,
        start_iso: str,
        end_iso: str,
        summary: str = "Focus / Meeting",
        description: str = "",
        attendees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Book a meeting room or phone booth directly on user's primary calendar with room resource attached.
        """
        try:
            service = self.auth_service.get_calendar_service()
            attendee_list = [{"email": PRINCIPAL_EMAIL, "responseStatus": "accepted"}]
            attendee_list.append({
                "email": room.email,
                "displayName": room.clean_name,
                "resource": True,
            })
            if attendees:
                for att in attendees:
                    if att and att not in (PRINCIPAL_EMAIL, room.email):
                        attendee_list.append({"email": att})

            event_body = {
                "summary": f"[{room.clean_name}] {summary}",
                "location": f"{room.name}, {room.building}",
                "description": description or f"Reserved by Agenica S for Abhi Sethi ({room.clean_name})",
                "start": {"dateTime": start_iso, "timeZone": DEFAULT_TIMEZONE},
                "end": {"dateTime": end_iso, "timeZone": DEFAULT_TIMEZONE},
                "attendees": attendee_list,
                "conferenceData": {
                    "createRequest": {
                        "requestId": f"meet-room-{int(datetime.now().timestamp())}",
                        "conferenceSolutionKey": {"type": "hangoutsMeet"},
                    }
                },
            }

            created = service.events().insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1,
                sendUpdates="all",
            ).execute()

            meet_link = created.get("hangoutLink", "")
            cal_link = created.get("htmlLink", f"https://calendar.google.com/calendar/u/{PRINCIPAL_EMAIL}/r")

            return {
                "status": "confirmed",
                "event_id": created.get("id"),
                "room_name": room.clean_name,
                "full_room_name": room.name,
                "building": room.building,
                "floor": room.floor,
                "meet_link": meet_link,
                "calendar_link": cal_link,
                "summary": created.get("summary"),
                "message": f"Successfully reserved {room.clean_name} ({room.building} Floor {room.floor}) with Google Meet.",
            }
        except Exception as e:
            logger.error("Failed booking room %s: %s", room.name, e)
            return {
                "status": "failed",
                "error": str(e),
                "room_name": room.clean_name,
                "message": f"Could not reserve {room.clean_name}: {e}",
            }
