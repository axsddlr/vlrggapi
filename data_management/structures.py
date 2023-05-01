class Player():
    name: str
    shortname: str
    role: str
    team: str
    def __init__(self, name: str, shortname: str, role: str, team: str) -> None:
        self.name = name
        self.shortname = shortname
        self.role = role
        self.team = team

class Players():
    def __init__(self) -> None:
        self.items = []
        
    def add(self, player: Player):
        self.items.append(player)
    
    def __iter__(self):
        return iter(self.items)

class Team():
    
    id: int
    name: str
    shortname: str
    active: bool
    members: Players
    twitter: str
    website: str
    region: str
    
    def __init__(self, id: int, name: str, shortname: str, active: bool,  twitter: str, website: str, region: str) -> None:
        self.id = id
        self.name = name
        self.shortname = shortname
        self.active = active
        self.twitter = twitter
        self.website = website
        self.region = region
    
    def __str__(self) -> str:
        return f"{self.name} ({self.shortname}), {self.region}, {self.active}, {self.twitter}, {self.website}"
    
        

        
        
# table team has columns: name, shortname, region
# table player has columns: name, shortname, team -> team being a foreign key to team.id