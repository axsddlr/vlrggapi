from selectolax.parser import HTMLParser
import re
from utils.utils import headers, region, month
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

      if "https" not in logo:
        # replace the slashes at the url start | example: "//owcdn.net"
        logo = re.sub(r"^//", "https://", logo)


      date_from_day = dates.replace("—", " ").split(" ")[1]
      date_to_day = dates.replace("—", " ").split(" ")[-1]

      date_from_month = month[dates.split(" ")[0].lower()]
      if dates.replace("—", " ").split(" ")[-2].isdigit():
        date_to_month = date_from_month
      else:
        date_to_month = month[dates.replace("—", " ").split(" ")[-2].lower()]

      print(dates.replace("—", " "))

      date_from = f"{date_from_month} {date_from_day}"
      date_to = f"{date_to_month} {date_to_day}"

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
