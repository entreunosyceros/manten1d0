"""Descubrimiento de dispositivos en la red local."""

import socket
import subprocess
import threading

import psutil
import tkinter as tk
from tkinter import messagebox

try:
    import nmap
except ImportError:
    nmap = None


def obtener_red_local():
    for _interface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                return f"{addr.address}/{netmask_to_cidr(addr.netmask)}"
    return None


def netmask_to_cidr(netmask):
    return sum(bin(int(x)).count("1") for x in netmask.split("."))


def _tabla_arp():
    tabla = {}
    try:
        with open("/proc/net/arp", encoding="utf-8") as archivo:
            next(archivo)
            for linea in archivo:
                partes = linea.split()
                if len(partes) >= 4 and partes[3] != "00:00:00:00:00:00":
                    tabla[partes[0]] = partes[3]
    except OSError:
        pass
    return tabla


def _resolver_nombre(ip):
    try:
        nombre = socket.getfqdn(ip)
        if nombre and nombre != ip:
            return nombre
    except OSError:
        pass
    return "—"


def _ordenar_ip(ip):
    try:
        return tuple(int(octeto) for octeto in ip.split("."))
    except ValueError:
        return (999, 999, 999, 999)


def encontrar_dispositivos_en_red():
    if nmap is None:
        raise RuntimeError("Falta el módulo python-nmap. Instálalo con: sudo apt install python3-nmap")
    red = obtener_red_local()
    if not red:
        return []
    escaner = nmap.PortScanner()
    escaner.scan(hosts=red, arguments="-sn")
    hosts = list(escaner.all_hosts())
    if not hosts:
        return []

    samba = set()
    try:
        puertos = nmap.PortScanner()
        puertos.scan(
            hosts=" ".join(hosts),
            arguments="-p 139,445 --open --max-retries 1 --host-timeout 4s",
        )
        for host in puertos.all_hosts():
            tcp = puertos[host].get("tcp") or {}
            if any(tcp.get(puerto, {}).get("state") == "open" for puerto in (139, 445)):
                samba.add(host)
    except Exception:
        pass

    arp = _tabla_arp()
    dispositivos = []
    for host in hosts:
        info = escaner[host]
        nombre = info.hostname() or _resolver_nombre(host)
        mac = (info.get("addresses") or {}).get("mac") or arp.get(host) or "—"
        dispositivos.append({
            "ip": host,
            "nombre": nombre or "—",
            "mac": mac,
            "samba": host in samba,
        })
    dispositivos.sort(key=lambda item: _ordenar_ip(item["ip"]))
    return dispositivos


def formatear_dispositivo(item):
    samba = "Samba: sí" if item.get("samba") else "Samba: no"
    return f"{item['ip']:<16} {item.get('nombre') or '—':<22} {item.get('mac') or '—':<18} {samba}"


def ip_de_linea(texto, lista=None):
    if lista is not None:
        seleccion = lista.curselection()
        dispositivos = getattr(lista, "dispositivos", None)
        if dispositivos and seleccion:
            return dispositivos[seleccion[0]]["ip"]
    return (texto or "").split()[0]


def abrir_administrador_de_archivos(ip):
    try:
        subprocess.Popen(["nautilus", f"smb://{ip}"])
    except FileNotFoundError:
        messagebox.showerror("Error", "Administrador de archivos no encontrado.")
    except Exception as e:
        messagebox.showerror("Error", f"Error al abrir el administrador de archivos: {e}")


def doble_clic(_, lista_dispositivos):
    ip = ip_de_linea(lista_dispositivos.get(tk.ACTIVE), lista_dispositivos)
    if not ip:
        return
    threading.Thread(target=abrir_administrador_de_archivos, args=(ip,), daemon=True).start()
