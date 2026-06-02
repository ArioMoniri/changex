"""RFC 8785 JSON Canonicalization Scheme (JCS) + sha256 hash chaining.

A single, pinned canonicalization is what makes the hash chain **reproducible
across languages** (including the future Rust viewer): ``canonical(event)`` must
be byte-identical everywhere. We implement the subset of RFC 8785 that the
journal needs — our event payloads only contain JSON strings, integers, floats
that are whole numbers, booleans, ``null``, objects and arrays.

JCS rules implemented here:

* Object keys are sorted by their UTF-16 code-unit sequence.
* No insignificant whitespace.
* Strings use the JSON minimal escaping from RFC 8785 section 3.2.2.3.
* Integers are emitted without a decimal point; non-integer numbers use the
  ECMAScript ``Number.prototype.toString`` shortest round-trip form (we restrict
  journal numbers to integers, so this path is defensive only).

Threat model
------------
The chain gives **tamper-evidence** for accidental corruption and naive
tampering: editing any past event invalidates every later hash. It is **not**
adversarial integrity — an attacker who controls the ``.changex`` can recompute
the whole chain. Real integrity requires out-of-band storage or signing
(deferred to M6). Do not represent ``verify()`` as proof against a motivated
adversary.
"""

from __future__ import annotations

import hashlib
from typing import Any

# Per RFC 8785 3.2.2.3: control chars get \uXXXX except the named short escapes.
_ESCAPE_MAP = {
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def _escape_string(value: str) -> str:
    out: list[str] = ['"']
    for ch in value:
        code = ord(ch)
        if code in _ESCAPE_MAP:
            out.append(_ESCAPE_MAP[code])
        elif code < 0x20:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _serialize_number(value: int | float) -> str:
    if isinstance(value, bool):  # bool is a subclass of int; guard explicitly
        raise TypeError("bool is not a JCS number")
    if isinstance(value, int):
        return str(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("NaN/Infinity are not valid JCS numbers")
    if value.is_integer():
        return str(int(value))
    # Shortest round-trip; Python's repr matches ECMAScript for our value range.
    return repr(value)


def _serialize(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return _escape_string(value)
    if isinstance(value, (int, float)):
        return _serialize_number(value)
    if isinstance(value, dict):
        # Sort by UTF-16 code units. Python str comparison is by code point;
        # for the BMP-only keys we use this is equivalent. Keys must be strings.
        items = sorted(value.items(), key=lambda kv: _utf16_key(kv[0]))
        body = ",".join(f"{_escape_string(k)}:{_serialize(v)}" for k, v in items)
        return "{" + body + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(_serialize(v) for v in value) + "]"
    raise TypeError(f"value of type {type(value).__name__} is not JCS-serializable")


def _utf16_key(key: str) -> tuple[int, ...]:
    if not isinstance(key, str):
        raise TypeError("JCS object keys must be strings")
    return tuple(key.encode("utf-16-be"))


def canonicalize(obj: dict[str, Any]) -> bytes:
    """Return the RFC 8785 (JCS) canonical UTF-8 encoding of ``obj``."""
    return _serialize(obj).encode("utf-8")


def chain_hash(prev_hash: str | None, event: dict[str, Any]) -> str:
    """Return ``sha256(prev_hash + JCS(event))`` as a lowercase hex digest.

    ``prev_hash`` is the empty string when ``None`` (the genesis link). The
    ``event`` dict passed in must **exclude** its own ``hash`` and ``prev_hash``
    fields so the digest is over content only.
    """
    digest = hashlib.sha256()
    digest.update((prev_hash or "").encode("utf-8"))
    digest.update(canonicalize(event))
    return digest.hexdigest()


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex sha256 of raw ``data`` (used for baselines)."""
    return hashlib.sha256(data).hexdigest()
