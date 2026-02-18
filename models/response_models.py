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


# --- Match Detail ---

class MatchDetailEvent(BaseModel):
    name: str = ""
    series: str = ""
    logo: str = ""


class MatchDetailTeam(BaseModel):
    name: str = ""
    tag: str = ""
    logo: str = ""
    score: str = ""
    is_winner: bool = False


class MatchPlayerStat(BaseModel):
    name: str = ""
    agent: str = ""
    rating: str = ""
    acs: str = ""
    kills: str = ""
    deaths: str = ""
    assists: str = ""
    kast: str = ""
    adr: str = ""
    hs_pct: str = ""
    fk: str = ""
    fd: str = ""
    fk_diff: str = ""
    kd_diff: str = ""


class MatchRound(BaseModel):
    round_num: int
    winner: str = ""
    side: str = ""
    title: str = ""


class MatchMapScore(BaseModel):
    team1: Any = ""
    team2: Any = ""


class MatchMap(BaseModel):
    map_name: str = ""
    picked_by: str = ""
    duration: str = ""
    score: MatchMapScore = MatchMapScore()
    score_ct: MatchMapScore = MatchMapScore()
    score_t: MatchMapScore = MatchMapScore()
    players: dict = {}
    rounds: List[MatchRound] = []


class MatchH2HEntry(BaseModel):
    event: str = ""
    date: str = ""
    teams: List[dict] = []
    score: str = ""
    url: str = ""


class MatchStream(BaseModel):
    name: str = ""
    url: str = ""


class MatchPerformance(BaseModel):
    kill_matrix: List[dict] = []
    advanced_stats: List[dict] = []


class MatchDetail(BaseModel):
    match_id: str
    event: MatchDetailEvent = MatchDetailEvent()
    date: str = ""
    patch: str = ""
    status: str = ""
    teams: List[MatchDetailTeam] = []
    streams: List[MatchStream] = []
    vods: List[MatchStream] = []
    maps: List[MatchMap] = []
    head_to_head: List[MatchH2HEntry] = []
    performance: MatchPerformance = MatchPerformance()
    economy: List[dict] = []


# --- Player Profile ---

class SocialLink(BaseModel):
    platform: str = ""
    url: str = ""


class PlayerCurrentTeam(BaseModel):
    name: str = ""
    tag: str = ""
    logo: str = ""
    joined: str = ""


class PlayerPastTeam(BaseModel):
    name: str = ""
    tag: str = ""
    dates: str = ""
    logo: str = ""


class PlayerAgentStat(BaseModel):
    agent: str = ""
    usage_count: str = ""
    usage_pct: str = ""
    rounds: str = ""
    rating: str = ""
    acs: str = ""
    kd: str = ""
    adr: str = ""
    kast: str = ""
    kpr: str = ""
    apr: str = ""
    fkpr: str = ""
    fdpr: str = ""
    kills: str = ""
    deaths: str = ""
    assists: str = ""
    fk: str = ""
    fd: str = ""


class PlayerEventPlacement(BaseModel):
    event: str = ""
    placement: str = ""
    prize: str = ""
    team: str = ""
    date: str = ""


class PlayerNewsItem(BaseModel):
    title: str = ""
    url: str = ""
    date: str = ""


class PlayerProfile(BaseModel):
    id: str
    name: str = ""
    real_name: str = ""
    avatar: str = ""
    country: str = ""
    social_links: List[SocialLink] = []
    current_team: PlayerCurrentTeam = PlayerCurrentTeam()
    past_teams: List[PlayerPastTeam] = []
    agent_stats: List[PlayerAgentStat] = []
    event_placements: List[PlayerEventPlacement] = []
    news: List[PlayerNewsItem] = []
    total_winnings: str = ""


# --- Player Match History ---

class MatchTeamBrief(BaseModel):
    name: str = ""
    tag: str = ""
    logo: str = ""


class PlayerMatchItem(BaseModel):
    match_id: str = ""
    url: str = ""
    event: str = ""
    date: str = ""
    team1: MatchTeamBrief = MatchTeamBrief()
    team2: MatchTeamBrief = MatchTeamBrief()
    score: str = ""
    result: str = ""


# --- Team Profile ---

class TeamRating(BaseModel):
    rank: str = ""
    rating: str = ""
    peak_rating: str = ""
    streak: str = ""


class TeamRosterMember(BaseModel):
    id: str = ""
    url: str = ""
    alias: str = ""
    real_name: str = ""
    avatar: str = ""
    country: str = ""
    is_captain: bool = False
    role: str = ""
    is_staff: bool = False


class TeamEventPlacement(BaseModel):
    event: str = ""
    series: str = ""
    placement: str = ""
    prize: str = ""
    date: str = ""
    url: str = ""


class TeamProfile(BaseModel):
    id: str
    name: str = ""
    tag: str = ""
    successor: str = ""
    logo: str = ""
    country: str = ""
    country_name: str = ""
    description: str = ""
    social_links: List[SocialLink] = []
    rating: TeamRating = TeamRating()
    roster: List[TeamRosterMember] = []
    event_placements: List[TeamEventPlacement] = []
    total_winnings: str = ""


# --- Team Transactions ---

class TransactionPlayer(BaseModel):
    name: str = ""
    id: str = ""
    url: str = ""
    avatar: str = ""
    country: str = ""


class TeamTransaction(BaseModel):
    date: str = ""
    action: str = ""
    player: TransactionPlayer = TransactionPlayer()
    role: str = ""


# --- Event Matches ---

class EventMatchTeam(BaseModel):
    name: str = "TBD"
    score: str = ""
    is_winner: bool = False


class EventMatchVOD(BaseModel):
    label: str = ""
    url: str = ""


class EventMatchItem(BaseModel):
    match_id: str = ""
    url: str = ""
    date: str = ""
    status: str = ""
    note: str = ""
    event_series: str = ""
    team1: EventMatchTeam = EventMatchTeam()
    team2: EventMatchTeam = EventMatchTeam()
    vods: List[EventMatchVOD] = []
