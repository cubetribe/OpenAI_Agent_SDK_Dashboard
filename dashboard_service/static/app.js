const RUNTIME_MIN_WIDTH = 1180;
const RUNTIME_MIN_HEIGHT = 680;
const RUNTIME_MARGIN_X = 90;
const RUNTIME_MARGIN_Y = 86;
const RUNTIME_LAYER_GAP = 360;
const RUNTIME_ROW_GAP = 168;
const RUNTIME_NODE_MIN_WIDTH = 290;
const RUNTIME_NODE_MAX_WIDTH = 390;
const RUNTIME_NODE_BASE_HEIGHT = 116;
const ZOOM_MIN = 0.4;
const ZOOM_MAX = 2.5;
const ZOOM_STEP = 0.15;

const ACRONYMS = new Map([
  ["api", "API"],
  ["gpt", "GPT"],
  ["id", "ID"],
  ["llm", "LLM"],
  ["mcp", "MCP"],
  ["rag", "RAG"],
  ["sdk", "SDK"],
  ["url", "URL"],
]);

const KIND_META = {
  workflow: { icon: "TR", subtitle: "trace" },
  task: { icon: "TS", subtitle: "runner task" },
  agent: { icon: "AG", subtitle: "agent span" },
  turn: { icon: "TN", subtitle: "agent turn" },
  tool: { icon: "FN", subtitle: "tool call" },
  external: { icon: "AI", subtitle: "model call" },
  handoff: { icon: "HF", subtitle: "handoff" },
  guardrail: { icon: "GR", subtitle: "guardrail" },
  span: { icon: "SP", subtitle: "span" },
  status: { icon: "..", subtitle: "status" },
  node: { icon: "ND", subtitle: "node" },
};

const state = {
  config: null,
  socket: null,
  events: [],
  nodes: new Map(),
  edges: [],
  zoom: 1,
  graphSize: { width: 920, height: 390 },
};

const elements = {
  brandName: document.querySelector("#brand-name"),
  graphPanel: document.querySelector(".graph-panel"),
  graph: document.querySelector("#workflow-graph"),
  form: document.querySelector("#token-form"),
  tokenInput: document.querySelector("#token-input"),
  clearToken: document.querySelector("#clear-token"),
  archiveForm: document.querySelector("#archive-form"),
  zoomOut: document.querySelector("#zoom-out"),
  zoomLevel: document.querySelector("#zoom-level"),
  zoomIn: document.querySelector("#zoom-in"),
  zoomReset: document.querySelector("#zoom-reset"),
  zoomFit: document.querySelector("#zoom-fit"),
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

elements.archiveForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const token = currentToken();
  if (!token) return;

  const data = new FormData(elements.archiveForm);
  const params = new URLSearchParams();
  const status = data.get("status")?.toString().trim();
  const query = data.get("q")?.toString().trim();
  if (status) params.set("status", status);
  if (query) params.set("q", query);
  params.set("limit", "100");

  const response = await fetch(`/api/events/search?${params.toString()}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    setConnection("Archive error");
    return;
  }

  const payload = await response.json();
  state.events = payload.events ?? [];
  renderGraph();
  renderFeed();
});

elements.zoomOut.addEventListener("click", () => setZoom(state.zoom - ZOOM_STEP));
elements.zoomIn.addEventListener("click", () => setZoom(state.zoom + ZOOM_STEP));
elements.zoomReset.addEventListener("click", () => setZoom(1));
elements.zoomFit.addEventListener("click", () => fitGraphToPanel());

elements.graphPanel.addEventListener(
  "wheel",
  (event) => {
    if (!event.metaKey && !event.ctrlKey) return;
    event.preventDefault();
    setZoom(state.zoom + (event.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP));
  },
  { passive: false },
);

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
      renderGraph();
      renderFeed();
      return;
    }
    if (payload.type === "event" && payload.event) {
      state.events.unshift(payload.event);
      state.events = state.events.slice(0, 100);
      renderGraph(payload.event);
      renderFeed();
    }
  });
}

async function loadReplay() {
  const token = currentToken();
  if (!token) return;

  const response = await fetch("/api/events/replay", {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    setConnection("Replay error");
    return;
  }

  const payload = await response.json();
  state.events = payload.events ?? [];
  renderGraph();
  renderFeed();
}

function currentToken() {
  return elements.tokenInput.value.trim() || window.localStorage.getItem("dashboard-token") || "";
}

function renderGraph(activeEvent = null) {
  if (usesRuntimeGraph()) {
    renderRuntimeGraph(activeEvent);
    return;
  }
  renderConfiguredGraph(activeEvent);
}

function renderConfiguredGraph(activeEvent = null) {
  const viewBox = state.config.viewBox ?? "0 0 920 390";
  elements.graph.setAttribute("viewBox", viewBox);
  state.graphSize = sizeFromViewBox(viewBox);
  applyGraphZoom();
  elements.graph.replaceChildren();
  state.nodes.clear();
  state.edges = [];
  drawGraphDefs();

  for (const edge of state.config.edges ?? []) {
    const from = configuredNodeById(edge.from);
    const to = configuredNodeById(edge.to);
    if (!from || !to) continue;
    drawEdge(edge, from, to, false);
  }

  for (const node of state.config.nodes ?? []) {
    drawNode(node);
  }

  for (const event of sortedEvents()) {
    applyEvent(event, false);
  }
  if (activeEvent) {
    applyEvent(activeEvent, true);
  }
  updateActiveNode(activeEvent ?? newestEventWithNode());
}

function renderRuntimeGraph(activeEvent = null) {
  const events = runtimeEvents();
  const graph = buildRuntimeGraph(events);
  const size = layoutRuntimeGraph(graph);

  elements.graph.setAttribute("viewBox", `0 0 ${size.width} ${size.height}`);
  state.graphSize = size;
  applyGraphZoom();
  elements.graph.replaceChildren();
  state.nodes.clear();
  state.edges = [];
  drawGraphDefs();

  for (const edge of graph.edges) {
    const from = graph.nodes.get(edge.from);
    const to = graph.nodes.get(edge.to);
    if (!from || !to) continue;
    const flowsNow = activeEvent?.status === "active" && edge.touches?.has(resolveNodeId(activeEvent));
    drawEdge(edge, from, to, flowsNow);
  }

  for (const node of graph.nodes.values()) {
    drawNode(node);
  }

  for (const event of sortedEvents(events)) {
    applyEvent(event, false);
  }
  if (activeEvent) {
    applyEvent(activeEvent, true);
  }
  updateActiveNode(activeEvent ?? newestEventWithNode(events));
}

function drawGraphDefs() {
  const defs = svg("defs", {});
  const marker = svg("marker", {
    id: "edge-arrow",
    viewBox: "0 0 10 10",
    refX: 9,
    refY: 5,
    markerWidth: 7,
    markerHeight: 7,
    orient: "auto-start-reverse",
  });
  marker.append(
    svg("path", {
      class: "edge-arrow",
      d: "M 0 0 L 10 5 L 0 10 z",
    }),
  );
  defs.append(marker);
  elements.graph.append(defs);
}

function drawEdge(edge, from, to, flowing) {
  const start = connectionPoint(from, to);
  const end = connectionPoint(to, from);
  const line = svg("path", {
    class: `edge ${statusClass(edge.status)} ${edge.relation ?? ""}${flowing ? " flowing" : ""}`,
    d: edgePath(start, end),
    "marker-end": "url(#edge-arrow)",
  });
  elements.graph.append(line);
  state.edges.push({ ...edge, element: line });
}

function drawNode(node) {
  const group = svg("g", {
    class: `node ${node.kind ?? "node"} ${statusClass(node.status)}`,
    "data-node-id": node.id,
  });
  const parts = node.shape === "circle" ? circleNodeParts(node) : cardNodeParts(node);
  group.append(...parts);
  elements.graph.append(group);
  state.nodes.set(node.id, { ...node, element: group });
}

function cardNodeParts(node) {
  const { width, height } = nodeSize(node);
  const left = node.x - width / 2;
  const top = node.y - height / 2;
  const icon = node.icon ?? iconForKind(node.kind);
  const titleLines = labelLines(node.label).slice(0, 3);
  const subtitle = node.subtitle ?? KIND_META[node.kind ?? "node"]?.subtitle;
  const titleStartY = top + (titleLines.length === 1 ? 46 : 34);
  const lineHeight = 22;

  const parts = [
    svg("rect", {
      class: "node-body",
      x: left,
      y: top,
      width,
      height,
      rx: 10,
    }),
    svg("rect", {
      class: "node-icon-bg",
      x: left + 18,
      y: top + 22,
      width: 58,
      height: 58,
      rx: 12,
    }),
    textElement(icon, {
      class: "node-icon-label",
      x: left + 47,
      y: top + 58,
    }),
    svg("circle", {
      class: "node-port node-port-in",
      cx: left,
      cy: node.y,
      r: 8,
    }),
    svg("circle", {
      class: "node-port node-port-out",
      cx: left + width,
      cy: node.y,
      r: 8,
    }),
  ];

  titleLines.forEach((line, index) => {
    parts.push(
      textElement(line, {
        class: "node-label",
        x: left + 94,
        y: titleStartY + index * lineHeight,
      }),
    );
  });

  if (subtitle) {
    parts.push(
      textElement(subtitle, {
        class: "node-subtitle",
        x: left + 94,
        y: top + height - 22,
      }),
    );
  }

  parts.push(statusDot(node));
  return parts;
}

function circleNodeParts(node) {
  return [circleNode(node), nodeLabel(node), statusDot(node)];
}

function buildRuntimeGraph(events) {
  const nodes = new Map();
  const edges = [];
  const edgeKeys = new Set();
  const spanToNode = new Map();
  const traceToWorkflow = new Map();
  let order = 0;

  for (const event of sortedEvents(events)) {
    const workflow = ensureWorkflowNode(nodes, traceToWorkflow, event, order++);
    if (isTraceEvent(event)) {
      mergeNodeStatus(workflow, event);
      continue;
    }

    const spanType = normalizedSpanType(event);
    const node = runtimeNodeForEvent(event, order++);
    if (!node) continue;

    const taskMatchesWorkflow =
      spanType === "task" && comparableLabel(node.label) === comparableLabel(workflow.label);
    if (taskMatchesWorkflow) {
      if (event.span_id) {
        spanToNode.set(event.span_id, workflow.id);
      }
      mergeNodeStatus(workflow, event);
      continue;
    }

    const storedNode = ensureNode(nodes, node);
    mergeNodeStatus(storedNode, event);

    if (event.span_id) {
      spanToNode.set(event.span_id, storedNode.id);
    }

    const parentId = event.parent_span_id ? spanToNode.get(event.parent_span_id) : null;
    const from = parentId ?? workflow.id;
    addRuntimeEdge(edges, edgeKeys, from, storedNode.id, event);
    addDeclaredAgentBranches(nodes, edges, edgeKeys, storedNode, event);
  }

  if (nodes.size === 0) {
    ensureNode(nodes, {
      id: "runtime-waiting",
      label: ["Waiting for", "trace events"],
      kind: "status",
      status: "unknown",
      subtitle: "connect an SDK run",
      width: 320,
      height: RUNTIME_NODE_BASE_HEIGHT,
      order: 0,
    });
  }

  return { nodes, edges };
}

function ensureWorkflowNode(nodes, traceToWorkflow, event, order) {
  const label = workflowLabel(event);
  const key = event.trace_id ? `trace:${event.trace_id}` : `workflow:${slug(label)}`;
  const existingId = event.trace_id ? traceToWorkflow.get(event.trace_id) : null;
  const id = existingId ?? key;
  if (event.trace_id) {
    traceToWorkflow.set(event.trace_id, id);
  }
  return ensureNode(nodes, {
    id,
    label: wrapLabel(humanizeLabel(label), 26, 3),
    kind: "workflow",
    status: event.status ?? "active",
    subtitle: "trace",
    icon: "TR",
    width: 350,
    height: RUNTIME_NODE_BASE_HEIGHT,
    order,
  });
}

function runtimeNodeForEvent(event, order = 0) {
  if (!isSpanEvent(event)) return null;

  const metadata = event.metadata ?? {};
  const spanType = normalizedSpanType(event);
  const name = firstText(
    event.node_id,
    event.agent_id,
    event.tool_name,
    metadata.agent_name,
    metadata.name,
    metadata.task_name,
  );

  if (event.node_id) {
    return runtimeNode(event.node_id, name ?? event.node_id, "node", event, order);
  }
  if (spanType === "agent") {
    const label = event.agent_id ?? metadata.name ?? "Agent";
    return runtimeNode(`agent:${label}`, label, "agent", event, order);
  }
  if (spanType === "turn") {
    const agentName = event.agent_id ?? metadata.agent_name ?? metadata.name ?? "Agent";
    const turn = metadata.turn ? `Turn ${metadata.turn}` : "Turn";
    return runtimeNode(`turn:${agentName}:${turn}`, `${turn} ${agentName}`, "turn", event, order);
  }
  if (spanType === "task") {
    const label = metadata.task_name ?? metadata.name ?? "Runner task";
    return runtimeNode(`task:${label}`, label, "task", event, order);
  }
  if (spanType === "function" || spanType === "tool") {
    const label = event.tool_name ?? metadata.name ?? "Tool call";
    return runtimeNode(`tool:${label}`, label, "tool", event, order);
  }
  if (spanType === "mcp_tools") {
    const label = metadata.server ? `MCP ${metadata.server}` : "MCP tools";
    return runtimeNode(`tool:${label}`, label, "tool", event, order);
  }
  if (spanType === "response" || spanType === "generation") {
    const label = metadata.model ?? (spanType === "generation" ? "Model generation" : "OpenAI response");
    return runtimeNode(`model:${label}`, label, "external", event, order);
  }
  if (spanType === "handoff") {
    const fromAgent = metadata.from_agent ?? "agent";
    const toAgent = metadata.to_agent ?? "agent";
    return runtimeNode(
      `handoff:${fromAgent}:${toAgent}`,
      `Handoff ${fromAgent} to ${toAgent}`,
      "handoff",
      event,
      order,
    );
  }
  if (spanType === "guardrail") {
    const label = metadata.name ?? "Guardrail";
    return runtimeNode(`guardrail:${label}`, label, "guardrail", event, order);
  }

  const fallback = name ?? event.summary ?? shortId(event.span_id) ?? spanType ?? "Span";
  const id = event.span_id ? `span:${event.span_id}` : `span:${slug(fallback)}`;
  return runtimeNode(id, fallback, "span", event, order);
}

function runtimeNode(id, label, kind, event, order) {
  const displayLabel = humanizeLabel(label);
  const lines = wrapLabel(displayLabel, kind === "workflow" ? 26 : 24, 3);
  const longest = Math.max(...lines.map((line) => line.length), 10);
  const width = Math.min(Math.max(longest * 10 + 128, RUNTIME_NODE_MIN_WIDTH), RUNTIME_NODE_MAX_WIDTH);
  const height = RUNTIME_NODE_BASE_HEIGHT + Math.max(lines.length - 2, 0) * 20;

  return {
    id,
    label: lines,
    kind,
    status: event.status ?? "unknown",
    subtitle: KIND_META[kind]?.subtitle,
    icon: iconForKind(kind),
    width,
    height,
    order,
  };
}

function ensureNode(nodes, node) {
  const existing = nodes.get(node.id);
  if (existing) {
    existing.label = node.label ?? existing.label;
    existing.kind = node.kind ?? existing.kind;
    existing.subtitle = node.subtitle ?? existing.subtitle;
    existing.icon = node.icon ?? existing.icon;
    existing.width = Math.max(existing.width ?? 0, node.width ?? 0);
    existing.height = Math.max(existing.height ?? 0, node.height ?? 0);
    existing.status = node.status ?? existing.status;
    existing.order = Math.min(existing.order ?? node.order ?? 0, node.order ?? 0);
    return existing;
  }
  nodes.set(node.id, node);
  return node;
}

function mergeNodeStatus(node, event) {
  if (!node) return;
  node.status = event.status ?? node.status ?? "unknown";
}

function addRuntimeEdge(edges, edgeKeys, from, to, event, relation = "executed") {
  if (!from || !to || from === to) return;
  const key = `${from}->${to}:${relation}`;
  if (edgeKeys.has(key)) {
    const edge = edges.find((item) => item.from === from && item.to === to && item.relation === relation);
    if (edge) {
      edge.status = event.status ?? edge.status;
      edge.touches.add(to);
    }
    return;
  }
  edgeKeys.add(key);
  edges.push({
    from,
    to,
    status: event.status ?? "unknown",
    relation,
    touches: new Set([from, to]),
  });
}

function addDeclaredAgentBranches(nodes, edges, edgeKeys, sourceNode, event) {
  const metadata = event.metadata ?? {};
  if (normalizedSpanType(event) !== "agent") return;

  for (const tool of safeStringList(metadata.tools)) {
    const id = `declared-tool:${sourceNode.id}:${tool}`;
    ensureNode(nodes, {
      id,
      label: wrapLabel(humanizeLabel(tool), 24, 3),
      kind: "tool",
      status: "idle",
      subtitle: "available tool",
      icon: "FN",
      width: RUNTIME_NODE_MIN_WIDTH,
      height: RUNTIME_NODE_BASE_HEIGHT,
      order: (sourceNode.order ?? 0) + 0.1,
    });
    addRuntimeEdge(edges, edgeKeys, sourceNode.id, id, { status: "idle" }, "declared");
  }

  for (const handoff of safeStringList(metadata.handoffs)) {
    const id = `declared-handoff:${sourceNode.id}:${handoff}`;
    ensureNode(nodes, {
      id,
      label: wrapLabel(humanizeLabel(handoff), 24, 3),
      kind: "agent",
      status: "idle",
      subtitle: "handoff target",
      icon: "AG",
      width: RUNTIME_NODE_MIN_WIDTH,
      height: RUNTIME_NODE_BASE_HEIGHT,
      order: (sourceNode.order ?? 0) + 0.2,
    });
    addRuntimeEdge(edges, edgeKeys, sourceNode.id, id, { status: "idle" }, "declared");
  }
}

function layoutRuntimeGraph(graph) {
  const incoming = new Map();
  const children = new Map();
  for (const nodeId of graph.nodes.keys()) {
    incoming.set(nodeId, 0);
    children.set(nodeId, []);
  }
  for (const edge of graph.edges) {
    incoming.set(edge.to, (incoming.get(edge.to) ?? 0) + 1);
    children.get(edge.from)?.push(edge.to);
  }

  const roots = [...graph.nodes.keys()].filter((id) => (incoming.get(id) ?? 0) === 0);
  const levels = new Map();
  const queue = roots.map((id) => [id, 0]);
  for (const [id] of queue) {
    levels.set(id, 0);
  }

  while (queue.length > 0) {
    const [id, level] = queue.shift();
    for (const child of children.get(id) ?? []) {
      const nextLevel = level + 1;
      if (!levels.has(child) || nextLevel > levels.get(child)) {
        levels.set(child, nextLevel);
        queue.push([child, nextLevel]);
      }
    }
  }

  for (const nodeId of graph.nodes.keys()) {
    if (!levels.has(nodeId)) {
      levels.set(nodeId, 0);
    }
  }

  const levelBuckets = new Map();
  for (const [nodeId, level] of levels.entries()) {
    if (!levelBuckets.has(level)) {
      levelBuckets.set(level, []);
    }
    levelBuckets.get(level).push(nodeId);
  }

  const maxLevel = Math.max(...levels.values(), 0);
  const maxRows = Math.max(...[...levelBuckets.values()].map((ids) => ids.length), 1);
  const width = Math.max(
    RUNTIME_MIN_WIDTH,
    RUNTIME_MARGIN_X * 2 + maxLevel * RUNTIME_LAYER_GAP + RUNTIME_NODE_MAX_WIDTH,
  );
  const height = Math.max(RUNTIME_MIN_HEIGHT, RUNTIME_MARGIN_Y * 2 + maxRows * RUNTIME_ROW_GAP);

  for (const [level, ids] of levelBuckets.entries()) {
    ids.sort((a, b) => (graph.nodes.get(a)?.order ?? 0) - (graph.nodes.get(b)?.order ?? 0));
    const columnHeight = (ids.length - 1) * RUNTIME_ROW_GAP;
    const startY = height / 2 - columnHeight / 2;
    ids.forEach((id, index) => {
      const node = graph.nodes.get(id);
      if (!node) return;
      node.x = RUNTIME_MARGIN_X + nodeSize(node).width / 2 + level * RUNTIME_LAYER_GAP;
      node.y = startY + index * RUNTIME_ROW_GAP;
    });
  }

  return { width, height };
}

function setZoom(value) {
  state.zoom = clamp(value, ZOOM_MIN, ZOOM_MAX);
  applyGraphZoom();
}

function fitGraphToPanel() {
  const padding = 56;
  const availableWidth = Math.max(elements.graphPanel.clientWidth - padding, 1);
  const availableHeight = Math.max(elements.graphPanel.clientHeight - padding, 1);
  const widthRatio = availableWidth / state.graphSize.width;
  const heightRatio = availableHeight / state.graphSize.height;
  setZoom(Math.min(widthRatio, heightRatio));
}

function applyGraphZoom() {
  const width = Math.max(1, Math.round(state.graphSize.width * state.zoom));
  const height = Math.max(1, Math.round(state.graphSize.height * state.zoom));
  elements.graph.style.width = `${width}px`;
  elements.graph.style.height = `${height}px`;
  elements.zoomLevel.value = `${Math.round(state.zoom * 100)}%`;
}

function applyEvent(event, animateEdges) {
  const nodeId = resolveNodeId(event);
  if (!nodeId) return;

  const node = state.nodes.get(nodeId);
  if (!node) return;

  node.element.classList.remove("active", "success", "error", "unknown", "idle");
  node.element.classList.add(event.status ?? "active");

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
    ...[...state.events].sort((a, b) => timestampMs(b) - timestampMs(a)).map((event) => {
      const item = document.createElement("li");
      item.className = `event-item ${event.status ?? "unknown"}`;

      const summary = document.createElement("div");
      summary.className = "event-summary";
      summary.textContent = event.summary ?? event.event_type ?? "Event";

      const meta = document.createElement("div");
      meta.className = "event-meta";
      const time = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : "";
      const node = nodeLabelForEvent(event) ?? "unmapped";
      const duration = event.duration_ms ? ` · ${event.duration_ms} ms` : "";
      meta.textContent = `${time} · ${node}${duration}`;

      item.append(summary, meta);
      return item;
    }),
  );
}

function updateActiveNode(event) {
  const label = event ? nodeLabelForEvent(event) : null;
  elements.activeNode.textContent = label ?? "None";
}

function resolveNodeId(event) {
  if (usesRuntimeGraph()) {
    if (isTraceEvent(event)) {
      const label = workflowLabel(event);
      return event.trace_id ? `trace:${event.trace_id}` : `workflow:${slug(label)}`;
    }
    return runtimeNodeForEvent(event)?.id ?? null;
  }

  if (event.node_id) return event.node_id;
  const mappings = state.config.eventMappings ?? {};
  return (
    mappings[event.summary] ??
    mappings[event.agent_id] ??
    mappings[event.tool_name] ??
    mappings[event.span_type] ??
    mappings[event.metadata?.workflow_name] ??
    mappings[event.metadata?.name] ??
    mappings[event.event_type] ??
    null
  );
}

function nodeLabelForEvent(event) {
  const nodeId = resolveNodeId(event);
  const node = nodeId ? state.nodes.get(nodeId) : null;
  if (node) return labelText(node.label);
  if (usesRuntimeGraph() && isTraceEvent(event)) return humanizeLabel(workflowLabel(event));
  if (usesRuntimeGraph() && isSpanEvent(event)) return labelText(runtimeNodeForEvent(event)?.label);
  return null;
}

function usesRuntimeGraph() {
  return state.config?.graphMode === "runtime" || state.config?.runtimeGraph?.enabled === true;
}

function runtimeEvents() {
  const traceLimit = Number(state.config?.runtimeGraph?.maxTraces ?? 1);
  const events = state.events.filter((event) => event.trace_id || event.span_id);
  if (traceLimit <= 0) return events;

  const selectedTraceIds = new Set();
  for (const event of [...events].sort((a, b) => timestampMs(b) - timestampMs(a))) {
    const traceId = event.trace_id ?? `event:${event.event_id}`;
    if (selectedTraceIds.size < traceLimit) {
      selectedTraceIds.add(traceId);
    }
  }
  return events.filter((event) => selectedTraceIds.has(event.trace_id ?? `event:${event.event_id}`));
}

function sortedEvents(events = state.events) {
  return [...events].sort((a, b) => timestampMs(a) - timestampMs(b));
}

function newestEventWithNode(events = state.events) {
  return [...events].sort((a, b) => timestampMs(b) - timestampMs(a)).find((event) => resolveNodeId(event));
}

function timestampMs(event) {
  const value = event.timestamp ? Date.parse(event.timestamp) : Number.NaN;
  return Number.isFinite(value) ? value : 0;
}

function isTraceEvent(event) {
  return event.event_type === "trace_start" || event.event_type === "trace_end";
}

function isSpanEvent(event) {
  return event.event_type === "span_start" || event.event_type === "span_end";
}

function workflowLabel(event) {
  const metadata = event.metadata ?? {};
  return (
    metadata.workflow_name ??
    stripLifecycleSuffix(event.summary) ??
    shortId(event.trace_id) ??
    "Workflow"
  );
}

function normalizedSpanType(event) {
  const metadata = event.metadata ?? {};
  return String(
    event.span_type ??
      metadata.sdk_span_type ??
      metadata.span_data_type ??
      metadata.name ??
      "span",
  ).toLowerCase();
}

function stripLifecycleSuffix(value) {
  if (!value) return null;
  return String(value).replace(/\s+(started|finished)$/i, "");
}

function rectNode(node) {
  const { width, height } = nodeSize(node);
  return svg("rect", {
    class: "node-body",
    x: node.x - width / 2,
    y: node.y - height / 2,
    width,
    height,
    rx: 8,
  });
}

function circleNode(node) {
  return svg("circle", {
    class: "node-body",
    cx: node.x,
    cy: node.y,
    r: nodeSize(node).radius,
  });
}

function nodeLabel(node) {
  const text = svg("text", { class: "node-label circle-label", x: node.x, y: node.y });
  const lines = labelLines(node.label);
  const lineHeight = Number(node.labelLineHeight ?? 18);
  const startOffset = ((lines.length - 1) * lineHeight) / -2;

  lines.forEach((line, index) => {
    const tspan = svg("tspan", {
      x: node.x,
      dy: index === 0 ? startOffset : lineHeight,
    });
    tspan.textContent = line;
    text.append(tspan);
  });

  return text;
}

function statusDot(node) {
  const { width, height, radius } = nodeSize(node);
  const x = node.shape === "circle" ? node.x + radius * 0.67 : node.x + width / 2 - 16;
  const y = node.shape === "circle" ? node.y - radius * 0.67 : node.y - height / 2 + 16;
  return svg("circle", {
    class: `status-dot ${statusClass(node.status)}`,
    cx: x,
    cy: y,
    r: 5,
  });
}

function connectionPoint(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const distance = Math.hypot(dx, dy) || 1;

  if (from.shape === "circle") {
    const radius = nodeSize(from).radius + 4;
    return {
      x: from.x + (dx / distance) * radius,
      y: from.y + (dy / distance) * radius,
    };
  }

  const { width, height } = nodeSize(from);
  if (Math.abs(dx) >= Math.abs(dy)) {
    return {
      x: from.x + (dx >= 0 ? width / 2 : -width / 2),
      y: from.y,
    };
  }

  return {
    x: from.x,
    y: from.y + (dy >= 0 ? height / 2 : -height / 2),
  };
}

function edgePath(start, end) {
  const dx = end.x - start.x;
  const curve = Math.max(Math.min(Math.abs(dx) * 0.42, 160), 70);
  const direction = dx >= 0 ? 1 : -1;
  return `M ${start.x} ${start.y} C ${start.x + curve * direction} ${start.y}, ${end.x - curve * direction} ${end.y}, ${end.x} ${end.y}`;
}

function nodeSize(node) {
  return {
    width: Number(node.width ?? 150),
    height: Number(node.height ?? 58),
    radius: Number(node.radius ?? 44),
  };
}

function sizeFromViewBox(value) {
  const parts = String(value).split(/\s+/).map(Number);
  if (parts.length !== 4 || parts.some((part) => !Number.isFinite(part))) {
    return { width: 920, height: 390 };
  }
  return { width: parts[2], height: parts[3] };
}

function labelLines(label) {
  if (Array.isArray(label)) {
    return label.map((line) => String(line));
  }
  return String(label ?? "").split("\n");
}

function labelText(label) {
  return labelLines(label).join(" ");
}

function wrapLabel(value, limit, maxLines = 3) {
  const words = String(value).split(/\s+/).filter(Boolean);
  if (words.length === 0) return [""];
  const lines = [];
  let current = "";

  for (const rawWord of words) {
    const chunks = rawWord.length > limit ? chunkWord(rawWord, limit) : [rawWord];
    for (const word of chunks) {
      if (!current) {
        current = word;
        continue;
      }
      if (`${current} ${word}`.length <= limit) {
        current = `${current} ${word}`;
        continue;
      }
      lines.push(current);
      current = word;
    }
  }
  lines.push(current);

  if (lines.length <= maxLines) {
    return lines;
  }

  const clipped = lines.slice(0, maxLines);
  clipped[maxLines - 1] = `${clipped[maxLines - 1].replace(/\.+$/, "")}...`;
  return clipped;
}

function chunkWord(value, limit) {
  const output = [];
  for (let index = 0; index < value.length; index += limit) {
    output.push(value.slice(index, index + limit));
  }
  return output;
}

function humanizeLabel(value) {
  const cleaned = String(value ?? "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) return "Unknown";

  return cleaned
    .split(" ")
    .map((word) => {
      const lower = word.toLowerCase();
      if (ACRONYMS.has(lower)) return ACRONYMS.get(lower);
      if (word.length <= 3 && word === word.toUpperCase()) return word;
      if (/[A-Z]/.test(word.slice(1))) return word;
      return `${word.charAt(0).toUpperCase()}${word.slice(1)}`;
    })
    .join(" ");
}

function comparableLabel(label) {
  return labelText(label).toLowerCase().replace(/[^a-z0-9]+/g, "");
}

function iconForKind(kind) {
  return KIND_META[kind ?? "node"]?.icon ?? "ND";
}

function statusClass(value) {
  return String(value ?? "unknown")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");
}

function slug(value) {
  return statusClass(value) || "unknown";
}

function shortId(value) {
  return value ? String(value).replace(/^trace_/, "").replace(/^span_/, "").slice(0, 8) : null;
}

function firstText(...values) {
  for (const value of values) {
    if (value === null || value === undefined) continue;
    const text = String(value).trim();
    if (text) return text;
  }
  return null;
}

function safeStringList(value) {
  return Array.isArray(value) ? value.filter((item) => typeof item === "string" && item.trim()) : [];
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function textElement(content, attributes) {
  const text = svg("text", attributes);
  text.textContent = content;
  return text;
}

function setConnection(value) {
  elements.connectionState.textContent = value;
}

function configuredNodeById(id) {
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
