# `backend/wsgi.py`

```py
from flask import Flask
from .fetch_api import fetch_api
from dotenv import load_dotenv
import os

load_dotenv()

from webaiku.extension import WEBAIKU

app = Flask(__name__)


def _webapp_dist_path() -> str:
    webapp_folder = os.getenv("DKU_WEBAPP_FOLDER")
    if not webapp_folder:
        raise ValueError(
            "DKU_WEBAPP_FOLDER env var is required (example: 'my_react_webapp')"
        )
    return f"webapps/{webapp_folder}/dist"


WEBAIKU(app, _webapp_dist_path(), int(os.getenv("VITE_API_PORT", "5000")))
WEBAIKU.extend(app, [fetch_api])

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("VITE_API_PORT", "5000")), debug=True)
```
