"""Generate local web bindings from Buf descriptors with the declared ES plugin."""

import os
import shutil
import subprocess
from pathlib import Path

from google.protobuf import descriptor_pb2
from google.protobuf.compiler import plugin_pb2

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / 'app/views/proto'
PREFIXES = ('app/models/proto/', 'buf/validate/')


def web_name(name: str) -> str:
    return Path(name).name if name.startswith(PREFIXES) else name


descriptors = descriptor_pb2.FileDescriptorSet.FromString(
    Path(os.environ['HISTORY_DESCRIPTORS']).read_bytes()
)
request = plugin_pb2.CodeGeneratorRequest(
    parameter='target=ts,json_types=false,valid_types=protovalidate_required'
)
for original in descriptors.file:
    file = request.proto_file.add()
    file.CopyFrom(original)
    file.name = web_name(original.name)
    file.dependency[:] = [web_name(name) for name in original.dependency]
    if original.name.startswith(PREFIXES):
        request.file_to_generate.append(file.name)

node = shutil.which('node')
if node is None:
    raise RuntimeError('Node is required for the installed protoc-gen-es')
plugin = ROOT / 'node_modules/@bufbuild/protoc-gen-es/bin/protoc-gen-es'
# The executable is the fixed, locally installed plugin, never a shell command.
result = subprocess.run(
    [node, str(plugin)],
    input=request.SerializeToString(),
    capture_output=True,
    check=True,
    timeout=120,
)
response = plugin_pb2.CodeGeneratorResponse.FromString(result.stdout)
if response.error:
    raise RuntimeError(response.error)
OUTPUT.mkdir(parents=True, exist_ok=True)
for file in response.file:
    target = (OUTPUT / file.name).resolve()
    if not target.is_relative_to(OUTPUT.resolve()):
        raise RuntimeError(f'Invalid generated path: {file.name}')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(file.content, encoding='utf-8')
print(f'Generated {len(response.file)} web bindings with project ES plugin options')
