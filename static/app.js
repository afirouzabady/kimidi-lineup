const slots = new Map(
  [...document.querySelectorAll(".slot")].map((el) => [el.dataset.role, el])
);

let state = null;

function escapeAttr(value) {
  return String(value).replace(/[&"<>]/g, (ch) => ({
    "&": "&amp;",
    "\"": "&quot;",
    "<": "&lt;",
    ">": "&gt;",
  }[ch]));
}

function emptySlot(role) {
  return `<div class="marker" aria-label="${role} empty"></div><span class="role">${role}</span>`;
}

function render(snap) {
  state = snap;
  for (const slot of snap.slots) {
    const el = slots.get(slot.role);
    if (!el) continue;
    const card = slot.card;
    const id = card ? card.request_id : "";
    if (el.dataset.requestId === id) continue;
    el.dataset.requestId = id;
    if (!card) {
      el.innerHTML = emptySlot(slot.role);
      continue;
    }
    const label = escapeAttr([card.name, card.title].filter(Boolean).join(", ") || "Player card");
    const src = escapeAttr(card.image_url);
    el.innerHTML = `<img class="card enter" alt="${label}" src="${src}">`;
  }

  if (snap.background) showBackground(snap.background);

  const queue = document.getElementById("queue");
  if (snap.queue_length > 0) {
    queue.hidden = false;
    queue.textContent = `Next team · ${snap.queue_length}`;
  } else {
    queue.hidden = true;
    queue.textContent = "";
  }
}

function tickHold() {
  const hold = document.getElementById("hold");
  const bar = document.getElementById("hold-bar");
  if (!state || state.phase !== "holding" || !state.hold_until) {
    hold.hidden = true;
  } else {
    hold.hidden = false;
    const total = Math.max(state.hold_seconds, 0.001) * 1000;
    const remain = state.hold_until * 1000 - Date.now();
    const pct = Math.max(0, Math.min(1, remain / total));
    bar.style.transform = `scaleX(${pct})`;
  }
  requestAnimationFrame(tickHold);
}

function connect() {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws`);
  ws.onmessage = (event) => {
    let msg;
    try {
      msg = JSON.parse(event.data);
    } catch (err) {
      return;
    }
    if (msg && msg.type === "snapshot") render(msg);
  };
  ws.onclose = () => {
    setTimeout(connect, 1000);
  };
}

const players = [...document.querySelectorAll(".stadium")];
let front = 0;
let currentUrl = "";
let playToken = 0;

function silence(video) {
  video.defaultMuted = true;
  if (!video.muted) video.muted = true;
  if (video.volume !== 0) video.volume = 0;
}

function showBackground(url) {
  if (!url || url === currentUrl) return;
  currentUrl = url;
  const token = ++playToken;
  const incoming = players[1 - front];
  const outgoing = players[front];
  silence(incoming);

  const reveal = () => {
    if (token !== playToken) return;
    incoming.classList.add("on");
    outgoing.classList.remove("on");
    front = 1 - front;
    document.body.classList.remove("no-video");
  };

  const fail = () => {
    if (token !== playToken) return;
    if (!outgoing.classList.contains("on") || outgoing.error) {
      document.body.classList.add("no-video");
    }
  };

  incoming.onerror = fail;
  const playIncoming = () => {
    if (token !== playToken) return;
    silence(incoming);
    incoming.play().then(reveal).catch(fail);
  };

  if (incoming.src === url && incoming.readyState >= 2 && !incoming.error) {
    playIncoming();
    return;
  }

  incoming.oncanplay = () => {
    incoming.oncanplay = null;
    playIncoming();
  };
  incoming.src = url;
}

for (const video of players) {
  silence(video);
  video.addEventListener("volumechange", () => silence(video));
  video.addEventListener("play", () => silence(video));
}

const first = players[0];
if (first.getAttribute("src")) {
  currentUrl = first.src;
  silence(first);
  first.play().then(() => document.body.classList.remove("no-video")).catch(() => {
    document.body.classList.add("no-video");
  });
}

// The event wall is 6m x 2.5m. ?screen=WxH sets another wall, ?screen=auto trusts the window.
const WALL_ASPECT = 6 / 2.5;

function screenAspect() {
  const value = new URLSearchParams(location.search).get("screen");
  if (value === "auto") return innerWidth / innerHeight;
  const match = value && value.match(/^(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)$/);
  if (match && Number(match[1]) > 0 && Number(match[2]) > 0) return Number(match[1]) / Number(match[2]);
  return WALL_ASPECT;
}

function fitScreen() {
  const aspect = screenAspect();
  const root = document.documentElement.style;
  root.setProperty("--screen-aspect", aspect);
  root.setProperty("--screen-fit", innerWidth / (innerHeight * aspect));
}

window.addEventListener("resize", fitScreen);
fitScreen();

connect();
tickHold();
