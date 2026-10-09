"""P0-1 · Module boundary rule: no cross-module model imports."""
import ast
import pathlib

MODULES = pathlib.Path(__file__).resolve().parent.parent / "app" / "modules"


def test_no_cross_module_model_imports():
    violations = []
    for mod_dir in MODULES.iterdir():
        if not mod_dir.is_dir() or mod_dir.name == "__pycache__":
            continue
        for py in mod_dir.rglob("*.py"):
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "modules":
                        target_mod = parts[2]
                        if target_mod != mod_dir.name and "models" in parts:
                            violations.append(f"{py.name} ({mod_dir.name}) imports {node.module}")
                        # repository internals are also off-limits
                        if target_mod != mod_dir.name and "repository" in parts:
                            violations.append(f"{py.name} ({mod_dir.name}) imports {node.module}")
    assert not violations, "Boundary violations:\n" + "\n".join(violations)


def test_all_modules_registered():
    from app.modules import ROUTERS

    assert len(ROUTERS) == 17  # 16 domain modules + platform /me router
