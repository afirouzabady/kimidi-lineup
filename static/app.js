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

const video = document.getElementById("stadium");
video.addEventListener("playing", () => document.body.classList.remove("no-video"));
video.addEventListener("error", () => document.body.classList.add("no-video"));
if (video.error) document.body.classList.add("no-video");
video.play().catch(() => document.body.classList.add("no-video"));

connect();
tickHold();
