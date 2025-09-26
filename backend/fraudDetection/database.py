from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


database_name = "database.db"

engine = create_engine(f'sqlite:///{database_name}',connect_args={"check_same_thread":False})

sessionLocal = sessionmaker(bind=engine,autocommit=False,autoflush=False)

Base = declarative_base()

def get_db():
    db = sessionLocal()

    try:
        yield db
    finally:
        db.close()
