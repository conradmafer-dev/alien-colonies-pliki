"""Public website on the existing Alien Colonies HTTP server and world."""
from __future__ import annotations

import html
import ipaddress
import json
import mimetypes
import os
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import app

WEB = Path(__file__).resolve().parent / "web"
PAGES = (
    "/", "/poradnik/", "/poradnik/pierwsza-kolonia/",
    "/poradnik/surowce-i-rozwoj/", "/poradnik/flota-i-sojusze/",
    "/poradnik/wybor-rasy/", "/poradnik/druga-kolonia/",
    "/poradnik/raport-zwiadowczy/",
)
LEGACY_HOST = "pogranicze-serwer-production.up.railway.app"
PAGE_ALIASES = {page + "index.html": page for page in PAGES}
GAME_HANDLER = app.Handler


def configured_origin() -> str:
    value = os.environ.get("SITE_ORIGIN", "https://aliencolonies.com").strip().rstrip("/")
    if not value:
        return ""
    if any(ord(char) <= 32 or ord(char) == 127 for char in value):
        raise ValueError("SITE_ORIGIN zawiera nieprawidłowe znaki.")
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
        raise ValueError("SITE_ORIGIN musi być adresem HTTPS domeny, bez ścieżki.")
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if not re.fullmatch(r"[A-Za-z0-9.-]+", parsed.hostname):
            raise ValueError("SITE_ORIGIN zawiera nieprawidłową domenę.")
    _ = parsed.port
    return value


class WebsiteHandler(GAME_HANDLER):
    def _document(self, body: bytes, content_type: str, *, status=200, cache="no-cache", noindex=False, head=False, location=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        if noindex or not self.website_origin:
            self.send_header("X-Robots-Tag", "noindex, nofollow")
        if location:
            self.send_header("Location", location)
        self.send_header("Connection", "close")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _website(self, *, head=False) -> bool:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path.startswith("/api/") or path.rstrip("/") in ("/health", "/privacy", "/delete-account", "/admin/announcement"):
            return False
        if path == "/site-config":
            body = json.dumps({"development": not self.server.website_hosted, "web_build": app.VERSION}).encode()
            self._document(body, "application/json; charset=utf-8", cache="no-store", noindex=True, head=head)
            return True
        if path == "/robots.txt":
            origin = self.website_origin
            text = "User-agent: *\nDisallow: /\n"
            if origin:
                text = f"User-agent: *\nAllow: /\nDisallow: /api/\nDisallow: /delete-account\nDisallow: /admin/\nDisallow: /health\nDisallow: /site-config\nSitemap: {origin}/sitemap.xml\n"
            self._document(text.encode(), "text/plain; charset=utf-8", head=head)
            return True
        if path == "/sitemap.xml":
            urls = "".join(f"<url><loc>{html.escape(self.website_origin + page)}</loc></url>" for page in PAGES) if self.website_origin else ""
            xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
            self._document(xml.encode(), "application/xml; charset=utf-8", head=head)
            return True
        if path == "/favicon.ico":
            self._document(b"", "text/plain", status=308, location="/assets/favicon-0121.ico", head=head)
            return True
        canonical = path if path in PAGES else PAGE_ALIASES.get(path)
        if canonical is None and path + "/" in PAGES:
            canonical = path + "/"
        if canonical is not None:
            # Redirect public documents from the known old host only. Keep the
            # Android API and game at their existing URLs; never trust forwarded
            # host headers or redirect development/unknown hosts.
            host_values = self.headers.get_all("Host", [])
            legacy = len(host_values) == 1 and host_values[0].strip().lower() == LEGACY_HOST
            change_host = (
                self.server.website_hosted and self.website_origin and legacy
                and urlsplit(self.website_origin).hostname != LEGACY_HOST
            )
            if canonical != path or change_host:
                location = (self.website_origin if change_host else "") + canonical
                location += "?" + parsed.query if parsed.query else ""
                self._document(b"", "text/plain", status=308, location=location, head=head)
                return True
        if path == "/play":
            location = "/play/" + ("?" + parsed.query if parsed.query else "")
            self._document(b"", "text/plain", status=308, location=location, head=head, noindex=True)
            return True
        relative = unquote(path).lstrip("/")
        if "\x00" in relative:
            self._not_found(head)
            return True
        try:
            candidate = (WEB / relative).resolve()
            if candidate.is_dir():
                candidate = (candidate / "index.html").resolve()
        except (OSError, RuntimeError, ValueError):
            self._not_found(head)
            return True
        if not candidate.is_relative_to(WEB) or any(part.startswith(".") for part in Path(relative).parts):
            self._not_found(head)
            return True
        if not candidate.is_file():
            self._not_found(head)
            return True
        if candidate.suffix == ".html":
            text = candidate.read_text(encoding="utf-8")
            if self.website_origin:
                text = text.replace("__SITE_ORIGIN__", html.escape(self.website_origin, quote=True))
            else:
                text = "\n".join(line for line in text.splitlines() if "__SITE_ORIGIN__" not in line)
            self._document(text.encode(), "text/html; charset=utf-8", noindex=path.startswith("/play"), head=head)
        else:
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            if candidate.suffix == ".js":
                content_type = "text/javascript"
            # Revalidate entry modules and styles, including old unversioned URLs.
            # Artwork is content-addressed; executable UI must never be stuck in cache.
            cache = "no-store" if path.startswith("/play/") else "public, max-age=3600"
            self._document(candidate.read_bytes(), content_type, cache=cache, head=head)
        return True

    @property
    def website_origin(self):
        return self.server.website_origin

    def _not_found(self, head=False):
        body = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="robots" content="noindex"><title>Page not found — Alien Colonies</title><h1>Page not found</h1><p><a href="/">Back to Alien Colonies</a></p></html>'.encode()
        self._document(body, "text/html; charset=utf-8", status=404, noindex=True, head=head)

    def do_GET(self):
        try:
            if not self._website():
                GAME_HANDLER.do_GET(self)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass

    def do_HEAD(self):
        try:
            if not self._website(head=True):
                self.send_error(405, "HEAD is supported for website documents only")
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass


def install_website(*, hosted=True, origin=None):
    """Only replace the HTTP handler; keep original main, world and database."""
    resolved_origin = configured_origin() if origin is None else origin
    if not WEB.is_dir():
        raise RuntimeError("Brak katalogu web strony Alien Colonies.")
    manifest_path = WEB / "play" / "release.json"
    try:
        import hashlib
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["version"] != app.VERSION:
            raise ValueError("web/server version mismatch")
        for relative, expected in manifest["files"].items():
            file = (WEB / relative).resolve()
            if not file.is_relative_to(WEB) or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                raise ValueError("missing or mismatched web file: " + relative)
    except (OSError, ValueError, KeyError) as error:
        raise RuntimeError("Incomplete Alien Colonies web release. Upload the COMPLETE web folder from the same release as app.py. " + str(error)) from error
    original_server_init = app.GameHTTPServer.__init__
    if getattr(app.GameHTTPServer, "_website_installed", False):
        raise RuntimeError("Witryna została już zainstalowana w tym procesie.")

    def server_init(self, *args, **kwargs):
        self.website_origin = resolved_origin
        self.website_hosted = hosted
        original_server_init(self, *args, **kwargs)

    app.GameHTTPServer.__init__ = server_init
    app.GameHTTPServer._website_installed = True
    app.Handler = WebsiteHandler

