import base64
import hashlib
import hmac
import logging
import re
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from starlette.websockets import WebSocketDisconnected
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .config import API_KEY, API_SECRET, BACKGROUND_VIDEOS, DATA_DIR, DEV_SIMULATE, HOLD_SECONDS, STATIC_DIR
from .lineup import Lineup

log = logging.getLogger("card_webhook")

MAX_IMAGE_BYTES = 8 * 1024 * 1024


class Hub:
    def __init__(self):
        self._clients: set[WebSocket] = set()

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def discard(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, payload: dict) -> None:
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)


def safe_eq(left: str, right: str) -> bool:
    left_b = left.encode("utf-8")
    right_b = right.encode("utf-8")
    if len(left_b) != len(right_b):
        return False
    return hmac.compare_digest(left_b, right_b)


def sniff_image(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    return None


def decode_avatar(value) -> bytes | None:
    if not isinstance(value, str) or value.strip() == "":
        return None
    if value.startswith("data:"):
        parts = value.split(",", 1)
        if len(parts) != 2:
            return None
        value = parts[1]
    value = re.sub(r"\s+", "", value)
    value += "=" * (-len(value) % 4)
    try:
        raw = base64.b64decode(value, validate=False)
    except Exception:
        return None
    if len(raw) < 24 or len(raw) > MAX_IMAGE_BYTES:
        return None
    if sniff_image(raw) is None:
        return None
    return raw


def text_field(payload: dict, key: str) -> str:
    value = payload.get(key, "")
    if value is None:
        return ""
    return str(value)


async def accept_card(payload: dict) -> dict:
    request_id = text_field(payload, "request_id").strip() or uuid.uuid4().hex
    image = decode_avatar(payload.get("avatar_image_base64"))
    ext = sniff_image(image) if image else None
    card = None
    if image and ext:
        card = {
            "user_id": text_field(payload, "user_id"),
            "name": text_field(payload, "name"),
            "title": text_field(payload, "title"),
        }
    result = await app.state.lineup.submit(request_id, card, image, ext)
    log.info(
        "card result=%s request_id=%s user_id=%s",
        result,
        request_id,
        text_field(payload, "user_id"),
    )
    return {"ok": True, "result": result}


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (STATIC_DIR / "media").mkdir(parents=True, exist_ok=True)
    app.state.hub = Hub()
    app.state.lineup = Lineup(HOLD_SECONDS, DATA_DIR, app.state.hub.broadcast, BACKGROUND_VIDEOS)
    yield
    app.state.lineup.cancel()


class CardIssued(BaseModel):
    event: str = "card_issued"
    request_id: str = ""
    issued_at: str = ""
    user_id: str = ""
    name: str = ""
    title: str = ""
    extra: Any = Field(default=None, description="Ignored.")
    avatar_mime: str = ""
    avatar_image_base64: str = Field(default="", description="PNG or JPEG, raw or data-URL base64. This image is the card.")


class CardResult(BaseModel):
    ok: bool = True
    result: str = Field(description="placed, queued, duplicate, or no_image")


app = FastAPI(
    title="Card lineup",
    description="Signed card_issued webhook. Finished cards appear in a 4-3-3 on the stadium page.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/", include_in_schema=False)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.post(
    "/webhook",
    response_model=CardResult,
    summary="Receive a signed card_issued event",
    responses={
        400: {"description": "Empty body or invalid JSON", "content": {"text/plain": {"schema": {"type": "string"}}}},
        401: {"description": "Bad API key or signature", "content": {"text/plain": {"schema": {"type": "string"}}}},
    },
)
async def webhook(
    request: Request,
    payload: CardIssued,
    x_api_key: Annotated[str, Header(description="CARD_API_KEY")],
    x_signature: Annotated[str, Header(description="HMAC-SHA256 hex digest of the raw JSON body, using CARD_API_SECRET")],
):
    raw = await request.body()
    if raw == b"":
        return PlainTextResponse("Empty body", status_code=400)

    if not safe_eq(x_api_key, API_KEY):
        return PlainTextResponse("Unauthorized", status_code=401)

    expected = hmac.new(API_SECRET.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    if not safe_eq(x_signature, expected):
        return PlainTextResponse("Invalid signature", status_code=401)

    # `extra` is ignored. The sender asked us not to use it.
    return JSONResponse(await accept_card(payload.model_dump()))


@app.post(
    "/dev/card",
    response_model=CardResult,
    summary="Submit a card without a signature",
    description="Only available when DEV_SIMULATE=1.",
)
async def dev_card(payload: CardIssued):
    if not DEV_SIMULATE:
        return PlainTextResponse("Not found", status_code=404)
    return JSONResponse(await accept_card(payload.model_dump()))


@app.get("/cards/{card_id}")
async def card_image(card_id: str):
    if not re.fullmatch(r"[a-f0-9]{32}\.(jpg|png)", card_id):
        raise HTTPException(status_code=404)
    path = DATA_DIR / card_id
    if not path.is_file():
        raise HTTPException(status_code=404)
    media = "image/png" if card_id.endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=86400"})


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    hub: Hub = websocket.app.state.hub
    lineup: Lineup = websocket.app.state.lineup
    hub.add(websocket)
    try:
        await websocket.send_json(await lineup.current())
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
    except (WebSocketDisconnect, WebSocketDisconnected):
        pass
    finally:
        hub.discard(websocket)


app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
app.mount("/media", StaticFiles(directory=STATIC_DIR / "media"), name="media")
