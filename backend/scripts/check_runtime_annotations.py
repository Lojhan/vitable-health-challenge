from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CHATBOT_DIR = ROOT / 'chatbot'


def _is_runtime_file(path: Path) -> bool:
    normalized = path.as_posix()
    if '/migrations/' in normalized:
        return False
    if '/tests/' in normalized:
        return False
    name = path.name
    if name.startswith('test_') or name.endswith('_test.py') or name.endswith('_tests.py'):
        return False
    if normalized.endswith('/test_api_chat.py'):
        return False
    return True


def _function_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _missing_annotations(func: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[str], bool]:
    args = list(func.args.posonlyargs) + list(func.args.args) + list(func.args.kwonlyargs)
    if func.args.vararg is not None:
        args.append(func.args.vararg)
    if func.args.kwarg is not None:
        args.append(func.args.kwarg)

    missing_params = [
        arg.arg
        for arg in args
        if arg.arg != 'self' and arg.annotation is None
    ]
    missing_return = func.returns is None
    return missing_params, missing_return


def main() -> int:
    offenders: list[str] = []

    for file_path in sorted(CHATBOT_DIR.rglob('*.py')):
        if not _is_runtime_file(file_path):
            continue

        tree = ast.parse(file_path.read_text(encoding='utf-8'))
        for func in _function_nodes(tree):
            if func.name.startswith('__') and func.name.endswith('__'):
                continue
            missing_params, missing_return = _missing_annotations(func)
            if missing_params or missing_return:
                problems: list[str] = []
                if missing_params:
                    problems.append(f"missing params: {', '.join(missing_params)}")
                if missing_return:
                    problems.append('missing return annotation')
                rel_path = file_path.relative_to(ROOT).as_posix()
                joined_problems = '; '.join(problems)
                offenders.append(
                    f'{rel_path}:{func.lineno}:{func.name} ({joined_problems})'
                )

    if offenders:
        print('Runtime annotation check failed. Missing annotations found:')
        for offender in offenders:
            print(f' - {offender}')
        return 1

    print('Runtime annotation check passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
