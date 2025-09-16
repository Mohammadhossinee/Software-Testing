import unittest
import itertools
from main import generate_t_wise_suite

class TestTWise(unittest.TestCase):

    def test_2_wise_coverage(self):
        """
        Tests if the generated suite covers all 2-wise combinations.
        """
        parameters = {
            'P1': ['A', 'B'],
            'P2': ['X', 'Y'],
            'P3': [1, 2]
        }
        t = 2

        # 1. Generate all expected 2-wise combinations
        expected_pairs = set()
        param_combos = itertools.combinations(parameters.keys(), t)
        for p1, p2 in param_combos:
            for v1 in parameters[p1]:
                for v2 in parameters[p2]:
                    expected_pairs.add(frozenset({(p1, v1), (p2, v2)}))

        # 2. Generate the test suite
        suite = generate_t_wise_suite(t, parameters)

        # 3. Check if all pairs are covered
        covered_pairs = set()
        for test_case in suite:
            param_combos_in_case = itertools.combinations(test_case.keys(), t)
            for p1, p2 in param_combos_in_case:
                pair = frozenset({(p1, test_case[p1]), (p2, test_case[p2])})
                covered_pairs.add(pair)

        self.assertEqual(expected_pairs, covered_pairs)

if __name__ == '__main__':
    unittest.main()
