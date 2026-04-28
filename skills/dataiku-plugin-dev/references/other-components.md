# Dataiku Plugin — Component Reference (non-LLM)

Patterns for Connector, Recipe, Runnable, Trigger, Webapp, Agent Tool, and Guardrail.

---

## Official documentation

- Plugin param reference: https://doc.dataiku.com/dss/latest/plugins/reference/params.html
- Custom connector guide: https://doc.dataiku.com/dss/latest/plugins/reference/connectors.html
- Custom recipe guide: https://doc.dataiku.com/dss/latest/plugins/reference/custom-recipes.html
- Runnables guide: https://doc.dataiku.com/dss/latest/plugins/reference/runnables.html
- Agent tools guide: https://doc.dataiku.com/dss/latest/generative-ai/llm-connection/agent-tools.html
- Guardrails guide: https://doc.dataiku.com/dss/latest/generative-ai/llm-connection/guardrails.html
- Python datasets API: https://developer.dataiku.com/latest/api-reference/python/datasets.html
- Python managed folders API: https://developer.dataiku.com/latest/api-reference/python/managed-folders.html
- Python projects API: https://developer.dataiku.com/latest/api-reference/python/projects.html

---

## Connector (`python-connectors/`)

### connector.json

```json
{
  "meta": {"label": "My Connector", "description": "...", "icon": "fas fa-plug"},
  "readable": true,
  "writable": false,
  "params": [
    {"name": "endpoint",  "label": "Endpoint URL", "type": "STRING",  "mandatory": true},
    {"name": "pageSize",  "label": "Page Size",    "type": "INT",     "defaultValue": 100, "mandatory": false}
  ]
}
```

Set `"readable": true` to expose `generate_rows`. Set `"writable": true` to expose `get_writer`.

---

### connector.py

```python
import logging
from dataiku.connector import Connector

logger = logging.getLogger(__name__)

class MyConnector(Connector):
    def __init__(self, config, plugin_config):
        Connector.__init__(self, config, plugin_config)
        self.endpoint  = config["endpoint"]
        self.page_size = int(config.get("pageSize", 100))
        self.client    = MyApiClient(self.endpoint)

    def get_read_schema(self):
        # Return None to let DSS auto-detect from the first rows
        # Return explicit schema dict to fix the schema upfront
        return {
            "columns": [
                {"name": "id",    "type": "bigint"},
                {"name": "name",  "type": "string"},
                {"name": "score", "type": "double"},
            ]
        }

    def generate_rows(self, dataset_schema=None, dataset_partitioning=None,
                      partition_id=None, records_limit=-1):
        n = 0
        page = 1
        while True:
            rows = self.client.get_page(page, self.page_size)
            if not rows:
                break
            for row in rows:
                yield {"id": row["id"], "name": row["name"], "score": row["score"]}
                n += 1
                if 0 <= records_limit <= n:
                    return
            page += 1

    def get_writer(self, dataset_schema=None, dataset_partitioning=None,
                   partition_id=None, write_mode="OVERWRITE"):
        return MyWriter(self.config, dataset_schema, write_mode)
```

**`records_limit=-1` means unlimited.** Check `records_limit < 0` (not `== -1`) before enforcing the limit.  
**`get_read_schema()` returning `None`** tells DSS to infer schema from the first yielded rows.

---

### CustomDatasetWriter

```python
from dataiku.connector import CustomDatasetWriter

class MyWriter(CustomDatasetWriter):
    def __init__(self, config, schema, write_mode):
        self.rows  = []
        self.mode  = write_mode  # "OVERWRITE" | "APPEND"

    def write_row(self, row):
        # row is a list of values aligned with schema columns
        self.rows.append(row)

    def flush(self):
        # Optional: called periodically. Batch-write accumulated rows.
        self._push(self.rows)
        self.rows = []

    def close(self):
        # Always called at end — flush remaining rows here too
        if self.rows:
            self._push(self.rows)
```

---

## Recipe (`custom-recipes/`)

### recipe.json

```json
{
  "meta": {"label": "My Recipe", "description": "...", "icon": "fas fa-cogs"},
  "kind": "PYTHON",
  "inputRoles": [
    {
      "name": "input_ds",
      "label": "Input Dataset",
      "arity": "UNARY",
      "required": true,
      "acceptsDataset": true
    }
  ],
  "outputRoles": [
    {
      "name": "output_ds",
      "label": "Output Dataset",
      "arity": "UNARY",
      "required": true,
      "acceptsDataset": true
    }
  ],
  "params": [
    {"name": "textColumn", "label": "Text Column", "type": "COLUMN", "columnRole": "input_ds", "mandatory": true},
    {"name": "batchSize",  "label": "Batch Size",  "type": "INT",    "defaultValue": 10, "mandatory": false}
  ]
}
```

`columnRole` must exactly match the `inputRoles[].name`. `"arity": "UNARY"` = exactly one dataset; `"NARY"` = multiple.

---

### Multiple inputs and outputs (NARY and optional outputs)

```json
{
  "inputRoles": [
    {"name": "left_ds",  "label": "Left Dataset",  "arity": "UNARY", "required": true,  "acceptsDataset": true},
    {"name": "right_ds", "label": "Right Dataset",  "arity": "UNARY", "required": true,  "acceptsDataset": true}
  ],
  "outputRoles": [
    {"name": "inner_out",  "label": "Inner Join",   "arity": "UNARY", "required": false, "acceptsDataset": true},
    {"name": "left_out",   "label": "Left Only",    "arity": "UNARY", "required": false, "acceptsDataset": true}
  ]
}
```

Optional outputs may not be wired — always check before writing:
```python
def get_opt_output(role):
    names = get_output_names_for_role(role)
    return dataiku.Dataset(names[0]) if names else None

inner = get_opt_output("inner_out")
if inner:
    inner.write_with_schema(inner_df)
```

### Folder outputs in recipes

```json
{
  "outputRoles": [
    {
      "name": "output_folder",
      "label": "Output Folder",
      "arity": "UNARY",
      "required": true,
      "acceptsManagedFolder": true,
      "acceptsDataset": false
    }
  ]
}
```

```python
folder_name = get_output_names_for_role("output_folder")[0]
folder      = dataiku.Folder(folder_name)
folder_path = folder.get_path()   # local filesystem path
with open(os.path.join(folder_path, "result.json"), "w") as f:
    json.dump(data, f)
```

---

### recipe.py

```python
import dataiku
from dataiku.customrecipe import get_input_names_for_role, get_output_names_for_role, get_recipe_config

config = get_recipe_config()

input_ds  = dataiku.Dataset(get_input_names_for_role("input_ds")[0])
output_ds = dataiku.Dataset(get_output_names_for_role("output_ds")[0])

text_column = config["textColumn"]
batch_size  = int(config.get("batchSize", 10))

df = input_ds.get_dataframe()
# ... process df ...
output_ds.write_with_schema(df)
```

Always access datasets **by role name**, not by dataset name — the same recipe can be used on differently named datasets.

---

## Runnable (`python-runnables/`)

### runnable.json

```json
{
  "meta": {"label": "Run Sync", "description": "...", "icon": "fas fa-play"},
  "resultType": "HTML",
  "params": [
    {"type": "SEPARATOR", "label": "Configuration"},
    {"name": "targetEnv", "label": "Target Env", "type": "STRING", "mandatory": true}
  ]
}
```

`resultType`: `"HTML"` | `"TEXT"` | `"RESULT_TABLE"`

---

### runnable.py

```python
import logging
from dataiku.runnables import Runnable

logger = logging.getLogger(__name__)

class MyRunnable(Runnable):
    def __init__(self, project_key, config, plugin_config):
        self.project_key  = project_key
        self.config       = config
        self.plugin_config = plugin_config

    def get_progress_target(self):
        # Return (total_count, unit_string) or None
        return None

    def run(self, progress_callback):
        target = self.config["targetEnv"]
        steps = get_steps(target)

        for i, step in enumerate(steps):
            progress_callback(i, f"Processing step {i+1}/{len(steps)}: {step.name}")
            execute(step)

        # Return value type must match resultType in runnable.json
        return f"<h5>Completed {len(steps)} steps on {target}</h5>"  # HTML
        # return "Done"                                                # TEXT
        # return pd.DataFrame({"step": [...], "status": [...]})       # RESULT_TABLE
```

**`progress_callback(current, message)`** — DSS shows a progress bar + message in the UI.

**`get_progress_target()`** returns `(total_count, unit_name)`:
```python
def get_progress_target(self):
    return (100, "FILES")   # shows "X / 100 FILES"
```

**Throttle progress updates** — calling `progress_callback` too often freezes the UI:
```python
import time
last_update = time.time()
for i, item in enumerate(items):
    process(item)
    now = time.time()
    if now - last_update > 3:   # at most once every 3 seconds
        progress_callback(i, f"Processing {item.name}")
        last_update = now
```

### ResultTable return type

When `resultType` is `"RESULT_TABLE"`, return a `ResultTable` object — **not** a pandas DataFrame:

```python
from dataiku.runnables import Runnable, ResultTable

class MyRunnable(Runnable):
    def run(self, progress_callback):
        rt = ResultTable()
        rt.add_column("action",  "Action",  "STRING")
        rt.add_column("status",  "Status",  "STRING")
        rt.add_column("count",   "Count",   "BIGINT")
        
        for item in results:
            rt.add_record([item.name, item.status, item.count])
        
        return rt
```

`add_column(name, label, type)` — `type` is a DSS type string: `"STRING"`, `"BIGINT"`, `"DOUBLE"`, `"DATE"`.  
`add_record(list)` — list must be in the same column order as `add_column` calls.

---

## Trigger (`python-triggers/`)

### trigger.json

```json
{
  "meta": {"label": "Custom Trigger", "description": "...", "icon": "fas fa-clock"},
  "params": [
    {"name": "webhookUrl", "label": "Webhook URL", "type": "STRING", "mandatory": true}
  ]
}
```

---

### trigger.py

```python
import logging
from dataiku.scenario import Trigger

logger = logging.getLogger(__name__)

class MyTrigger(Trigger):
    def __init__(self):
        pass

    def set_config(self, config, plugin_config):
        self.webhook_url = config["webhookUrl"]

    def run(self, trigger_fire):
        """Called periodically by DSS. Call trigger_fire() if the trigger condition is met."""
        event = poll_for_event(self.webhook_url)
        if event:
            trigger_fire(
                params={"eventId": event["id"]},  # passed to the scenario
                message=f"Event {event['id']} received"
            )
```

---

## Webapp (`python-webapps/`)

### webapp.json

```json
{
  "meta": {"label": "My App", "description": "...", "icon": "fas fa-desktop"},
  "baseType": "STANDARD",
  "hasBackend": "true",
  "enableJavascriptModules": "true",
  "noJSSecurity": "true",
  "standardWebAppLibraries": ["dataiku", "jquery"],
  "params": [
    {"name": "llmId",          "label": "LLM",            "type": "LLM",     "mandatory": true, "llmUsagePurpose": "GENERIC_COMPLETION"},
    {"name": "loggingDataset", "label": "Logging Dataset", "type": "DATASET", "acceptsDataset": true, "canCreateDataset": true, "mandatory": false}
  ]
}
```

---

### backend.py

**`app` must be a Flask application object at module level** — DSS imports the module and looks for `app`.

```python
import logging
from flask import Flask, request, jsonify
import dataiku

logger = logging.getLogger(__name__)
app = Flask(__name__)

@app.route("/query", methods=["POST"])
def query():
    payload = request.get_json(force=True)
    user_msg = payload.get("message", "")

    # Access webapp params via dataiku.customwebapp
    from dataiku.customwebapp import get_webapp_config
    config  = get_webapp_config()
    llm_id  = config["llmId"]

    client   = dataiku.api_client()
    project  = client.get_default_project()
    llm      = project.get_llm(llm_id)
    response = llm.new_completion().with_message(user_msg).execute()

    return jsonify({"reply": response.text})

@app.route("/config", methods=["GET"])
def get_config():
    from dataiku.customwebapp import get_webapp_config
    cfg = get_webapp_config()
    return jsonify({"llmId": cfg.get("llmId")})
```

For complex apps, register Flask **Blueprints**:
```python
from myapp.routes import api_blueprint
app.register_blueprint(api_blueprint, url_prefix="/api")
```

---

## Agent Tool (`python-agent-tools/`)

### tool.json

```json
{
  "meta": {"label": "Weather Tool", "description": "Get weather for a city", "icon": "fas fa-cloud-sun"},
  "params": [
    {"name": "connection", "label": "API Connection", "type": "CONNECTION", "mandatory": true},
    {"name": "units",      "label": "Units",          "type": "SELECT",     "mandatory": false,
     "defaultValue": "celsius", "selectChoices": [{"value": "celsius", "label": "Celsius"}, {"value": "fahrenheit", "label": "Fahrenheit"}]}
  ]
}
```

---

### tool.py

```python
import logging
from dataiku.llm.agent_tools import BaseAgentTool

logger = logging.getLogger(__name__)

class MyTool(BaseAgentTool):
    def set_config(self, config, plugin_config):
        self.units      = config.get("units", "celsius")
        self.api_client = build_weather_client(config["connection"])

    def get_descriptor(self, tool):
        return {
            "description": "Get the current weather for a city.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name, e.g. 'Paris'"},
                    "country": {"type": "string", "description": "ISO country code, e.g. 'FR'"}
                },
                "required": ["city"]
            }
        }

    def invoke(self, input, trace):
        args    = input.get("input", {})
        city    = args.get("city")
        country = args.get("country", "")

        # Trace for observability
        trace.span["name"]      = "WEATHER_TOOL_CALL"
        trace.inputs["city"]    = city
        trace.inputs["country"] = country

        try:
            result = self.api_client.get_weather(city, country, self.units)
            output = f"Weather in {city}: {result['temp']}°, {result['description']}"
        except Exception as e:
            output = f"Error fetching weather: {e}"
            logger.warning("Weather tool error: %s", e)

        trace.outputs["output"] = output
        return {"output": output}

    def load_sample_query(self, tool):
        # Optional: shows an example in the DSS tool testing UI
        return {"city": "Paris", "country": "FR"}
```

**Three required methods**: `set_config`, `get_descriptor`, `invoke`.  
`invoke(input, trace)` — `input` is `{"input": {...}}` (note the nested `"input"` key).  
Return `{"output": str}` for text, or `{"output": dict}` for structured data.

---

## Guardrail (`python-guardrails/`)

### guardrail.json

```json
{
  "meta": {"label": "Content Guardrail", "description": "...", "icon": "fas fa-shield-alt"},
  "operatesOnQueries": true,
  "operatesOnResponsesBasedOnParameterName": "guardrailScope",
  "operatesOnResponsesBasedOnParameterValue": "responses",
  "mayRespondDirectlyToQueriesBasedOnParameterName": "action",
  "mayRespondDirectlyToQueriesBasedOnParameterValue": "DECLINE",
  "params": [
    {
      "name": "action",
      "label": "Action on Violation",
      "type": "SELECT",
      "mandatory": true,
      "defaultValue": "REJECT",
      "selectChoices": [
        {"value": "REJECT",  "label": "Reject (raise error)"},
        {"value": "AUDIT",   "label": "Audit (log and pass through)"},
        {"value": "DECLINE", "label": "Decline (polite refusal)"}
      ]
    },
    {
      "name": "declineMessage",
      "label": "Decline Message",
      "type": "TEXTAREA",
      "mandatory": false,
      "defaultValue": "I'm sorry, I can't help with that.",
      "visibilityCondition": "model.action == 'DECLINE'"
    }
  ]
}
```

---

### guardrail.py

```python
import logging
from dataiku.llm.guardrails import BaseGuardrail

logger = logging.getLogger(__name__)

class MyGuardrail(BaseGuardrail):
    def set_config(self, config, plugin_config):
        self.action       = config.get("action", "REJECT")
        self.decline_msg  = config.get("declineMessage", "I'm sorry, I can't help with that.")
        self.classifier   = build_classifier(config, plugin_config)

    def process(self, input, trace):
        """
        input: string (user query or assistant response)
        Returns dict with "action" key: "ACCEPT" | "REJECT" | "DECLINE" | "AUDIT"
        """
        is_flagged = self.classifier.is_flagged(input)

        if not is_flagged:
            return {"action": "ACCEPT"}

        if self.action == "DECLINE":
            return {"action": "DECLINE", "message": self.decline_msg}
        elif self.action == "AUDIT":
            logger.warning("Guardrail triggered (AUDIT): input='%.100s'", input)
            return {"action": "AUDIT"}
        else:  # REJECT
            return {"action": "REJECT", "message": "Content policy violation detected."}
```

`operatesOnQueries: true` — the guardrail checks user input before the LLM.  
`operatesOnResponsesBasedOnParameterName/Value` — checks responses only when the named param equals the given value.  
`mayRespondDirectlyToQueriesBasedOnParameterName/Value` — allows the guardrail to return `"DECLINE"` with a custom message instead of passing to the LLM.

---

## Parameter Set (`parameter-sets/`)

Shared credential/preset that multiple components can reference via a `PRESET` param.

### parameter-set.json

```json
{
  "meta": {"label": "OAuth Credentials"},
  "params": [
    {"name": "clientId",     "label": "Client ID",     "type": "STRING",   "mandatory": true},
    {"name": "clientSecret", "label": "Client Secret", "type": "PASSWORD", "mandatory": true},
    {"name": "refreshToken", "label": "Refresh Token", "type": "PASSWORD", "mandatory": false}
  ]
}
```

In `connector.json`:
```json
{
  "name": "oauth",
  "label": "OAuth Credentials",
  "type": "PRESET",
  "parameterSetId": "oauth-credentials",
  "mandatory": true
}
```

In Python:
```python
oauth = config["oauth"]  # dict: {"clientId": "...", "clientSecret": "...", "refreshToken": "..."}
```

---

## Dataiku API — common calls from plugin Python code

```python
import dataiku

client = dataiku.api_client()

# Projects
project = client.get_default_project()    # current project
project = client.get_project("KEY")       # specific project
project.project_key                        # project key string
projects = client.list_projects()          # list of project dicts

# LLM (consume Dataiku LLM connections)
llm = project.get_llm(llm_id)
resp = llm.new_completion() \
    .with_message("system prompt", "system") \
    .with_message("user query",    "user") \
    .execute()
text = resp.text
json_data = resp.json   # only if .with_json_output() was called

# Datasets
ds = dataiku.Dataset("name")
df = ds.get_dataframe()
ds.write_with_schema(df)
schema = ds.read_schema()               # list of column dicts

# Managed folders
folder = dataiku.Folder("id")
path   = folder.get_path()                          # local filesystem path
files  = folder.list_paths_in_partition()           # list of file paths
with folder.get_download_stream("/my/file.json") as s:
    data = json.load(s)

# Connections
conn_info = client.get_connection("name").get_info()
conn_type  = conn_info.get("type", "")
params     = conn_info.get("params", {})
aws_cred   = conn_info.get_aws_credential()        # {"accessKey", "secretKey", "sessionToken"}

# Users / auth
auth_info = client.get_auth_info()                 # current user info
auth_info = client.get_auth_info_from_browser_headers(headers)  # in webapp routes
user = client.get_user(auth_info["authIdentifier"])
user_info = user.get_info()
email      = user_info.email
groups     = user_info.groups

# Instance info
instance = client.get_instance_info()
license_id = instance.raw["licenseId"]

# Webapps (from backend.py)
from dataiku.customwebapp import get_webapp_config
config = get_webapp_config()   # dict matching webapp.json params

# Clusters
cluster = client.get_cluster(cluster_id)
cluster_info = cluster.get_info()

# Saved models
model = project.get_saved_model(model_id)
info  = model.get_info()   # {"type": "PREDICTION", ...}
```

---

## paramsPythonSetup — dynamic parameter choices

Referenced from any component JSON root:
```json
{
  "paramsPythonSetup": "resource/browse.py",
  "params": [
    {"name": "base", "type": "SELECT", "getChoicesFromPython": true, "mandatory": true},
    {"name": "table", "type": "SELECT", "getChoicesFromPython": true,
     "triggerParameters": ["base"], "mandatory": true}
  ]
}
```

The Python file must define a `do()` function:
```python
# resource/browse.py
def do(payload, config, plugin_config, inputs):
    param_name = payload.get("parameterName")
    
    if param_name == "base":
        bases = fetch_all_bases(config)
        choices = [{"value": b["id"], "label": b["name"]} for b in bases]
        choices.append({"value": "__manual__", "label": "-- Enter manually --"})
        return {"choices": choices}
    
    elif param_name == "table":
        base_id = config.get("base")
        if not base_id or base_id == "__manual__":
            return {"choices": []}
        tables = fetch_tables(base_id, config)
        return {"choices": [{"value": t["id"], "label": t["name"]} for t in tables]}
    
    return {"choices": []}
```

- Signature is always `do(payload, config, plugin_config, inputs)` — never named after the param.
- `payload["parameterName"]` tells you which param to populate.
- `config` contains the current form state (including values of `triggerParameters`).
- Place the file in `resource/` (auto-discovered) or reference it relative to the plugin root.

---

## Shared library (`python-lib/`)

All subdirectories of `python-lib/` are auto-added to `sys.path`. Import directly:

```
python-lib/
└── myplugin/
    ├── __init__.py
    ├── client.py
    └── utils.py
```

```python
# In any component:
from myplugin.client import MyApiClient
from myplugin.utils import parse_response
```

No path manipulation needed inside DSS. In test scripts, add `python-lib/` to `sys.path` manually.
