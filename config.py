
import os

class Config:
    MYSQL_HOST = "127.0.0.1"
    MYSQL_PORT = 3307
    MYSQL_USER = "root"
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "root")
    MYSQL_DB = "student_management_db"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
