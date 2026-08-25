from __future__ import annotations

from starlette.routing import Mount

from . import app as base
from .pipeline_api import create_pipeline_router


app = base.app


def _install_pipeline_router() -> None:
    if getattr(app.state, "sonicforge_pipeline_router_installed", False):
        return
    app.include_router(create_pipeline_router(base))
    # base.app mounts the SPA at '/'. Starlette evaluates routes in order, so a
    # catch-all root Mount added before this router would swallow /addon/v1/*.
    # Keep the SPA mount last while preserving every existing route object.
    root_mounts = [
        route
        for route in app.router.routes
        if isinstance(route, Mount) and route.name == "frontend"
    ]
    if root_mounts:
        for route in root_mounts:
            app.router.routes.remove(route)
        app.router.routes.extend(root_mounts)
    app.state.sonicforge_pipeline_router_installed = True


_install_pipeline_router()
