# flatten_dict_lib

Flatten and restore nested mappings with a configurable separator.

## Usage

```python
from flatten_dict_lib import flatten, unflatten

flat = flatten({"a": {"b": 1, "c": 2}})
# {'a.b': 1, 'a.c': 2}

original = unflatten(flat)
# {'a': {'b': 1, 'c': 2}}
```

A custom separator can be passed to both functions:

```python
from flatten_dict_lib import flatten, unflatten

flat = flatten({"a": {"b": 1}}, sep="/")
# {'a/b': 1}

unflatten(flat, sep="/")
# {'a': {'b': 1}}
```

## Why this exists

There is no single standard "flatten a dict" in the Python ecosystem, and
the ad-hoc versions people write tend to break on empty mappings, keys
that contain the separator, or non-string keys. This library makes one
deliberate set of choices and tests them.

The trade-off: only `Mapping` instances are treated as nesting. Lists,
tuples, strings, `None`, and everything else are leaf values. If you
need to flatten sequences into index-keyed entries, convert them to
dicts first. This keeps round-trips lossless and avoids the
string-key-collides-with-integer-index problem.

## Edge cases you will hit

- **Keys containing the separator** are escaped with backslashes by
  `flatten` and correctly unescaped by `unflatten`. Backslashes in keys
  are themselves escaped. This means round-tripping is safe even with
  pathological keys like `{"a.b": {"c/d": 1}}`.
- **Empty nested mappings** (`{"a": {}}`) are preserved as empty-dict
  leaf values, not dropped. `unflatten` restores them to empty dicts.
- **Non-string keys** raise `TypeError`. Joining non-string keys with a
  string separator is type-incoherent and does not round-trip.
- If two flattened keys overlap such that one is a prefix of another and
  both contribute dict values (e.g. `{"a": {"z": 9}, "a.b": 1}`),
  `unflatten` merges them rather than clobbering.

## Exports

`flatten(obj: Mapping[str, Any], sep: str = ".") -> Dict[str, Any]`
`unflatten(flat: Mapping[str, Any], sep: str = ".") -> Dict[str, Any]`

## Design notes

The window stores values eagerly rather than keeping running aggregates. Running
sums drift with floating point over long streams, and recomputing from a small
buffer is cheap enough that the drift is not worth the speed.

