import psycopg2
from utils.database import DB_CONFIG, SERVER_CONFIG

def dropdatabase(name):
    conn = psycopg2.connect(
        dbname="sysbench",
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        host=DB_CONFIG['host'],
    )

    conn.autocommit = True
    cur = conn.cursor()

    drop_database_query = f"DROP DATABASE IF EXISTS {name}"

    cur.execute(drop_database_query)

    conn.commit()

    cur.close()
    conn.close()
