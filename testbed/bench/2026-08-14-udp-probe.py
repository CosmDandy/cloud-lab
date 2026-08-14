import socket, sys
targets = [("8.8.8.8", 53, b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x07example\x03com\x00\x00\x01\x00\x01", "DNS 8.8.8.8:53 (контроль)"),
           ("167.104.104.131", 39443, b"PROBE-UDP", "своя нода sto-01:39443")]
for host, port, payload, label in targets:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(6)
    try:
        s.sendto(payload, (host, port))
        data, _ = s.recvfrom(2048)
        print(f"{label:34} ОТВЕТ получен ({len(data)} байт)")
    except socket.timeout:
        print(f"{label:34} ТИШИНА (таймаут 6 с)")
    except Exception as e:
        print(f"{label:34} ОШИБКА {e}")
    finally:
        s.close()
