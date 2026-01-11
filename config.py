import os

class Config:
    SQLALCHEMY_DATABASE_URI = os.getenv("DB_URL", "sqlite:///nms.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Timeouts SSH
    SSH_CONNECT_TIMEOUT = int(os.getenv("SSH_CONNECT_TIMEOUT", "10"))
    SSH_AUTH_TIMEOUT = int(os.getenv("SSH_AUTH_TIMEOUT", "10"))
