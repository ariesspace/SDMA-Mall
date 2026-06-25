# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
BASE_PATH = os.getenv("SDMA_MALL_BASE_PATH", os.getenv("RNP_MALL_BASE_PATH", "/mall")).rstrip("/") or "/mall"
ADMIN_CODE = os.getenv("SDMA_MALL_ADMIN_CODE", os.getenv("RNP_MALL_ADMIN_TOKEN", "change-me"))
DB_PATH = Path(os.getenv("SDMA_MALL_DB", os.getenv("RNP_MALL_DB", str(ROOT / "data" / "sdma-mall.sqlite3"))))
HOST = os.getenv("SDMA_MALL_HOST", "0.0.0.0")
PORT = int(os.getenv("SDMA_MALL_PORT", os.getenv("RNP_MALL_PORT", "8090")))


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def init_db() -> None:
    timestamp = now_text()
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_no TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL DEFAULT '',
                team TEXT NOT NULL DEFAULT '',
                points INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                price INTEGER NOT NULL,
                original_price INTEGER NOT NULL DEFAULT 0,
                stock INTEGER,
                image_url TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                total_points INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                product_name TEXT NOT NULL,
                unit_price INTEGER NOT NULL,
                quantity INTEGER NOT NULL
            );
            """
        )
        count = db.execute("SELECT COUNT(*) AS count FROM products").fetchone()["count"]
        if count == 0:
            seed_products = [
                ("반중력 오피스 체어 Mk.II", "허리와 마음을 동시에 띄워주는 근무용 의자", 3200, 4500, 8, "https://images.unsplash.com/photo-1580480055273-228ff5388ef8?auto=format&fit=crop&w=800&q=80"),
                ("초공간 노이즈 캔슬링 헤드셋", "회의 소음과 우주 먼지를 함께 차단", 2890, 3500, 12, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80"),
                ("홀로그램 디스플레이 27인치", "보고서도 SF처럼 보이는 업무 화면", 4500, 5200, 5, "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?auto=format&fit=crop&w=800&q=80"),
                ("레트로 기계식 키보드", "타건감으로 행성 궤도를 맞추는 키보드", 1250, 1500, 20, "https://images.unsplash.com/photo-1587829741301-dc798b83add3?auto=format&fit=crop&w=800&q=80"),
            ]
            db.executemany(
                """
                INSERT INTO products
                    (name, description, price, original_price, stock, image_url, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [(*item, timestamp, timestamp) for item in seed_products],
            )


def render_template(name: str) -> bytes:
    html = (ROOT / "templates" / name).read_text(encoding="utf-8")
    html = html.replace("__BASE_PATH__", BASE_PATH)
    return html.encode("utf-8")


def require_admin(handler: BaseHTTPRequestHandler) -> bool:
    return handler.headers.get("X-Admin-Code", "") == ADMIN_CODE


def get_public_state() -> dict:
    with connect() as db:
        products = [
            row_to_dict(row)
            for row in db.execute(
                """
                SELECT * FROM products
                WHERE is_active = 1
                ORDER BY id DESC
                """
            )
        ]
    return {"products": products}


def get_admin_state() -> dict:
    with connect() as db:
        users = [row_to_dict(row) for row in db.execute("SELECT * FROM users ORDER BY team, name, employee_no")]
        products = [row_to_dict(row) for row in db.execute("SELECT * FROM products ORDER BY is_active DESC, id DESC")]
        orders = [row_to_dict(row) for row in db.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 100")]
    return {"users": users, "products": products, "orders": orders, "receipts": build_receipts()}


def login_user(employee_no: str) -> dict:
    value = employee_no.strip()
    if not value:
        return {"ok": False, "message": "사번을 입력해주세요."}
    with connect() as db:
        user = db.execute("SELECT * FROM users WHERE employee_no = ?", (value,)).fetchone()
    if user is None:
        return {"ok": False, "message": "등록되지 않은 사번입니다. 관리자에게 점수 등록을 요청해주세요."}
    return {"ok": True, "user": row_to_dict(user)}


def save_user(payload: dict) -> dict:
    employee_no = str(payload.get("employee_no", "")).strip()
    name = str(payload.get("name", "")).strip()
    team = str(payload.get("team", "")).strip()
    points = int(payload.get("points") or 0)
    if not employee_no:
        return {"ok": False, "message": "사번은 필수입니다."}
    timestamp = now_text()
    with connect() as db:
        db.execute(
            """
            INSERT INTO users (employee_no, name, team, points, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(employee_no)
            DO UPDATE SET name = excluded.name,
                          team = excluded.team,
                          points = excluded.points,
                          updated_at = excluded.updated_at
            """,
            (employee_no, name, team, points, timestamp, timestamp),
        )
    return {"ok": True, "message": "사용자 점수를 저장했습니다.", "state": get_admin_state()}


def save_product(payload: dict) -> dict:
    product_id = int(payload.get("id") or 0)
    name = str(payload.get("name", "")).strip()
    description = str(payload.get("description", "")).strip()
    image_url = str(payload.get("image_url", "")).strip()
    price = int(payload.get("price") or 0)
    original_price = int(payload.get("original_price") or 0)
    stock_value = payload.get("stock")
    stock = None if stock_value in ("", None) else int(stock_value)
    is_active = 1 if payload.get("is_active", True) else 0
    if not name or price <= 0:
        return {"ok": False, "message": "상품명과 1P 이상의 가격을 입력해주세요."}
    if original_price <= 0:
        original_price = price
    timestamp = now_text()
    with connect() as db:
        if product_id:
            db.execute(
                """
                UPDATE products
                SET name = ?, description = ?, price = ?, original_price = ?, stock = ?,
                    image_url = ?, is_active = ?, updated_at = ?
                WHERE id = ?
                """,
                (name, description, price, original_price, stock, image_url, is_active, timestamp, product_id),
            )
        else:
            db.execute(
                """
                INSERT INTO products
                    (name, description, price, original_price, stock, image_url, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (name, description, price, original_price, stock, image_url, is_active, timestamp, timestamp),
            )
    return {"ok": True, "message": "상품을 저장했습니다.", "state": get_admin_state()}


def checkout(payload: dict) -> dict:
    user_id = int(payload.get("user_id") or 0)
    raw_items = payload.get("items") or []
    items = [
        {"product_id": int(item.get("product_id")), "quantity": int(item.get("quantity") or 0)}
        for item in raw_items
        if int(item.get("quantity") or 0) > 0
    ]
    if user_id <= 0 or not items:
        return {"ok": False, "message": "구매자와 상품을 확인해주세요."}
    timestamp = now_text()
    with connect() as db:
        user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            return {"ok": False, "message": "구매자를 찾을 수 없습니다."}

        placeholders = ",".join("?" for _ in items)
        products = {
            row["id"]: row
            for row in db.execute(
                f"SELECT * FROM products WHERE id IN ({placeholders}) AND is_active = 1",
                [item["product_id"] for item in items],
            )
        }
        total = 0
        order_items = []
        for item in items:
            product = products.get(item["product_id"])
            if product is None:
                return {"ok": False, "message": "판매 중인 상품만 구매할 수 있습니다."}
            quantity = item["quantity"]
            if product["stock"] is not None and product["stock"] < quantity:
                return {"ok": False, "message": f"{product['name']} 재고가 부족합니다."}
            total += product["price"] * quantity
            order_items.append((product, quantity))

        if total > user["points"]:
            return {"ok": False, "message": f"보유 포인트가 부족합니다. 보유 {user['points']:,}P / 필요 {total:,}P"}

        cursor = db.execute(
            "INSERT INTO orders (user_id, total_points, created_at) VALUES (?, ?, ?)",
            (user_id, total, timestamp),
        )
        order_id = cursor.lastrowid
        for product, quantity in order_items:
            db.execute(
                """
                INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity)
                VALUES (?, ?, ?, ?, ?)
                """,
                (order_id, product["id"], product["name"], product["price"], quantity),
            )
            if product["stock"] is not None:
                db.execute("UPDATE products SET stock = stock - ?, updated_at = ? WHERE id = ?", (quantity, timestamp, product["id"]))
        db.execute("UPDATE users SET points = points - ?, updated_at = ? WHERE id = ?", (total, timestamp, user_id))

    return {"ok": True, "message": "결제가 완료되었습니다.", "receipt": get_order(order_id), "state": get_public_state()}


def get_order(order_id: int) -> dict:
    with connect() as db:
        order = db.execute(
            """
            SELECT o.*, u.employee_no, u.name, u.team
            FROM orders o
            JOIN users u ON u.id = o.user_id
            WHERE o.id = ?
            """,
            (order_id,),
        ).fetchone()
        items = [row_to_dict(row) for row in db.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY id", (order_id,))]
    return {"order": row_to_dict(order), "items": items}


def build_receipts() -> dict:
    with connect() as db:
        orders = db.execute(
            """
            SELECT o.id, o.total_points, o.created_at, u.employee_no, u.name, u.team
            FROM orders o
            JOIN users u ON u.id = o.user_id
            ORDER BY o.id DESC
            """
        ).fetchall()
        items = db.execute("SELECT * FROM order_items ORDER BY order_id, id").fetchall()
    item_map: dict[int, list[dict]] = {}
    for item in items:
        item_map.setdefault(item["order_id"], []).append(row_to_dict(item))
    receipt_list = []
    lines = []
    for order in orders:
        order_dict = row_to_dict(order)
        order_items = item_map.get(order["id"], [])
        label = f"{order['team']} {order['employee_no']} {order['name']}".strip()
        summary = ", ".join(f"{item['product_name']} {item['quantity']}개" for item in order_items)
        lines.append(f"[{order['created_at']}] {label} - {summary} / 총 {order['total_points']:,}P")
        receipt_list.append({"order": order_dict, "items": order_items})
    return {"list": receipt_list, "text": "\n".join(lines)}


def reset_orders() -> dict:
    with connect() as db:
        db.executescript("DELETE FROM order_items; DELETE FROM orders;")
    return {"ok": True, "message": "구매 내역을 초기화했습니다.", "state": get_admin_state()}


class SDMAMallHandler(BaseHTTPRequestHandler):
    server_version = "SDMAMall/1.0"

    def do_GET(self) -> None:
        path = self.normalized_path()
        if path in ("", "/"):
            self.redirect(BASE_PATH + "/")
            return
        if path in (BASE_PATH, BASE_PATH + "/"):
            self.send_bytes(render_template("index.html"), "text/html; charset=utf-8")
            return
        if path == BASE_PATH + "/admin":
            self.send_bytes(render_template("admin.html"), "text/html; charset=utf-8")
            return
        if path.startswith(BASE_PATH + "/static/"):
            self.send_static(path.removeprefix(BASE_PATH + "/static/"))
            return
        if path == BASE_PATH + "/api/state":
            self.send_json(get_public_state())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = self.normalized_path()
        if path == BASE_PATH + "/api/admin/check":
            self.send_json({"ok": self.read_json().get("code") == ADMIN_CODE})
            return
        if path == BASE_PATH + "/api/login":
            self.send_json(login_user(str(self.read_json().get("employee_no", ""))))
            return
        if path == BASE_PATH + "/api/checkout":
            self.send_json(checkout(self.read_json()))
            return

        admin_routes = {
            BASE_PATH + "/api/admin/state": lambda: {"ok": True, "state": get_admin_state()},
            BASE_PATH + "/api/admin/users": lambda: save_user(self.read_json()),
            BASE_PATH + "/api/admin/products": lambda: save_product(self.read_json()),
            BASE_PATH + "/api/admin/reset-orders": reset_orders,
        }
        if path in admin_routes:
            if not require_admin(self):
                self.send_json({"ok": False, "message": "관리자 코드가 올바르지 않습니다."}, 403)
                return
            self.send_json(admin_routes[path]())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def normalized_path(self) -> str:
        parsed = urlparse(self.path).path
        return parsed if parsed == BASE_PATH + "/" else parsed.rstrip("/")

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8") or "{}")

    def send_json(self, payload: dict | list, status: int = 200) -> None:
        self.send_bytes(json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_static(self, relative_path: str) -> None:
        target = (ROOT / "static" / relative_path).resolve()
        static_root = (ROOT / "static").resolve()
        if static_root not in target.parents or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        self.send_bytes(target.read_bytes(), content_type)

    def redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()


if __name__ == "__main__":
    init_db()
    print(f"SDMA Mall listening on http://{HOST}:{PORT}{BASE_PATH}", flush=True)
    ThreadingHTTPServer((HOST, PORT), SDMAMallHandler).serve_forever()
