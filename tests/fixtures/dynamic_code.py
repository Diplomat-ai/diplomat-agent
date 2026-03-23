"""Dynamic code loading and execution — all should be detected as destructive effects."""


def load_strategy(module_path: str, class_name: str):
    """Dynamic module loading — CRITICAL effect."""
    import importlib
    module = importlib.import_module(module_path)
    strategy = getattr(module, class_name)
    return strategy()


def execute_generated_code(code: str):
    """Exec of generated code — CRITICAL effect."""
    exec(code)


def evaluate_expression(expr: str):
    """Eval of expression — CRITICAL effect."""
    return eval(expr)


def safe_import():
    """Static import with literal — still detected, dev can mark # canary:ok."""
    import importlib
    module = importlib.import_module("known_module.strategy")
    return module
