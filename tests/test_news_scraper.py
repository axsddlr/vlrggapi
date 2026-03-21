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

LIVE_NEWS_HTML = """
<html>
  <body>
    <a class="wf-module-item mod-first" href="/645756/eternal-fire-replaces-ulf-esports-in-vct-emea">
      <div>
        <div>
          Eternal Fire replaces ULF Esports in VCT EMEA
        </div>
        <div>
          A new banner for the ULF Esports core.
        </div>
        <div class="ge-text-light">
          <i class="flag mod-tr"></i> <span>&bull;</span> March 20, 2026 <span>&bull;</span> by jenopelle
        </div>
      </div>
    </a>
    <a class="wf-module-item" href="/644767/m80-rebuild-heats-up-with-kaplan-and-nismos-return">
      <div>
        <div>
          M80 rebuild heats up with kaplan and NiSMO's return
        </div>
        <div>
          After a long spell with Sen City, kaplan is taking NiSMO's spot in the coaching booth following his return to play.
        </div>
        <div class="ge-text-light">
          <i class="flag mod-us"></i> <span>&bull;</span> March 19, 2026 <span>&bull;</span> by jenopelle
        </div>
      </div>
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


@pytest.mark.anyio
async def test_vlr_news_parses_live_like_markup_without_raw_text_splitting(monkeypatch):
    cache_manager.clear_all()
    client = FakeAsyncClient(FakeResponse(200, LIVE_NEWS_HTML))

    monkeypatch.setattr("api.scrapers.news.get_http_client", lambda: client)

    data = await vlr_news()

    assert data == {
        "data": {
            "status": 200,
            "segments": [
                {
                    "title": "Eternal Fire replaces ULF Esports in VCT EMEA",
                    "description": "A new banner for the ULF Esports core.",
                    "date": "March 20, 2026",
                    "author": "jenopelle",
                    "url_path": "https://www.vlr.gg/645756/eternal-fire-replaces-ulf-esports-in-vct-emea",
                },
                {
                    "title": "M80 rebuild heats up with kaplan and NiSMO's return",
                    "description": "After a long spell with Sen City, kaplan is taking NiSMO's spot in the coaching booth following his return to play.",
                    "date": "March 19, 2026",
                    "author": "jenopelle",
                    "url_path": "https://www.vlr.gg/644767/m80-rebuild-heats-up-with-kaplan-and-nismos-return",
                },
            ],
        }
    }
    assert client.calls == [("https://www.vlr.gg/news", None)]
    cache_manager.clear_all()
