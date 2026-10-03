import secrets
import string

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

app = FastAPI()

urls: dict[str, str] = {}

ALPHABET = string.ascii_letters + string.digits
CODE_LENGTH = 6


def generate_code() -> str:
    characters = []
    for _ in range(CODE_LENGTH):
        characters.append(secrets.choice(ALPHABET))
    code = "".join(characters)
    return code


class ShortenRequest(BaseModel):
    url: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/shorten")
def shorten(body: ShortenRequest, request: Request):
    code = generate_code()
    while code in urls:
        code = generate_code()
    urls[code] = body.url
    return {"short_url": f"{request.base_url}{code}"}


@app.get("/{code}")
def redirect(code: str):
    url = urls.get(code)
    if url is None:
        raise HTTPException(status_code=404, detail="Code not found")
    return RedirectResponse(url, status_code=307)
