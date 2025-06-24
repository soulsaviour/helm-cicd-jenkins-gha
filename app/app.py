"""inventory-api: a small read-only inventory service.

Health endpoints are split so Kubernetes can tell "restart me" (/healthz)
apart from "don't send me traffic yet" (/readyz).
"""

import os

from flask import Flask, abort, jsonify

ITEMS = {
    "sku-1001": {"sku": "sku-1001", "name": "USB-C cable", "stock": 120},
    "sku-1002": {"sku": "sku-1002", "name": "27-inch monitor", "stock": 8},
    "sku-1003": {"sku": "sku-1003", "name": "Mechanical keyboard", "stock": 0},
}


def create_app() -> Flask:
    app = Flask(__name__)
    version = os.environ.get("APP_VERSION", "dev")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        return {"status": "ready"}

    @app.get("/")
    def index():
        return {"service": "inventory-api", "version": version}

    @app.get("/items")
    def list_items():
        return jsonify(list(ITEMS.values()))

    @app.get("/items/<sku>")
    def get_item(sku):
        if sku not in ITEMS:
            abort(404)
        return ITEMS[sku]

    return app


app = create_app()
