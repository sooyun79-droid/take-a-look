import unittest

from calculator import average


class AverageTests(unittest.TestCase):
    def test_regular_values(self):
        self.assertEqual(average([2, 4, 6]), 4)

    def test_single_value(self):
        self.assertEqual(average([7]), 7)
