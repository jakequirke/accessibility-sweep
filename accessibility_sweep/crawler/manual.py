from accessibility_sweep.crawler.auto import _is_page_url


class ManualCrawler:
    """Accept a pre-defined list of URLs — no crawling needed."""

    def __init__(self, urls: list[str]):
        self.urls = urls

    def crawl(self) -> list[str]:
        urls = list(dict.fromkeys(self.urls))  # deduplicate, preserve order
        return [u for u in urls if _is_page_url(u)]
