from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="SIFT API")


class Item(BaseModel):
    name: str
    price: float


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.post("/items")
def create_item(item: Item):
    return item
