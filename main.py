from fastapi import FastAPI

app = FastAPI()


@app.get("/ping")
def ping():
    return {"status": "ok"}


@app.get("/match/{slug}")
def match_stub(slug: str):
    """
    Test endpoint.
    Later this will call cs2api and return real match stats.
    """
    return {"received_slug": slug}
