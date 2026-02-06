import requests
from selectolax.parser import HTMLParser

from utils.utils import headers
from utils.constants import VLR_BASE_URL


def vlr_news():
    url = f"{VLR_BASE_URL}/news"
    resp = requests.get(url, headers=headers)
    html = HTMLParser(resp.text)
    status = resp.status_code

    result = []
    for item in html.css("a.wf-module-item"):
        date_author = item.css_first("div.ge-text-light").text()
        date, author = date_author.split("by")

        desc = item.css_first("div").css_first("div:nth-child(2)").text().strip()

        title = item.css_first("div:nth-child(1)").text().strip().split("\n")[0]
        title = title.replace("\t", "")

        url = item.css_first("a.wf-module-item").attributes["href"]

        result.append(
            {
                "title": title,
                "description": desc,
                "date": date.split("\u2022")[1].strip(),
                "author": author.strip(),
                "url_path": "https://vlr.gg" + url,
            }
        )

    data = {"data": {"status": status, "segments": result}}

    if status != 200:
        raise Exception("API response: {}".format(status))
    return data
