import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.exception_handlers import register_exception_handlers
from app.routers import auth, users, products, cart, orders, admin

# Create tables
Base.metadata.create_all(bind=engine)

# Ensure storage directory exists
os.makedirs("storage/products", exist_ok=True)

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_exception_handlers(app)

# Routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(admin.router)

# Static files
app.mount("/storage", StaticFiles(directory="storage"), name="storage")
