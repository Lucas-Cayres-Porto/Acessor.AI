import psycopg2 as pg 
from app.config import DATABASE_URL

def get_conn():
    return pg.connect(DATABASE_URL)