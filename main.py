from fastapi import FastAPI, HTTPException, Request
from urllib.parse import urlparse
from typing import Any, Dict, Optional, List
import inspect
import asyncio

from cs2api import CS2

app = FastAPI()


# -----------------------------
# BASIC
# -----------------------------
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
ALLOWED_METHODS = {
    # MATCH
    "get_live_matches",
    "get_live_match_snapshot",
    "get_match_details",
    "get_todays_matches",
    "finished",

    # TEAM
    "search_teams",
    "get_team_data",
    "get_team_matches",
    "get_team_upcoming_matches",
    "get_team_news",
    "get_team_stats",
    "get_team_transfers",

    # PLAYER
    "search_players",
    "get_player_details",
    "get_player_stats",
    "get_player_matches",
    "get_player_transfers",
}


@app.get("/methods")
async def methods():
    return {"get_methods": sorted(ALLOWED_METHODS)}


@app.get("/describe/{method_name}")
async def describe(method_name: str):
    """
    Pokaže točan signature metode u cs2api wrapperu.
    """
    if method_name not in ALLOWED_METHODS:
        raise HTTPException(status_code=404, detail="Unknown or not allowed method")

    async with CS2() as cs2:
        fn = getattr(cs2, method_name, None)
        if not fn:
            raise HTTPException(status_code=404, detail="Method not found on CS2 client")
        sig = inspect.signature(fn)

    return {"method": method_name, "signature": str(sig)}


@app.get("/call/{method_name}")
async def call_method(method_name: str, request: Request):
    """
    Univerzalni endpoint:
    - radi za metode bez parametara (npr. get_todays_matches, finished)
    - radi za keyword parametre (query=..., team_slug=..., team_id=..., slug=..., player_id=...)
    - radi i za positional fallback
    """
    if method_name not in ALLOWED_METHODS:
        raise HTTPException(status_code=404, detail="Unknown or not allowed method")

    params: Dict[str, Any] = dict(request.query_params)

    try:
        async with CS2() as cs2:
            fn = getattr(cs2, method_name, None)
            if not fn:
                raise HTTPException(status_code=404, detail="Method not found on CS2 client")

            sig = inspect.signature(fn)
            expected_names = set(sig.parameters.keys())

            # 1) no-arg methods
            if len(sig.parameters) == 0:
                data = await fn()
                return {"method": method_name, "params": params, "data": data}

            # 2) keyword args (only those method actually accepts)
            kwargs = {k: v for k, v in params.items() if k in expected_names}
            if kwargs:
                data = await fn(**kwargs)
                return {"method": method_name, "params": params, "resolved_kwargs": kwargs, "data": data}

            # 3) positional fallback
            if not params:
                raise HTTPException(status_code=400, detail="No params provided")

            value = next(iter(params.values()))
            data = await fn(value)
            return {"method": method_name, "params": params, "resolved_positional": value, "data": data}

    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Bad params: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -----------------------------
# MATCH RAW + CLEAN
# -----------------------------
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
            "id": (m.get("tournament") or {}).get("id"),
            "name": (m.get("tournament") or {}).get("name"),
            "slug": (m.get("tournament") or {}).get("slug"),
            "image_url": (m.get("tournament") or {}).get("image_url"),
            "parsing_allowed": (m.get("tournament") or {}).get("parsing_allowed"),
        },

        "team1": {
            "id": (m.get("team1") or {}).get("id"),
            "name": (m.get("team1") or {}).get("name"),
            "slug": (m.get("team1") or {}).get("slug"),
            "rank": (m.get("team1") or {}).get("rank"),
            "image_url": (m.get("team1") or {}).get("image_url"),
        },

        "team2": {
            "id": (m.get("team2") or {}).get("id"),
            "name": (m.get("team2") or {}).get("name"),
            "slug": (m.get("team2") or {}).get("slug"),
            "rank": (m.get("team2") or {}).get("rank"),
            "image_url": (m.get("team2") or {}).get("image_url"),
        },

        "ai_prediction": {
            "team1_score": (m.get("ai_predictions") or {}).get("prediction_team1_score"),
            "team2_score": (m.get("ai_predictions") or {}).get("prediction_team2_score"),
            "winner_team_id": (m.get("ai_predictions") or {}).get("prediction_winner_team_id"),
        },

        "odds": {
            "provider": (m.get("bet_updates") or {}).get("provider"),
            "team1_coeff": ((m.get("bet_updates") or {}).get("team_1") or {}).get("coeff"),
            "team2_coeff": ((m.get("bet_updates") or {}).get("team_2") or {}).get("coeff"),
            "markets_count": (m.get("bet_updates") or {}).get("markets_count"),
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


# -----------------------------
# ENRICHED MATCH
# (lineups + form + h2h + map winrate + odds)
# -----------------------------
def _is_finished(m: dict) -> bool:
    st = (m.get("status") or "").lower()
    pst = (m.get("parsed_status") or "").lower()
    return st == "finished" or pst == "finished"


def _winner_team_id(m: dict) -> Optional[int]:
    t1 = m.get("team1_id") or (m.get("team1") or {}).get("id")
    t2 = m.get("team2_id") or (m.get("team2") or {}).get("id")
    s1 = m.get("team1_score")
    s2 = m.get("team2_score")

    if t1 is None or t2 is None:
        return None
    if not isinstance(s1, int) or not isinstance(s2, int):
        return None

    if s1 > s2:
        return int(t1)
    if s2 > s1:
        return int(t2)
    return None


def _opponent_id(m: dict, team_id: int) -> Optional[int]:
    t1 = m.get("team1_id") or (m.get("team1") or {}).get("id")
    t2 = m.get("team2_id") or (m.get("team2") or {}).get("id")
    if t1 == team_id and t2:
        return int(t2)
    if t2 == team_id and t1:
        return int(t1)
    return None


def _safe_list(x: Any) -> List[dict]:
    return x if isinstance(x, list) else []


def _compute_form(team_id: int, matches: List[dict], take: int = 10) -> Dict[str, Any]:
    finished = [m for m in matches if _is_finished(m)]
    finished = finished[:take]

    wins = losses = 0
    recent = []
    for m in finished:
        w = _winner_team_id(m)
        if w is None:
            continue
        is_win = (w == team_id)
        recent.append({
            "id": m.get("id"),
            "slug": m.get("slug"),
            "start_date": m.get("start_date"),
            "win": is_win,
            "team1_score": m.get("team1_score"),
            "team2_score": m.get("team2_score"),
        })
        if is_win:
            wins += 1
        else:
            losses += 1

    # streak (from most recent)
    streak = 0
    for r in recent:
        if r["win"]:
            if streak >= 0:
                streak += 1
            else:
                break
        else:
            if streak <= 0:
                streak -= 1
            else:
                break

    return {
        "sample_size": len(recent),
        "wins": wins,
        "losses": losses,
        "streak": streak,
        "recent": recent,
    }


def _compute_h2h(team1_id: int, team2_id: int, matches_team1: List[dict], limit: int = 10) -> Dict[str, Any]:
    h2h = []
    for m in matches_team1:
        opp = _opponent_id(m, team1_id)
        if opp == team2_id:
            h2h.append(m)
        if len(h2h) >= limit:
            break

    t1w = t2w = 0
    out = []
    for m in h2h:
        w = _winner_team_id(m)
        if w == team1_id:
            t1w += 1
        elif w == team2_id:
            t2w += 1
        out.append({
            "id": m.get("id"),
            "slug": m.get("slug"),
            "start_date": m.get("start_date"),
            "team1_score": m.get("team1_score"),
            "team2_score": m.get("team2_score"),
        })

    return {
        "sample_size": len(out),
        "team1_wins": t1w,
        "team2_wins": t2w,
        "matches": out,
    }


def _extract_odds(md: dict) -> Optional[dict]:
    bu = md.get("bet_updates") or {}
    if not bu:
        return None
    return {
        "provider": bu.get("provider"),
        "markets_count": bu.get("markets_count"),
        "team_1": bu.get("team_1"),
        "team_2": bu.get("team_2"),
        "path": bu.get("path"),
    }


def _extract_lineups(md: dict) -> Optional[dict]:
    """
    BO3 payloads vary; if they include roster/players/lineups return them, else None.
    """
    for key in ("lineups", "players", "rosters"):
        val = md.get(key)
        if val:
            return {key: val}
    return None


def _map_winrate_from_team_stats(team_stats: dict) -> Optional[dict]:
    """
    Your cs2api get_team_stats returns:
      {"general_stats": {...}, "advanced_stats": {...}}
    If any map breakdown exists, return it. Otherwise None.
    """
    if not isinstance(team_stats, dict):
        return None

    # Try common places
    general = team_stats.get("general_stats") or {}
    advanced = team_stats.get("advanced_stats") or {}

    # Some APIs put map pool here; we just surface whatever exists.
    for container in (general, advanced, team_stats):
        if not isinstance(container, dict):
            continue
        for key in ("maps", "map_stats", "map_pool", "mapWinrate", "map_winrate", "map_stats_data"):
            if key in container and container.get(key):
                return {key: container.get(key)}
    return None


@app.get("/match_enriched")
async def match_enriched(slug: str, form_last: int = 10, h2h_last: int = 10):
    """
    One-call JSON for Make:
      - lineups (if present)
      - form (last N finished matches)
      - h2h (last N between these teams)
      - map winrate (from team_stats if available)
      - odds (from match_details bet_updates)
    """
    try:
        async with CS2() as cs2:
            md = await cs2.get_match_details(slug=slug)

            team1 = md.get("team1") or {}
            team2 = md.get("team2") or {}

            team1_id = team1.get("id") or md.get("team1_id")
            team2_id = team2.get("id") or md.get("team2_id")
            team1_slug = team1.get("slug")
            team2_slug = team2.get("slug")

            if team1_id is None or team2_id is None:
                raise HTTPException(status_code=500, detail="Missing team ids in match_details")

            # Fetch in parallel
            tasks = [
                cs2.get_team_matches(team_id=int(team1_id)),
                cs2.get_team_matches(team_id=int(team2_id)),
            ]

            # stats are optional but helpful for map winrate
            if team1_slug:
                tasks.append(cs2.get_team_stats(team_slug=str(team1_slug)))
            else:
                tasks.append(asyncio.sleep(0, result=None))

            if team2_slug:
                tasks.append(cs2.get_team_stats(team_slug=str(team2_slug)))
            else:
                tasks.append(asyncio.sleep(0, result=None))

            t1_matches, t2_matches, t1_stats, t2_stats = await asyncio.gather(*tasks)

        # Ensure lists
        t1_matches_list = _safe_list(t1_matches)
        t2_matches_list = _safe_list(t2_matches)

        return {
            "match": {
                "id": md.get("id"),
                "slug": md.get("slug"),
                "status": md.get("status"),
                "start_date": md.get("start_date"),
                "bo_type": md.get("bo_type"),
                "tournament": md.get("tournament"),
                "team1": team1,
                "team2": team2,
            },
            "odds": _extract_odds(md),
            "lineups": _extract_lineups(md),
            "form": {
                "team1": _compute_form(int(team1_id), t1_matches_list, take=int(form_last)),
                "team2": _compute_form(int(team2_id), t2_matches_list, take=int(form_last)),
            },
            "h2h": _compute_h2h(int(team1_id), int(team2_id), t1_matches_list, limit=int(h2h_last)),
            "map_winrate": {
                "team1": _map_winrate_from_team_stats(t1_stats or {}) if isinstance(t1_stats, dict) else None,
                "team2": _map_winrate_from_team_stats(t2_stats or {}) if isinstance(t2_stats, dict) else None,
                "note": "If null, BO3 team stats payload doesn't include per-map winrate. We can compute it by calling get_match_details for many matches (heavier).",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
