from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from app.modules.public_accident_cases.service import load_public_dataset, render_public_page


router = APIRouter(prefix="/public/accident-cases", tags=["public-accident-cases"])

PUBLIC_HEADERS = {
    "Cache-Control": "public, max-age=300, s-maxage=300",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
    ),
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Robots-Tag": "noindex, nofollow, noarchive, nosnippet",
}


@router.get("", response_class=HTMLResponse, include_in_schema=False)
def public_accident_cases_page() -> HTMLResponse:
    dataset = load_public_dataset()
    return HTMLResponse(render_public_page(dataset), headers=PUBLIC_HEADERS)


@router.get("/data", include_in_schema=False)
def public_accident_cases_data() -> JSONResponse:
    return JSONResponse(load_public_dataset(), headers=PUBLIC_HEADERS)
