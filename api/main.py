from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routes import router

app = FastAPI(title="StockTeacher Web API", version="0.1.0")

init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(router)


@app.get("/healthz", tags=["system"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
