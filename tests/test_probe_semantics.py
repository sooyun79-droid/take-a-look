import unittest

from take_a_look.probes import Unsupported, probe


class ProbeSemanticsTests(unittest.TestCase):
    def test_bounded_interpreter_agrees_with_python_on_authored_cases(self):
        sources = [
            "def f(xs):\n return sum(xs)/len(xs)",
            "def f(xs):\n if not xs:\n  return 0\n return sum(xs)/len(xs)",
            "def f(xs):\n if len(xs) == 0:\n  return None\n return sum(xs)//len(xs)",
            "def f(xs):\n if len(xs) > 0:\n  return sum(xs)/len(xs)\n return -1",
            "def f(xs):\n n = len(xs)\n if n <= 0 or not xs:\n  return 4\n return 2 % len(xs)",
            "def f(x, y):\n if y == 0:\n  return x + 3\n return x/y",
            "def f(x):\n return x/0",
        ]
        for source in sources:
            with self.subTest(source=source):
                line = next(i for i, text in enumerate(source.splitlines(), 1) if "/" in text or "%" in text)
                result = probe(source, "f", line)
                # Test-only execution of literal strings authored above, never user input.
                namespace = {}
                exec(compile(source, "<authored-test-case>", "exec"), namespace)
                try:
                    value = namespace["f"](**result["inputs"])
                    expected = {"outcome": "returned", "value": value}
                except ZeroDivisionError:
                    expected = {"outcome": "zero_division"}
                self.assertEqual(result["observations"], [expected] * 3)

    def test_tuple_coercion_cannot_create_false_evidence(self):
        with self.assertRaises(Unsupported):
            probe("def f(xs):\n if xs == ():\n  return 0\n return sum(xs)/len(xs)", "f", 4)

    def test_resource_growth_is_rejected(self):
        with self.assertRaises(Unsupported):
            probe("def f(xs):\n n = 999999999 * 999999999\n return n/len(xs)", "f", 3)


if __name__ == "__main__":
    unittest.main()
