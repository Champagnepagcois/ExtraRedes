from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional
from netmiko import ConnectHandler
from services.ssh_jump import JumpSession, netmiko_connect_direct, netmiko_connect_via_jump
from services.ios_parse import parse_show_ip_int_brief, mask_from_running_config_int_section, other_host_in_30

@dataclass
class DeviceHop:
    name: str               # "R1", "R2", "R3" (deducido o provisional)
    mgmt_ip: str            # IP a la que se entra por SSH
    jump_via: Optional[str] # IP del salto (None para semilla)

def _discover_next_hop_ip(conn) -> Optional[str]:
    """
    En un router ya accesible, detecta el vecino del enlace /30.
    Regla: busca interfaces con IP y saca máscara del running-config.
    Si encuentra /30, deduce el otro host.
    """
    ip_int = conn.send_command("show ip interface brief")
    parsed = parse_show_ip_int_brief(ip_int)

    run_cfg = conn.send_command("show running-config")
    for it in parsed:
        if it["ip"].lower() == "unassigned":
            continue
        int_name = it["name"]
        ip, mask = mask_from_running_config_int_section(run_cfg, int_name)
        if not ip or not mask:
            continue
        neigh = other_host_in_30(ip, mask)
        if neigh:
            return neigh
    return None

def _enable_rip(conn):
    # Muy estándar (ajusta versión/redistribución según tu profe)
    cmds = [
        "conf t",
        "router rip",
        "version 2",
        "no auto-summary",
        # red “catch-all”: en la práctica conviene calcular por interfaces,
        # pero para examen suele bastar declarar las principales redes.
        # Si quieres fino: leer redes de interfaces y añadir "network X".
        "end",
        "wr mem"
    ]
    return conn.send_config_set(cmds)

def _enable_ospf(conn, process_id: int = 1, area: int = 0):
    cmds = [
        "conf t",
        f"router ospf {process_id}",
        # igual: en examen suelen aceptar network 0.0.0.0 255.255.255.255 area 0
        # o declarar por redes. Aquí uso el comodín.
        f"network 0.0.0.0 255.255.255.255 area {area}",
        "end",
        "wr mem"
    ]
    return conn.send_config_set(cmds)

def configure_routing_seed_jump(
    seed_ip: str,
    ssh_user: str,
    ssh_pass: str,
    protocol: str,               # "RIP" | "OSPF"
    max_devices: int = 3,
    device_type: str = "cisco_ios",
    timeout: int = 10,
) -> Dict:
    """
    1) Conecta directo a R1 (semilla) desde VM
    2) Deduce IP de R2 por /30 y entra via jump
    3) Deduce IP de R3 por /30 y entra via jump
    4) En cada uno, configura RIP u OSPF
    """
    protocol = protocol.upper().strip()
    if protocol not in ("RIP", "OSPF"):
        raise ValueError("protocol debe ser RIP u OSPF")

    hops: List[DeviceHop] = []
    results = []

    # ---- R1 (directo) ----
    r1 = netmiko_connect_direct(seed_ip, ssh_user, ssh_pass, device_type=device_type, timeout=timeout)
    hops.append(DeviceHop(name="R1", mgmt_ip=seed_ip, jump_via=None))

    try:
        # Configurar en R1
        out = _enable_rip(r1) if protocol == "RIP" else _enable_ospf(r1)
        results.append({"device": "R1", "ip": seed_ip, "via": None, "configured": True, "output": out})

        current_conn = r1
        current_jump_ip = seed_ip  # salto para el siguiente

        # ---- R2..Rn (via jump) ----
        for idx in range(2, max_devices + 1):
            next_ip = _discover_next_hop_ip(current_conn)
            if not next_ip:
                results.append({"device": f"R{idx}", "configured": False, "error": "No se detectó siguiente salto /30"})
                break

            # Abrir jump (paramiko) hacia el router actual (como salto)
            jump = JumpSession(current_jump_ip, ssh_user, ssh_pass, timeout=timeout, auth_timeout=timeout)
            jump.open()
            try:
                nxt = netmiko_connect_via_jump(jump, next_ip, ssh_user, ssh_pass, device_type=device_type, timeout=timeout)
                try:
                    hops.append(DeviceHop(name=f"R{idx}", mgmt_ip=next_ip, jump_via=current_jump_ip))
                    out2 = _enable_rip(nxt) if protocol == "RIP" else _enable_ospf(nxt)
                    results.append({"device": f"R{idx}", "ip": next_ip, "via": current_jump_ip, "configured": True, "output": out2})

                    # Preparar el próximo salto
                    current_conn = nxt
                    current_jump_ip = next_ip
                finally:
                    try:
                        nxt.disconnect()
                    except Exception:
                        pass
            finally:
                jump.close()

    finally:
        try:
            r1.disconnect()
        except Exception:
            pass

    return {
        "protocol": protocol,
        "seed_ip": seed_ip,
        "devices": [h.__dict__ for h in hops],
        "results": results,
    }
