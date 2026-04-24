# embr-foundry-tool-sample

A single Python service that demonstrates **Scenario 2** of the [Embr × Foundry POC](https://github.com/coreai-microsoft/embr/issues/300):

> A **Foundry-hosted agent** reaches into an Embr-hosted app as a tool. The same app exposes the same tools via **two** surfaces side-by-side, so we can compare both integration paths from one deployment:
>
> 1. **OpenAPI skill** (`/api/*` + `/openapi.json`) — for Foundry's custom-OpenAPI-tool feature.
> 2. **MCP server** (`/mcp`, streamable HTTP) — for Foundry's MCP tool feature via a project connection.

```
                   ┌─────────────────────────────┐
                   │     Foundry-hosted agent    │
                   └──────────────┬──────────────┘
                                  │
              ┌───────────────────┴────────────────────┐
              │                                        │
    registers │ (as OpenAPI skill)       registers (as MCP tool)
              │                                        │
              ▼                                        ▼
   ┌────────────────────┐                  ┌────────────────────┐
   │ /api/weather       │                  │ /mcp               │
   │ /api/time          │                  │ (streamable HTTP)  │
   └─────────┬──────────┘                  └─────────┬──────────┘
             │   same implementation               │
             └────────────┬────────────────────────┘
                          ▼
               ┌────────────────────┐
               │   app/tools.py     │  (get_weather, get_time)
               └────────────────────┘
```

---

## Part 1 — Run it locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Optional: set TOOL_API_KEY to require an x-api-key header on /api/*
cp .env.example .env

uvicorn app.main:app --reload --port 8000
```

Quick checks:

```bash
# OpenAPI surface
curl 'http://localhost:8000/api/weather?location=Seattle'
curl 'http://localhost:8000/api/time?timezone=America/New_York'
curl http://localhost:8000/openapi.json | jq .info

# MCP surface — initialize handshake
curl -X POST http://localhost:8000/mcp/ \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1"}}}'
```

Interactive API docs: http://localhost:8000/docs

---

## Part 2 — Deploy to Embr

```bash
gh repo create embr-foundry-tool-sample --source=. --public --push
embr quickstart deploy <your-user>/embr-foundry-tool-sample -i <installation-id>
```

Grab the public URL from `embr deployments list`. For this deployment it's:

```
https://production-embr-foundry-tool-sample-5ad18952.app.embr.azure
```

---

## Part 3 — Create the Foundry resources (portal)

### 3a. Create a Foundry project + deploy a model

1. Go to [ai.azure.com](https://ai.azure.com), **+ New project**, accept defaults.
2. **Models + endpoints → + Deploy model → Deploy base model** → pick `gpt-4o-mini` (or any model that supports tool-calling).

### 3b. Create an agent

1. In the project, open **Agents → + New agent**.
2. Pick the model deployment from 3a.
3. Instructions: *"You are a helpful assistant that uses the available tools to answer questions about weather and time. Prefer tools over guessing."*
4. Save — now you can add tools to it.

### 3c. Wire up the OpenAPI skill (custom tool)

1. On the agent page click **+ Add → Custom tool → OpenAPI 3.0 specified tool**.
2. Give it a name (e.g., `embr_tools_openapi`).
3. Paste the URL of your spec:
   ```
   https://production-embr-foundry-tool-sample-5ad18952.app.embr.azure/openapi.json
   ```
4. **Authentication**: Foundry **does not allow anonymous** OpenAPI tools. Pick **API key** (or any option) and fill in dummy values — the server ignores the key unless you set `TOOL_API_KEY` via `embr variables set`. This is one of the platform gaps we're documenting.
5. Save.

### 3d. Wire up the MCP server (project connection)

1. Back in the project, open **Connected resources → + New connection → Custom keys → MCP server**.
2. Server label: `embr_tools_mcp`. Server URL:
   ```
   https://production-embr-foundry-tool-sample-5ad18952.app.embr.azure/mcp/
   ```
   (trailing slash matters — the app mounts MCP at `/mcp` and FastMCP's streamable-HTTP handler is at `/`)
3. Auth: `None` (v1) — or set a bearer token if you've locked it down later.
4. Save the connection. Then on the agent page, **+ Add → MCP server** → pick the connection.

### 3e. Test it

In the agent playground:

- *"What's the weather in Tokyo right now?"* — the model should call `getWeather` (OpenAPI) **or** `get_weather` (MCP) depending on which one Foundry picks up first. Force it to compare by disabling one tool at a time.
- *"What time is it in Sydney?"* — should call `getTime` / `get_time`.

---

## Project layout

```
.
├── app/
│   ├── __init__.py
│   ├── tools.py        # Shared tool logic (get_weather, get_time)
│   ├── mcp_server.py   # FastMCP server wrapping the same logic
│   └── main.py         # FastAPI app: OpenAPI routes + mounts MCP at /mcp
├── embr.yaml
├── requirements.txt
├── .env.example
└── README.md
```

## Known limitations / gaps

- **Unauthenticated in v1.** Both surfaces are wide-open by default. `TOOL_API_KEY` can gate `/api/*` with a header check, but that's all.
- **Foundry refuses anonymous OpenAPI tools** — you're forced to declare an auth scheme in the spec even if the backend ignores it. Candidate Embr platform feature: auto-generate a throwaway API key on `embr.yaml: expose_as: tool` so this isn't a manual step.
- **MCP mount path quirk.** `FastMCP.streamable_http_app()` mounts its own `/mcp` sub-route by default, so without `streamable_http_path="/"` you'd end up serving at `/mcp/mcp`. Worth documenting.
- **FastMCP DNS-rebinding protection** rejects requests with HTTP 421 `Invalid Host header` when deployed behind any proxy — because its `host` param defaults to `127.0.0.1`, which auto-enables a localhost-only allow-list (see `mcp/server/fastmcp/server.py:178-181`). Fix: pass `host="0.0.0.0"` to `FastMCP(...)`. This sample already does this; flagging it for anyone copying the pattern.
- **No rate limiting.** A real tool service needs per-tenant throttling.
