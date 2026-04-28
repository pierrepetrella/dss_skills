# Dataiku Plugin — OAuth & Credential Management

Complete guide to authentication patterns across all Dataiku plugin credential types.

---

## Architecture: Where Credentials Live

| Location | Purpose | Who Configures |
|----------|---------|---------------|
| `parameter-sets/<id>/parameter-set.json` | Reusable credential presets users can fill in once | End users (Profile → Credentials) or admins |
| `plugin.json` params | Connection-level admin settings | DSS admin only |
| `llm.json` / `connector.json` / `tool.json` params | Per-instance config | Whoever creates the LLM/dataset/tool |
| `PRESET` param in any component | Reference to a parameter-set | User picks from existing presets |

---

## parameter-set.json Structure

```json
{
  "meta": {"label": "My Credentials"},
  "defaultDefinableInline": true,
  "defaultDefinableAtProjectLevel": true,
  "params": [
    {"name": "api_key", "label": "API Key", "type": "PASSWORD", "mandatory": true}
  ]
}
```

**Scope control:**
- `"defaultDefinableInline": false` — credential can only be set at project level, not inline per-dataset. Use for OAuth presets that require a browser redirect.
- `"defaultDefinableAtProjectLevel": false` — credential must be set once at plugin level by an admin. Use for shared service accounts.

**pluginParams** — plugin-level defaults applied to all instances:
```json
{
  "pluginParams": [
    {"name": "personal_access_token", "type": "CREDENTIAL_REQUEST", "credentialRequestSettings": {"type": "SINGLE_FIELD"}}
  ]
}
```

---

## CREDENTIAL_REQUEST param type

Used inside `parameter-set.json` to trigger a browser-assisted credential acquisition. Three subtypes:

### OAuth2 Authorization Code Flow (per-user)

```json
{
  "name": "oauth_token",
  "type": "CREDENTIAL_REQUEST",
  "label": "Sign in with Google",
  "credentialRequestSettings": {
    "type": "OAUTH2",
    "oauth2Flow": "authorization_code",
    "authorizationEndpoint": "https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&prompt=consent",
    "tokenEndpoint": "https://oauth2.googleapis.com/token",
    "scope": "https://www.googleapis.com/auth/drive"
  }
}
```

Real examples by service:
| Service | scope |
|---------|-------|
| Google Drive | `https://www.googleapis.com/auth/drive` |
| Google Sheets | `https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive` |
| Google Calendar | `https://www.googleapis.com/auth/calendar.events` |
| Google Analytics | `https://www.googleapis.com/auth/analytics.readonly` |
| OneDrive | `offline_access files.read.all files.readwrite` |
| SharePoint | `User.Read AllSites.Read AllSites.Write List.Read List.Write` |
| Airtable | `data.records:read schema.bases:read` |
| Salesforce | `api refresh_token full` |

For **Azure AD OAuth**, add `"oauth2Provider": "AZURE"`:
```json
{
  "credentialRequestSettings": {
    "type": "OAUTH2",
    "oauth2Flow": "authorization_code",
    "oauth2Provider": "AZURE",
    "authorizationEndpoint": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/authorize",
    "tokenEndpoint": "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
    "scope": "openid Dataset.ReadWrite.All",
    "resources": ["https://analysis.windows.net/powerbi/api"]
  }
}
```

### Single-Field Personal Access Token

```json
{
  "name": "personal_access_token",
  "type": "CREDENTIAL_REQUEST",
  "label": "Personal Access Token",
  "credentialRequestSettings": {
    "type": "SINGLE_FIELD"
  }
}
```

Used by: Airtable (user-account), GitHub (personal-access-token). The user pastes a token — DSS stores it encrypted and provides it as a string.

### BASIC (Username + Password)

```json
{
  "name": "basic_login",
  "type": "CREDENTIAL_REQUEST",
  "label": "Username / Password",
  "credentialRequestSettings": {
    "type": "BASIC"
  }
}
```

Used by: PI System (basic-auth), ServiceNow (basic-per-user), SAP OData (basic-auth). DSS shows a username+password form and returns `{"username": "...", "password": "..."}`.

---

## PRESET param — referencing a parameter-set

In any component JSON (connector.json, recipe.json, tool.json, etc.):
```json
{
  "name": "oauth_credentials",
  "label": "Google Credentials",
  "type": "PRESET",
  "parameterSetId": "oauth-credentials",
  "mandatory": true
}
```

`parameterSetId` must match the directory name under `parameter-sets/`.

**Accessing in Python:**
```python
# config["oauth_credentials"] is a DICT with the preset's fields
oauth = config["oauth_credentials"]
access_token = oauth["access_token"]          # CREDENTIAL_REQUEST OAUTH2
api_key      = oauth["api_key"]               # PASSWORD field
username     = oauth.get("username", "")      # BASIC username
```

**Nested access pattern:**
```python
# WRONG — access_token is NOT at the top level of config
token = config.get("access_token")  # None

# CORRECT — it's nested under the preset param name
token = config["oauth_credentials"]["access_token"]
```

**Multiple auth method pattern:**
```python
auth_type = config.get("auth_type", "oauth")

if auth_type == "oauth":
    preset = config.get("oauth_credentials", {})
    access_token = preset.get("access_token")
    if isinstance(access_token, dict):
        raise ValueError("OAuth settings cannot be used inline — select a preset.")
    credentials = AccessTokenCredentials(access_token, "my-plugin/1.0")

elif auth_type == "service_account":
    preset = config.get("service_account_credentials", {})
    json_key = preset.get("credentials")
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(
        json.loads(json_key), scopes
    )

elif auth_type == "basic":
    preset = config.get("basic_credentials", {})
    username = preset.get("username")
    password = preset.get("password")
```

---

## PASSWORD param — direct API key storage

For simple API keys that don't need a browser flow. Stored encrypted by DSS.

```json
{
  "name": "api_key",
  "label": "API Key",
  "type": "PASSWORD",
  "mandatory": true
}
```

In Python: `config["api_key"]` → `str`

---

## CONNECTION param — reuse DSS connection credentials

Lets the user pick an existing DSS connection and reuse its credentials.

```json
{
  "name": "s3_connection",
  "label": "AWS Connection",
  "type": "CONNECTION",
  "allowedConnectionTypes": ["S3"],
  "mandatory": false
}
```

**Credential extraction by connection type:**

```python
client = dataiku.api_client()
conn_info = client.get_connection(connection_name).get_info()

# AWS (S3, Bedrock, Transcribe, etc.)
aws_cred = conn_info.get_aws_credential()
# Returns {"accessKey": "...", "secretKey": "...", "sessionToken": "..."}

# Generic params inspection
params = conn_info.get("params", {})
conn_type = conn_info.get("type", "")  # e.g. "S3", "Snowflake", "Databricks"

# Databricks (Personal Access Token)
host  = params.get("host")
token = params.get("personalAccessToken") or params.get("password")

# Databricks (OAuth2 App)
token = conn_info.get("resolvedOAuth2Credential", {}).get("accessToken")

# Snowflake
account   = params.get("host")
user      = params.get("user")
password  = params.get("password")
warehouse = params.get("warehouse")
database  = params.get("db")

# Vertex AI (VertexAILLM connection type)
project   = params.get("project")
location  = params.get("location")
```

`allowedConnectionTypes` filters the picker. Common values: `"S3"`, `"Snowflake"`, `"PostgreSQL"`, `"MySQL"`, `"Databricks"`, `"VertexAILLM"`, `"AzureOpenAI"`.

---

## Credential safety patterns

**Prevent logging secrets:**
```python
# Never log config or plugin_config directly — they may contain passwords
logger.info("Connecting to %s", self.base_url)  # OK
# logger.info("Config: %s", config)              # BAD
```

**Validate inline OAuth (crash early):**
```python
preset = config.get("oauth_credentials", {})
access_token = preset.get("access_token")
if isinstance(access_token, dict):
    raise ValueError(
        "The OAuth preset is set to 'Manually defined'. "
        "You must configure it in Profile → Credentials first."
    )
```

When a CREDENTIAL_REQUEST preset is set to "Manually defined" (not filled via the OAuth flow), the `access_token` field is a dict placeholder instead of a string.

---

## Full example: Google Drive connector

**parameter-sets/oauth-credentials/parameter-set.json:**
```json
{
  "meta": {"label": "Google OAuth Credentials"},
  "defaultDefinableInline": false,
  "defaultDefinableAtProjectLevel": false,
  "params": [
    {
      "name": "access_token",
      "type": "CREDENTIAL_REQUEST",
      "label": "Sign in with Google Drive",
      "credentialRequestSettings": {
        "type": "OAUTH2",
        "oauth2Flow": "authorization_code",
        "authorizationEndpoint": "https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&prompt=consent",
        "tokenEndpoint": "https://oauth2.googleapis.com/token",
        "scope": "https://www.googleapis.com/auth/drive"
      }
    }
  ]
}
```

**connector.json:**
```json
{
  "params": [
    {
      "name": "oauth_credentials",
      "type": "PRESET",
      "parameterSetId": "oauth-credentials",
      "label": "Google Credentials",
      "mandatory": true
    }
  ]
}
```

**connector.py:**
```python
class MyConnector(Connector):
    def __init__(self, config, plugin_config):
        Connector.__init__(self, config, plugin_config)
        preset = config["oauth_credentials"]
        access_token = preset["access_token"]
        if isinstance(access_token, dict):
            raise ValueError("Sign in with Google in Profile → Credentials first.")
        credentials = AccessTokenCredentials(access_token, "my-plugin/1.0")
        self.drive = build("drive", "v3", credentials=credentials)
```
