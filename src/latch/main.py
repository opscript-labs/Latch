from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from latch import __version__


class HealthResponse(BaseModel):
    service: Literal["Latch"]
    version: str
    status: Literal["healthy"]


app = FastAPI(title="Latch", version=__version__)


@app.get("/", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="Latch", version=__version__, status="healthy")
