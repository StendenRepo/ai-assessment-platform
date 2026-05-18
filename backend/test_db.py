from app.database import engine, Base
from app.models import *

Base.metadata.create_all(bind=engine)
print("All tables created successfully!")