from fastapi import FastAPI, HTTPException, Request
from urllib.parse import urlparse
from typing import Any, Dict, Callable
from cs2api import CS2

app = FastAPI()


@app.get("/ping")
async def ping():
    return {"status": "ok"}


def extract_slug_from_url(url: str) -> str:
    """
    Prima BO3 URL i vadi slug
    """
    path = urlparse(url).path
    parts = [p for p in path.split("/") if p]
    if not parts:
        raise ValueError("Cannot extract slug from URL")
    return parts[-1]


# -----------------------------
# METHODS REGISTRY (whitelist)
# -----------------------------
# Ovdje eksplicitno dopuštaš samo ove metode (sigurnije nego dir(client))
ALLOWED_METHODS = {
    "get_live_match_snapshot",
    "get_live_matches",
    "get_match_details",
    "get_player_details",
    "get_player_matches",
    "get_player_stats",
    "get_player_transfers",
    "get_team_data",
    "get_team_matches",
    "get_team_news",
    "get_team_stats",
    "get_team_transfers",
    "get_team_upcoming_matches",
    "get_todays_matches",
}


@app.get("/methods")
async def methods():
    # vraća samo whitelist (stabilno i predvidljivo)
    return {"get_methods": sorted(ALLOWED_METHODS)}


@app.get("/call/{method_name}")
async def call_method(method_name: str, request: Request):
    """
    Univerzalni endpoint: proslijediš query params i on pozove cs2.<method>(**params)

    Primjer:
    /call/get_match_details?slug=mousesports-vs-faze-12-12-2025
    /call/get_team_matches?team_id=123
    /call/get_player_stats?player_id=456
    """
    if method_name not in ALLOWED_METHODS:
        raise HTTPException(status_code=404, detail="Unknown or not allowed method")

    # query params -> dict (FastAPI QueryParams može imati više vrijednosti; uzimamo zadnju)
    params: Dict[str, Any] = dict(request.query_params)

    try:
        async with CS2() as cs2:
            fn = getattr(cs2, method_name, None)
            if not fn:
                raise HTTPException(status_code=404, detail="Method not found on CS2 client")

            # poziv metode
            data = await fn(**params)

        return {"method": method_name, "params": params, "data": data}

    except TypeError as e:
        # najčešće: krivo ime parametra ili fali obavezni parametar
        raise HTTPException(status_code=400, detail=f"Bad params: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🔹 RAW MATCH (pun BO3 response – samo za debug)
@app.get("/match")
async def get_match_raw(url: str | None = None, slug: str | None = None):
    if url:
        slug = extract_slug_from_url(url)

    if not slug:
        raise HTTPException(status_code=400, detail="Provide 'url' or 'slug'.")

    try:
        async with CS2() as cs2:
            match = await cs2.get_match_details(slug=slug)
        return match
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🔹 CLEAN MATCH (ZA MAKE / AUTOMATION)
@app.get("/match_clean")
async def get_match_clean(url: str | None = None, slug: str | None = None):
    if url:
        slug = extract_slug_from_url(url)

    if not slug:
        raise HTTPException(status_code=400, detail="Provide 'url' or 'slug'.")

    async with CS2() as cs2:
        m = await cs2.get_match_details(slug=slug)

    return {
        "id": m.get("id"),
        "slug": m.get("slug"),
        "status": m.get("status"),
        "start_date": m.get("start_date"),
        "bo_type": m.get("bo_type"),

        "tournament": {
            "id": m.get("tournament", {}).get("id"),
            "name": m.get("tournament", {}).get("name"),
            "slug": m.get("tournament", {}).get("slug"),
        },

        "team1": {
            "id": m.get("team1", {}).get("id"),
            "name": m.get("team1", {}).get("name"),
            "slug": m.get("team1", {}).get("slug"),
            "rank": m.get("team1", {}).get("rank"),
        },

        "team2": {
            "id": m.get("team2", {}).get("id"),
            "name": m.get("team2", {}).get("name"),
            "slug": m.get("team2", {}).get("slug"),
            "rank": m.get("team2", {}).get("rank"),
        },

        "ai_prediction": {
            "team1_score": m.get("ai_predictions", {}).get("prediction_team1_score"),
            "team2_score": m.get("ai_predictions", {}).get("prediction_team2_score"),
            "winner_team_id": m.get("ai_predictions", {}).get("prediction_winner_team_id"),
        },

        "odds": {
            "provider": m.get("bet_updates", {}).get("provider"),
            "team1_coeff": m.get("bet_updates", {}).get("team_1", {}).get("coeff"),
            "team2_coeff": m.get("bet_updates", {}).get("team_2", {}).get("coeff"),
            "markets_count": m.get("bet_updates", {}).get("markets_count"),
        },

        "streams": [
            {
                "platform": s.get("platform"),
                "language": s.get("language"),
                "url": s.get("raw_url"),
            }
            for s in (m.get("streams") or [])
        ],
    }
