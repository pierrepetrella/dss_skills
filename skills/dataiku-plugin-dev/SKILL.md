---
name: dataiku-plugin-dev
description: Build, extend, and debug Dataiku DSS plugins. Use when asked to create a plugin component (LLM connection, connector, recipe, runnable, trigger, webapp, agent tool, guardrail), add params to plugin.json or llm.json, fix a plugin bug, write a test script for a plugin, or understand how Dataiku plugin APIs work.
compatibility: Designed for Claude Code. Requires an existing Dataiku plugin folder or the intent to create one.
metadata:
  author: pierre.petrella
  version: "1.0"
---

# Dataiku Plugin Developer

You are an expert Dataiku DSS plugin developer. Follow this skill whenever the user is working on a Dataiku plugin.

## How to start

1. Read the existing plugin structure — always read `plugin.json` first, then the relevant component directories.
2. Identify the component type the user wants to build or fix.
3. Apply the exact patterns from this skill and its reference files — do not invent conventions.
4. Never use `print()` for logging — use `logging.getLogger(__name__)`.

---

## Plugin directory layout

```
<plugin-id>/
├── plugin.json                    # REQUIRED — manifest and connection-level params
├── code-env/python/
│   ├── desc.json                  # Python version constraints
│   └── spec/requirements.txt     # pip dependencies
├── python-lib/<package>/          # Shared library — auto-added to sys.path
├── python-llms/<id>/              # Custom LLM connection
│   ├── llm.json
│   └── llm.py
├── python-connectors/<id>/        # Dataset connector
│   ├── connector.json
│   └── connector.py
├── custom-recipes/<id>/           # Visual recipe
│   ├── recipe.json
│   └── recipe.py
├── python-runnables/<id>/         # Macro / runnable
│   ├── runnable.json
│   └── runnable.py
├── python-triggers/<id>/          # Scenario trigger
│   ├── trigger.json
│   └── trigger.py
├── python-webapps/<id>/           # Webapp with optional backend
│   ├── webapp.json
│   └── backend.py
├── python-agent-tools/<id>/       # LLM agent tool
│   ├── tool.json
│   └── tool.py
├── python-agents/<id>/            # Custom agent (external agent service as LLM)
│   ├── agent.json
│   └── agent.py
├── python-guardrails/<id>/        # LLM guardrail
│   ├── guardrail.json
│   └── guardrail.py
└── parameter-sets/<id>/           # Shared credential/preset
    └── parameter-set.json
```

---

## plugin.json — manifest

```json
{
  "id": "my-plugin",
  "version": "1.0.0",
  "meta": {
    "label": "My Plugin",
    "description": "What this plugin does",
    "author": "name",
    "icon": "fas fa-cloud",
    "category": "Connect",
    "tags": ["aws", "llm"],
    "url": "https://...",
    "licenseInfo": "Apache Software License",
    "supportLevel": "SUPPORTED"
  },
  "params": []
}
```

- `params` here = **connection-level** params (admin-only). Passed as `plugin_config` to `set_config()`.
- `supportLevel`: `"SUPPORTED"` | `"TIER2_SUPPORT"` | `"NOT_SUPPORTED"`
- `icon`: FontAwesome 5.15.4 class (e.g. `"fas fa-bolt"`)

For the full param types catalogue (including CREDENTIAL_REQUEST, FOLDER, SAVED_MODEL, DATE, KEY_VALUE_LIST, DATASET_COLUMN, and more) → see [references/param-types.md](references/param-types.md)

For OAuth, API keys, and all credential patterns → see [references/oauth-credentials.md](references/oauth-credentials.md)

Official reference: https://doc.dataiku.com/dss/latest/plugins/reference/params.html

---

## Component quick-reference

### Custom LLM (`python-llms/`)

```python
from dataiku.llm.python import BaseLLM

class MyLLM(BaseLLM):
    def set_config(self, config: dict, plugin_config: dict) -> None:
        # config       → params from llm.json  (per-LLM instance)
        # plugin_config → params from plugin.json (connection-level)
        self.model_id = config.get("modelId")

    def get_max_parallelism(self) -> int:
        return int(self.plugin_config.get("maxParallelism", 8))

    def process(self, query, settings, trace) -> dict:
        # query["messages"] — list of {role, content}
        # settings keys: temperature, max_tokens, top_p, stop
        return {
            "text": "response",
            "promptTokens": 0,      # optional
            "completionTokens": 0,  # optional
            "estimatedCost": 0.0,   # optional, USD
            "toolCalls": [],
        }

    def process_stream(self, query, settings, trace):
        yield {"chunk": {"text": "partial"}}
        yield {"footer": {"promptTokens": 0, "completionTokens": 0,
                          "estimatedCost": 0.0, "toolCalls": []}}
```

Full LLM patterns (tool use, streaming gotchas, message format) → [references/llm-component.md](references/llm-component.md)

---

### Connector (`python-connectors/`)

```python
from dataiku.connector import Connector, CustomDatasetWriter

class MyConnector(Connector):
    def __init__(self, config, plugin_config):
        Connector.__init__(self, config)

    def get_read_schema(self):
        return {"columns": [{"name": "id", "type": "bigint"}, {"name": "name", "type": "string"}]}

    def generate_rows(self, dataset_schema=None, dataset_partitioning=None,
                      partition_id=None, records_limit=-1):
        for row in self.fetch():
            yield {"id": row.id, "name": row.name}

    def get_writer(self, dataset_schema=None, dataset_partitioning=None,
                   partition_id=None, write_mode="OVERWRITE"):
        return MyWriter(self.config, dataset_schema)
```

---

### Recipe (`custom-recipes/`)

```python
import dataiku
from dataiku.customrecipe import get_input_names_for_role, get_output_names_for_role, get_recipe_config

config = get_recipe_config()
input_ds  = dataiku.Dataset(get_input_names_for_role("input_ds")[0])
output_ds = dataiku.Dataset(get_output_names_for_role("output_ds")[0])

df = input_ds.get_dataframe()
# ... process ...
output_ds.write_with_schema(df)
```

---

### Runnable (`python-runnables/`)

```python
from dataiku.runnables import Runnable

class MyRunnable(Runnable):
    def __init__(self, project_key, config, plugin_config):
        self.project_key = project_key
        self.config = config

    def run(self, progress_callback):
        return "<h2>Done</h2>"  # for resultType: HTML
```

---

### Agent Tool (`python-agent-tools/`)

```python
from dataiku.llm.agent_tools import BaseAgentTool

class MyTool(BaseAgentTool):
    def set_config(self, config, plugin_config):
        self.config = config

    def get_descriptor(self, tool):
        return {
            "description": "What this tool does",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }

    def execute(self, tool_input, trace=None):
        return {"type": "TEXT", "content": "result"}  # type: TEXT | JSON | ERROR
```

Full patterns for runnables (ResultTable), triggers, webapps, guardrails, paramsPythonSetup, Dataiku API → [references/other-components.md](references/other-components.md)

---

## DSS Python API — most common calls

```python
import dataiku

# Dataset
ds = dataiku.Dataset("name")
df = ds.get_dataframe()
ds.write_with_schema(df)

# Managed folder
folder = dataiku.Folder("id")
path = folder.get_path()

# API client
client = dataiku.api_client()
project = client.get_project("PROJECT_KEY")

# Connection credentials (AWS)
cred = client.get_connection("conn-name").get_info().get_aws_credential()
# cred keys: accessKey, secretKey, sessionToken
```

---

## Code environment

`code-env/python/desc.json`:
```json
{
  "acceptedPythonInterpreters": ["PYTHON39", "PYTHON310", "PYTHON311", "PYTHON312"],
  "corePackagesSet": "AUTO",
  "forceConda": false,
  "installCorePackages": true,
  "installJupyterSupport": false
}
```

`code-env/python/spec/requirements.txt`:
```
boto3>=1.34.0
requests>=2.28.0,<3.0.0
```

---

## API & documentation references

| Topic | URL |
|-------|-----|
| Plugin param types (all types, all attributes) | https://doc.dataiku.com/dss/latest/plugins/reference/params.html |
| Plugin development overview | https://doc.dataiku.com/dss/latest/plugins/reference/index.html |
| Python API — connections (credential resolution) | https://developer.dataiku.com/latest/api-reference/python/connections.html |
| Python API — datasets | https://developer.dataiku.com/latest/api-reference/python/datasets.html |
| Python API — managed folders | https://developer.dataiku.com/latest/api-reference/python/managed-folders.html |
| Python API — projects | https://developer.dataiku.com/latest/api-reference/python/projects.html |
| Python API — LLM (completion API) | https://developer.dataiku.com/latest/api-reference/python/llm.html |
| Custom LLM plugin guide | https://doc.dataiku.com/dss/latest/generative-ai/llm-connection/custom-llm.html |
| Custom connector guide | https://doc.dataiku.com/dss/latest/plugins/reference/connectors.html |
| Custom recipe guide | https://doc.dataiku.com/dss/latest/plugins/reference/custom-recipes.html |
| Runnables guide | https://doc.dataiku.com/dss/latest/plugins/reference/runnables.html |
| Agent tools guide | https://doc.dataiku.com/dss/latest/generative-ai/llm-connection/agent-tools.html |
| Guardrails guide | https://doc.dataiku.com/dss/latest/generative-ai/llm-connection/guardrails.html |
| Code environments | https://doc.dataiku.com/dss/latest/code-envs/index.html |

---

## Critical gotchas

1. **`config` vs `plugin_config`** — never swap them. `config` = per-component (llm.json). `plugin_config` = per-connection (plugin.json).
2. **`CONNECTION` returns a string** (single name). `CONNECTIONS` returns a list. Use `CONNECTION` for exactly-one selectors.
3. **Streaming footer must be last** — yield all `{"chunk": ...}` before the single `{"footer": ...}`.
4. **`MyLLM` class name is required** — DSS looks up that exact name in the module.
5. **`SEPARATOR` params store no value** — never read them in Python.
6. **`visibilityCondition` is JavaScript**, not Python — runs in the browser, uses `model.<paramName>`.
7. **Flask `app` must be at module level** in `backend.py` — DSS imports the module and looks for `app`.
8. **All `python-lib/` subdirectories are auto-added to `sys.path`** — import directly.
9. **Recipe inputs by role name**, not dataset name — always use `get_input_names_for_role("role")[0]`.
10. **`mandatory: false` is not the default** — always set it explicitly.

For the complete gotchas list (35 entries) → [references/gotchas.md](references/gotchas.md)

---

## Writing a test script

When the user asks for a test script for an LLM plugin, create `test_llm.py` at the plugin root:

```python
import sys, os, types

# Path setup
PLUGIN_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "python-lib"))
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "python-llms", "<llm-dir>"))

# Mock dataiku.llm.python.BaseLLM
_dku = types.ModuleType("dataiku")
_llm = types.ModuleType("dataiku.llm")
_py  = types.ModuleType("dataiku.llm.python")
class BaseLLM: pass
_py.BaseLLM = BaseLLM
_llm.python = _py; _dku.llm = _llm
sys.modules.setdefault("dataiku", _dku)
sys.modules.setdefault("dataiku.llm", _llm)
sys.modules.setdefault("dataiku.llm.python", _py)

from llm import MyLLM

LLM_CONFIG    = {"modelId": "amazon.nova-pro-v1:0"}  # per-llm params
PLUGIN_CONFIG = {}                                     # connection-level params

llm = MyLLM()
llm.set_config(LLM_CONFIG, PLUGIN_CONFIG)

class Trace:
    pass

result = llm.process(
    {"messages": [{"role": "user", "content": "Say hi"}], "tools": []},
    {"temperature": 0.7, "max_tokens": 128},
    Trace()
)
print(result)
```
