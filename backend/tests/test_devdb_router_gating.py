from __future__ import annotations

import importlib

from app.config import get_settings


def _reload_main():
    import app.main as main_module

    return importlib.reload(main_module)


def test_devdb_router_not_registered_when_disabled(monkeypatch):
    monkeypatch.delenv("DEV_DB_TOOLS_ENABLED", raising=False)
    get_settings.cache_clear()

    main_module = _reload_main()
    route_paths = {route.path for route in main_module.app.routes}
    assert "/api/dev/db/tables" not in route_paths
    assert "/api/dev/db/schema-context" not in route_paths
    get_settings.cache_clear()


def test_devdb_router_registered_when_enabled(monkeypatch):
    monkeypatch.setenv("DEV_DB_TOOLS_ENABLED", "true")
    get_settings.cache_clear()

    main_module = _reload_main()
    route_paths = {route.path for route in main_module.app.routes}
    assert "/api/dev/db/tables" in route_paths
    assert "/api/dev/db/schema-context" in route_paths
    get_settings.cache_clear()
