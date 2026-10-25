"""
Name-to-ID registry for teams and events.

Populated incrementally by scrapers during normal operation. Nothing reads the
registry back yet, so it is bookkeeping rather than a cache: listing scrapers
parse names directly from the pages they already fetch.
"""
from __future__ import annotations


class IdMapper:
    """Name → ID registry for teams and events.

    Populated by scrapers when they encounter team/event meta during normal
    scraping (e.g. match_detail extracts team IDs from header links). No
    consumer reads it back today: the lookup methods were dropped once the
    listing scrapers kept parsing names from their own pages.

    Names are case-folded on write so a future consumer can match regardless of
    casing differences between listing and detail pages.
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

    def clear(self) -> None:
        self._team_name_to_id.clear()
        self._event_name_to_id.clear()


id_mapper = IdMapper()
