"""
This script implements a T-wise test case generation algorithm.
It takes T as an input and a set of parameters to generate a test suite.
"""

import itertools

def _remove_covered(uncovered_combinations, test_case, t, param_names):
    """Helper function to remove covered combinations."""
    combos_in_test_case = itertools.combinations(param_names, t)
    for combo_keys in combos_in_test_case:
        combo = frozenset((key, test_case[key]) for key in combo_keys)
        if combo in uncovered_combinations:
            uncovered_combinations.remove(combo)
    return uncovered_combinations

def _count_newly_covered(uncovered_combinations, partial_test_case, t):
    """Helper function to count newly covered combinations."""
    count = 0
    param_names_in_partial = list(partial_test_case.keys())
    if len(param_names_in_partial) < t:
        return 0

    t_combos_of_params = itertools.combinations(param_names_in_partial, t)
    for combo_keys in t_combos_of_params:
        combo = frozenset((key, partial_test_case[key]) for key in combo_keys)
        if combo in uncovered_combinations:
            count += 1
    return count

def generate_t_wise_suite(t, parameters):
    """
    Generates a T-wise test suite using a greedy algorithm.
    """
    param_names = sorted(list(parameters.keys()))

    # 1. Generate all T-way value combinations to be covered
    uncovered_combinations = set()
    param_combos = itertools.combinations(param_names, t)
    for param_combo in param_combos:
        value_lists = [parameters[p] for p in param_combo]
        for value_tuple in itertools.product(*value_lists):
            uncovered_combinations.add(frozenset(zip(param_combo, value_tuple)))

    test_suite = []

    # 2. Create the first test case with the first value of each parameter
    if not all(parameters.values()):
        return [] # Handle empty parameter lists

    first_test_case = {p: parameters[p][0] for p in param_names}
    test_suite.append(first_test_case)
    uncovered_combinations = _remove_covered(uncovered_combinations, first_test_case, t, param_names)

    # 3. Greedily build the rest of the test suite
    while uncovered_combinations:
        # Sort to make selection deterministic
        sorted_uncovered = sorted(list(uncovered_combinations), key=lambda f: str(sorted(list(f))))
        base_combo = dict(sorted_uncovered[0])

        new_test_case = base_combo.copy()

        for param in param_names:
            if param not in new_test_case:
                best_value = None
                max_newly_covered = -1

                for value in parameters[param]:
                    current_test_case = new_test_case.copy()
                    current_test_case[param] = value

                    count = _count_newly_covered(uncovered_combinations, current_test_case, t)

                    if count > max_newly_covered:
                        max_newly_covered = count
                        best_value = value

                new_test_case[param] = best_value if best_value is not None else parameters[param][0]

        test_suite.append(new_test_case)
        uncovered_combinations = _remove_covered(uncovered_combinations, new_test_case, t, param_names)

    return test_suite

if __name__ == "__main__":
    # Triangle problem example

    # Parameters for the triangle problem
    triangle_params = {
        'a': ['a' , 'b'], # Represents different classes of lengths
        'b': [1, 2, 3 , 4],
        'c': ['x' , 'y']
    }

    # Generate a 2-wise test suite
    t=3
    test_suite = generate_t_wise_suite(t, triangle_params)

    # Sort the test suite for consistent, readable output
    param_names = sorted(triangle_params.keys())
    test_suite.sort(key=lambda x: [x[p] for p in param_names])

    # Print the formatted output
    print(f"Generated Test Cases for T={t}:")
    header = f"{'Test Case':<10} " + " ".join([f"{p:<5}" for p in param_names])
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    for i, test_case in enumerate(test_suite):
        # Ensure that test_case values are strings for formatting
        row = f"{i+1:<10} " + " ".join([f"{str(test_case[p]):<5}" for p in param_names])
        print(row)

    print("-" * len(header))
    print(f"Total Test Cases: {len(test_suite)}")
