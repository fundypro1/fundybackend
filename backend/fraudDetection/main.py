from fastapi import FastAPI,Depends,Request
from fraudDetection.routers import admin, earn, purchase, withdraw
from . import schemas,models
from .database import engine
from sqlalchemy.orm import Session
from fraudDetection.routers import user,authentication,deposit
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi.middleware import SlowAPIMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware


from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import os
from pathlib import Path

from .models import User
from .schemas import AdminDashboardStats





app = FastAPI(debug=True)

models.Base.metadata.create_all(engine)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


origins = [
    "http://localhost:5173",
    "https://earnfundypro.netlify.app"
]

app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
# Make templates available to routes
app.state.templates = templates


app.include_router(user.router)
app.include_router(authentication.router)
app.include_router(deposit.router, tags=["deposits"])
app.include_router(admin.router)
app.include_router(purchase.router)
app.include_router(earn.router)
app.include_router(withdraw.router)




limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)







#app.mount("/static", StaticFiles(directory="static"), name="static")


# templates = Jinja2Templates(directory="templates")


# @app.get("/transaction", response_class=HTMLResponse)
# async def read_item(request: schemas.OrgTransaction):
#     return templates.TemplateResponse(
#         request=request, name="index.html", context=""
#     )






