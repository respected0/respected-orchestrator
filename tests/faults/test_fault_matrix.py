import unittest

from tests.faults import matrix


class FaultMatrixTests(unittest.TestCase):
    def test_matrix_is_well_formed_and_every_test_exists(self):
        self.assertEqual(matrix.check_structure(), [])

    def test_at_least_twenty_faults_over_every_area(self):
        self.assertGreaterEqual(len(matrix.MATRIX), 20)
        self.assertEqual({e[1] for e in matrix.MATRIX} & set(matrix.AREAS), set(matrix.AREAS))

    def test_a_broken_matrix_is_reported_not_ignored(self):
        original = list(matrix.MATRIX)
        try:
            matrix.MATRIX.append(("FX", "network", "x", "y", ["tests.faults.test_direct.FaultTests.test_does_not_exist"]))
            self.assertTrue(any("cannot be loaded" in p or "not exactly one" in p for p in matrix.check_structure()))
        finally:
            matrix.MATRIX[:] = original


if __name__ == "__main__":
    unittest.main()
