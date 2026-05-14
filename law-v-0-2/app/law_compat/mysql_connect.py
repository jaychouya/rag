import os

from mysql import connector


DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")


def openConnect(dbName, autocommit=False):
    return connector.connect(
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=int(DB_PORT),
        database=dbName,
        charset="utf8mb4",
        autocommit=autocommit,
    )


def closeConnect(cnx):
    cnx.close()
