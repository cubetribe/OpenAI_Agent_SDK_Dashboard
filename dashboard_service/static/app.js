const state = {
  config: null,
  socket: null,
  events: [],
  nodes: new Map(),
  edges: [],
};

const elements = {
  brandName: document.querySelector("#brand-name"),
  graph: document.querySelector("#workflow-graph"),
  form: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#token-input"),
  clearToken: document.querySelector("#clear-token"),
  connectionState: document.querySelector("#connection-state"),
  activeNode: document.querySelector("#active-node"),
  eventCount: document.querySelector("#event-count"),
  feed: document.querySelector("#event-feed"),
};

const storedToken = window.localStorage.getItem("dashboard-token");
if (storedToken) {
  elements.tokenInput.value = storedToken;
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const token = new FormData(elements.form).get("token")?.toString().trim();
  if (!token) return;
  window.localStorage.setItem("dashboard-token", token);
  connect(token);
});

elements.clearToken.addEventListener("click", () => {
  window.localStorage.removeItem("dashboard-token");
  elements.tokenInput.value = "";
  if (state.socket) {
    state.socket.close();
  }
});

async function boot() {
  const response = await fetch("/api/config");
  state.config = await response.json();
  elements.brandName.textContent = state.config.brand?.name ?? "Agent SDK Dashboard";
  applyBrand(state.config.brand ?? {});
  renderGraph();

  if (storedToken) {
    connect(storedToken);
  }
}

function applyBrand(brand) {
  const root = document.documentElement;
  if (brand.accent) root.style.setProperty("--accent", brand.accent);
  if (brand.warning) root.style.setProperty("--warning", brand.warning);
  if (brand.danger) root.style.setProperty("--danger", brand.danger);
}

function renderGraph() {
  elements.graph.replaceChildren();
  state.nodes.clear();
  state.edges = [];

  for (const edge of state.config.edges ?? []) {
    const from = nodeById(edge.from);
    const to = nodeById(edge.to);
    if (!from || !to) continue;

    const line = svg("path", {
      class: "edge",
      d: `M ${from.x + 68} ${from.y} C ${from.x + 130} ${from.y}, ${to.x - 130} ${to.y}, ${to.x - 68} ${to.y}`,
    });
    elements.graph.append(line);
    state.edges.push({ ...edge, element: line });
  }

  for (const node of state.config.nodes ?? []) {
    const group = svg("g", { class: "node", "data-node-id": node.id });
    const rect = svg("rect", {
      class: "node-body",
      x: node.x - 74,
      y: node.y - 36,
      width: 148,
      height: 72,
      rx: 8,
    });
    const label = svg("text", { class: "node-label", x: node.x, y: node.y });
    label.textContent = node.label;
    group.append(rect, label);
    elements.graph.append(group);
    state.nodes.set(node.id, { ...node, element: group });
  }
}

function connect(token) {
  if (state.socket) {
    state.socket.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  const socketUrl = `${protocol}://${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`;
  state.socket = new WebSocket(socketUrl);
  setConnection("Connecting");

  state.socket.addEventListener("open", () => setConnection("Online"));
  state.socket.addEventListener("close", () => setConnection("Offline"));
  state.socket.addEventListener("error", () => setConnection("Error"));
  state.socket.addEventListener("message", (message) => {
    const payload = JSON.parse(message.data);
    if (payload.type === "replay") {
      state.events = payload.events ?? [];
      resetGraph();
      for (const event of state.events) {
        applyEvent(event, false);
      }
      renderFeed();
      return;
    }
    if (payload.type === "event" && payload.event) {
      state.events.unshift(payload.event);
      state.events = state.events.slice(0, 50);
      applyEvent(payload.event, true);
      renderFeed();
    }
  });
}

function applyEvent(event, animateEdges) {
  const nodeId = resolveNodeId(event);
  if (!nodeId) return;

  const node = state.nodes.get(nodeId);
  if (!node) return;

  node.element.classList.remove("active", "success", "error");
  node.element.classList.add(event.status ?? "active");
  elements.activeNode.textContent = node.label;

  if (animateEdges) {
    for (const edge of state.edges) {
      const touchesNode = edge.from === nodeId || edge.to === nodeId;
      edge.element.classList.toggle("flowing", touchesNode && event.status === "active");
    }
  }
}

function renderFeed() {
  elements.eventCount.textContent = String(state.events.length);
  elements.feed.replaceChildren(
    ...state.events.map((event) => {
      const item = document.createElement("li");
      item.className = `event-item ${event.status ?? "unknown"}`;

      const summary = document.createElement("div");
      summary.className = "event-summary";
      summary.textContent = event.summary ?? event.event_type ?? "Event";

      const meta = document.createElement("div");
      meta.className = "event-meta";
      const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "";
      const node = resolveNodeId(event) ?? "unmapped";
      const duration = event.duration_ms ? ` · ${event.duration_ms} ms` : "";
      meta.textContent = `${time} · ${node}${duration}`;

      item.append(summary, meta);
      return item;
    }),
  );
}

function resetGraph() {
  for (const node of state.nodes.values()) {
    node.element.classList.remove("active", "success", "error");
  }
  for (const edge of state.edges) {
    edge.element.classList.remove("flowing");
  }
}

function resolveNodeId(event) {
  if (event.node_id) return event.node_id;
  const mappings = state.config.eventMappings ?? {};
  return mappings[event.agent_id] ?? mappings[event.tool_name] ?? mappings[event.span_type] ?? null;
}

function setConnection(value) {
  elements.connectionState.textContent = value;
}

function nodeById(id) {
  return (state.config.nodes ?? []).find((node) => node.id === id);
}

function svg(tagName, attributes) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tagName);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }
  return element;
}

boot();
