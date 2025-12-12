from fastapi import FastAPI, HTTPException
from urllib.parse import urlparse
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


# 🔹 RAW MATCH (pun BO3 response – samo za debug)
@app.get("/match")
async def get_match_raw(url: str | None = None, slug: str | None = None):
    if url:
        slug = extract_slug_from_url(url)

    if not slug:
        raise HTTPException(status_code=400, detail="Provide 'url' or 'slug'.")

    try:
        async with CS2() as cs2:
            match = await cs2.get_match_details(slug)
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
        m = await cs2.get_match_details(slug)

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
