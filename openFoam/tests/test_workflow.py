"""Host-side integration checks. Run: python3 -m unittest discover -s tests -v"""
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('geometry', ROOT / 'scripts/prepare_geometry.py')
geometry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(geometry)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='foam-workflow-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ('scripts', 'templates'):
            shutil.copytree(ROOT / folder, self.root / folder)
        (self.root / 'build').mkdir()
        shutil.copy2(ROOT / 'build/foamctl', self.root / 'build/foamctl')
        (self.root / 'runs').mkdir()

    def cli(self, *args, success=True):
        result = subprocess.run([str(self.root / 'build/foamctl'), *args], text=True, capture_output=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_complete_independent_cases_and_no_overwrite(self):
        self.cli('new', 'cavity')
        self.cli('new', 'incomp')
        first = self.root / 'runs/run1'
        for file in ('0/U', '0/p', 'system/controlDict', 'system/blockMeshDict',
                     'system/fvSchemes', 'system/fvSolution', 'constant/transportProperties', 'Allrun', 'case.foam'):
            self.assertTrue((first / file).is_file(), file)
        self.assertTrue(os.access(first / 'Allrun', os.X_OK))
        (first / '0/U').write_text('my edited conditions')
        self.cli('new', 'cavity', 'run1', success=False)
        self.assertEqual((first / '0/U').read_text(), 'my edited conditions')
        self.assertNotEqual((self.root / 'templates/cavity/0/U').read_text(), 'my edited conditions')
        self.assertTrue((self.root / 'runs/run2/0/U').is_file())

    def test_rejects_paths_unknown_types_and_extra_options(self):
        self.cli('new', 'not-a-solver', success=False)
        self.cli('new', 'cavity', '../escape', success=False)
        self.cli('new', 'cavity', 'bad;name', success=False)
        self.cli('new', 'cavity', 'valid')
        self.cli('run', 'valid', '--parallel', '0', success=False)
        self.cli('mesh', 'valid', '--parallel', '2', success=False)
        self.assertFalse((self.root / 'escape').exists())

    def test_binary_stl_scaling_and_single_region(self):
        source = self.root / 'millimetres.stl'
        source.write_bytes(b'solid binary'.ljust(80, b' ') + struct.pack('<I', 1) +
                           struct.pack('<12fH', 0, 0, 1, 0, 0, 0, 1000, 0, 0, 0, 1000, 0, 0))
        target = self.root / 'normal.stl'
        geometry.normalize(source, target, scale=0.001)
        self.assertEqual(geometry.read_triangles(target), [((0., 0., 0.), (1., 0., 0.), (0., 1., 0.))])
        self.assertTrue(target.read_text().startswith('solid body\n'))
        with self.assertRaises(FileExistsError):
            geometry.normalize(source, target)

    def test_bad_geometry_does_not_create_destination(self):
        source = self.root / 'bad.stl'
        source.write_text('solid bad\nfacet normal 0 0 0\nouter loop\n' +
                          'vertex 0 0 0\n' * 3 + 'endloop\nendfacet\nendsolid bad\n')
        output = self.root / 'out.stl'
        with self.assertRaises(ValueError):
            geometry.normalize(source, output)
        self.assertFalse(output.exists())

    def test_import_refuses_meshed_case(self):
        self.cli('new', 'external-stl', 'part')
        mesh = self.root / 'runs/part/constant/polyMesh'
        mesh.mkdir()
        (mesh / 'points').touch()
        result = subprocess.run([str(self.root / 'scripts/import_geometry.sh'), 'part',
                                 str(ROOT / 'examples/geometry/cube.stl')], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Mesh already exists', result.stderr)

    def test_mesh_check_uses_current_log_and_blocks_failed_mesh(self):
        self.cli('new', 'cavity', 'checked')
        case = self.root / 'runs/checked'
        (case / 'constant/polyMesh').mkdir()
        (case / 'constant/polyMesh/points').touch()
        (case / 'logs').mkdir()
        # A container's PID is often 1 for every invocation: old logs must not win.
        (case / 'logs/20000101T000000-1-checkMesh.log').write_text('Failed 1 mesh checks.\n')
        bin_dir = self.root / 'mock-bin'
        bin_dir.mkdir()
        checker = bin_dir / 'checkMesh'
        checker.write_text('#!/bin/bash\necho "Mesh OK."\n')
        checker.chmod(0o755)
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])
        command = ['bash', 'scripts/case_pipeline.sh', 'runs/checked', 'check', '1']
        result = subprocess.run(command, cwd=self.root, env=env, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        checker.write_text('#!/bin/bash\necho "Failed 1 mesh checks."\nexit 0\n')
        result = subprocess.run(command, cwd=self.root, env=env, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Mesh validation failed', result.stderr)

    def test_remesh_protects_existing_results(self):
        self.cli('new', 'cavity', 'protected')
        case = self.root / 'runs/protected'
        (case / 'constant/polyMesh').mkdir()
        (case / 'constant/polyMesh/points').write_text('preserve this mesh')
        (case / '0.1').mkdir()
        result = subprocess.run(['bash', 'scripts/case_pipeline.sh', 'runs/protected', 'remesh'],
                                cwd=self.root, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Results/partitions exist', result.stderr)
        self.assertEqual((case / 'constant/polyMesh/points').read_text(), 'preserve this mesh')

    def test_solve_refuses_changed_meshing_inputs(self):
        self.cli('new', 'cavity', 'stale')
        case = self.root / 'runs/stale'
        (case / '.mesh-complete').touch()
        signature = subprocess.check_output(['sha256sum', 'system/blockMeshDict'], cwd=case, text=True)
        (case / '.mesh-inputs.sha256').write_text(signature)
        with (case / 'system/blockMeshDict').open('a') as stream:
            stream.write('\n// a later mesh edit\n')
        result = subprocess.run(['bash', 'scripts/case_pipeline.sh', 'runs/stale', 'solve'],
                                cwd=self.root, text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Meshing inputs changed', result.stderr)


if __name__ == '__main__':
    unittest.main()
