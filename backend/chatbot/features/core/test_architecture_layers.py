import ast
from pathlib import Path
from typing import NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _py_files(glob_pattern: str) -> list[Path]:
    return sorted((PROJECT_ROOT).glob(glob_pattern))


def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


class _FunctionSymbol(NamedTuple):
    path: Path
    qualname: str
    name: str
    is_private: bool


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(_read(path))
    modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module is not None:
                modules.add(node.module)

    return modules


def _class_defs(path: Path) -> list[ast.ClassDef]:
    tree = ast.parse(_read(path))
    return [node for node in tree.body if isinstance(node, ast.ClassDef)]


def _function_symbols(path: Path) -> list[_FunctionSymbol]:
    tree = ast.parse(_read(path))
    symbols: list[_FunctionSymbol] = []
    parents: dict[int, ast.AST] = {}

    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name.startswith('__') and node.name.endswith('__'):
            continue
        if node.name in {'execute', '__enter__', '__exit__'}:
            continue
        if any(
            isinstance(decorator, ast.Name) and decorator.id == 'abstractmethod'
            for decorator in node.decorator_list
        ):
            continue

        parent = parents.get(id(node))
        if isinstance(parent, ast.ClassDef):
            qualname = f'{parent.name}.{node.name}'
        else:
            qualname = node.name

        symbols.append(
            _FunctionSymbol(
                path=path,
                qualname=qualname,
                name=node.name,
                is_private=node.name.startswith('_'),
            )
        )

    return symbols


def _reference_count(symbol_name: str, files: list[Path]) -> int:
    count = 0

    for file_path in files:
        tree = ast.parse(_read(file_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id == symbol_name:
                    count += 1
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                if node.attr == symbol_name:
                    count += 1

    return count


def _base_names(class_def: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in class_def.bases:
        if isinstance(base, ast.Name):
            names.add(base.id)
        elif isinstance(base, ast.Attribute):
            names.add(base.attr)
    return names


def test_api_layer_does_not_import_infrastructure_or_tools_modules():
    api_files = [
        PROJECT_ROOT / 'chatbot/api.py',
        *_py_files('chatbot/features/**/api/**/*.py'),
    ]

    forbidden_fragments = ('.infrastructure.', '.tools')
    offenders: list[str] = []

    for file_path in api_files:
        if not file_path.exists():
            continue
        imported = _imported_modules(file_path)
        for module in imported:
            if any(fragment in module for fragment in forbidden_fragments):
                offenders.append(f'{file_path.relative_to(PROJECT_ROOT)} -> {module}')

    assert offenders == []


def test_application_layer_does_not_import_api_or_infrastructure_modules():
    application_files = _py_files('chatbot/features/**/application/**/*.py')
    forbidden_fragments = ('.api.', '.infrastructure.', '.tools')
    offenders: list[str] = []

    for file_path in application_files:
        imported = _imported_modules(file_path)
        for module in imported:
            if any(fragment in module for fragment in forbidden_fragments):
                offenders.append(f'{file_path.relative_to(PROJECT_ROOT)} -> {module}')

    assert offenders == []


def test_scheduling_tools_module_is_only_an_adapter_to_application_use_cases():
    tools_module = PROJECT_ROOT / 'chatbot/features/scheduling/tools.py'
    imported = _imported_modules(tools_module)

    forbidden_modules = (
        'django',
        'dateutil',
        'chatbot.features.scheduling.models',
        'chatbot.features.scheduling.provider_seed_data',
        'chatbot.features.scheduling.time_context',
    )
    offenders = [
        module
        for module in imported
        if module.startswith(forbidden_modules)
    ]

    assert offenders == []


def test_use_case_classes_in_application_layer_inherit_base_use_case():
    application_files = _py_files('chatbot/features/**/application/**/*.py')
    offenders: list[str] = []

    for file_path in application_files:
        for class_def in _class_defs(file_path):
            if not class_def.name.endswith('UseCase'):
                continue
            if class_def.name == 'BaseUseCase':
                continue
            if 'BaseUseCase' not in _base_names(class_def):
                offenders.append(
                    f'{file_path.relative_to(PROJECT_ROOT)}::{class_def.name}'
                )

    assert offenders == []


def test_use_case_classes_are_only_defined_in_application_use_cases_directory():
    application_files = _py_files('chatbot/features/**/application/**/*.py')
    offenders: list[str] = []

    for file_path in application_files:
        is_use_cases_dir = 'application/use_cases/' in file_path.as_posix()
        for class_def in _class_defs(file_path):
            if not class_def.name.endswith('UseCase'):
                continue
            if class_def.name == 'BaseUseCase':
                continue
            if not is_use_cases_dir:
                offenders.append(
                    f'{file_path.relative_to(PROJECT_ROOT)}::{class_def.name}'
                )

    assert offenders == []


def test_each_application_use_case_file_contains_single_use_case_class():
    use_case_files = _py_files('chatbot/features/**/application/use_cases/*.py')
    offenders: list[str] = []

    for file_path in use_case_files:
        if file_path.name == '__init__.py':
            continue

        use_case_classes = [
            class_def
            for class_def in _class_defs(file_path)
            if class_def.name.endswith('UseCase') and class_def.name != 'BaseUseCase'
        ]
        if len(use_case_classes) != 1:
            offenders.append(
                f'{file_path.relative_to(PROJECT_ROOT)}::{len(use_case_classes)}'
            )

    assert offenders == []


def test_unit_of_work_classes_infrastructure_layer_inherit_base_unit_of_work():
    infrastructure_files = _py_files('chatbot/features/**/infrastructure/**/*.py')
    offenders: list[str] = []

    for file_path in infrastructure_files:
        for class_def in _class_defs(file_path):
            if 'UnitOfWork' not in class_def.name:
                continue
            if 'BaseUnitOfWork' not in _base_names(class_def):
                offenders.append(
                    f'{file_path.relative_to(PROJECT_ROOT)}::{class_def.name}'
                )

    assert offenders == []


def test_unit_of_work_classes_are_only_defined_in_infrastructure_unit_of_work_directory():
    infrastructure_files = _py_files('chatbot/features/**/infrastructure/**/*.py')
    offenders: list[str] = []

    for file_path in infrastructure_files:
        is_unit_of_work_dir = 'infrastructure/unit_of_work/' in file_path.as_posix()
        for class_def in _class_defs(file_path):
            if 'UnitOfWork' not in class_def.name:
                continue
            if class_def.name == 'BaseUnitOfWork':
                continue
            if not is_unit_of_work_dir:
                offenders.append(
                    f'{file_path.relative_to(PROJECT_ROOT)}::{class_def.name}'
                )

    assert offenders == []


def test_each_unit_of_work_file_contains_single_unit_of_work_class():
    unit_of_work_files = _py_files('chatbot/features/**/infrastructure/unit_of_work/*.py')
    offenders: list[str] = []

    for file_path in unit_of_work_files:
        if file_path.name == '__init__.py':
            continue

        uow_classes = [
            class_def
            for class_def in _class_defs(file_path)
            if 'UnitOfWork' in class_def.name and class_def.name != 'BaseUnitOfWork'
        ]
        if len(uow_classes) != 1:
            offenders.append(
                f'{file_path.relative_to(PROJECT_ROOT)}::{len(uow_classes)}'
            )

    assert offenders == []


def test_scheduling_tools_tests_are_split_by_use_case_file():
    monolith_file = PROJECT_ROOT / 'chatbot/features/scheduling/test_tools.py'
    assert monolith_file.exists() is False


def test_root_api_module_does_not_define_route_handlers_or_schemas():
    api_module = PROJECT_ROOT / 'chatbot/api.py'
    tree = ast.parse(_read(api_module))

    route_handler_defs: list[str] = []
    schema_defs: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            base_names = _base_names(node)
            if 'Schema' in base_names:
                schema_defs.append(node.name)
        if isinstance(node, ast.FunctionDef):
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    func = decorator.func
                else:
                    func = decorator
                if isinstance(func, ast.Attribute) and func.attr in {'get', 'post', 'delete', 'put', 'patch'}:
                    route_handler_defs.append(node.name)

    assert route_handler_defs == []
    assert schema_defs == []


def test_users_signup_application_module_does_not_import_use_case_module():
    signup_module = PROJECT_ROOT / 'chatbot/features/users/application/signup.py'
    imported = _imported_modules(signup_module)
    offenders = [
        module
        for module in imported
        if module.startswith('chatbot.features.users.application.use_cases')
    ]

    assert offenders == []


def test_scheduling_use_cases_package_init_has_no_imports():
    use_cases_package_init = PROJECT_ROOT / 'chatbot/features/scheduling/application/use_cases/__init__.py'
    imported = _imported_modules(use_cases_package_init)
    assert imported == set()


def test_non_init_wrapper_modules_are_not_used_for_re_exports():
    wrapper_module_candidates = [
        PROJECT_ROOT / 'chatbot/features/billing/pricing.py',
        PROJECT_ROOT / 'chatbot/features/users/infrastructure/signup.py',
    ]

    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for path in wrapper_module_candidates
        if path.exists()
    ]

    assert offenders == []


def test_placeholder_modules_are_not_present_in_feature_apps():
    placeholder_modules = [
        PROJECT_ROOT / 'chatbot/features/users/views.py',
        PROJECT_ROOT / 'chatbot/features/users/admin.py',
        PROJECT_ROOT / 'chatbot/features/scheduling/admin.py',
    ]

    offenders = [
        str(path.relative_to(PROJECT_ROOT))
        for path in placeholder_modules
        if path.exists()
    ]

    assert offenders == []


def test_openrouter_agent_does_not_import_scheduling_modules_directly():
    agent_module = PROJECT_ROOT / 'chatbot/features/ai/openrouter_agent.py'
    imported = _imported_modules(agent_module)
    offenders = [
        module
        for module in imported
        if module.startswith('chatbot.features.scheduling.')
    ]
    assert offenders == []


def _has_orm_manager_calls(path: Path) -> bool:
    """Return True if the file contains any .objects attribute access in its AST."""
    tree = ast.parse(_read(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == 'objects':
            return True
    return False


def test_api_layer_has_no_direct_orm_calls():
    """API handlers must never call Model.objects.* — only infrastructure/UoW may do ORM."""
    api_files = [
        PROJECT_ROOT / 'chatbot/api.py',
        *_py_files('chatbot/features/**/api/**/*.py'),
    ]
    offenders: list[str] = []

    for file_path in api_files:
        if not file_path.exists():
            continue
        if _has_orm_manager_calls(file_path):
            offenders.append(str(file_path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_application_layer_has_no_direct_orm_calls():
    """Use cases must never call Model.objects.* — only infrastructure/UoW may do ORM."""
    application_files = _py_files('chatbot/features/**/application/**/*.py')
    offenders: list[str] = []

    for file_path in application_files:
        if file_path.name == '__init__.py':
            continue
        if _has_orm_manager_calls(file_path):
            offenders.append(str(file_path.relative_to(PROJECT_ROOT)))

    assert offenders == []


FEATURE_MODULES = ('ai', 'billing', 'chat', 'scheduling', 'users')


def _feature_from_file_path(path: Path) -> str | None:
    parts = path.as_posix().split('/')
    try:
        features_index = parts.index('features')
    except ValueError:
        return None

    if features_index + 1 >= len(parts):
        return None

    return parts[features_index + 1]


def _feature_from_imported_module(module_name: str) -> str | None:
    if not module_name.startswith('chatbot.features.'):
        return None

    parts = module_name.split('.')
    if len(parts) < 3:
        return None

    return parts[2]


def test_feature_modules_follow_standard_architecture_layout():
    required_relative_paths = (
        'application',
        'application/use_cases',
        'infrastructure',
        'infrastructure/unit_of_work',
        'tests',
        'composition.py',
        'application/use_cases/__init__.py',
        'infrastructure/unit_of_work/__init__.py',
        'tests/__init__.py',
    )

    missing: list[str] = []
    for module in FEATURE_MODULES:
        module_root = PROJECT_ROOT / 'chatbot/features' / module
        for relative_path in required_relative_paths:
            target = module_root / relative_path
            if not target.exists():
                missing.append(f'{module}/{relative_path}')

    assert missing == []


def test_non_ai_composition_modules_only_import_local_or_core_features():
    composition_files = _py_files('chatbot/features/*/composition.py')
    offenders: list[str] = []

    for file_path in composition_files:
        source_feature = _feature_from_file_path(file_path)
        if source_feature is None:
            continue

        # AI is the orchestrator feature and may compose across feature boundaries.
        if source_feature == 'ai':
            continue

        imported = _imported_modules(file_path)
        for module_name in imported:
            target_feature = _feature_from_imported_module(module_name)
            if target_feature is None:
                continue
            if target_feature not in {source_feature, 'core'}:
                offenders.append(
                    f'{file_path.relative_to(PROJECT_ROOT)} -> {module_name}'
                )

    assert offenders == []


def test_cross_feature_imports_are_allowed_only_for_ai_or_explicit_contracts():
    """
    Enforce strict cross-feature boundaries:
    - Any feature may import itself and core.
    - AI may orchestrate across feature boundaries.
    - Non-AI features may cross-import only explicit contracts.
    """
    module_files = _py_files('chatbot/features/**/*.py')
    offenders: list[str] = []

    allowed_cross_feature_contract_imports_by_file = {
        'chatbot/features/billing/tools.py': {
            'chatbot.features.ai.tooling',
        },
            'chatbot/features/chat/api/post_chat.py': {
            'chatbot.features.ai.composition',
        },
        'chatbot/features/scheduling/tools.py': {
            'chatbot.features.ai.tooling',
        },
    }

    for file_path in module_files:
        file_posix = file_path.as_posix()
        if '/migrations/' in file_posix:
            continue
        if '/tests/' in file_posix:
            continue
        if file_path.name.startswith('test_') or file_path.name == 'tests.py':
            continue

        source_feature = _feature_from_file_path(file_path)
        if source_feature is None:
            continue

        imported = _imported_modules(file_path)
        relative_path = str(file_path.relative_to(PROJECT_ROOT))
        allowed_modules = allowed_cross_feature_contract_imports_by_file.get(
            relative_path,
            set(),
        )

        for module_name in imported:
            target_feature = _feature_from_imported_module(module_name)
            if target_feature is None:
                continue
            if target_feature in {source_feature, 'core'}:
                continue
            if source_feature == 'ai':
                continue
            if module_name in allowed_modules:
                continue

            offenders.append(f'{relative_path} -> {module_name}')

    assert offenders == []


def test_feature_modules_have_no_root_level_test_files():
    offenders: list[str] = []

    for module in FEATURE_MODULES:
        module_root = PROJECT_ROOT / 'chatbot/features' / module
        for file_path in module_root.glob('test*.py'):
            offenders.append(str(file_path.relative_to(PROJECT_ROOT)))
        tests_dot_py = module_root / 'tests.py'
        if tests_dot_py.exists():
            offenders.append(str(tests_dot_py.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_base_agent_does_not_define_tool_input_schemas_inline():
    base_module = PROJECT_ROOT / 'chatbot/features/ai/base.py'
    tree = ast.parse(_read(base_module))
    offenders: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            if node.name.endswith('InputSchema'):
                offenders.append(node.name)

    assert offenders == []


def test_query_modules_live_only_in_infrastructure_layer():
    query_files = _py_files('chatbot/features/**/*.py')
    offenders: list[str] = []

    for file_path in query_files:
        path_str = file_path.as_posix()
        if file_path.name not in {'queries.py', 'query.py'}:
            continue
        if '/infrastructure/' not in path_str:
            offenders.append(str(file_path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_production_symbols_are_not_dead_or_test_only():
    reference_files = [
        path
        for path in _py_files('chatbot/**/*.py')
        if '/tests/' not in path.as_posix()
        and '/migrations/' not in path.as_posix()
        and not path.name.startswith('test_')
    ]
    symbol_files = [
        path
        for path in reference_files
        if '/api/' not in path.as_posix()
    ]
    test_files = [
        path
        for path in _py_files('chatbot/**/*.py')
        if path not in reference_files
    ]
    offenders: list[str] = []

    for file_path in symbol_files:
        for symbol in _function_symbols(file_path):
            production_refs = _reference_count(symbol.name, reference_files)
            test_refs = _reference_count(symbol.name, test_files)
            relative_path = file_path.relative_to(PROJECT_ROOT)

            if production_refs == 0 and test_refs > 0:
                offenders.append(
                    f'{relative_path}::{symbol.qualname} is only referenced from tests'
                )
            elif symbol.is_private and production_refs == 0 and test_refs == 0:
                offenders.append(
                    f'{relative_path}::{symbol.qualname} is dead private code'
                )

    assert offenders == []


def test_helper_utility_files_live_only_in_infrastructure_or_tests():
    """
    Enforce that helper/utility/read-model files must reside in proper layers:
        - Infrastructure-layer files (gateways, seeds, temporal context):
            chatbot/features/*/infrastructure/
    - Test helpers: chatbot/features/*/tests/ (via conftest.py)
    
    Forbidden patterns at feature root:
    - *_helpers.py, *_test_helpers.py, helpers.py
    - *_context.py, context.py
    - *_seed*.py, seed*.py
    - *gateway.py, gateway.py
    - provider_seed_data.py and similar data fixtures
    """
    helper_patterns = [
        '*_helpers.py',
        '*_test_helpers.py',
        'helpers.py',
        '*_context.py',
        'context.py',
        '*_seed*.py',
        'seed*.py',
        '*gateway.py',
        'gateway.py',
    ]
    
    offenders: list[str] = []
    
    for module in FEATURE_MODULES:
        module_root = PROJECT_ROOT / 'chatbot/features' / module
        for pattern in helper_patterns:
            for file_path in module_root.glob(pattern):
                # Skip if it's in a subdirectory (infrastructure, tests, application, etc.)
                if file_path.parent != module_root:
                    continue
                offenders.append(str(file_path.relative_to(PROJECT_ROOT)))
    
    assert offenders == [], (
        f'Helper/utility files must be in infrastructure/ or tests/, '
        f'not at feature root. Found: {offenders}'
    )


def test_feature_root_python_files_are_expected_modules():
    """
    Root-level .py files in features should be feature-specific modules,
    not helper/utility files. This catches when utilities are placed
    at the wrong layer (should be in infrastructure or tests).
    """
    # These are acceptable at feature root
    # - Standard Django: models.py, admin.py, apps.py, views.py
    # - Architecture: composition.py
    # - Legacy re-export: pricing.py
    # - Feature-specific: api.py, tools.py, message_burst.py, sse.py, etc.
    # 
    # Rejected patterns:
    # - *_helpers.py, *_test_helpers.py
    # - *_context.py (except part of class names)
    # - *_seed*.py
    # - *gateway.py
    rejected_patterns = [
        '*_helpers.py',
        '*_test_helpers.py',
        'helpers.py',
        '*_seed*.py',
        'seed*.py',
    ]
    
    offenders: list[str] = []
    
    for module in FEATURE_MODULES:
        module_root = PROJECT_ROOT / 'chatbot/features' / module
        for pattern in rejected_patterns:
            for file_path in module_root.glob(pattern):
                # Skip if it's in a subdirectory
                if file_path.parent != module_root:
                    continue
                offenders.append(str(file_path.relative_to(PROJECT_ROOT)))
    
    assert offenders == [], (
        f'Utility/helper files must be moved to infrastructure/ or tests/. '
        f'Found at feature root: {offenders}'
    )
