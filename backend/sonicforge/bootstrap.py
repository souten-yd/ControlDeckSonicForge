from __future__ import annotations

from starlette.routing import Mount

from . import app as base
from .delivery_api import create_delivery_router
from .job_extensions import install_job_extensions
from .pipeline_api import create_pipeline_router


app = base.app


def _move_frontend_last() -> None:
    # base.app mounts the SPA at '/'. Starlette evaluates routes in order, so a
    # catch-all root Mount added before extension routers would swallow them.
    root_mounts = [
        route
        for route in app.router.routes
        if isinstance(route, Mount) and route.name == "frontend"
    ]
    if root_mounts:
        for route in root_mounts:
            app.router.routes.remove(route)
        app.router.routes.extend(root_mounts)


def _install_extension_routers() -> None:
    if getattr(app.state, "sonicforge_extension_routers_installed", False):
        return
    install_job_extensions(base.jobs)
    app.include_router(create_pipeline_router(base))
    app.include_router(create_delivery_router(base))
    _move_frontend_last()
    app.state.sonicforge_extension_routers_installed = True


_install_extension_routers()
