from flask import Flask, request, jsonify
from config import Config
from db import db
from models import Router, Interface, Event
from services.routing_seed_jump import configure_routing_seed_jump

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.get("/api/health")
    def health():
        return {"ok": True}

    # 1) Configurar enrutamiento (RIP/OSPF) sin rutas previas: semilla + saltos
    @app.post("/api/routing/configure")
    def routing_configure():
        """
        Body JSON:
        {
          "seed_ip": "148.204.58.1",      // IP de R1 accesible desde la VM
          "ssh_user": "cisco",
          "ssh_pass": "cisco",
          "protocol": "OSPF",            // o "RIP"
          "max_devices": 3
        }
        """
        body = request.get_json(force=True)
        seed_ip = body["seed_ip"]
        ssh_user = body["ssh_user"]
        ssh_pass = body["ssh_pass"]
        protocol = body["protocol"]
        max_devices = int(body.get("max_devices", 3))

        try:
            result = configure_routing_seed_jump(
                seed_ip=seed_ip,
                ssh_user=ssh_user,
                ssh_pass=ssh_pass,
                protocol=protocol,
                max_devices=max_devices,
                timeout=app.config["SSH_CONNECT_TIMEOUT"],
            )

            # Guardar evidencia en BD (mínimo)
            ev = Event(event_type="ROUTING_CONFIG", message=f"Se configuró {protocol} desde semilla {seed_ip}")
            db.session.add(ev)

            # Registrar routers detectados por salto (R1,R2,R3...)
            for d in result["devices"]:
                ip = d["mgmt_ip"]
                via = d["jump_via"]
                existing = Router.query.filter_by(mgmt_ip=ip).first()
                if not existing:
                    db.session.add(Router(mgmt_ip=ip, jump_via_ip=via))
            db.session.commit()

            return jsonify(result), 200

        except Exception as e:
            db.session.add(Event(level="ERROR", event_type="ROUTING_CONFIG", message=str(e)))
            db.session.commit()
            return jsonify({"error": str(e)}), 400

    # 2) Explorar red (placeholder para que lo completes)
    @app.post("/api/discovery/run")
    def discovery_run():
        # Aquí normalmente harías: SNMP/SSH discovery, topología, guardar BD, generar gráfico
        return jsonify({
            "status": "TODO",
            "hint": "Implementa descubrimiento (SNMP/SSH), guarda topología y genera gráfico."
        }), 200

    # 3) Routers (leer BD)
    @app.get("/api/routers")
    def routers_list():
        routers = Router.query.order_by(Router.id.asc()).all()
        return jsonify([{
            "id": r.id,
            "hostname": r.hostname,
            "mgmt_ip": r.mgmt_ip,
            "jump_via_ip": r.jump_via_ip,
            "discovered_at": r.discovered_at.isoformat()
        } for r in routers]), 200

    @app.get("/api/routers/<int:router_id>")
    def routers_get(router_id: int):
        r = Router.query.get_or_404(router_id)
        return jsonify({
            "id": r.id,
            "hostname": r.hostname,
            "mgmt_ip": r.mgmt_ip,
            "jump_via_ip": r.jump_via_ip,
            "discovered_at": r.discovered_at.isoformat()
        }), 200

    # 4) Alertas/eventos (leer BD)
    @app.get("/api/alerts")
    def alerts_list():
        events = Event.query.order_by(Event.ts.desc()).limit(200).all()
        return jsonify([{
            "id": e.id,
            "ts": e.ts.isoformat(),
            "level": e.level,
            "event_type": e.event_type,
            "message": e.message
        } for e in events]), 200

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
