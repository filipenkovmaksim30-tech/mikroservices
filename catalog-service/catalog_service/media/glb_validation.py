import json
import struct

MAX_GLB_BYTES = 25 * 1024 * 1024
_HEADER = struct.Struct("<4sII")
_CHUNK_HEADER = struct.Struct("<I4s")


class InvalidProductModelError(ValueError):
    pass


def validate_product_glb(data: bytes) -> None:
    if not data or len(data) > MAX_GLB_BYTES:
        raise InvalidProductModelError("GLB must be between 1 byte and 25 MiB")
    if len(data) < _HEADER.size + _CHUNK_HEADER.size:
        raise InvalidProductModelError("Invalid GLB header")

    magic, version, declared_length = _HEADER.unpack_from(data)
    if magic != b"glTF" or version != 2 or declared_length != len(data):
        raise InvalidProductModelError("Invalid GLB header, version or length")

    chunks: list[tuple[bytes, bytes]] = []
    offset = _HEADER.size
    while offset < len(data):
        if len(data) - offset < _CHUNK_HEADER.size:
            raise InvalidProductModelError("Truncated GLB chunk header")
        length, kind = _CHUNK_HEADER.unpack_from(data, offset)
        offset += _CHUNK_HEADER.size
        if length % 4 or length > len(data) - offset:
            raise InvalidProductModelError("Invalid GLB chunk length")
        chunks.append((kind, data[offset : offset + length]))
        offset += length

    if not 1 <= len(chunks) <= 2 or chunks[0][0] != b"JSON":
        raise InvalidProductModelError("GLB must start with one JSON chunk")
    if len(chunks) == 2 and chunks[1][0] != b"BIN\x00":
        raise InvalidProductModelError("Invalid GLB binary chunk")

    try:
        document = json.loads(chunks[0][1].rstrip(b" ").decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidProductModelError("Invalid GLB JSON") from exc

    if not isinstance(document, dict) or not isinstance(document.get("asset"), dict):
        raise InvalidProductModelError("Invalid GLB asset")
    if document["asset"].get("version") != "2.0":
        raise InvalidProductModelError("Only glTF 2.0 is supported")

    binary_length = len(chunks[1][1]) if len(chunks) == 2 else 0
    buffers = document.get("buffers", [])
    images = document.get("images", [])
    if not isinstance(buffers, list) or not isinstance(images, list):
        raise InvalidProductModelError("Invalid GLB resources")
    for buffer in buffers:
        if not isinstance(buffer, dict) or "uri" in buffer:
            raise InvalidProductModelError("External resources are not supported")
        byte_length = buffer.get("byteLength")
        if type(byte_length) is not int or byte_length < 0 or byte_length > binary_length:
            raise InvalidProductModelError("Invalid GLB buffer length")
    if len(buffers) > 1:
        raise InvalidProductModelError("GLB supports one binary buffer")
    for image in images:
        if not isinstance(image, dict) or "uri" in image:
            raise InvalidProductModelError("External resources are not supported")
