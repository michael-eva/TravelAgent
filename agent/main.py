from fastapi import FastAPI
from enum import Enum

app = FastAPI()

@app.get("/ping")
async def ping():
    return {"message": "pong"}