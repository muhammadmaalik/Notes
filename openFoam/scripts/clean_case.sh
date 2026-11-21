#!/usr/bin/env bash
# Remove generated output. Preserve initial fields in 0/ and input dictionaries.
set -euo pipefail
if [ ! -f system/controlDict ]; then
    echo "Error: run this script from inside a case folder." >&2
    exit 1
fi
python3 - <<'PY'
import re
import shutil
from decimal import Decimal
from pathlib import Path

root = Path.cwd()
if 'templates' in root.parts:
    raise SystemExit('Refusing to clean a reference template; clone it first.')

# Complete numeric time names, never arbitrary names beginning with a digit.
time_name = re.compile(r'\d+(?:\.\d+)?(?:[eE][+-]?\d+)?')
processor_name = re.compile(r'processors?\d+(?:_\d+-\d+)?')
for path in root.iterdir():
    generated_dir = (
        path.name in {'postProcessing', 'dynamicCode'}
        or processor_name.fullmatch(path.name)
        or (time_name.fullmatch(path.name) and Decimal(path.name) != 0)
    )
    generated_file = (
        path.name.startswith('log.')
        or path.suffix in {'.foam', '.OpenFOAM'}
        or path.name == 'residuals.png'
    )
    if path.is_symlink():
        continue  # Never follow user-created links during cleanup.
    if path.is_dir() and generated_dir:
        shutil.rmtree(path)
        print(f'Removed {path.name}/')
    elif path.is_file() and generated_file:
        path.unlink()
        print(f'Removed {path.name}')
mesh = root / 'constant' / 'polyMesh'
if mesh.is_dir() and not mesh.is_symlink():
    shutil.rmtree(mesh)
    print('Removed constant/polyMesh/')
print('Cleaned generated output. Kept 0/ and inputs. setFields reinitializes its configured fields next run.')
PY
