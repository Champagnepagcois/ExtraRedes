from __future__ import annotations
import ipaddress
import re

def parse_show_ip_int_brief(output: str):
    """
    Devuelve lista de dicts: {name, ip, status, protocol}
    Compatible con formato típico Cisco IOS.
    """
    lines = [l.rstrip() for l in output.splitlines() if l.strip()]
    items = []
    # Saltar encabezado
    for line in lines:
        if line.lower().startswith("interface"):
            continue
        # Ejemplo:
        # FastEthernet0/0 148.204.58.1 YES manual up up
        parts = re.split(r"\s+", line)
        if len(parts) < 6:
            continue
        name = parts[0]
        ip = parts[1]
        status = parts[-2]
        proto = parts[-1]
        items.append({"name": name, "ip": ip, "status": status, "protocol": proto})
    return items

def mask_from_running_config_int_section(run_cfg: str, int_name: str):
    """
    Busca en 'show running-config' la máscara para una interfaz.
    Retorna (ip, mask) o (None, None) si no encuentra.
    """
    # Muy simple: localizar bloque "interface X" hasta el siguiente "interface" o fin
    pattern = re.compile(rf"^interface\s+{re.escape(int_name)}\s*$", re.MULTILINE)
    m = pattern.search(run_cfg)
    if not m:
        return (None, None)
    start = m.end()
    end = len(run_cfg)
    m2 = re.search(r"^interface\s+\S+", run_cfg[start:], re.MULTILINE)
    if m2:
        end = start + m2.start()

    block = run_cfg[start:end]
    m_ip = re.search(r"ip address\s+(\d+\.\d+\.\d+\.\d+)\s+(\d+\.\d+\.\d+\.\d+)", block)
    if not m_ip:
        return (None, None)
    return (m_ip.group(1), m_ip.group(2))

def other_host_in_30(ip: str, mask: str) -> str | None:
    """
    Si ip/mask es /30, regresa el otro host del /30.
    """
    try:
        net = ipaddress.ip_network(f"{ip}/{mask}", strict=False)
    except Exception:
        return None
    if net.prefixlen != 30:
        return None
    hosts = list(net.hosts())
    if len(hosts) != 2:
        return None
    ip_obj = ipaddress.ip_address(ip)
    return str(hosts[1] if hosts[0] == ip_obj else hosts[0])
