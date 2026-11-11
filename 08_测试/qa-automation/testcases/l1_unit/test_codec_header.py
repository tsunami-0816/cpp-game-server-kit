# -*- coding: utf-8 -*-
"""L1 单元：4B 大端长度头编解码规则（复刻 include/proto_codec/Codec.h 口径）。"""
import struct

import pytest

MAX_BODY = 4 * 1024 * 1024
HEADER_LEN = 4


def encode(body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + body


def try_decode_header(buf: bytes):
    if len(buf) < HEADER_LEN:
        return None
    (ln,) = struct.unpack(">I", buf[:HEADER_LEN])
    if ln == 0 or ln > MAX_BODY:
        return None
    return ln


@pytest.mark.l1
def test_encode_big_endian_length_prefix():
    body = b"hello"
    pkt = encode(body)
    assert len(pkt) == HEADER_LEN + len(body)
    (ln,) = struct.unpack(">I", pkt[:HEADER_LEN])
    assert ln == 5
    assert pkt[HEADER_LEN:] == body


@pytest.mark.l1
def test_decode_rejects_truncated_header():
    assert try_decode_header(b"\x00\x00") is None


@pytest.mark.l1
def test_decode_rejects_zero_length():
    pkt = struct.pack(">I", 0) + b""
    assert try_decode_header(pkt) is None


@pytest.mark.l1
def test_decode_rejects_oversize_body():
    pkt = struct.pack(">I", MAX_BODY + 1)
    assert try_decode_header(pkt) is None


@pytest.mark.l1
def test_decode_accepts_valid_length():
    body = b"x" * 100
    pkt = encode(body)
    assert try_decode_header(pkt) == 100
