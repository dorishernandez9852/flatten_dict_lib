"""Flatten and restore nested mappings with a configurable separator."""

from typing import Any, Dict, Mapping, MutableMapping, Tuple


# A flattened key is a tuple of path components. Using a tuple (not a
# string joined by a separator) as the intermediate representation makes
# unflattening unambiguous regardless of separator choice, and keeps the
# separator concern purely at the string<->tuple boundary.
_FlatKey = Tuple[str, ...]


def _is_mapping(obj: Any) -> bool:
    """Return True only for *Mapping* instances.

    We intentionally exclude UserDict subclasses here is not necessary --
    isinstance(obj, Mapping) already covers them. The key design decision
    is that we treat only Mappings as nesting: lists, tuples, sets, and
    strings are treated as leaf values. This is deliberate -- flattening
    sequences would require index-based keys ("0", "1", ...) which collide
    with string keys and produce surprising round-trips. If you need to
    flatten sequences, map them to dicts first.
    """
    return isinstance(obj, Mapping)


def _flatten_into(
    obj: Any,
    prefix: _FlatKey,
    sep: str,
    out: Dict[_FlatKey, Any],
) -> None:
    """Recursively walk *obj*, writing leaf paths into *out*.

    Internal helper -- callers ensure *out* is a fresh dict.
    """
    if _is_mapping(obj):
        if len(obj) == 0:
            # An empty mapping is a leaf: we cannot descend further, so
            # the prefix itself is the path to this empty mapping.
            if prefix:
                out[prefix] = {}
            return
        for key, value in obj.items():
            if not isinstance(key, str):
                raise TypeError(
                    "flatten only supports string keys; got "
                    f"{type(key).__name__}: {key!r}"
                )
            _flatten_into(value, prefix + (key,), sep, out)
    else:
        out[prefix] = obj


def flatten(
    obj: Mapping[str, Any],
    sep: str = ".",
) -> Dict[str, Any]:
    """Flatten a nested mapping into a single-level dict keyed by joined paths.

    Nested keys are joined with *sep*::

        >>> flatten({"a": {"b": 1}})
        {'a.b': 1}

    Empty nested mappings are preserved as empty-dict leaf values at their
    path::

        >>> flatten({"a": {}})
        {'a': {}}

    Non-mapping values (lists, strings, numbers, None, ...) are treated as
    leaves and never recursed into.

    Raises:
        TypeError: if any mapping key is not a string. Non-string keys are
            rejected because joining them with a string separator is
            type-incoherent and would round-trip incorrectly.
    """
    if not _is_mapping(obj):
        raise TypeError(f"flatten expects a Mapping; got {type(obj).__name__}")
    if not isinstance(sep, str):
        raise TypeError(f"sep must be a str; got {type(sep).__name__}")

    flat: Dict[_FlatKey, Any] = {}
    _flatten_into(obj, (), sep, flat)
    return {_join_unescaped(k, sep): v for k, v in flat.items()}


def _join_unescaped(parts: Tuple[str, ...], sep: str) -> str:
    """Join *parts* with *sep*, escaping occurrences of *sep* within parts.

    Each part is a single path segment that came from a single original
    key. If that key itself contained the separator, we must escape it so
    that unflattening can split the joined string back into the original
    segments. We use a backslash escape, and escape backslashes themselves
    so the encoding is reversible.
    """
    escaped = []
    for part in parts:
        # Order matters: escape backslash first, otherwise we would
        # double-escape backslashes introduced by escaping separators.
        part = part.replace("\\", "\\\\")
        if sep:
            part = part.replace(sep, "\\" + sep)
        escaped.append(part)
    return sep.join(escaped)


def _split_escaped(joined: str, sep: str) -> Tuple[str, ...]:
    """Split *joined* on unescaped occurrences of *sep*.

    Inverse of :func:`_join_unescaped`.
    """
    if sep == "":
        # An empty separator means each character is its own segment.
        # This is a degenerate but well-defined case for round-tripping.
        return tuple(joined)

    parts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(joined)
    slen = len(sep)
    while i < n:
        ch = joined[i]
        if ch == "\\":
            if i + 1 < n:
                nxt = joined[i + 1]
                # We only un-escape \sep and \\ here. Any other \x is
                # left as a literal backslash followed by x, preserving the
                # original content verbatim.
                if nxt == "\\":
                    buf.append("\\")
                    i += 2
                    continue
                if joined[i + 1 : i + 1 + slen] == sep:
                    buf.append(sep)
                    i += 1 + slen
                    continue
            # Lone backslash or backslash before non-special: keep literal.
            buf.append(ch)
            i += 1
            continue
        if joined[i : i + slen] == sep:
            parts.append("".join(buf))
            buf = []
            i += slen
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return tuple(parts)


def unflatten(
    flat: Mapping[str, Any],
    sep: str = ".",
) -> Dict[str, Any]:
    """Restore a nested mapping from a flattened dict produced by :func:`flatten`.

    Inverse of :func:`flatten` when the same *sep* is used and keys do not
    contain unescaped separators::

        >>> unflatten({"a.b": 1})
        {'a': {'b': 1}}

    If a key in *flat* contains the separator as a literal substring, it
    will be interpreted as a path boundary unless it was escaped. Keys
    produced by :func:`flatten` are always safe because flatten escapes
    separator characters that appear inside individual segment strings.

    A leaf value that is an empty dict is treated as an empty mapping at
    that path, mirroring :func:`flatten`'s handling of empty nested dicts.

    Raises:
        TypeError: if *flat* contains non-string keys.
    """
    if not _is_mapping(flat):
        raise TypeError(f"unflatten expects a Mapping; got {type(flat).__name__}")
    if not isinstance(sep, str):
        raise TypeError(f"sep must be a str; got {type(sep).__name__}")

    result: Dict[str, Any] = {}
    for joined, value in flat.items():
        if not isinstance(joined, str):
            raise TypeError(
                "unflatten only supports string keys; got "
                f"{type(joined).__name__}: {joined!r}"
            )
        segments = _split_escaped(joined, sep)
        if len(segments) == 0:
            # Only possible with sep == "" and joined == ""; this maps to
            # the root-level empty-string key.
            result[""] = value
            continue
        current: MutableMapping[str, Any] = result
        for i, seg in enumerate(segments):
            is_last = i == len(segments) - 1
            if is_last:
                if seg in current and isinstance(current[seg], dict) and isinstance(value, dict):
                    # Both old and new values are dicts; merge to avoid
                    # clobbering a sibling branch that was set first.
                    current[seg] = _merge_dicts(current[seg], value)
                else:
                    current[seg] = value
            else:
                if seg not in current or not isinstance(current[seg], dict):
                    current[seg] = {}
                current = current[seg]
    return result


def _merge_dicts(a: Dict[str, Any], b: Mapping[str, Any]) -> Dict[str, Any]:
    """Shallowly merge *b* into a copy of *a*, recursing one level for dict values.

    Used when two flattened keys map to overlapping prefixes and both
    contribute dict values at the overlap point.
    """
    out: Dict[str, Any] = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _merge_dicts(out[k], v)
        else:
            out[k] = v
    return out
