import psycopg2
from utils.database import DB_CONFIG, SERVER_CONFIG

def createdatabase(name):
    conn = psycopg2.connect(
        dbname="sysbench",
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        host=DB_CONFIG['host'],
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(f"CREATE DATABASE {name}")

    conn.commit()

    cur.close()
    conn.close()
