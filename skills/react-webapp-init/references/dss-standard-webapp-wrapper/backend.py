from webaiku.extension import WEBAIKU
from {__YOUR_WEBAPPLICATION_FOLDER__}.backend.fetch_api import fetch_api

WEBAIKU(app, "webapps/{__YOUR_WEBAPPLICATION_FOLDER__}/dist")
WEBAIKU.extend(app, [fetch_api])
