from datetime import datetime
from db import db

class Router(db.Model):
    __tablename__ = "routers"
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column(db.String(128), nullable=True)
    mgmt_ip = db.Column(db.String(64), nullable=False, unique=True)
    discovered_at = db.Column(db.DateTime, default=datetime.utcnow)

    # opcional: quién es el “salto” para llegar (R1->R2->R3)
    jump_via_ip = db.Column(db.String(64), nullable=True)

class Interface(db.Model):
    __tablename__ = "interfaces"
    id = db.Column(db.Integer, primary_key=True)
    router_id = db.Column(db.Integer, db.ForeignKey("routers.id"), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    ip = db.Column(db.String(64), nullable=True)
    mask = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(64), nullable=True)

class Event(db.Model):
    __tablename__ = "events"
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, default=datetime.utcnow)
    level = db.Column(db.String(16), default="INFO")
    event_type = db.Column(db.String(64), nullable=False)
    message = db.Column(db.Text, nullable=False)
