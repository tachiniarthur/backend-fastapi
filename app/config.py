import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database.sqlite")
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key-change-in-production")
STORAGE_PATH = "storage"
PRODUCTS_IMAGE_PATH = "storage/products"
