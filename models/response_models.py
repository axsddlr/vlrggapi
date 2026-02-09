"""
Pydantic models for API responses
"""
from typing import List, Optional, Any

from pydantic import BaseModel


# --- V2 Base Response ---

class V2Response(BaseModel):
    status: str = "success"
    data: Any = None
    meta: Optional[dict] = None
    message: Optional[str] = None


# --- Events ---

class EventModel(BaseModel):
    title: str
    status: str
    prize: str
    dates: str
    region: str
    thumb: str
    url_path: str


# --- Matches ---

class UpcomingMatch(BaseModel):
    team1: str
    team2: str
    flag1: str
    flag2: str
    time_until_match: str
    match_series: str
    match_event: str
    unix_timestamp: str
    match_page: str


class LiveMatch(BaseModel):
    team1: str
    team2: str
    flag1: str
    flag2: str
    team1_logo: str = ""
    team2_logo: str = ""
    score1: str
    score2: str
    team1_round_ct: str = "N/A"
    team1_round_t: str = "N/A"
    team2_round_ct: str = "N/A"
    team2_round_t: str = "N/A"
    map_number: str = "Unknown"
    current_map: str = "Unknown"
    time_until_match: str
    match_event: str
    match_series: str
    unix_timestamp: str
    match_page: str


class ResultMatch(BaseModel):
    team1: str
    team2: str
    score1: str
    score2: str
    flag1: str
    flag2: str
    time_completed: str
    round_info: str
    tournament_name: str
    match_page: str
    tournament_icon: str
    page_number: int = 1


class ExtendedMatch(BaseModel):
    team1: str
    team2: str
    flag1: str
    flag2: str
    score1: str = ""
    score2: str = ""
    time_until_match: str
    match_series: str
    match_event: str
    unix_timestamp: str
    match_page: str
    tournament_icon: str = ""
    page_number: int = 1


# --- News ---

class NewsItem(BaseModel):
    title: str
    description: str
    date: str
    author: str
    url_path: str


# --- Rankings ---

class RankingItem(BaseModel):
    rank: str
    team: str
    country: str
    last_played: str
    last_played_team: str
    last_played_team_logo: str
    record: str
    earnings: str
    logo: str


# --- Stats ---

class StatsPlayer(BaseModel):
    player: str
    org: str
    agents: List[str]
    rounds_played: str
    rating: str
    average_combat_score: str
    kill_deaths: str
    kill_assists_survived_traded: str
    average_damage_per_round: str
    kills_per_round: str
    assists_per_round: str
    first_kills_per_round: str
    first_deaths_per_round: str
    headshot_percentage: str
    clutch_success_percentage: str


# --- Health ---

class SiteHealth(BaseModel):
    status: str
    status_code: Optional[int] = None


class HealthStatus(BaseModel):
    sites: dict[str, SiteHealth] = {}
