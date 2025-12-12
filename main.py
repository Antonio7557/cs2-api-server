from fastapi import FastAPI, HTTPException
from urllib.parse import urlparse
from cs2api import CS2  # Python wrapper za BO3.gg

app = FastAPI()


@app.get("/ping")
async def ping():
    return {"status": "ok"}


def extract_slug_from_url(url: str) -> str:
    """
    Prima BO3 URL i vadi zadnji dio patha kao slug.
    Primjer:
    https://bo3.gg/matches/star-opens-2025-mouz-vs-faze -> 'star-opens-2025-mouz-vs-faze'
    """
    path = urlparse(url).path  # npr. "/matches/star-opens-2025-mouz-vs-faze"
    parts = [p for p in path.split("/") if p]
    if not parts:
        raise ValueError("Cannot extract slug from URL")
    return parts[-1]


@app.get("/match")
async def get_match(url: str | None = None, slug: str | None = None):
    """
    Dohvati podatke o meču s BO3.gg

    Možeš zvati na dva načina:

    1) /match?url=FULL_BO3_URL
       npr: /match?url=https://bo3.gg/matches/star-opens-2025-mouz-vs-faze

    2) /match?slug=star-opens-2025-mouz-vs-faze
    """

    if url:
        try:
            slug = extract_slug_from_url(url)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not slug:
        raise HTTPException(
            status_code=400,
            detail="Provide either 'url' (bo3.gg match URL) or 'slug'.",
        )

    try:
        async with CS2() as cs2:
            # ovo koristi BO3 API i vraća kompletne podatke za meč
            match_details = await cs2.get_match_details(slug)
        return match_details

    except Exception as e:
        # za debug možeš ovdje printati error u log
        raise HTTPException(status_code=500, detail=f"Error fetching match: {e}")
