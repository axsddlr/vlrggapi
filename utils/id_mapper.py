"""
Name-to-ID mapper for teams and events.

Populated incrementally by scrapers during normal operation. Lookups are O(1) dict
gets, eliminating redundant HTTP detail-page requests when building match/event
listings. Phase 1 is in-memory; Phase 2 (future) swaps the backing store to Redis.
"""
from __future__ import annotations


class IdMapper:
    """Bi-directional name → ID mapping for teams and events.

    Populated by scrapers when they encounter team/event meta during normal
    scraping (e.g. match_detail extracts team IDs from header links). Consumed
    by listing scrapers to resolve team/event names to their numeric IDs
    without additional requests.

    Names are case-folded for lookups since vlr.gg may vary casing between
    listing pages and detail pages.
    """

    def __init__(self) -> None:
        self._team_name_to_id: dict[str, str] = {}
        self._event_name_to_id: dict[str, str] = {}

    # -- Register -----------------------------------------------------------------

    def register_team(self, name: str, team_id: str) -> None:
        if name and team_id:
            self._team_name_to_id[name.strip().lower()] = team_id

    def register_event(self, name: str, event_id: str) -> None:
        if name and event_id:
            self._event_name_to_id[name.strip().lower()] = event_id

    # -- Lookup -------------------------------------------------------------------

    def get_team_id(self, name: str) -> str | None:
        key = name.strip().lower() if name else ""
        return self._team_name_to_id.get(key) if key else None

    def get_event_id(self, name: str) -> str | None:
        key = name.strip().lower() if name else ""
        return self._event_name_to_id.get(key) if key else None

    def bulk_get_team_ids(self, names: list[str]) -> dict[str, str | None]:
        return {name: self.get_team_id(name) for name in names}

    # -- Introspection -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._team_name_to_id) + len(self._event_name_to_id)

    def clear(self) -> None:
        self._team_name_to_id.clear()
        self._event_name_to_id.clear()


id_mapper = IdMapper()
