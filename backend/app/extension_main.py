"""Additive entrypoint; frozen Anomaly Lab app and source are not edited."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from app.main import app as legacy_app,lifespan as legacy_lifespan
from reflex_safety.api import router
from reflex_safety import store
ROOT=Path(__file__).resolve().parents[2]
@asynccontextmanager
async def lifespan(app):
    store.recover()
    async with legacy_lifespan(legacy_app):yield
app=FastAPI(title='REFLEX — Inspection Studio and Safety Station',version='0.2.0',lifespan=lifespan)
app.include_router(router)
@app.middleware('http')
async def extension_headers(request,call_next):
    response=await call_next(request)
    if request.url.path.startswith(('/safety','/api/safety')):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY','Permissions-Policy':'camera=(self), microphone=(), geolocation=()',
          'Content-Security-Policy':"default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'"})
    return response
@app.get('/safety',include_in_schema=False)
def safety():return FileResponse(ROOT/'frontend/safety.html',media_type='text/html')
@app.get('/safety-assets/{name}',include_in_schema=False)
def asset(name:str):
    if name not in ['safety.css','safety.js']:raise HTTPException(404)
    return FileResponse(ROOT/'frontend'/name,media_type='text/css' if name.endswith('.css') else 'text/javascript')
app.mount('/',legacy_app)
