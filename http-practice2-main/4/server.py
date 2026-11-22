
import socket
import threading
import hashlib
import base64
import struct

HOST = "127.0.0.1"
PORT = 9002
MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

clients = []
lock = threading.Lock()


def read_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Соединение закрыто")
        data += chunk
    return data


def send_frame(sock, opcode, data=b"", masked=False):
    frame = bytearray([0x80 | opcode])
    length = len(data)

    if length < 126:
        frame.append(length)
    elif length < 65536:
        frame.append(126)
        frame.extend(struct.pack("!H", length))
    else:
        frame.append(127)
        frame.extend(struct.pack("!Q", length))

    sock.sendall(frame + data)


def recv_frame(sock):
    first, second = read_exact(sock, 2)
    opcode = first & 0x0F
    length = second & 0x7F

    if length == 126:
        length = struct.unpack("!H", read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(sock, 8))[0]

    if not second & 0x80:
        raise ValueError("Клиентский кадр без маски")

    mask = read_exact(sock, 4)
    data = read_exact(sock, length)

    return opcode, bytes(
        b ^ mask[i % 4] for i, b in enumerate(data)
    )


def broadcast(message, sender):
    data = message.encode("utf-8")

    with lock:
        receivers = [c for c in clients if c is not sender]

    for client in receivers:
        try:
            send_frame(client, 1, data)
        except OSError:
            with lock:
                if client in clients:
                    clients.remove(client)


def handle_client(conn):
    try:
        request = b""
        while b"\r\n\r\n" not in request:
            chunk = conn.recv(1024)
            if not chunk:
                return
            request += chunk

        key = None
        for line in request.decode().split("\r\n"):
            if line.lower().startswith("sec-websocket-key:"):
                key = line.split(":", 1)[1].strip()

        if not key:
            return

        accept = base64.b64encode(
            hashlib.sha1((key + MAGIC).encode()).digest()
        ).decode()

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n\r\n"
        )

        conn.sendall(response.encode())

        with lock:
            clients.append(conn)

        print("Клиент подключился!")

        while True:
            opcode, data = recv_frame(conn)

            if opcode == 8:
                send_frame(conn, 8, data)
                break

            if opcode == 9:
                send_frame(conn, 10, data)
                print("PING -> PONG")
                continue

            if opcode == 1:
                message = data.decode("utf-8")
                print("Сообщение:", message)
                broadcast(message, conn)

    except (OSError, ConnectionError, ValueError) as e:
        print("Ошибка:", e)

    finally:
        with lock:
            if conn in clients:
                clients.remove(conn)

        conn.close()
        print("Клиент отключился")


with socket.socket() as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"Чат запущен: ws://{HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(
            target=handle_client,
            args=(conn,),
            daemon=True
        ).start()
