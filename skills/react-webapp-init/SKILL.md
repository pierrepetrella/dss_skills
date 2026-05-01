---
name: react-webapp-init
description: Initialize a React + Vite webapp inside a Dataiku Code Studio so it works behind Code Studio browser paths and can be deployed to a DSS Standard Webapp (build dist/ with a relative base). Use when scaffolding or configuring a React/Vite project in this workspace, including vite.config.ts base path handling, .env/env.d.ts setup, Flask backend scaffold, and DSS wrapper wiring.
---

# React Webapp Init (Dataiku Code Studio)

## Inputs

- `project_name`: folder name under `project-lib-versioned/webapps/` (example: `my_react_webapp`).
- `client_port` (default: `4200`): Vite dev server port.
- `api_port` (default: `5000`): Flask backend port.
- `webapp_folder` (default: `project_name`): DSS webapp wrapper folder name (used for serving `dist/`).

## Workflow

### 1) (Optional) Fix npm cache permissions

If npm cache permissions are broken in the Code Studio:

```bash
mkdir -p ~/.npm-cache
npm config set cache ~/.npm-cache
npm config get cache
```

### 2) Scaffold the React app

Create the project under the synced folder:

```bash
mkdir -p project-lib-versioned/webapps
cd project-lib-versioned/webapps
npm create vite@latest <project_name> -- --template react-ts
cd <project_name>
npm install
npm install dotenv --save-dev
```

### 3) Add `.env`

Create `<project_root>/.env` using `references/env.md`.

### 4) Add `env.d.ts`

Create `<project_root>/env.d.ts` using `references/env-d-ts.md`.

### 5) Update `vite.config.ts` for Code Studio browser paths

Ensure Vite uses the Code Studio browser path for the chosen port.

Update `<project_root>/vite.config.ts` using `references/vite-config-ts.md`.

### 6) Update `package.json` build command for DSS

For deployment in a **DSS Standard Webapp**, build with a relative base.

Update script:

- Set `build` to `tsc -b && vite build --base=./`

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

- In the Dataiku project, confirm there is a **Standard Webapp** (a folder under workspace root `webapps/<WEBAPP_ID>/` containing `backend.py`, `app.js`, `body.html`, `style.css`).
- `WEBAPP_ID` is usually `<project_name>_<Random_ID>`.

If it does not exist yet, try creating it using the provided skill script:

```bash
source /opt/dataiku/pyenv/bin/activate
/opt/dataiku/pyenv/bin/python scripts/create_dku_webapp.py <project_name>
```

If the script fails, instruct the user to create the Standard Webapp manually in DSS and sync files with Code Studio.

1) Ensure DSS can import `webapps` python modules

Edit `project-lib-versioned/external-libraries.json` so `pythonPath` includes `webapps`.

2) Update **Python backend tab** (`webapps/<WEBAPP_ID>/backend.py`)

Replace `{__YOUR_WEBAPPLICATION_FOLDER__}` with `<project_name>` and use template:

- `references/dss-standard-webapp-wrapper/backend.py`

3) Update **JavaScript tab** (`webapps/<WEBAPP_ID>/app.js`)

Use template:

- `references/dss-standard-webapp-wrapper/app.js`

4) Clear HTML/CSS tabs

- `webapps/<WEBAPP_ID>/body.html`: empty
- `webapps/<WEBAPP_ID>/style.css`: empty

Reference templates:

- `references/dss-standard-webapp-wrapper/backend.py`
- `references/dss-standard-webapp-wrapper/app.js`
- `references/dss-standard-webapp-wrapper/body.html`
- `references/dss-standard-webapp-wrapper/style.css`

# Run Dev Frontend and Backend (in Code Studio)

From `<project_root>`:

Frontend dev server:
```bash
npm run dev
```

Backend (select a Dataiku code env first):

```bash
source /opt/dataiku/python-code-envs/<YOUR_CODE_ENV>/bin/activate
python -m backend.wsgi
```

# Build and Deploy (DSS Standard Webapp)

## 1) Build the project for DSS

From `<project_root>`:

```bash
npm run build
```

This writes production bundle to `dist/` using a relative base (`--base=./`).

## 2) Deploy/run in DSS

Ask user to:
- Sync Code Studio changes with DSS.
- Open Standard Webapp in DSS and start backend.
- No need to copy `dist/`; WEBAIKU serves it from project library path.
