from selectolax.parser import HTMLParser
import re
from utils.utils import headers, region
import requests

def vlr_events(region_key):
    url = "https://www.vlr.gg/events/" + region[str(region_key).lower()]
    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []


    for event in html.css("a.wf-card"):
      item = event.css_first("div.event-item-inner")
      eventName = item.css_first("div.event-item-title").text().strip()
      eventStatus = item.css_first("div.event-item-desc-item").css_first("span").text().strip()
      logo = event.css_first("div.event-item-thumb").css_first("img").attributes["src"]
      prizePool = item.css_first("div.mod-prize").text(strip=True, deep=False)
      logo = re.sub(r"\/img\/vlr\/tmp\/vlr.png", "", logo)
      dates = item.css_first("div.mod-dates").text(strip=True, deep=False)



      if "—" in dates:
        date_from = dates.split("—")[0].strip()
        date_to = dates.split("—")[1].strip() 
      else:
        date_from = dates.strip()
        date_to = dates.strip()

      if " " not in date_to:
        month = date_from.split(" ")[0]
        date_to = f"{month} {date_to}"


      result.append(
        {
           "eventName": eventName,
           "eventStatus": eventStatus,
           "prizePool": prizePool,
           "logo": logo,
           "date-from": date_from,
           "date-to": date_to
        }
      )


    data = {"status": status, "data": result}

    if status != 200:
      raise Exception("API response: {}".format(status))
    return data
