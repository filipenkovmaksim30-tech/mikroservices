import json
import struct

import pytest

from catalog_service.media.glb_validation import (
    MAX_GLB_BYTES,
    InvalidProductModelError,
    validate_product_glb,
)


def make_glb(document: dict | None = None, binary: bytes | None = None) -> bytes:
    document = document or {"asset": {"version": "2.0"}}
    payload = json.dumps(document).encode("utf-8")
    payload += b" " * (-len(payload) % 4)
    chunks = struct.pack("<I4s", len(payload), b"JSON") + payload
    if binary is not None:
        padded = binary + b"\x00" * (-len(binary) % 4)
        chunks += struct.pack("<I4s", len(padded), b"BIN\x00") + padded
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def test_valid_embedded_glb() -> None:
    document = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 3}]}
    validate_product_glb(make_glb(document, b"abc"))


@pytest.mark.parametrize("data", [b"", b"not glb"])
def test_empty_and_garbage_are_rejected(data: bytes) -> None:
    with pytest.raises(InvalidProductModelError):
        validate_product_glb(data)


def test_oversize_is_rejected() -> None:
    with pytest.raises(InvalidProductModelError):
        validate_product_glb(b"x" * (MAX_GLB_BYTES + 1))


def test_wrong_header_version_and_total_length_are_rejected() -> None:
    valid = make_glb()
    for data in (
        b"xxxx" + valid[4:],
        valid[:4] + struct.pack("<I", 1) + valid[8:],
        valid[:8] + struct.pack("<I", len(valid) + 4) + valid[12:],
    ):
        with pytest.raises(InvalidProductModelError):
            validate_product_glb(data)


def test_invalid_chunk_length_and_json_are_rejected() -> None:
    valid = make_glb()
    invalid_length = valid[:12] + struct.pack("<I", 999) + valid[16:]
    invalid_json = valid.replace(b'"asset"', b'"xxxxx"')
    for data in (invalid_length, invalid_json):
        with pytest.raises(InvalidProductModelError):
            validate_product_glb(data)


@pytest.mark.parametrize(
    "document",
    [
        {"asset": {"version": "1.0"}},
        {
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "https://example.test/data.bin", "byteLength": 1}],
        },
        {"asset": {"version": "2.0"}, "images": [{"uri": "texture.png"}]},
        {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 8}]},
    ],
)
def test_unsupported_or_external_resources_are_rejected(document: dict) -> None:
    with pytest.raises(InvalidProductModelError):
        validate_product_glb(make_glb(document, b"abc"))
