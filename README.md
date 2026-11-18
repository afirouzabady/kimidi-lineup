# Card lineup webhook

Receives the same signed `card_issued` POST as `card_api_test.php` and shows each finished card image in a 4-3-3 on a stadium page.

`extra` is ignored. The avatar image is the card.

## Run

```bash
cd card_webhook
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/`. The page loops `static/media/stadium.mp4` when that file is present. Without it, a dark pitch is the background.

Point the PHP sender at this process:

`EXTERNAL_CARD_API_URL` = `http://localhost:8000/webhook`

`CARD_API_KEY` and `CARD_API_SECRET` default to the values in `card_api_test.php`. Override them with those env vars if the sender uses different secrets. `LINEUP_HOLD_SECONDS` defaults to 8.

## What arrives

`POST /webhook` with `X-Api-Key` and `X-Signature` (HMAC-SHA256 of the raw body). A 200 means the sender can move on.

Cards fill from the back: GK, LB, LCB, RCB, RB, LCM, CM, RCM, LW, ST, RW. The full team stays up for the hold. The next card waits, then starts the following lineup as GK.

`DEV_SIMULATE=1` opens `POST /dev/card`, which takes the same JSON without a signature.
