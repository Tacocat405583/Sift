from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import search
from app.db import pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool.open()
    yield
    pool.close()


app = FastAPI(title="SIFT API", lifespan=lifespan)
app.include_router(search.router)


@app.get("/health")
def health():
    return {"status": "ok"}
