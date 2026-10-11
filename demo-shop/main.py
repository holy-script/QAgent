"""Demo shop: a tiny storefront with five deliberately seeded, toggleable bugs.

Bug 1  cart badge counts distinct lines instead of total quantity   (DOM check, UI vs API)
Bug 2  postal code is not validated at checkout                     (edge-case flow + DOM check)
Bug 3  every 3rd payment request returns 500                        (network check)
Bug 4  spinner never clears after applying a coupon                 (settle timeout + wait frames)
Bug 5  tax applied before discount, giving a wrong total            (formula check)

All bugs are on by default. Override with DEMO_BUGS="1,3" at startup, or at
runtime with POST /__bugs {"1": false}. POST /__reset clears cart + payment counter.
"""
import os
import re
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Demo Shop")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

TAX_RATE = 0.08
COUPONS = {"SAVE10": 0.10}  # EXPIRED10 is deliberately absent: it is the "expired coupon" edge case

PRODUCTS = [
    {"id": 1, "name": "Wireless Headphones", "price": 99.00},
    {"id": 2, "name": "Mechanical Keyboard", "price": 149.00},
    {"id": 3, "name": "USB-C Cable", "price": 12.50},
]


def _default_bugs() -> Dict[int, bool]:
    raw = os.getenv("DEMO_BUGS")
    enabled = {1, 2, 3, 4, 5} if raw is None else {int(b) for b in re.findall(r"\d+", raw)}
    return {n: n in enabled for n in range(1, 6)}


current_sid: ContextVar[str] = ContextVar("current_sid", default="")


class State:
    """Carts and coupons are per browser session (cookie), so parallel flows do not collide."""

    def __init__(self) -> None:
        self.bugs = _default_bugs()
        self.reset()

    def reset(self) -> None:
        self.sessions: Dict[str, dict] = {}
        self.payment_requests = 0

    def _session(self) -> dict:
        return self.sessions.setdefault(current_sid.get(), {"cart": {}, "coupon": ""})

    @property
    def cart(self) -> Dict[int, int]:
        return self._session()["cart"]

    @property
    def coupon(self) -> str:
        return self._session()["coupon"]

    @coupon.setter
    def coupon(self, value: str) -> None:
        self._session()["coupon"] = value


state = State()


def cart_snapshot() -> dict:
    items = []
    for pid, qty in state.cart.items():
        product = next(p for p in PRODUCTS if p["id"] == pid)
        items.append({"id": pid, "name": product["name"], "price": product["price"], "qty": qty})
    subtotal = round(sum(i["price"] * i["qty"] for i in items), 2)
    rate = COUPONS.get(state.coupon, 0.0)
    discount = round(subtotal * rate, 2)
    if state.bugs[5]:
        total = round(subtotal * (1 + TAX_RATE) - discount, 2)  # BUG 5: tax before discount
    else:
        total = round((subtotal - discount) * (1 + TAX_RATE), 2)
    return {
        "items": items,
        "subtotal": subtotal,
        "discount": discount,
        "coupon": state.coupon,
        "tax_rate": TAX_RATE,
        "total": total,
        "count": sum(i["qty"] for i in items),
    }


def badge_count() -> int:
    if state.bugs[1]:
        return len(state.cart)  # BUG 1: distinct lines, not quantity
    return sum(state.cart.values())


def render(request: Request, name: str, **ctx):
    return templates.TemplateResponse(request, name, {"badge": badge_count(), "bugs": state.bugs, **ctx})


@app.middleware("http")
async def session_cookie(request: Request, call_next):
    sid = request.cookies.get("sid")
    new = sid is None
    sid = sid or uuid.uuid4().hex
    current_sid.set(sid)
    response = await call_next(request)
    if new:
        response.set_cookie("sid", sid, httponly=True, samesite="lax")
    return response


@app.get("/")
async def index():
    return RedirectResponse("/products")


@app.get("/products")
async def products(request: Request):
    return render(request, "products.html", products=PRODUCTS)


@app.get("/cart")
async def cart(request: Request):
    return render(request, "cart.html", cart=cart_snapshot())


@app.get("/checkout")
async def checkout(request: Request):
    return render(request, "checkout.html", cart=cart_snapshot())


@app.get("/api/products")
async def api_products():
    return PRODUCTS


@app.get("/api/cart")
async def api_cart():
    return cart_snapshot()


@app.post("/api/cart/add")
async def api_cart_add(payload: dict):
    pid = int(payload.get("id", 0))
    qty = int(payload.get("qty", 1))
    if not any(p["id"] == pid for p in PRODUCTS) or qty < 1:
        return JSONResponse({"error": "invalid item"}, status_code=400)
    state.cart[pid] = state.cart.get(pid, 0) + qty
    return {**cart_snapshot(), "badge": badge_count()}


@app.post("/api/cart/update")
async def api_cart_update(payload: dict):
    pid = int(payload.get("id", 0))
    qty = int(payload.get("qty", 0))
    if qty <= 0:
        state.cart.pop(pid, None)
    elif pid in state.cart:
        state.cart[pid] = qty
    return {**cart_snapshot(), "badge": badge_count()}


@app.post("/api/coupon")
async def api_coupon(payload: dict):
    code = str(payload.get("code", "")).strip().upper()
    if code not in COUPONS:
        return JSONResponse({"error": "Coupon is invalid or expired"}, status_code=400)
    state.coupon = code
    return {**cart_snapshot(), "badge": badge_count(), "hang": state.bugs[4]}


@app.post("/api/checkout")
async def api_checkout(payload: dict):
    postal = str(payload.get("postal_code", "")).strip()
    if not state.bugs[2] and not re.fullmatch(r"\d{5}", postal):  # BUG 2: validation skipped
        return JSONResponse({"error": "Postal code must be 5 digits"}, status_code=400)
    return {"ok": True, "postal_code": postal}


@app.post("/api/pay")
async def api_pay(payload: dict | None = None):
    state.payment_requests += 1
    if state.bugs[3] and state.payment_requests % 3 == 0:  # BUG 3: every 3rd payment fails
        return JSONResponse({"error": "Payment gateway error"}, status_code=500)
    return {"ok": True, "charged": cart_snapshot()["total"]}


@app.post("/__reset")
async def reset():
    state.reset()
    return {"ok": True, "bugs": state.bugs}


@app.post("/__bugs")
async def set_bugs(payload: dict):
    for key, value in payload.items():
        if int(key) in state.bugs:
            state.bugs[int(key)] = bool(value)
    return {"bugs": state.bugs}


@app.get("/__bugs")
async def get_bugs():
    return {"bugs": state.bugs}
