from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scraper.http_client import HttpClient
from utils.text import clean_text, unique


class SiteContentCrawler:
    """Extrae páginas institucionales públicas; nunca usa contenido escrito a mano."""

    KEYWORDS = {
        "empresa": ("nosotros", "acerca", "empresa", "quienes-somos"),
        "politicas": ("politica", "términos", "terminos", "privacidad", "devolucion", "envio"),
        "faq": ("faq", "preguntas", "frecuentes", "ayuda"),
    }

    def __init__(self, client: HttpClient, base_url: str):
        self.client = client
        self.base_url = base_url

    def crawl(self) -> dict[str, str]:
        result = {key: "" for key in self.KEYWORDS}
        try:
            response = self.client.get(self.base_url)
            response.raise_for_status()
        except Exception:
            return result
        soup = BeautifulSoup(response.text, "html.parser")
        candidates: dict[str, list[str]] = {key: [] for key in self.KEYWORDS}
        for anchor in soup.select("a[href]"):
            url = urljoin(response.url, anchor["href"])
            if urlsplit(url).netloc != urlsplit(response.url).netloc:
                continue
            haystack = f"{anchor.get_text(' ', strip=True)} {url}".casefold()
            for key, words in self.KEYWORDS.items():
                if any(word.casefold() in haystack for word in words):
                    candidates[key].append(url)
        # La portada sí es una fuente empresarial oficial.
        main = soup.select_one("main, #content, .site-content")
        result["empresa"] = clean_text(main.get_text(" ", strip=True) if main else "")
        for key, urls in candidates.items():
            texts = []
            for url in unique(urls)[:8]:
                try:
                    page = self.client.get(url)
                    if page.status_code >= 400:
                        continue
                    page_soup = BeautifulSoup(page.text, "html.parser")
                    content = page_soup.select_one("main, article, #content, .entry-content")
                    if content:
                        texts.append(f"Fuente: {page.url}\n{clean_text(content.get_text(' ', strip=True))}")
                except Exception:
                    continue
            if texts:
                result[key] = "\n\n".join(texts)
        return result

