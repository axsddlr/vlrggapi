from api.scrape import Vlr

vlr = Vlr()

for i in range(2,4):
    print(str(vlr.vlr_team(i)[1]))

