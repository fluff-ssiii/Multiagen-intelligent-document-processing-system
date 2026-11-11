"""Drop and recreate ALL tables (development only).  Usage (from backend/):  python -m scripts.reset_db"""
from app.database import models  # noqa: F401  (register tables)
from app.database.connection import Base, engine, init_db

if input("This deletes all rows in the database. Type 'yes' to continue: ").strip().lower() == "yes":
    Base.metadata.drop_all(bind=engine)
    init_db()
    print("Database reset. (Files under uploads/ are untouched; delete them manually if you want.)")