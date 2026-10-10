# Agent Service

Agent service is a FastAPI-based, multi-tenant and multi-session service built with AgentScope 2.0.

This example demonstrates

- how to set up the agent service with Redis storage, and
- how to launch the service and its companion Web UI

Details about the agent service please refer to the [tutorial](https://docs.agentscope.io/latest/en/deploy/agent-service).

## Prerequisites

- Python ≥ 3.11
- Node.js ≥ 20 with `npx`
- [optional] Gaode/AMap API key in `AMAP_API_KEY` (for the `amap` MCP)

## Quickstart

Install AgentScope from PyPI or source:

```bash
uv pip install agentscope[full]
# or
# uv pip install -e [full]
```

Install Redis and start it as backend storage:

```bash
# macOS (Homebrew)
brew install redis
brew services start redis

# Linux (systemd)
sudo apt install redis-server
sudo systemctl start redis-server

# Docker (cross-platform)
docker run --rm -p 6379:6379 redis:7
```

Start the agent service:

```bash
cd examples/agent_service

python main.py
```

Launch the Web UI in a separate terminal to experience a chat-style interface:

```bash
cd examples/web_ui/

pnpm install
# or npm install

# Run in dev mode
pnpm dev
```

After that, you can set the API endpoint `http://localhost:8000` in the Web UI and start experiencing the agent service.

<img src="https://gw.alicdn.com/imgextra/i2/O1CN01Phmg1G1brIVC8WXyU_!!6000000003518-2-tps-2938-1736.png" alt="Web UI Screenshot" width="100%">

## What Next

### Ordered model failover

In the Web UI, open the primary model selector and choose **Model failover**
(**模型故障切换**). Enable the provider model catalogue to automatically use
the same candidate list exposed by `GET /model?provider=...`, or enter
alternative names in order. Set the response timeout, for example 60 seconds.
Catalogue entries are candidates, not proof that the credential can access
every model. All names use the primary credential and model parameters.

The session's `chat_model_config` accepts these additional fields:

```json
{
  "fallback_from_catalog": true,
  "fallback_models": [],
  "request_timeout": 60
}
```

Include the existing `type`, `credential_id`, `model` and `parameters` when
patching this nested configuration. The attempt order is primary model,
explicit alternative names, catalogue names in API order, then the existing
`fallback_chat_model_config` if configured. Duplicate names in the primary
credential's list are removed. Each new model call starts at the primary;
this is failover, not load balancing or a persistent round-robin cursor.

With alternatives configured, AgentScope's model retries are disabled.
The underlying provider SDK may still retry before surfacing an error;
the configured timeout also bounds that wait. All candidates failing raises
the last error; the list is never cycled indefinitely. Timeout covers response
creation plus the first stream chunk, then each subsequent stream wait.
Errors before output can trigger failover. Once a stream has yielded output,
errors stop that response rather than mixing or replaying partial text/tool
calls from another model. User cancellation never starts another candidate.
Without these fields, existing configurations remain valid and provider
timeouts still apply. Restart a backend running without hot reload after
updating the code.

- You can customize the service in `main.py` by adding your own MCPs, middlewares, or workspace manager implementations.

- Experience the agent service, including
    - human-in-the-loop interactions & permission system
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01vGGiBw20agWwpzmjy_!!6000000006866-2-tps-2934-1732.png" alt="Permission System" width="100%">

    - schedule tasks
<img src="https://gw.alicdn.com/imgextra/i1/O1CN01Xi3Qw71E2haKKu4z0_!!6000000000294-2-tps-2932-1738.png" alt="Schedule Tasks" width="100%">

    - and more! (stay tuned for future updates)
