import pytest

from api.scrapers.news import vlr_news
from utils.cache_manager import cache_manager


NEWS_HTML = """
<html>
  <body>
    <a class="wf-module-item" href="/123/example-news">
      <div>
        <div>Article title</div>
        <div>Article summary</div>
      </div>
      <div class="ge-text-light">Posted • April 23, 2024 by author_name</div>
    </a>
  </body>
</html>
"""


class FakeResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class FakeAsyncClient:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls: list[tuple[str, int | None]] = []

    async def get(self, url: str, timeout=None):
        self.calls.append((url, timeout))
        return self.response


@pytest.mark.anyio
async def test_vlr_news_parses_fixture_shape(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(FakeResponse(200, NEWS_HTML))

    monkeypatch.setattr("api.scrapers.news.get_http_client", lambda: client)

    data = await vlr_news()

    assert data == {
        "data": {
            "status": 200,
            "segments": [
                {
                    "title": "Article title",
                    "description": "Article summary",
                    "date": "April 23, 2024",
                    "author": "author_name",
                    "url_path": "https://www.vlr.gg/123/example-news",
                }
            ],
        }
    }
    assert client.calls == [("https://www.vlr.gg/news", None)]
    cache_manager.clear_all()
