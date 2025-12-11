from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 명시적 로딩
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"

if env_path.exists():
    load_dotenv(env_path)
    print(f"✓ Loaded environment variables from {env_path}")
else:
    print(f"⚠ Warning: .env file not found at {env_path}")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import chat_service as chat_service_module
from .chat_service import ChatService
from .redis_cache import RedisSessionCache
from ingestion.services.chroma_client import default_chroma_client
from llm.client.openai_client import OpenAIClient

from .database import init_db
from .routes import router

app = FastAPI(title="StockTeacher Web API", version="0.1.0")

init_db()

# Initialize chat service
openai_client = OpenAIClient.from_env()
redis_cache = RedisSessionCache()
chat_service_module.chat_service = ChatService(
    openai_client,
    redis_cache,
    chroma_client=default_chroma_client(),
)

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
