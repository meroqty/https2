
import socket
import threading
import base64
import hashlib
import os
import struct

HOST = "127.0.0.1"
PORT = 9002
MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

running = True


def read_exact(sock, n):
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("Соединение закрыто")
        data += chunk
    return data


def send_frame(sock, opcode, data=b""):
    mask = os.urandom(4)
    frame = bytearray([0x80 | opcode])
    length = len(data)

    if length < 126:
        frame.append(0x80 | length)
    elif length < 65536:
        frame.append(0x80 | 126)
        frame.extend(struct.pack("!H", length))
    else:
        frame.append(0x80 | 127)
        frame.extend(struct.pack("!Q", length))

    frame.extend(mask)
    frame.extend(
        b ^ mask[i % 4] for i, b in enumerate(data)
    )

    sock.sendall(frame)


def recv_frame(sock):
    first, second = read_exact(sock, 2)
    opcode = first & 0x0F
    length = second & 0x7F

    if length == 126:
        length = struct.unpack("!H", read_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack("!Q", read_exact(sock, 8))[0]

    data = read_exact(sock, length)
    return opcode, data


def receive_messages(sock):
    global running

    try:
        while running:
            opcode, data = recv_frame(sock)

            if opcode == 1:
                print("\n" + data.decode("utf-8"))

            elif opcode == 10:
                print("\n[PONG] Сервер отвечает!")

            elif opcode == 9:
                send_frame(sock, 10, data)

            elif opcode == 8:
                print("\nСервер закрыл соединение")
                break

    except (OSError, ConnectionError):
        pass

    running = False


name = input("Введите имя: ")

with socket.create_connection((HOST, PORT)) as sock:
    key = base64.b64encode(os.urandom(16)).decode()

    request = (
        "GET / HTTP/1.1\r\n"
        f"Host: {HOST}:{PORT}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n\r\n"
    )

    sock.sendall(request.encode())

    response = b""
    while b"\r\n\r\n" not in response:
        response += sock.recv(1024)

    expected = base64.b64encode(
        hashlib.sha1((key + MAGIC).encode()).digest()
    ).decode()

    if b"101 Switching Protocols" not in response:
        raise ConnectionError("Ошибка подключения")

    if f"Sec-WebSocket-Accept: {expected}".encode() not in response:
        raise ConnectionError("Неверный ответ сервера")

    print("Подключено к чату!")
    print("Команды: /ping, /exit")

    threading.Thread(
        target=receive_messages,
        args=(sock,),
        daemon=True
    ).start()

    while running:
        try:
            message = input()
        except (EOFError, KeyboardInterrupt):
            message = "/exit"

        if message == "/exit":
            send_frame(sock, 8, struct.pack("!H", 1000))
            break

        elif message == "/ping":
            send_frame(sock, 9, b"ping")

        elif message:
            send_frame(
                sock, 1,
                f"{name}: {message}".encode("utf-8")
            )
