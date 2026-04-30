import sys
import types
from flask_appbuilder.api import BaseApi

SECRET_KEY = "supersecret_poc_key_change_in_prod"
PREVENT_UNSAFE_DB_CONNECTIONS = False
WTF_CSRF_ENABLED = False

# Vendor dependencies must be on sys.path before Superset imports anything
# that might trigger a failed pydantic_core lookup and poison the import cache.
sys.path.insert(0, "/app/extensions/vendor")

# ---------------------------------------------------------------------------
# superset_core shim — stub module expected by the bi-ai extension backends.
# ---------------------------------------------------------------------------
_pending_extension_apis: list = []


def _add_extension_api(cls):
    _pending_extension_apis.append(cls)
    return cls


_sc = types.ModuleType("superset_core")
_sc_api = types.ModuleType("superset_core.api")
_sc_api_rest = types.ModuleType("superset_core.api.rest_api")
_sc_api_rest.RestApi = type("RestApi", (BaseApi,), {"allow_browser_login": True})
_sc_api_rest.add_extension_api = _add_extension_api
sys.modules.setdefault("superset_core", _sc)
sys.modules["superset_core.api"] = _sc_api
sys.modules["superset_core.api.rest_api"] = _sc_api_rest
_sc.api = _sc_api
_sc_api.rest_api = _sc_api_rest

# Injected into every Superset HTML page to bootstrap the extension sidebar.
_EXTENSION_LOADER = """
<div id="bi-ai-root" style="position:fixed;top:0;right:0;z-index:1000"></div>
<script>
(function(){
  var root=document.getElementById('bi-ai-root');
  var s=document.createElement('script');
  s.src='/api/v1/extensions/bi-ai.text2sql/bi-ai-text2sql.standalone.js';
  s.onload=function(){
    var e=window.__biAiExtensions&&window.__biAiExtensions['bi-ai.text2sql'];
    if(e&&e.activate)e.activate(root);
  };
  document.head.appendChild(s);
})();
</script>
"""


def FLASK_APP_MUTATOR(app):
    sys.path.insert(0, "/app/extensions/chartgen/src")
    sys.path.insert(0, "/app/extensions/text2sql/src")

    import bi_ai.text2sql.entrypoint  # noqa: F401 — registers Text2SqlAPI
    import bi_ai.chartgen.entrypoint  # noqa: F401 — registers ChartGenAPI

    from superset.extensions import appbuilder
    for api_cls in _pending_extension_apis:
        appbuilder.add_api(api_cls)

    from flask import send_from_directory

    @app.route("/api/v1/extensions/bi-ai.text2sql/<path:filename>")
    def serve_extension_file(filename):
        return send_from_directory("/app/extensions/text2sql/dist", filename)

    @app.after_request
    def inject_extension_loader(response):
        ct = response.content_type or ""
        if "text/html" in ct:
            data = response.get_data(as_text=True)
            if "</body>" in data:
                data = data.replace("</body>", _EXTENSION_LOADER + "</body>", 1)
                response.set_data(data.encode("utf-8"))
        return response
