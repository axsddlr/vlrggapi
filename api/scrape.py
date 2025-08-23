from api.scrapers import (
    check_health,
    vlr_events,
    vlr_live_score,
    vlr_match_results,
    vlr_news,
    vlr_rankings,
    vlr_stats,
    vlr_upcoming_matches,
)


class Vlr:
    @staticmethod
    def vlr_news():
        return vlr_news()

    @staticmethod
    def vlr_rankings(region):
        return vlr_rankings(region)

    @staticmethod
    def vlr_stats(region: str, timespan: str):
        return vlr_stats(region, timespan)

    @staticmethod
    def vlr_upcoming_matches(num_pages=1, from_page=None, to_page=None):
        return vlr_upcoming_matches(num_pages, from_page, to_page)

    @staticmethod
    def vlr_live_score(num_pages=1, from_page=None, to_page=None):
        return vlr_live_score(num_pages, from_page, to_page)

    @staticmethod
    def vlr_match_results(num_pages=1, from_page=None, to_page=None, max_retries=3, request_delay=1.0, timeout=30):
        return vlr_match_results(num_pages, from_page, to_page, max_retries, request_delay, timeout)

    @staticmethod
    def vlr_events(upcoming=True, completed=True, page=1):
        return vlr_events(upcoming, completed, page)

    @staticmethod
    def check_health():
        return check_health()


if __name__ == "__main__":
    print(Vlr.vlr_live_score())
