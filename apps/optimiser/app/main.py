"""FastAPI surface for the optimiser microservice."""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .baseline import reconstruct_baseline
from .config import settings
from .marginal import marginal_cost
from .optimise import OPTIMISER_VERSION, optimise
from .schemas import (
    BaselineRequest,
    BaselineResponse,
    MarginalCostRequest,
    MarginalCostResponse,
    OptimiseRequest,
    OptimiseResponse,
)

app = FastAPI(
    title="Grasmere Optimiser",
    version=OPTIMISER_VERSION,
    description=(
        "VRP solver and cost estimator for Grasmere Routes. Cost-minimising "
        "objective, mirrors the TS cost-model byte-for-byte so UI £ figures "
        "exactly match the figures the solver optimises against."
    ),
)

# Trust only the expected origin in prod; opened up here for dev/preview.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    cfg = settings()
    if cfg.api_key and x_api_key != cfg.api_key:
        raise HTTPException(status_code=401, detail="invalid api key")


@app.get("/")
def health() -> dict:
    cfg = settings()
    return {
        "status": "ok",
        "version": OPTIMISER_VERSION,
        "mapbox": "real" if cfg.mapbox_token else "haversine_fallback",
    }


@app.post("/optimise", response_model=OptimiseResponse, dependencies=[Depends(require_api_key)])
async def optimise_route(req: OptimiseRequest) -> OptimiseResponse:
    if not req.vehicles:
        raise HTTPException(status_code=400, detail="vehicles list cannot be empty")
    return await optimise(req)


@app.post(
    "/marginal_cost",
    response_model=MarginalCostResponse,
    dependencies=[Depends(require_api_key)],
)
async def marginal_cost_endpoint(req: MarginalCostRequest) -> MarginalCostResponse:
    return await marginal_cost(req)


@app.post(
    "/baseline_cost",
    response_model=BaselineResponse,
    dependencies=[Depends(require_api_key)],
)
async def baseline_endpoint(req: BaselineRequest) -> BaselineResponse:
    return await reconstruct_baseline(req)
