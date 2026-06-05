# This file intentionally contains an invalid \U unicode escape that causes
# ast.parse() to raise SyntaxError on Python 3.x.
# Used by tests/test_scanner_correctness.py to verify scan_file warns and
# returns [] instead of silently swallowing parse failures.
def example(x):
    path = 'C:\Users\Administrator\Downloads\file.txt'
    return path
