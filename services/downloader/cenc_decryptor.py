"""
CENC Decryption Utilities for ByteDance & Short Drama Streaming Platforms
"""

import base64
from typing import Optional


def unwrap_spade(spade_a_b64: str) -> str:
    """
    Unwraps ByteDance spade_a / player_access_key into 16-byte (32 hex) AES-128-CTR content key.
    Enables native FFmpeg CENC decryption and prevents scrambled video / broken colors.
    """
    if not spade_a_b64:
        return ""
    try:
        spade = base64.b64decode(spade_a_b64)
    except Exception:
        return ""

    def _popcount(x): return bin(x & 0xffffffff).count("1")
    def _s8(v): v &= 0xff; return v - 256 if v >= 128 else v
    def _strncmp0(a, b, n):
        for k in range(n):
            ca = a[k] if k < len(a) else 0
            cb = b[k] if k < len(b) else 0
            if ca != cb: return False
            if ca == 0: return True
        return True

    for flag in [1, 0]:
        L = len(spade)
        if L < 3:
            continue
        bVar5 = spade[0] ^ spade[1] ^ spade[2]
        iVar9 = bVar5 - 0x30
        if iVar9 < 1:
            continue
        uVar1 = (L - bVar5) + 0x2f
        if uVar1 < 1 or 1 + uVar1 > L:
            continue
        dest = bytearray(spade[1:1 + uVar1])

        b16 = spade[L - iVar9 - 2]
        b14 = spade[L - iVar9 - 1]
        s1 = bytearray(iVar9)
        for i in range(iVar9):
            s1[i] = b14 ^ b16 ^ spade[i + (L - iVar9)]
        if _strncmp0(s1, b"app_v2", iVar9) or _strncmp0(s1, b"web_v2", iVar9):
            continue

        b14, b16 = 0x55, 0xfa
        for i in range(uVar1):
            b6 = dest[i]
            u18 = _popcount(i)
            b3, b7 = b6, b14
            if i & 1:
                b3, b7, b16 = b16, b6, b14
            cVar4 = (u18 + 0x15) if flag else _s8(-0x15 - u18)
            dest[i] = (cVar4 + (b16 ^ b6)) & 0xff
            b14, b16 = b7, b3

        b0 = dest[0]
        if 0x30 <= b0 <= 0x39:
            u11 = b0 - 0x30
        elif 0x61 <= b0 <= 0x7a:
            u11 = b0 - 0x57
        else:
            continue
        iv9 = uVar1 - (u11 & 0xff)
        if iv9 < 2:
            continue
        k = bytes(dest[1:iv9]).decode("latin1", "replace")
        if len(k) == 32 and all(c in "0123456789abcdef" for c in k.lower()):
            return k.lower()
    return ""

