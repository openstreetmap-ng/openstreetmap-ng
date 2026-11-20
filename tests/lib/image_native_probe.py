"""Run image tests without the unavailable Nix/database bootstrap.

Uses real Pillow, image code, exception implementation, and model type aliases.
Only configuration and unused native element-ID bindings are isolated. This is
not a full HTTP, database, Cython-compiled, or authentication integration test.
"""

import argparse
import ast
import importlib
import sys
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ByteSize, TypeAdapter

sys.path.insert(0, str(Path.cwd()))

names = {
    'AI_MODELS_DIR',
    'AI_TRANSFORMERS_DEVICE',
    'AVATAR_MAX_FILE_SIZE',
    'AVATAR_MAX_MEGAPIXELS',
    'AVATAR_MAX_RATIO',
    'BACKGROUND_MAX_FILE_SIZE',
    'BACKGROUND_MAX_MEGAPIXELS',
    'BACKGROUND_MAX_RATIO',
    'IMAGE_MAX_FRAMES',
    'IMAGE_PROXY_BLURHASH_MAX_COMPONENTS',
    'IMAGE_PROXY_IMAGE_MAX_SIDE',
    'IMAGE_PROXY_RECOMPRESS_QUALITY',
    'TRACE_POINT_QUERY_AREA_MAX_SIZE',
}
namespace = {'Path': Path, '_ByteSize': TypeAdapter(ByteSize).validate_python}


def _config_value(node: ast.expr):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_config_value(node.operand)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        return _config_value(node.left) * _config_value(node.right)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in namespace
        and len(node.args) == 1
        and not node.keywords
    ):
        return namespace[node.func.id](_config_value(node.args[0]))
    raise ValueError(f'Unsupported isolated configuration expression: {ast.dump(node)}')


configuration = ModuleType('app.config')
for node in ast.parse(Path('app/config.py').read_text(encoding='utf-8')).body:
    target = (
        node.target
        if isinstance(node, ast.AnnAssign)
        else (node.targets[0] if isinstance(node, ast.Assign) else None)
    )
    if isinstance(target, ast.Name) and target.id in names:
        assert node.value is not None
        value = _config_value(node.value)
        setattr(configuration, target.id, value)
sys.modules['app.config'] = configuration


def unused_native_binding(*args, **kwargs):
    raise AssertionError('Native element-ID functionality is outside this probe')


native = ModuleType('speedup')
native.element_type = unused_native_binding
sys.modules['speedup'] = native
element = ModuleType('app.models.element')
element.TypedElementId = str
sys.modules['app.models.element'] = element

# Preserve the real exception modules while avoiding unrelated native bootstrap.
package = ModuleType('app.exceptions')
package.__path__ = [str(Path('app/exceptions').resolve())]
sys.modules['app.exceptions'] = package
package.Exceptions = importlib.import_module('app.exceptions.default').Exceptions

arguments = argparse.ArgumentParser()
arguments.add_argument('--compiled-image', type=Path)
options = arguments.parse_args()
if options.compiled_image is not None:
    importlib.import_module('app.lib.io')
    specification = importlib.util.spec_from_file_location(
        'app.lib.io.image', options.compiled_image
    )
    assert specification is not None
    assert isinstance(specification.loader, importlib.machinery.ExtensionFileLoader)
    module = importlib.util.module_from_spec(specification)
    sys.modules['app.lib.io.image'] = module
    specification.loader.exec_module(module)
    print(f'Compiled image module: {module.__file__}')

print(f'Image source root: {Path.cwd()}')
print(
    f'Pillow={version("pillow")} Cython={version("cython")} FastAPI={version("fastapi")}'
)
raise SystemExit(
    pytest.main([
        '--noconftest',
        str(Path(__file__).with_name('test_image_upload_errors.py')),
    ])
)
