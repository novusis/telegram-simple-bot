import asyncio
import mimetypes
from pathlib import Path

from aiohttp import web

from data.game_config import GameConfig
from web.certificates import CertificateManager


mimetypes.add_type("application/wasm", ".wasm")


class WebServer:
    def __init__(self, game, config=None):
        self.game = game
        self.config = config if config is not None else GameConfig.app_optional("web_server", {})
        self.config = self.config or {}
        self.enabled = self.config.get("enabled", False)
        self.host = self.config.get("host", "0.0.0.0")
        self.port = int(self.config.get("port", 8080))
        self.default_root = Path(self.config.get("webroot", "web/webroot")).resolve()
        self.default_index = self.config.get("index", "index.html")
        self.domain_roots = self._make_domain_roots(self.config.get("domains", []))
        self.ssl_config = self.config.get("ssl", {})
        self.certificate_manager = CertificateManager(self.ssl_config)
        self.close_http_after_ssl_start = self.ssl_config.get(
            "close_http_after_ssl_start",
            self.certificate_manager.enabled
        )
        self.runner = None
        self.http_site = None
        self.https_site = None

    def create_app(self):
        app = web.Application()
        app["web_server"] = self
        app.router.add_get("/api/health", self.handle_health)
        app.router.add_get("/api/me", self.handle_me)
        app.router.add_post("/api/share-score", self.handle_share_score)
        app.router.add_get("/{path:.*}", self.handle_file)
        return app

    async def start(self):
        if not self.enabled:
            print(".web_server disabled", flush=True)
            return

        app = self.create_app()
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.http_site = web.TCPSite(self.runner, self.host, self.port)
        await self.http_site.start()
        print(f".web_server started on {self.host}:{self.port}", flush=True)
        await self.start_https()

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            self.http_site = None
            self.https_site = None
            print(".web_server stopped", flush=True)

    async def start_https(self):
        ssl_context = self.certificate_manager.prepare_ssl_context()
        if not ssl_context:
            print(".web_server HTTPS was not started: certificate is not ready", flush=True)
            return

        ssl_host = self.ssl_config.get("host", self.host)
        ssl_port = int(self.ssl_config.get("port", 8443))
        self.https_site = web.TCPSite(self.runner, ssl_host, ssl_port, ssl_context=ssl_context)
        await self.https_site.start()
        print(f".web_server HTTPS started on {ssl_host}:{ssl_port}", flush=True)

        if self.close_http_after_ssl_start and self.http_site:
            print(".web_server stopping HTTP bootstrap site after HTTPS start", flush=True)
            await self.http_site.stop()
            self.http_site = None

    async def handle_health(self, _request):
        return web.json_response({"ok": True})

    async def handle_me(self, request):
        if not self.game:
            return web.json_response({"error": "game controller is not configured"}, status=503)

        external_id = request.query.get("userId")
        if not external_id:
            return web.json_response({"authenticated": False})

        user = self.game.get_user(external_id, False)
        if not user:
            return web.json_response({"authenticated": False})

        return web.json_response({
            "authenticated": True,
            "user": self._user_view(user),
        })

    async def handle_share_score(self, request):
        if not self.game:
            return web.json_response({"error": "game controller is not configured"}, status=503)

        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "invalid json"}, status=400)

        external_id = data.get("userId")
        scores = data.get("scores")
        if not external_id:
            return web.json_response({"error": "userId required"}, status=400)
        if scores is None:
            return web.json_response({"error": "scores required"}, status=400)

        try:
            user = self.game.set_user_score(external_id, scores)
        except (TypeError, ValueError):
            return web.json_response({"error": "scores must be an integer"}, status=400)

        if not user:
            return web.json_response({"error": "user not found"}, status=404)

        return web.json_response({
            "message": "score saved",
            "game": data.get("game", ""),
            "user": self._user_view(user),
        })

    async def handle_file(self, request):
        rel_path = request.match_info.get("path", "")
        root, index = self._site_for_request(request)
        file_path = self._resolve_file(root, rel_path, index)
        if not file_path:
            raise web.HTTPNotFound()

        return web.FileResponse(file_path)

    def _site_for_request(self, request):
        host = self._normalize_host(request.headers.get("Host", ""))
        site = self.domain_roots.get(host)
        if site:
            return site["root"], site["index"]
        return self.default_root, self.default_index

    def _resolve_file(self, root, rel_path, index):
        clean_path = rel_path.strip("/")
        file_path = root / clean_path if clean_path else root / index
        file_path = file_path.resolve()

        try:
            file_path.relative_to(root)
        except ValueError:
            return None

        if file_path.is_dir():
            file_path = (file_path / index).resolve()
            try:
                file_path.relative_to(root)
            except ValueError:
                return None

        if not file_path.is_file():
            return None
        return file_path

    def _make_domain_roots(self, domains):
        result = {}
        for domain_config in domains:
            domain = self._normalize_host(domain_config.get("domain", ""))
            if not domain:
                continue
            root = Path(domain_config.get("root", self.default_root)).resolve()
            index = domain_config.get("index", self.default_index)
            result[domain] = {"root": root, "index": index}
        return result

    @staticmethod
    def _normalize_host(host):
        return host.split(":", 1)[0].strip().lower()

    @staticmethod
    def _user_view(user):
        return {
            "id": user.id,
            "external_id": user.external_id,
            "username": user.username,
            "name": user.name,
            "scores": user.scores,
            "coins": user.coins,
        }


async def run_web_server(game, stop_event):
    server = WebServer(game)
    await server.start()
    try:
        await stop_event.wait()
    finally:
        await server.stop()


async def main():
    stop_event = asyncio.Event()
    server = WebServer(game=None, config={"enabled": True})
    await server.start()
    try:
        await stop_event.wait()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
