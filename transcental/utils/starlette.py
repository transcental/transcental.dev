import logging
from pathlib import Path

from slack_bolt.adapter.starlette.async_handler import AsyncSlackRequestHandler
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

from transcental.config import config
from transcental.env import env

logger = logging.getLogger(__name__)

req_handler = AsyncSlackRequestHandler(env.app)
TEMPLATE_DIR = Path(Path.cwd() / config.starlette.directory / "templates")
STATIC_DIR = Path(Path.cwd() / config.starlette.directory / "static")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


async def endpoint(req: Request):
    return await req_handler.handle(req)


async def health(req: Request):
    try:
        await env.slack_client.api_test()
        slack_healthy = True
    except Exception:
        slack_healthy = False

    return JSONResponse(
        {
            "healthy": slack_healthy,
            "slack": slack_healthy,
        }
    )

async def index(req: Request):
    return templates.TemplateResponse(req, 'index.html')


app = Starlette(
    debug=True if config.environment != "production" else False,
    routes=[
        Route(path="/", endpoint=index, methods=["GET"]),
        Route(path="/slack/events", endpoint=endpoint, methods=["POST"]),
        Route(path="/health", endpoint=health, methods=["GET"]),
        Mount('/static', app=StaticFiles(directory=STATIC_DIR), name="static")
    ],
    lifespan=env.enter,
)
