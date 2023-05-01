class Player():
    name:       str
    shortname:  str
    role:       str
    team:       int
    def __init__(self, name: str, shortname: str, role: str, team: int) -> None:
        self.name       = name
        self.shortname  = shortname
        self.role       = role
        self.team       = team
    
    def __str__(self) -> str:
        return f"({self.name} ({self.shortname}), {self.role})"

class Players():
    def __init__(self) -> None:
        self.items = []
        
    def add(self, player: Player):
        self.items.append(player)
    
    def __iter__(self):
        return iter(self.items)
    
    def __str__(self) -> str:
        return ", ".join([str(x) for x in self.items])

class Team():
    
    id:         int
    name:       str
    shortname:  str
    active:     bool
    members:    Players
    twitter:    str
    website:    str
    region:     str
    
    def __init__(self, id: int, name: str, shortname: str, active: bool,  twitter: str, website: str, region: str, members: Players) -> None:
        self.id         = id
        self.name       = name
        self.shortname  = shortname
        self.active     = active
        self.twitter    = twitter
        self.website    = website
        self.region     = region
        self.members    = members
    
    def __str__(self) -> str:
        return f"{self.name} ({self.shortname}), {self.region}, {self.active}, {self.twitter}, {self.website}, \nRoster:\t{str(self.members)}"
    
        

        
        
# table team has columns: name, shortname, region
# table player has columns: name, shortname, team -> team being a foreign key to team.id