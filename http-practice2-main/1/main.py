
import json
from pathlib import Path

user = {
    "id": 1,
    "name": "Ivan",
    "email": "ivan@example.com",
    "active": True
}

json_data = json.dumps(
    user,
    ensure_ascii=False,
    separators=(",", ":")
).encode("utf-8")


def varint(value):
    result = bytearray()

    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7

    result.append(value)
    return bytes(result)


def encode_number(field, value):
    return varint(field << 3) + varint(value)


def encode_string(field, value):
    data = value.encode("utf-8")
    return (
        varint((field << 3) | 2)
        + varint(len(data))
        + data
    )


protobuf_data = (
    encode_number(1, user["id"])
    + encode_string(2, user["name"])
    + encode_string(3, user["email"])
    + encode_number(4, int(user["active"]))
)


folder = Path(__file__).resolve().parent

(folder / "user.json").write_bytes(json_data)
(folder / "user.pb").write_bytes(protobuf_data)

json_size = len(json_data)
protobuf_size = len(protobuf_data)

print("JSON:", json_size, "байт")
print("Protobuf:", protobuf_size, "байт")

print(
    "Экономия:",
    round((1 - protobuf_size / json_size) * 100, 2),
    "%"
)

print("\nФайлы user.json и user.pb созданы!")
