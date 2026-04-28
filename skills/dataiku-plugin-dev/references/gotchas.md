# Dataiku Plugin — Gotchas & Non-Obvious Patterns

Ordered from most commonly tripped to most subtle.

---

## 1. `config` vs `plugin_config` — never swap them

```python
def set_config(self, config: dict, plugin_config: dict) -> None:
    self.api_key = config["apiKey"]          # from llm.json / connector.json
    self.admin_setting = plugin_config["x"]  # from plugin.json (connection-level, admin-only)
```

`config` = per-component instance (what the user filling out the form configures).  
`plugin_config` = connection-level, set once by an admin in the plugin connection page.  
Swapping them means you silently read `None` or wrong values with no error.

---

## 2. `CONNECTION` vs `CONNECTIONS`

| Type | Returns | Use when |
|------|---------|----------|
| `CONNECTION` | `str` — connection name | Exactly one connection |
| `CONNECTIONS` | `list[str]` — connection names | Zero or more connections |

```python
# CONNECTION (singular):
connection_name = config.get("s3Connection", "")  # str

# CONNECTIONS (plural):
connections = config.get("connections", [])  # list[str]
```

Swapping these types in JSON causes a runtime type error the first time you try to use the value.

---

## 3. `MyLLM` class name is required

DSS loads the `llm.py` module and does `module.MyLLM()`. If you rename the class, DSS fails silently (loads nothing) or raises an `AttributeError`.

---

## 4. Streaming footer must be the last yield

```python
def process_stream(self, query, settings, trace):
    for chunk in stream:
        yield {"chunk": {"text": chunk.text}}     # all chunks first
    yield {"footer": {...}}                        # ALWAYS last — never yield after this
```

If you yield a chunk after the footer, DSS will discard the footer's token counts and tool calls.

---

## 5. Tool call `arguments` must be a JSON string, not a dict

```python
# CORRECT
"arguments": '{"city": "Paris", "unit": "celsius"}'

# WRONG — DSS expects a string, not a parsed object
"arguments": {"city": "Paris", "unit": "celsius"}
```

This applies to both `process()` return value and the streaming footer's `toolCalls`.

---

## 6. `SEPARATOR` params store no value — never read them

```json
{"type": "SEPARATOR", "label": "Advanced Settings"}
```

`SEPARATOR` has no `name` field. Never reference it in Python. It is UI-only.

---

## 7. `visibilityCondition` is JavaScript, not Python

Conditions run in the **browser** against `model.<paramName>`. Common mistakes:

```js
// Correct JavaScript:
"model.authType == 'oauth'"
"model.useGuardrail"                          // truthy check
"model.features && model.features.length > 0" // array length check
"['a', 'b'].indexOf(model.x) >= 0"           // check if value in list

// Wrong — these are Python, not JS:
"config['authType'] == 'oauth'"
"model.authType in ['a', 'b']"               // Python syntax, fails silently
```

---

## 8. `mandatory: false` is not the default — always set it explicitly

DSS does not have a "default mandatory" — if you omit `mandatory`, the behavior is undefined and varies by DSS version. Always write `"mandatory": true` or `"mandatory": false`.

---

## 9. Recipe: access datasets by role name, not dataset name

```python
# CORRECT — role name matches inputRoles[].name in recipe.json
input_ds = dataiku.Dataset(get_input_names_for_role("input_ds")[0])

# WRONG — dataset name is user-chosen and varies per recipe instance
input_ds = dataiku.Dataset("my_dataset")
```

---

## 10. `columnRole` must match `inputRoles[].name` exactly

```json
// recipe.json
"inputRoles": [{"name": "input_dataset", "label": "Input Dataset", ...}]

// param — must use the internal name, not the label
{"name": "sourceCol", "type": "COLUMN", "columnRole": "input_dataset"}
```

Using the label (`"Input Dataset"`) instead of the internal name (`"input_dataset"`) causes the column picker to show no columns.

---

## 11. `PRESET` config value is a dict, not a string

```python
# In connector.json: {"name": "oauth", "type": "PRESET", "parameterSetId": "oauth-credentials"}
oauth = config["oauth"]
# oauth = {"clientId": "...", "clientSecret": "...", "refreshToken": "..."}
# NOT "oauth" = "some-preset-name"
```

---

## 12. `getChoicesFromPython` + `triggerParameters` — full re-evaluation on change

When `triggerParameters: ["parentParam"]` is set, DSS calls Python to regenerate choices every time `parentParam` changes in the UI. Use `"disableAutoReload": true` if the choices depend on a free-text field that changes on every keystroke:

```json
{
  "name": "projectKey",
  "type": "SELECT",
  "getChoicesFromPython": true,
  "triggerParameters": ["region"],
  "disableAutoReload": true
}
```

---

## 13. Duplicate param names with different `visibilityCondition` are intentional

DSS allows the same `name` to appear multiple times with mutually exclusive `visibilityCondition` values. Only one is visible at a time, but they all write to the same config key:

```json
{"name": "target", "label": "JQL Query",  "type": "STRING", "visibilityCondition": "model.mode == 'jql'"},
{"name": "target", "label": "Filter ID",  "type": "STRING", "visibilityCondition": "model.mode == 'filter'"}
```

In Python: `config["target"]` — one value regardless of which label the user saw.

---

## 14. `records_limit=-1` means unlimited — use `< 0`, not `== -1`

```python
def generate_rows(self, ..., records_limit=-1):
    n = 0
    for row in self.fetch_all():
        yield row
        n += 1
        if 0 <= records_limit <= n:   # correct
            return
```

`records_limit` can be -1 (unlimited) or any positive integer. Do not special-case -1 only.

---

## 15. Flask `app` must be at module level in `backend.py`

DSS imports `backend.py` and reads `module.app`. If `app` is created inside a function or a conditional, DSS cannot find it:

```python
# CORRECT
app = Flask(__name__)

@app.route("/api/query", methods=["POST"])
def query():
    ...
```

---

## 16. All `python-lib/` subdirectories are auto-added to `sys.path`

```
python-lib/
└── mypackage/          ← this directory itself is on sys.path
    ├── __init__.py
    └── client.py
```

Inside DSS: `import mypackage` works without any path manipulation.  
In test scripts: add `python-lib/` to `sys.path` manually:
```python
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "python-lib"))
```

---

## 17. `get_read_schema()` returning `None` ≠ error

`None` tells DSS to infer the schema from the first yielded rows. This is valid and often preferred. Return an explicit schema dict only when you know the schema upfront and want DSS to enforce it.

---

## 18. Agent Tool `invoke` input is nested: `input["input"]`

```python
def invoke(self, input, trace):
    args = input.get("input", {})   # note the nested key
    city = args.get("city")
```

The outer `input` dict has an `"input"` key containing the actual argument dict. A common bug is doing `city = input.get("city")` directly.

---

## 19. Runnable `resultType: "HTML"` — DSS does minimal sanitization

Return valid HTML. DSS renders it as-is in the macro result panel. Common pattern:
```python
return "<h5>Completed 5 steps</h5><ul><li>Step 1: OK</li></ul>"
```

For `resultType: "RESULT_TABLE"`, return a pandas DataFrame.  
For `resultType: "TEXT"`, return a plain string.

---

## 20. Streaming tool input arrives as JSON string fragments

The tool call `input` field arrives as partial JSON strings across multiple `contentBlockDelta` events (Bedrock) or `tool_calls[].function.arguments` deltas (OpenAI). Accumulate the string parts and parse the complete JSON only in the footer:

```python
# During stream:
open_tools[idx]["parts"].append(delta_fragment)

# After stream:
raw_args = "".join(open_tools[idx]["parts"])
parsed   = json.loads(raw_args)   # only parse the complete string
```

---

## 21. `${dip.home}` is interpolated in defaultValue

DSS replaces `${dip.home}` with the actual Dataiku home directory path at runtime. Use it for file path defaults:
```json
{"name": "tokenFile", "type": "STRING", "defaultValue": "${dip.home}/my_token.json"}
```

---

## 22. OBJECT_LIST sub-params are accessed as a list of dicts

```python
tools_config = config.get("tools", [])  # list
for tool in tools_config:
    name    = tool["toolName"]
    enabled = tool.get("toolEnabled", True)
```

Never expect a flat config structure for OBJECT_LIST params.

---

## 23. `paramsPythonSetup` function name must match the param name (camelCase to snake_case)

For a param named `projectKey` with `getChoicesFromPython: true`, DSS calls a function:
```python
# get_choices.py
def get_project_key_choices(config, plugin_config):
    return [{"value": k, "label": k} for k in get_all_projects()]
```

The function name is `get_<snake_case_param_name>_choices`. Getting the naming wrong means DSS silently shows an empty dropdown.

---

## 24. Conditional params may be absent from `config` even if not `mandatory`

When a param is hidden by `visibilityCondition`, DSS may not include it in `config` at all. Always use `.get()` with a default:

```python
guardrail_id = (config.get("guardrailIdentifier") or "").strip()
```

Without the `.get()`, you get a `KeyError` when the param is hidden.

---

## 25. `inferenceConfig` must not contain `None` values for Bedrock

Build the inference config dict only with present values:
```python
cfg = {}
if settings.get("temperature") is not None:
    cfg["temperature"] = float(settings["temperature"])
```

Passing `{"temperature": None}` to Bedrock raises a `ValidationException`.

---

## 26. Guardrail `process()` MODIFIES the input dict — it doesn't return a clean dict

The guardrail API is not `return {"action": "REJECT"}`. Instead you mutate `input`:

```python
def process(self, input, trace):
    text = (input.get("completionResponse") or {}).get("text", "")
    is_flagged = self.classifier.check(text)

    if not is_flagged:
        return  # or return None — both mean PASS

    if self.action == "REJECT":
        input["responseGuardrailResponse"] = {
            "action": "FAIL",
            "error": {"message": "Content policy violation."}
        }
    elif self.action == "DECLINE":
        input["responseGuardrailResponse"] = {"action": "RESPOND"}
        input["completionResponse"]["text"] = self.decline_message
    elif self.action == "AUDIT":
        input["responseGuardrailResponse"] = {
            "action": "PASS_WITH_AUDIT",
            "auditData": [{"origin": "guardrail", "violation": "flagged content"}]
        }
    elif self.action == "RETRY":
        input["responseGuardrailResponse"] = {
            "action": "RETRY",
            "updatedMessagesForRetry": modified_messages
        }
```

For query guardrails, use `input["queryGuardrailResponse"]` instead.

---

## 27. PRESET credential is a nested dict — one level deeper than you expect

```python
# param name is "oauth_credentials", type is PRESET
oauth = config["oauth_credentials"]   # this is a dict
token = oauth["access_token"]          # CORRECT

token = config["access_token"]         # WRONG — KeyError
token = config.get("access_token")     # WRONG — returns None silently
```

If `access_token` is a `dict` (not a string), the user selected the "Manually defined" option and has not authenticated via OAuth yet — fail loudly.

---

## 28. `paramsPythonSetup` function is always named `do()` — not named after the param

```python
# CORRECT — single do() dispatches on payload["parameterName"]
def do(payload, config, plugin_config, inputs):
    if payload["parameterName"] == "base":
        ...

# WRONG — DSS will not call get_base_choices()
def get_base_choices(config, plugin_config):
    ...
```

---

## 29. `ResultTable` (not DataFrame) for RESULT_TABLE runnables

```python
from dataiku.runnables import ResultTable

rt = ResultTable()
rt.add_column("col1", "Column 1", "STRING")
rt.add_record(["value1"])
return rt

# WRONG — returning a DataFrame raises a serialization error
return pd.DataFrame({"col1": ["value1"]})
```

---

## 30. `acceptsManagedFolder` in outputRoles — not `acceptsDataset`

```json
{
  "name": "output_folder",
  "arity": "UNARY",
  "required": true,
  "acceptsManagedFolder": true,
  "acceptsDataset": false   // must be false when using a folder
}
```

In Python: `get_output_names_for_role("output_folder")[0]` returns the folder ID, not a dataset name. Pass it to `dataiku.Folder(id)`, not `dataiku.Dataset(name)`.

---

## 31. `DATASET_COLUMN` uses `datasetParamName`, not `columnRole`

In webapps (no recipe context), column pickers reference a `DATASET` param:

```json
{"name": "ds",  "type": "DATASET",        "acceptsDataset": true},
{"name": "col", "type": "DATASET_COLUMN", "datasetParamName": "ds"}
```

In recipes, use `COLUMN` with `columnRole` instead. Using `datasetParamName` in a recipe won't work.

---

## 32. Connection params dict for non-AWS connections

For Databricks, Snowflake, and similar connections, credentials are in `conn_info.get("params", {})`, not via a dedicated helper like `get_aws_credential()`:

```python
conn_info = dataiku.api_client().get_connection(name).get_info()
params    = conn_info.get("params", {})
host      = params.get("host")
# Databricks PAT:
token     = params.get("personalAccessToken") or params.get("password")
# Databricks OAuth2:
token     = conn_info.get("resolvedOAuth2Credential", {}).get("accessToken")
```

---

## 33. python-agents/ class name defaults to `MyLLM` but can be overridden

DSS looks for `MyLLM` by default in both `llm.py` and `agent.py`. If you use a different class name, declare it in the JSON:

```json
// agent.json
{"className": "DatabricksAgent"}
```

Without this, DSS silently fails to find the class.

---

## 34. Inline OAuth token is a dict placeholder — detect before using

When a CREDENTIAL_REQUEST preset is shown as "Manually defined" (user hasn't gone through the OAuth flow), the token value is a dict, not a string:

```python
token = config.get("oauth_credentials", {}).get("access_token")
if isinstance(token, dict):
    raise ValueError(
        "Please authenticate via Profile → Credentials before using this connector."
    )
```

Calling `requests.get(..., headers={"Authorization": f"Bearer {token}"})` with a dict silently produces an invalid header.

---

## 35. Inference profile prefix for Bedrock cross-region routing

```python
_PROFILE_PREFIX = {"us": "us", "eu": "eu", "apac": "ap"}

if inference_profile:
    prefix = _PROFILE_PREFIX.get(inference_profile.lower(), inference_profile.lower())
    model_id = f"{prefix}.{base_model_id}"  # e.g. "us.amazon.nova-pro-v1:0"
```

The prefix is `ap` for APAC (not `apac`). Using the wrong prefix causes an unrecognized model ID error.
