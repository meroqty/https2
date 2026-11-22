
import socket
import hashlib
import base64

HOST = "127.0.0.1"
PORT = 9001

def read_exact(conn, size):
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("Клиент отключился")
        data += chunk
    return data


def send_frame(conn, opcode, payload):
    header = bytes([0x80 | opcode])
    length = len(payload)

    if length < 126:
        header += bytes([length])
    elif length < 65536:
        header += bytes([126]) + length.to_bytes(2, "big")
    else:
        header += bytes([127]) + length.to_bytes(8, "big")

    conn.sendall(header + payload)


def receive_frame(conn):
    first, second = read_exact(conn, 2)
    opcode = first & 0x0F

    length = second & 0x7F

    if length == 126:
        length = int.from_bytes(read_exact(conn, 2), "big")
    elif length == 127:
        length = int.from_bytes(read_exact(conn, 8), "big")

    masked = bool(second & 0x80)

    if not masked:
        raise ValueError("Кадр клиента должен иметь mask")

    mask = read_exact(conn, 4)
    payload = read_exact(conn, length)

    data = bytes(
        byte ^ mask[i % 4]
        for i, byte in enumerate(payload)
    )

    return opcode, data


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()

    print(f"WebSocket-сервер: ws://{HOST}:{PORT}", flush=True)

    while True:
        conn, addr = server.accept()

        with conn:
            try:
                request = b""
                while b"\r\n\r\n" not in request:
                    request += conn.recv(1024)
                headers = request.decode("utf-8")
                key = None

                for line in headers.split("\r\n"):
                    if line.lower().startswith("sec-websocket-key:"):
                        key = line.split(":", 1)[1].strip()

                if not key:
                    continue

                magic = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

                accept = base64.b64encode(
                    hashlib.sha1((key + magic).encode()).digest()
                ).decode()

                response = (
                    "HTTP/1.1 101 Switching Protocols\r\n"
                    "Upgrade: websocket\r\n"
                    "Connection: Upgrade\r\n"
                    f"Sec-WebSocket-Accept: {accept}\r\n"
                    "\r\n"
                )

                conn.sendall(response.encode())
                print("Клиент подключился!")

                while True:
                    opcode, data = receive_frame(conn)

                    if opcode == 8:
                        send_frame(conn, 8, b"")
                        break

                    if opcode == 9:
                        send_frame(conn, 10, data)
                        continue

                    if opcode == 1:
                        message = data.decode("utf-8")
                        print("Получено:", message)

                        send_frame(conn, 1, data)
                        print("Отправлено обратно:", message)

            except (ConnectionError, OSError, ValueError) as error:
                print("Соединение закрыто:", error)
