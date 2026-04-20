---
name: vuejs-webapp-init
description: Initialize a Vue 3 + Vite webapp inside a Dataiku Code Studio in a way that works behind Code Studio browser paths and can be deployed to a DSS Standard Webapp (build dist/ with a relative base). Use when Codex needs to scaffold or configure a Vue/Vite project in this workspace, including vite.config.ts base path handling, .env/env.d.ts setup, Flask backend scaffold, and external-libraries.json pythonPath updates.
---

# VueJS Webapp Init (Dataiku Code Studio)

## Inputs

- `project_name`: folder name under `project-lib-versioned/webapps/` (example: `marketpaceapp`).
- `client_port` (default: `4200`): Vite dev server port.
- `api_port` (default: `5000`): Flask backend port.
- `webapp_folder` (default: `project_name`): DSS webapp folder name (used for serving `dist/`).

## Workflow


### 0) Install Code Studio Volar extension

code-server --install-extension Vue.volar

### 1) Ensure npm cache is usable

Update the npm cache (needed for the current setup in code studios)

```bash
mkdir -p /home/dataiku/workspace/code_studio-resources/npm-cache
npm config set cache /home/dataiku/workspace/code_studio-resources/npm-cache
```

Note : If you run into any issues changing the cache folder, tell the user how they can do it.

### 2) Scaffold the Vue app

Create the project under the synced folder:

```bash
mkdir -p project-lib-versioned/webapps
cd project-lib-versioned/webapps
npm create vue@latest <project_name>
npm create vue@latest <project_name> -y -- --typescript --eslint --vitest --playwright --router
cd <project_name>
npm install
npm install dotenv
```


### 3) Add `.env`

Create `<project_root>/.env` using `references/env.md`.

### 4) Add `env.d.ts`

Create `<project_root>/env-d-ts.md` using `references/env-d-ts.md`.

### 5) Update `vite.config.ts` for Code Studio browser paths

Ensure Vite uses the Code Studio browser path for the chosen port.

Update `<project_root>/vite.config.ts` using `references/vite-config-ts.md`.

### 6) Update `package.json` build command for DSS

For deployment in a **DSS Standard Webapp**, build with a relative base.

Update the script:

- Set `build-only` to `vite build --base=./`

### 7) Scaffold the Flask backend

From `<project_root>`:

```bash
mkdir -p backend
touch backend/__init__.py
```

Create `backend/fetch_api.py` using `references/backend-fetch-api-py.md`.

Create `backend/wsgi.py` using `references/backend-wsgi-py.md`.


### 8) Wire the DSS Standard Webapp wrapper (root `webapps/`)

0) Confirm DSS Standard Webapp folder exists

- In the Dataiku project, confirm there is a **Standard Webapp** (a folder under the workspace root `webapps/<WEBAPP_ID>/` containing `backend.py`, `app.js`, `body.html`, `style.css`).
Note : The WEBAPP_ID is usually of the form : <project_name>_<Random_ID>

- If it does not exist yet, try creating it using the provided skill script:

```bash
source /opt/dataiku/pyenv/bin/activate
/opt/dataiku/pyenv/bin/python scripts/create_dku_webapp.py <project_name>
```

If the script fails, instruct the user to create the Standard Webapp manually in DSS and sync files with Code Studios.

1) Ensure DSS can import `webapps` python modules

Edit `project-lib-versioned/external-libraries.json` so `pythonPath` includes `webapps`.

When deploying, DSS serves the **Standard Webapp** from the workspace root `webapps/<WEBAPP_ID>/` folder (the one containing `backend.py`, `app.js`, `body.html`, `style.css`).

To embed your Vite build output into that Standard Webapp, update the wrapper files to:
Note : Do not delete and recreate each file, instead truncate and repopulate to edit.

2) **Python backend tab** (`webapps/<WEBAPP_ID>/backend.py`): point to your Vue app folder (the one under `project-lib-versioned/webapps/<project_name>/`) and import the blueprint from that same folder name.

Replace `{__YOUR_WEBAPPLICATION_FOLDER__}` with the **Vue project folder name** (for this skill, it is `<project_name>`):

Use the template at `references/dss-standard-webapp-wrapper/backend.py`.

3) **JavaScript tab** (`webapps/<WEBAPP_ID>/app.js`): load the `WEBAIKU`-served frontend in a full-page iframe:

Use the template at `references/dss-standard-webapp-wrapper/app.js`.

4) Clear Standard Webapp HTML/CSS tabs since the UI is served by the Vite build:

- `webapps/<WEBAPP_ID>/body.html`: empty
- `webapps/<WEBAPP_ID>/style.css`: empty

Reference template folder (copy/paste targets):

- `references/dss-standard-webapp-wrapper/backend.py`
- `references/dss-standard-webapp-wrapper/app.js`
- `references/dss-standard-webapp-wrapper/body.html`
- `references/dss-standard-webapp-wrapper/style.css`

# Run Dev Frontend and Backend (in Code Studio)

Note : If you run into any issue running the frontend or backend for the user, please instruct the user to start and new terminal and give them the commands listed bellow.

From `<project_root>`:

Frontend dev server
```bash
npm run dev
```

Backend (select a Dataiku code env first):

```bash
source /opt/dataiku/python-code-envs/sec_code_studio/bin/activate
python -m backend.wsgi

```

# Build and Deploy (DSS Standard Webapp)

## 1) Build the project for DSS

Note : Confirm that Wire the DSS Standard Webapp step was configured properly

From `<project_root>`:

```bash
npm run build-only
```

This writes the production bundle to `dist/` using a **relative** base (`--base=./`), which is required when serving under DSS webapp URLs.

## 2) Deploy/run in DSS

Ask the user to :
- Sync code studio changes with DSS
- Open the Standard Webapp in DSS and start the backend.
- No need to copy the /dist anywhere, the dataiku WEBAIKU will take care of serving it properly.
