import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()

# File extensions to skip — these are not web pages.
SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".tiff",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".zip", ".gz", ".tar", ".rar",
    ".mp3", ".mp4", ".wav", ".avi", ".mov", ".webm",
    ".woff", ".woff2", ".ttf", ".eot",
}


def _is_page_url(url: str) -> bool:
    """Return False for URLs that point to images, documents, or other non-page files."""
    path = urlparse(url).path.lower()
    return not any(path.endswith(ext) for ext in SKIP_EXTENSIONS)


class AutoCrawler:
    def __init__(self, seed_url: str, max_depth: int = 5, delay: float = 1.0):
        self.seed_url = seed_url
        self.base_domain = urlparse(seed_url).netloc
        self.max_depth = max_depth
        self.delay = delay
        self.visited: set[str] = set()
        self.robots = self._load_robots(seed_url)

    def _load_robots(self, url: str) -> RobotFileParser | None:
        rp = RobotFileParser()
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp.set_url(robots_url)
        try:
            rp.read()
            return rp
        except Exception:
            return None

    def _is_internal(self, url: str) -> bool:
        return urlparse(url).netloc == self.base_domain

    def _is_allowed(self, url: str) -> bool:
        if self.robots is None:
            return True
        return self.robots.can_fetch("*", url)

    def _normalize_url(self, url: str) -> str:
        """Strip fragments and trailing slashes for deduplication."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        normalized = parsed._replace(fragment="", path=path)
        return normalized.geturl()

    def crawl(self) -> list[str]:
        queue: list[tuple[str, int]] = [(self.seed_url, 0)]
        found: list[str] = []

        with console.status("[bold green]Crawling...") as status:
            while queue:
                url, depth = queue.pop(0)
                url = self._normalize_url(url)

                if url in self.visited or depth > self.max_depth:
                    continue
                if not _is_page_url(url):
                    continue
                if not self._is_allowed(url):
                    console.print(f"  [dim]Blocked by robots.txt: {url}[/dim]")
                    continue

                self.visited.add(url)
                found.append(url)
                status.update(f"[bold green]Crawling ({len(found)} pages found)... {url}")
                console.print(f"  [green]Found:[/green] {url}")
                time.sleep(self.delay)

                try:
                    response = httpx.get(url, follow_redirects=True, timeout=10)
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        continue
                    soup = BeautifulSoup(response.text, "html.parser")
                    for link in soup.find_all("a", href=True):
                        absolute = self._normalize_url(urljoin(url, link["href"]))
                        if self._is_internal(absolute) and absolute not in self.visited:
                            queue.append((absolute, depth + 1))
                except Exception as e:
                    console.print(f"  [red]Could not fetch {url}: {e}[/red]")

        return found
