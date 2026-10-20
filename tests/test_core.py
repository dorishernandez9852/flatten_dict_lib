import unittest

from flatten_dict_lib import flatten, unflatten


class TestFlatten(unittest.TestCase):
    def test_simple_nested(self):
        self.assertEqual(flatten({"a": {"b": 1}}), {"a.b": 1})

    def test_already_flat(self):
        self.assertEqual(flatten({"a": 1, "b": 2}), {"a": 1, "b": 2})

    def test_deeply_nested(self):
        self.assertEqual(
            flatten({"a": {"b": {"c": {"d": 42}}}}),
            {"a.b.c.d": 42},
        )

    def test_custom_separator(self):
        self.assertEqual(flatten({"a": {"b": 1}}, sep="/"), {"a/b": 1})

    def test_empty_nested_dict_preserved(self):
        self.assertEqual(flatten({"a": {}}), {"a": {}})

    def test_root_empty_dict(self):
        self.assertEqual(flatten({}), {})

    def test_list_is_leaf(self):
        data = {"a": [1, 2, 3]}
        self.assertEqual(flatten(data), {"a": [1, 2, 3]})

    def test_none_is_leaf(self):
        self.assertEqual(flatten({"a": None}), {"a": None})

    def test_non_string_key_raises(self):
        with self.assertRaises(TypeError):
            flatten({1: "value"})  # type: ignore[dict-item]

    def test_non_mapping_raises(self):
        with self.assertRaises(TypeError):
            flatten([("a", 1)])  # type: ignore[arg-type]


class TestUnflatten(unittest.TestCase):
    def test_simple_round_trip(self):
        self.assertEqual(unflatten({"a.b": 1}), {"a": {"b": 1}})

    def test_deep_round_trip(self):
        self.assertEqual(unflatten({"a.b.c.d": 42}),
                         {"a": {"b": {"c": {"d": 42}}}})

    def test_custom_sep_round_trip(self):
        self.assertEqual(unflatten({"a/b": 1}, sep="/"),
                         {"a": {"b": 1}})

    def test_empty_dict_leaf_round_trip(self):
        self.assertEqual(unflatten({"a": {}}), {"a": {}})

    def test_multiple_keys(self):
        flat = {"a.b": 1, "a.c": 2, "x.y": 3}
        expected = {"a": {"b": 1, "c": 2}, "x": {"y": 3}}
        self.assertEqual(unflatten(flat), expected)

    def test_overlapping_dict_leaves_merge(self):
        flat = {"a": {"z": 9}, "a.b": 1}
        result = unflatten(flat)
        self.assertEqual(result, {"a": {"b": 1, "z": 9}})


class TestRoundTrip(unittest.TestCase):
    def test_round_trip_nested(self):
        original = {"a": {"b": 1, "c": 2}, "x": {"y": {"z": 3}}}
        self.assertEqual(unflatten(flatten(original)), original)

    def test_round_trip_with_sep_in_values(self):
        original = {"a.b": {"c/d": "val"}}
        flat = flatten(original, sep=".")
        self.assertEqual(unflatten(flat, sep="."), original)

    def test_round_trip_with_backslash_in_key(self):
        original = {"a\\b": {"c": 1}}
        flat = flatten(original, sep=".")
        self.assertEqual(unflatten(flat, sep="."), original)

    def test_round_trip_empty_nested(self):
        original = {"a": {"b": {}}, "c": {}}
        self.assertEqual(unflatten(flatten(original)), original)

    def test_round_trip_list_values(self):
        original = {"a": [1, 2], "b": {"c": [3, 4]}}
        self.assertEqual(unflatten(flatten(original)), original)

    def test_round_trip_none_and_numbers(self):
        original = {"a": None, "b": {"c": 0, "d": 3.14}, "e": True}
        self.assertEqual(unflatten(flatten(original)), original)


if __name__ == "__main__":
    unittest.main()
