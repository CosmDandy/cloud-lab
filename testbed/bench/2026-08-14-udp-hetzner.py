import socket
for host, port, label in [("65.108.214.181", 39443, "Hetzner UDP/39443"),
                          ("167.104.104.131", 39443, "HostHatch UDP/39443 (контроль)")]:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(6)
    try:
        s.sendto(b"PROBE", (host, port)); d, _ = s.recvfrom(2048)
        print(f"{label:36} ОТВЕТ ({len(d)} байт)")
    except socket.timeout:
        print(f"{label:36} ТИШИНА")
    finally: s.close()
