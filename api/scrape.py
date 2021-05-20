import requests
from bs4 import BeautifulSoup
import requests


class Vlr:
    @staticmethod
    def vlr_recent():
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "3600",
            "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0",
        }
        URL = "https://www.vlr.gg/news"
        html = requests.get(URL, headers=headers).text
        response = requests.get(URL)
        soup = BeautifulSoup(html, "html.parser")
        status = response.status_code

        vlr_module = soup.find(id="wrapper").parent.find_all(
            "a", class_="wf-module-item"
        )

        result = []
        for module in vlr_module:

            # Titles of articles
            title = module.find(
                "div",
                attrs={"style": "font-weight: 700; font-size: 15px; line-height: 1.3;"},
            )
            title = module.find(
                "div",
                attrs={"style": "font-weight: 700; font-size: 15px; line-height: 1.3;"},
            ).text.strip()

            # get descriptions of articles
            desc = module.find(
                "div",
                attrs={
                    "style": " font-size: 13px; padding: 5px 0; padding-bottom: 6px; line-height: 1.4;"
                },
            ).text.strip()

            # get date of articles
            date = module.find("div", class_="ge-text-light").get_text().strip()
            date = date.replace("\u2022", "").strip()
            date = date.strip().split("  ")[0]
            # date = datetime.strptime(date, "%b %d, %Y")
            # date = date.replace(tzinfo=date.tzinfo)
            # date = date.isoformat()

            # get author of articles
            author = module.find("div", class_="ge-text-light").get_text().strip()
            author = author.replace("\u2022", "").strip()
            author = author.strip().split("  ")[1]
            # remove "by" in author section
            author = author.strip().split(" ")[1]

            # get url_path of articles
            url = module["href"]
            result.append(
                {
                    "title": title,
                    "description": desc,
                    "date": date,
                    "author": author,
                    "url_path": url,
                }
            )

        segments = {"status": status, "segments": result}

        data = {"data": segments}

        if status != 200:
            raise Exception("API response: {}".format(status))
        return data
