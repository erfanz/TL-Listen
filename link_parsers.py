from bs4 import BeautifulSoup


def extract_hackernews_digest_urls(email):
    """Extract only direct tr > th > a links from Hacker News Digest emails."""
    html = (email.get("html") or "").strip()
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for row in soup.find_all("tr"):
        for heading in row.find_all("th", recursive=False):
            for link in heading.find_all("a", recursive=False):
                href = (link.get("href") or "").strip()
                if href:
                    urls.append(href)
    return urls
