# Dataiku Plugin — LLM Component Reference

Full patterns for building `python-llms/<id>/llm.py`.

---

## Two types of LLM components

| Directory | Purpose | Class |
|-----------|---------|-------|
| `python-llms/<id>/` | Custom LLM connection — wraps any external model API | `MyLLM(BaseLLM)` |
| `python-agents/<id>/` | Custom agent — same interface, but the "model" is an external agent service | same `BaseLLM` + `process_stream` |

`python-agents/` uses `agent.json` (not `llm.json`) but the Python class is identical. The class name must match what DSS expects — default is `MyLLM` but `agent.json` can override with `"className"`.

---

## Official documentation

- Custom LLM plugin guide: https://doc.dataiku.com/dss/latest/generative-ai/llm-connection/custom-llm.html
- Python LLM completion API: https://developer.dataiku.com/latest/api-reference/python/llm.html
- Python connections API (credential resolution): https://developer.dataiku.com/latest/api-reference/python/connections.html

---

## Skeleton

```python
import logging
from dataiku.llm.python import BaseLLM

logger = logging.getLogger(__name__)

class MyLLM(BaseLLM):
    def set_config(self, config: dict, plugin_config: dict) -> None: ...
    def get_max_parallelism(self) -> int: ...
    def process(self, query, settings, trace) -> dict: ...
    def process_stream(self, query, settings, trace): ...  # generator
```

**The class must be named `MyLLM`** — DSS looks up that exact name.

---

## `set_config(config, plugin_config)`

Called once when DSS instantiates the LLM. Build your API client here.

- `config` — per-LLM params from `llm.json`
- `plugin_config` — connection-level params from `plugin.json`

```python
def set_config(self, config: dict, plugin_config: dict) -> None:
    # All per-LLM settings come from config (llm.json)
    self.model_id   = config["modelId"]
    self.api_key    = config.get("apiKey") or plugin_config.get("apiKey", "")
    self.base_url   = (config.get("baseUrl") or "https://api.example.com").rstrip("/")
    self.max_p      = int(config.get("maxParallelism") or 8)
    self.client     = build_client(self.api_key, self.base_url)
```

---

## `get_max_parallelism()`

DSS calls this to decide how many concurrent `process()` calls to allow.

```python
def get_max_parallelism(self) -> int:
    return self.max_p  # typically from config, default 8
```

---

## Input: `query` object

```python
query = {
    "messages": [...],   # list of message dicts
    "tools": [...],      # list of tool definitions (OpenAI function-call format)
}
```

### Message format

Each message is:
```python
{"role": "system"|"user"|"assistant"|"tool", "content": str | list}
```

`content` is **either** a plain string or a list of content blocks. Always handle both:

```python
def _get_text(content):
    if isinstance(content, str):
        return content
    # list of blocks: {"type": "text", "text": "..."}, {"type": "tool_use", ...}, {"type": "tool_result", ...}
    return "".join(b.get("text", "") for b in content if b.get("type") == "text")
```

### Tool result messages

When the model made a tool call and the caller provides results, the message looks like:
```python
{
    "role": "tool",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "call_abc123",
            "content": "Paris, France"  # or list of blocks
        }
    ]
}
```

---

## Input: `settings` object

Standard LLM settings — not all providers support all keys:

```python
settings = {
    "temperature":  0.7,
    "max_tokens":   1024,
    "top_p":        0.9,
    "stop":         ["\n\n"],       # or "stopSequences"
}
```

Safe extraction:
```python
def _build_inference_cfg(settings):
    cfg = {}
    if settings.get("temperature") is not None:
        cfg["temperature"] = float(settings["temperature"])
    if settings.get("max_tokens") is not None:
        cfg["max_tokens"] = int(settings["max_tokens"])
    if settings.get("top_p") is not None:
        cfg["top_p"] = float(settings["top_p"])
    stop = settings.get("stop") or settings.get("stopSequences")
    if stop:
        cfg["stop"] = stop if isinstance(stop, list) else [stop]
    return cfg
```

---

## Tool definition format (input)

DSS passes tools in OpenAI function-call format:
```python
{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get weather for a city",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string"}
            },
            "required": ["city"]
        }
    }
}
```

Convert to your provider's format as needed before sending.

---

## `process()` — synchronous

Must return:
```python
{
    "text":             str,   # assistant reply text (empty string if tool call only)
    "promptTokens":     int,   # optional but strongly recommended
    "completionTokens": int,   # optional
    "estimatedCost":    float, # optional, USD
    "toolCalls":        list,  # [] if none
}
```

### Tool call format (output)

Each tool call in `toolCalls`:
```python
{
    "type": "function",
    "id":   "call_abc123",
    "function": {
        "name":      "get_weather",
        "arguments": '{"city": "Paris"}',   # JSON string, not dict
    }
}
```

### Full example

```python
def process(self, query, settings, trace):
    messages = self._convert_messages(query["messages"])
    tools    = self._convert_tools(query.get("tools") or [])

    req = {"model": self.model_id, "messages": messages}
    req.update(self._build_inference_cfg(settings))
    if tools:
        req["tools"] = tools

    try:
        resp = self.client.chat.completions.create(**req)
    except Exception as e:
        raise RuntimeError(f"API error: {e}") from e

    choice    = resp.choices[0]
    msg       = choice.message
    text      = msg.content or ""
    usage     = resp.usage or {}
    pt, ct    = usage.prompt_tokens or 0, usage.completion_tokens or 0
    tool_calls = self._extract_tool_calls(msg.tool_calls or [])

    return {
        "text":             text,
        "promptTokens":     pt,
        "completionTokens": ct,
        "estimatedCost":    self._cost(pt, ct),
        "toolCalls":        tool_calls,
    }
```

---

## `process_stream()` — streaming

Must be a **generator**. Yield `{"chunk": {"text": "..."}}` for text, then a **single** `{"footer": {...}}` at the very end.

```python
def process_stream(self, query, settings, trace):
    req = self._build_request(query, settings)

    # Stream from provider
    stream = self.client.chat.completions.create(**req, stream=True)

    pt, ct = 0, 0
    tool_calls_acc = {}   # index -> {id, name, args_parts[]}

    for chunk in stream:
        choice = chunk.choices[0] if chunk.choices else None
        if not choice:
            # Usage in final chunk (provider-dependent)
            if chunk.usage:
                pt = chunk.usage.prompt_tokens or 0
                ct = chunk.usage.completion_tokens or 0
            continue

        delta = choice.delta

        # Text delta
        if delta.content:
            yield {"chunk": {"text": delta.content}}

        # Tool call delta (OpenAI-style streaming)
        for tc in delta.tool_calls or []:
            idx = tc.index
            if idx not in tool_calls_acc:
                tool_calls_acc[idx] = {"id": tc.id or "", "name": "", "parts": []}
            if tc.function.name:
                tool_calls_acc[idx]["name"] += tc.function.name
            if tc.function.arguments:
                tool_calls_acc[idx]["parts"].append(tc.function.arguments)

    # Reconstruct tool calls
    tool_calls = [
        {
            "type": "function",
            "id": v["id"],
            "function": {"name": v["name"], "arguments": "".join(v["parts"])},
        }
        for v in tool_calls_acc.values()
    ]

    # Footer must be the last yielded value
    yield {
        "footer": {
            "promptTokens":     pt,
            "completionTokens": ct,
            "estimatedCost":    self._cost(pt, ct),
            "toolCalls":        tool_calls,
        }
    }
```

### Streaming rules
1. **Footer must be last** — yield all chunks first, then yield one footer.
2. **Tool arguments arrive as JSON string fragments** — accumulate strings, parse at the end.
3. **Tool call JSON in footer must be a string** (`"arguments": '{"city": "Paris"}'`), not a dict.
4. Token counts typically arrive in the last chunk — don't assume they're non-zero on earlier chunks.

---

## Message conversion: Dataiku → Bedrock (reference implementation)

```python
def convert_messages(dku_messages):
    """Returns (bedrock_messages, system_list)."""
    system = []
    messages = []

    for msg in dku_messages:
        role    = msg["role"]
        content = msg["content"]

        if role == "system":
            texts = content if isinstance(content, str) else "".join(
                b.get("text", "") for b in content if b.get("type") == "text"
            )
            system.append({"text": texts})
            continue

        blocks = _convert_content(content, role)
        messages.append({"role": role, "content": blocks})

    return messages, system


def _convert_content(content, role):
    if isinstance(content, str):
        return [{"text": content}]

    blocks = []
    for block in content:
        btype = block.get("type")
        if btype == "text":
            blocks.append({"text": block["text"]})
        elif btype == "tool_use":
            blocks.append({
                "toolUse": {
                    "toolUseId": block["id"],
                    "name":      block["name"],
                    "input":     block.get("input") or {},
                }
            })
        elif btype == "tool_result":
            result_content = block.get("content", "")
            if isinstance(result_content, str):
                content_blocks = [{"text": result_content}]
            else:
                content_blocks = [
                    {"text": b["text"]} for b in result_content if b.get("type") == "text"
                ]
            blocks.append({
                "toolResult": {
                    "toolUseId": block["tool_use_id"],
                    "content":   content_blocks,
                }
            })
    return blocks
```

---

## Tool conversion: Dataiku → Bedrock

```python
def convert_tools(dku_tools):
    bedrock_tools = []
    for t in dku_tools:
        fn = t["function"]
        bedrock_tools.append({
            "toolSpec": {
                "name":        fn["name"],
                "description": fn.get("description", ""),
                "inputSchema": {"json": fn.get("parameters", {})},
            }
        })
    return bedrock_tools


def extract_tool_calls(output_content):
    tool_calls = []
    for block in output_content:
        if "toolUse" in block:
            tu = block["toolUse"]
            tool_calls.append({
                "type": "function",
                "id":   tu["toolUseId"],
                "function": {
                    "name":      tu["name"],
                    "arguments": json.dumps(tu.get("input") or {}),
                },
            })
    return tool_calls
```

---

## llm.json structure

```json
{
  "meta": {
    "label": "My LLM",
    "description": "Short description",
    "icon": "fas fa-cloud"
  },
  "params": [
    {"name": "apiKey",    "label": "API Key",    "type": "PASSWORD", "mandatory": true},
    {"name": "modelId",   "label": "Model",      "type": "SELECT",   "mandatory": true, "selectChoices": [...]},
    {"name": "maxParallelism", "label": "Max Parallelism", "type": "INT", "defaultValue": 8, "mandatory": false}
  ]
}
```

`llm.json` params are per-LLM instance. Connection-level params (admin-only) go in `plugin.json` and arrive as `plugin_config`.

---

## Pricing helper pattern

```python
_PRICING = {
    "gpt-4o":       {"prompt": 0.0025, "completion": 0.010},
    "gpt-4o-mini":  {"prompt": 0.00015, "completion": 0.0006},
}

def _cost(self, prompt_tokens: int, completion_tokens: int) -> float:
    p = self._pricing  # set in set_config from _PRICING.get(model_id, {prompt:0, completion:0})
    return (prompt_tokens / 1000.0) * p["prompt"] + (completion_tokens / 1000.0) * p["completion"]
```

---

## AWS credential resolution (S3 connection)

```python
import boto3
import dataiku

def get_boto3_session(connection_name: str, region: str) -> boto3.Session:
    if connection_name:
        try:
            cred = (
                dataiku.api_client()
                .get_connection(connection_name)
                .get_info()
                .get_aws_credential()
            )
            return boto3.Session(
                aws_access_key_id=cred.get("accessKey"),
                aws_secret_access_key=cred.get("secretKey"),
                aws_session_token=cred.get("sessionToken"),
                region_name=region,
            )
        except Exception:
            pass  # Fall through to default chain
    return boto3.Session(region_name=region)
```

---

---

## python-agents/ pattern (agent.json + agent.py)

```json
// agent.json — same shape as llm.json but called agent.json
{
  "meta": {"label": "My Agent", "description": "...", "icon": "fas fa-robot"},
  "supportsImageInputs": false,
  "paramsPythonSetup": "get_choices.py",
  "params": [
    {"name": "connection",     "type": "CONNECTION", "allowedConnectionTypes": ["Databricks"], "mandatory": true},
    {"name": "endpoint_name", "type": "SELECT",     "getChoicesFromPython": true, "mandatory": true}
  ]
}
```

```python
# agent.py — inherits BaseLLM, same as llm.py
from dataiku.llm.python import BaseLLM
import dataiku

class MyAgent(BaseLLM):  # class name must match agent.json "className" (default: MyLLM)
    def set_config(self, config, plugin_config):
        connection_name = config["connection"]
        client = dataiku.api_client()
        conn_info = client.get_connection(connection_name).get_info()
        params = conn_info.get("params", {})
        
        auth_type = params.get("authType")
        host = params.get("host")
        
        if auth_type == "PERSONAL_ACCESS_TOKEN":
            token = params.get("personalAccessToken") or params.get("password")
        elif auth_type == "OAUTH2_APP":
            token = conn_info.get("resolvedOAuth2Credential", {}).get("accessToken")
        
        self.endpoint_name = config["endpoint_name"]
        self._init_client(host, token)

    def process_stream(self, query, settings, trace):
        messages = query["messages"]
        for chunk in self._stream_from_external_agent(messages):
            yield {"chunk": {"text": chunk}}
        yield {"footer": {"promptTokens": 0, "completionTokens": 0, "estimatedCost": 0.0, "toolCalls": []}}
```

---

## Async streaming (aprocess_stream)

For agents that natively use async (Vertex AI ADK, LangChain, etc.):

```python
async def aprocess_stream(self, query, settings, trace):
    messages = query["messages"]
    async for chunk in self._async_stream(messages):
        yield {"chunk": {"text": chunk.text}}
    yield {"footer": {"promptTokens": 0, "completionTokens": 0, "estimatedCost": 0.0, "toolCalls": []}}
```

DSS calls `aprocess_stream` if it exists, otherwise falls back to `process_stream`. Don't implement both.

---

## Using Dataiku's LLM API inside a plugin

Plugins that need to call an LLM internally (not as a custom LLM, but as a consumer):

```python
import dataiku

# Basic completion
llm = dataiku.api_client().get_default_project().get_llm(llm_id)
resp = llm.new_completion() \
    .with_message("You are a helpful assistant.", "system") \
    .with_message(user_query, "user") \
    .execute()
text = resp.text

# With JSON output
completion = llm.new_completion()
completion.with_message(system_prompt, "system")
completion.with_message(user_query, "user")
completion.with_json_output()
resp = completion.execute()
data = resp.json   # already-parsed dict

# Cross-project LLM
llm = dataiku.api_client().get_project(project_key).get_llm(llm_id)

# With trace propagation (inside a tool invoke())
with trace.subspan("LLM decision step") as subspan:
    resp = completion.execute()
    subspan.outputs["decision"] = resp.text
```

---

## Tool invoke() — sources and artifacts

Beyond the basic `{"output": str}` return, tools can include sources and structured artifacts:

```python
def invoke(self, input, trace):
    args  = input.get("input", {})
    rows  = self._query_db(args["query"])
    
    return {
        "output": f"Found {len(rows)} results.",
        "sources": [
            {
                "toolCallDescription": f"SQL query: {sql}",
                "items": [{"type": "GENERATED_SQL_QUERY", "value": sql}]
            }
        ],
        "artifacts": [
            {
                "name": "Query Results",
                "parts": [{"type": "RECORDS", "records": {"columns": col_defs, "data": rows}}]
            }
        ]
    }
```

`sources[].items[].type` values: `"SIMPLE_DOCUMENT"`, `"GENERATED_SQL_QUERY"`, `"RECORDS"`, `"ERROR"`, `"INFO"`, `"QUERY"`

---

## Trace/span API in tools and guardrails

```python
def invoke(self, input, trace):
    # Named span for observability
    with trace.subspan("Calling external API") as subspan:
        subspan.inputs["query"] = input["input"].get("query")
        result = self._call_api(...)
        subspan.outputs["result"] = result

    # Top-level span metadata
    trace.span["name"]      = "MY_TOOL_CALL"
    trace.inputs["param"]   = value
    trace.outputs["output"] = result
    trace.attributes["config"] = {"endpoint": self.endpoint}
```

---

## Error handling

Wrap provider calls in `try/except` and re-raise as `RuntimeError`:
```python
try:
    resp = self.client.call(...)
except ProviderSpecificError as e:
    raise RuntimeError(f"Provider error: {e}") from e
```

DSS catches `RuntimeError` and surfaces it to the user.
