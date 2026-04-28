# Dataiku Plugin — Param Types Catalogue

Every param in `plugin.json`, `llm.json`, `connector.json`, `recipe.json`, `runnable.json`, `tool.json`, `guardrail.json`, and `webapp.json` uses one of these types.

---

## Common Attributes (all types)

| Attribute | Type | Notes |
|-----------|------|-------|
| `name` | string | Python key in the `config` dict |
| `label` | string | UI label |
| `description` | string | Help text shown below the field |
| `type` | string | See below |
| `mandatory` | boolean | **Always set explicitly** — there is no default |
| `defaultValue` | any | Default rendered when field is empty |
| `visibilityCondition` | JavaScript string | Controls whether the field is shown. Runs in the browser, uses `model.<paramName>`. |

---

## Scalar Types

### STRING
```json
{
  "name": "apiEndpoint",
  "label": "API Endpoint",
  "type": "STRING",
  "defaultValue": "https://api.example.com",
  "mandatory": true
}
```
Python: `config["apiEndpoint"]` → `str`

---

### INT
```json
{
  "name": "maxRetries",
  "label": "Max Retries",
  "type": "INT",
  "minI": 1,
  "maxI": 10,
  "defaultValue": 3,
  "mandatory": false
}
```
Sub-keys: `minI`, `maxI`  
Python: `config.get("maxRetries", 3)` → `int`

---

### DOUBLE
```json
{
  "name": "temperature",
  "label": "Temperature",
  "type": "DOUBLE",
  "minD": 0.0,
  "maxD": 2.0,
  "defaultValue": 0.7,
  "mandatory": false
}
```
Sub-keys: `minD`, `maxD`  
Python: `float(config.get("temperature", 0.7))`

---

### BOOLEAN
```json
{
  "name": "enableStreaming",
  "label": "Enable Streaming",
  "type": "BOOLEAN",
  "defaultValue": false,
  "mandatory": false
}
```
Python: `bool(config.get("enableStreaming", False))`  
Use `visibilityCondition` on sub-fields to implement progressive disclosure.

---

### TEXTAREA
```json
{
  "name": "systemPrompt",
  "label": "System Prompt",
  "type": "TEXTAREA",
  "mandatory": false
}
```
Multi-line text box. Python: `config.get("systemPrompt", "")` → `str`

---

### PASSWORD
```json
{
  "name": "apiKey",
  "label": "API Key",
  "type": "PASSWORD",
  "mandatory": true
}
```
Masked input, stored encrypted. Python: `config["apiKey"]` → `str`

---

## Selection Types

### SELECT
```json
{
  "name": "modelId",
  "label": "Model",
  "type": "SELECT",
  "mandatory": true,
  "defaultValue": "gpt-4o",
  "selectChoices": [
    {"value": "gpt-4o",       "label": "GPT-4o"},
    {"value": "gpt-4o-mini",  "label": "GPT-4o Mini"}
  ]
}
```
Python: `config["modelId"]` → `str`

**Visual separator trick**: use a sentinel value with a decorative label:
```json
{"value": "__openai__", "label": "──── OpenAI ─────────────────────────────────────"}
```
Guard in Python: `if model_id in {"__openai__", ...}: raise ValueError(...)`

**Dynamic choices** (choices come from Python):
```json
{
  "name": "projectKey",
  "type": "SELECT",
  "getChoicesFromPython": true,
  "triggerParameters": ["region"]
}
```
When `region` changes, DSS calls the `paramsPythonSetup` script to regenerate choices.

---

### MULTISELECT
```json
{
  "name": "enabledFeatures",
  "label": "Features",
  "type": "MULTISELECT",
  "mandatory": false,
  "selectChoices": [
    {"value": "search",  "label": "Web search"},
    {"value": "code",    "label": "Code execution"}
  ]
}
```
Python: `config.get("enabledFeatures", [])` → `list[str]`  
In `visibilityCondition`: `model.enabledFeatures && model.enabledFeatures.length > 0`

---

### STRINGS
```json
{
  "name": "stopSequences",
  "label": "Stop Sequences",
  "type": "STRINGS",
  "mandatory": false
}
```
UI shows a tag-style list input. Python: `config.get("stopSequences", [])` → `list[str]`

---

## Structured Types

### MAP
```json
{
  "name": "defaultHeaders",
  "label": "Default Headers",
  "type": "MAP",
  "mandatory": false
}
```
Key-value pairs. Python: `config.get("defaultHeaders", {})` → `dict[str, str]`

---

### OBJECT_LIST
```json
{
  "name": "tools",
  "label": "Tools",
  "type": "OBJECT_LIST",
  "subParams": [
    {"name": "toolName",        "type": "STRING",  "label": "Name",        "mandatory": true},
    {"name": "toolEndpoint",    "type": "STRING",  "label": "Endpoint",    "mandatory": true},
    {"name": "toolEnabled",     "type": "BOOLEAN", "label": "Enabled",     "defaultValue": true, "mandatory": false}
  ]
}
```
UI: user can add/remove rows. Python:
```python
tools = config.get("tools", [])
for tool in tools:
    name = tool["toolName"]
    endpoint = tool["toolEndpoint"]
```

Add `"triggerParameters": ["parentParam"]` to refresh choices within subParams when a parent param changes.

---

## Connection / Credential Types

### CONNECTION
```json
{
  "name": "s3Connection",
  "label": "AWS S3 Connection",
  "type": "CONNECTION",
  "mandatory": false,
  "allowedConnectionTypes": ["S3"]
}
```
**Returns a single string** (connection name). `CONNECTIONS` (plural) returns a list — use `CONNECTION` when you need exactly one.

Python:
```python
connection_name = config.get("s3Connection", "")
if connection_name:
    cred = dataiku.api_client().get_connection(connection_name).get_info().get_aws_credential()
    # cred = {"accessKey": "...", "secretKey": "...", "sessionToken": "..."}
```

`allowedConnectionTypes` filters the picker: `"S3"`, `"Snowflake"`, `"PostgreSQL"`, etc.

Python connections API reference: https://developer.dataiku.com/latest/api-reference/python/connections.html

---

### PRESET
```json
{
  "name": "oauthPreset",
  "label": "OAuth Credentials",
  "type": "PRESET",
  "parameterSetId": "oauth-credentials",
  "mandatory": true
}
```
Lets the user pick a shared credential preset (parameter-set). Python: `config["oauthPreset"]` → `dict` with the preset's fields.

---

### CREDENTIAL_REQUEST
Used inside `parameter-sets/` to define credential forms. Less common in component params.

---

## Dataset / Folder Types

### DATASET
```json
{
  "name": "loggingDataset",
  "label": "Logging Dataset",
  "type": "DATASET",
  "acceptsDataset": true,
  "canCreateDataset": true,
  "markCreatedAsBuilt": true,
  "mandatory": false
}
```
Used in webapp params. Python: `config["loggingDataset"]` → dataset name string.

---

### COLUMN
```json
{
  "name": "textColumn",
  "label": "Text Column",
  "type": "COLUMN",
  "columnRole": "input_dataset",
  "allowedColumnTypes": ["string"],
  "mandatory": true
}
```
`columnRole` must match an `inputRoles[].name` in `recipe.json`. Case-sensitive.  
`allowedColumnTypes`: `"string"`, `"int"`, `"double"`, `"boolean"`, `"date"`, `"object"`.

---

### COLUMNS (plural)
Same as `COLUMN` but allows selecting multiple columns. Python: `config["selectedColumns"]` → `list[str]`.

---

## Special / UI Types

### SEPARATOR
```json
{
  "type": "SEPARATOR",
  "label": "Bedrock Guardrail Settings"
}
```
Visual divider only — no value. **Never read in Python**; the param has no `name` field and stores nothing.

---

### LLM
```json
{
  "name": "llmId",
  "label": "LLM Connection",
  "type": "LLM",
  "mandatory": true,
  "llmUsagePurpose": "GENERIC_COMPLETION"
}
```
Lets user pick an LLM connection defined in the project. Python: `config["llmId"]` → LLM identifier string passed to Dataiku's LLM API.

`llmUsagePurpose` values: `"GENERIC_COMPLETION"`, `"EMBEDDINGS"`.

---

### CLUSTER
```json
{
  "name": "clusterId",
  "label": "Kubernetes Cluster",
  "type": "CLUSTER",
  "mandatory": true,
  "targetParamsKey": "clusterSettings"
}
```
Picks a DSS Kubernetes cluster. Python: `config["clusterId"]` → cluster ID string.

---

---

## DOUBLES

Array of double values — shown as a comma-separated tag input.

```json
{"name": "knots", "label": "Knots", "type": "DOUBLES", "mandatory": true}
```

Python: `config["knots"]` → `list[float]`

---

## DATE

Date picker (calendar UI).

```json
{"name": "from_date", "label": "From", "type": "DATE", "mandatory": false}
```

Python: `config.get("from_date")` → ISO date string or `None`

---

## KEY_VALUE_LIST

Ordered list of key-value pairs — like MAP but editable as a list with add/remove rows.

```json
{
  "name": "queryParams",
  "label": "Query Parameters",
  "description": "Will add ?key1=val1&key2=val2 to the URL",
  "type": "KEY_VALUE_LIST",
  "mandatory": false
}
```

Python: `config.get("queryParams", [])` → `list[{"key": str, "value": str}]`

---

## MANAGED_FOLDER / FOLDER

Picks a Dataiku managed folder. `MANAGED_FOLDER` is used in `macroRoles`; `FOLDER` is used in `params`.

In `macroRoles` (runnable.json) — makes the runnable context-aware:
```json
{
  "macroRoles": [
    {"type": "MANAGED_FOLDER", "targetParamsKey": "model_folder_id"}
  ],
  "params": [
    {"name": "model_folder_id", "label": "Model Folder", "type": "FOLDER", "mandatory": true}
  ]
}
```

In agent tool `tool.json`:
```json
{
  "name": "input_folder",
  "label": "Videos Folder",
  "type": "FOLDER",
  "agentDependency": true
}
```

`"agentDependency": true` tells DSS the agent needs access to this folder at runtime.

Python: `config["model_folder_id"]` → folder ID string. Then: `dataiku.Folder(folder_id)`.

---

## SAVED_MODEL

Picks a DSS saved model.

In `macroRoles`:
```json
{"macroRoles": [{"type": "SAVED_MODEL", "targetParamsKey": "saved_model_id"}]}
```

In `params`:
```json
{"name": "saved_model_id", "label": "Model", "type": "SAVED_MODEL", "mandatory": true}
```

Python: `config["saved_model_id"]` → model ID string.

---

## DATASET_COLUMN / DATASET_COLUMNS

Picks a column from a specific dataset (not a recipe input role) — used in **webapp params** where there is no recipe context.

```json
{
  "name": "dataset",
  "label": "Dataset",
  "type": "DATASET",
  "acceptsDataset": true,
  "mandatory": true
},
{
  "name": "valueColumn",
  "label": "Value column (Y)",
  "type": "DATASET_COLUMN",
  "datasetParamName": "dataset",
  "mandatory": true
},
{
  "name": "categoryColumns",
  "label": "Category columns",
  "type": "DATASET_COLUMNS",
  "datasetParamName": "dataset",
  "mandatory": false
}
```

`datasetParamName` links to another param of type `DATASET`. This is different from recipe `COLUMN` params which use `columnRole`.

Python: `config["valueColumn"]` → `str`; `config["categoryColumns"]` → `list[str]`

---

## PROJECT_MACROS

Used in `macroRoles` (runnable.json) to allow the runnable to be triggered from within any project.

```json
{"macroRoles": [{"type": "PROJECT_MACROS"}]}
```

No `params` entry needed — the macro inherits the current project context.

---

## API_SERVICE

Picks a DSS API service endpoint.

```json
{
  "name": "service_id_existing",
  "label": "API Service ID",
  "type": "API_SERVICE",
  "mandatory": true,
  "visibilityCondition": "!model.create_new_service"
}
```

Python: `config["service_id_existing"]` → service ID string.

---

## CREDENTIAL_REQUEST (expanded)

See **[references/oauth-credentials.md](references/oauth-credentials.md)** for the full guide. Quick reference:

```json
{
  "name": "oauth_token",
  "type": "CREDENTIAL_REQUEST",
  "credentialRequestSettings": {
    "type": "OAUTH2",           // or "SINGLE_FIELD" or "BASIC"
    "oauth2Flow": "authorization_code",
    "authorizationEndpoint": "https://...",
    "tokenEndpoint": "https://...",
    "scope": "read write"
  }
}
```

- `"type": "OAUTH2"` — OAuth2 browser flow; returns `{"access_token": "..."}`
- `"type": "SINGLE_FIELD"` — Personal access token; returns the token string directly
- `"type": "BASIC"` — Username + password form; returns `{"username": "...", "password": "..."}`

---

## visibilityCondition Examples

All expressions are **JavaScript** evaluated in the browser. `model` is the current form state.

```js
// Simple equality
"model.authType == 'oauth'"

// Boolean toggle
"model.useGuardrail"

// Array includes (use indexOf, not includes)
"['s3', 'gcs'].indexOf(model.storageType) >= 0"

// Array length check (MULTISELECT)
"model.selectedFeatures && model.selectedFeatures.length > 0"

// Combined
"model.useGuardrail && model.guardrailMode == 'advanced'"

// Always show
true
```

---

## visibilityCondition advanced patterns

```js
// Combined AND condition
"model.fit_with_mle == 'No' && model.distribution == 'Beta'"

// Check if value is from a set
"['OFFSETS', 'OFFSETS/EXPOSURES'].indexOf(model.offset_mode) >= 0"

// Negation
"!model.create_new_service"

// Always hidden (useful for placeholder params)
false
```

---

## Dynamic Choices (getChoicesFromPython)

When `"getChoicesFromPython": true`, add a `paramsPythonSetup` key at the JSON root pointing to a Python file:

```json
{
  "paramsPythonSetup": "get_choices.py",
  "params": [
    {
      "name": "projectKey",
      "type": "SELECT",
      "getChoicesFromPython": true,
      "triggerParameters": ["region"],
      "disableAutoReload": true
    }
  ]
}
```

`get_choices.py` is referenced from the JSON root via `"paramsPythonSetup": "get_choices.py"`. It exports a single `do()` function:
```python
# resource/get_choices.py   (file is in resource/ or at plugin root)
def do(payload, config, plugin_config, inputs):
    parameter_name = payload.get("parameterName")

    if parameter_name == "projectKey":
        client = dataiku.api_client()
        choices = [
            {"value": p["projectKey"], "label": p["name"]}
            for p in client.list_projects()
        ]
        return {"choices": choices}

    return {"choices": []}
```

**Signature is always `do(payload, config, plugin_config, inputs)`** — not a function named after the param.  
`payload["parameterName"]` identifies which param's choices to return.  
Return `{"choices": [{"value": ..., "label": ...}]}`.

`disableAutoReload: true` prevents refreshing choices on every keystroke (performance).
