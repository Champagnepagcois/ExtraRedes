from __future__ import annotations
import socket
import paramiko
from netmiko import ConnectHandler

class JumpSession:
    """
    Mantiene una sesión SSH (paramiko) contra el salto para reutilizar el transporte.
    """
    def __init__(self, jump_host: str, username: str, password: str,
                 port: int = 22, timeout: int = 10, auth_timeout: int = 10):
        self.jump_host = jump_host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.auth_timeout = auth_timeout

        self.client = None
        self.transport = None

    def open(self) -> None:
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(
            hostname=self.jump_host,
            port=self.port,
            username=self.username,
            password=self.password,
            timeout=self.timeout,
            auth_timeout=self.auth_timeout,
            look_for_keys=False,
            allow_agent=False,
        )
        self.transport = self.client.get_transport()

    def close(self) -> None:
        try:
            if self.client:
                self.client.close()
        finally:
            self.client = None
            self.transport = None

    def open_direct_channel(self, dest_host: str, dest_port: int = 22):
        if not self.transport or not self.transport.is_active():
            raise RuntimeError("Jump transport no está activo. Llama open() primero.")
        # src_addr es simbólico aquí; paramiko requiere una tupla
        src_addr = ("127.0.0.1", 0)
        dest_addr = (dest_host, dest_port)
        return self.transport.open_channel("direct-tcpip", dest_addr, src_addr)

def netmiko_connect_direct(host: str, username: str, password: str,
                           device_type: str = "cisco_ios", timeout: int = 10):
    return ConnectHandler(
        device_type=device_type,
        host=host,
        username=username,
        password=password,
        conn_timeout=timeout,
        banner_timeout=timeout,
        auth_timeout=timeout,
        fast_cli=False,
    )

def netmiko_connect_via_jump(jump: JumpSession, dest_host: str, username: str, password: str,
                             device_type: str = "cisco_ios", timeout: int = 10):
    channel = jump.open_direct_channel(dest_host, 22)
    return ConnectHandler(
        device_type=device_type,
        host=dest_host,           # solo para referencia/log
        username=username,
        password=password,
        sock=channel,             # <-- magia: tráfico via salto
        conn_timeout=timeout,
        banner_timeout=timeout,
        auth_timeout=timeout,
        fast_cli=False,
    )
