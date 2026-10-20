"""Verify an SDFormat 13 Python wheel against its sources and test it without installation."""
import argparse
from email.parser import BytesParser
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

from wheel.wheelfile import WheelFile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from export_sdformat13_python_wheel import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--sources', type=Path, required=True)
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    assert sys.version_info[:2] == (3, 8) and sys.platform == 'win32'
    assert importlib.util.find_spec('sdformat13') is None
    recipe, expected = prepare(args.sources.resolve())
    with WheelFile(str(wheel), 'r') as archive:
        assert set(archive.namelist()) == set(expected) | {archive.record_path}
        for name, data in expected.items():
            assert archive.read(name) == data, name
        metadata = BytesParser().parsebytes(archive.read(next(n for n in expected if n.endswith('/METADATA'))))
        assert not metadata.get_all('Requires-Dist')
        assert not any('api-ms-win-crt-' in name.lower() or name.lower().endswith('/ucrtbase.dll') for name in expected)
    print('PASS: wheel contents match the pinned source packages')
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith(('CONDA', 'MAMBA', 'PYTHON', 'SDF_', 'GZ_', 'IGN_', 'PIP_'))}
    environment.update(PATH=os.pathsep.join([str(Path(os.environ['SystemRoot']) / 'System32'), os.environ['SystemRoot']]),
                       PYTHONIOENCODING='utf-8', PIP_CONFIG_FILE=os.devnull)
    with tempfile.TemporaryDirectory(prefix='sdformat13-python-wheel-') as temporary:
        folder = Path(temporary).resolve()
        assert folder.parent == Path(tempfile.gettempdir()).resolve()

        def run(label, command, expected_code=0, answer=None):
            result = subprocess.run(command, cwd=str(folder), env=environment, input=answer,
                                    capture_output=True, encoding='utf-8', errors='replace', timeout=60)
            assert result.returncode == expected_code, (label, result.stdout, result.stderr)
            print('PASS:', label)
            return result

        downloads = folder / 'download'
        run('offline single-wheel resolution',
            [sys.executable, '-m', 'pip', '--isolated', 'download', '--no-index', '--only-binary=:all:',
             '--find-links', str(wheel.parent), '--dest', str(downloads),
             recipe['distribution'] + '==' + recipe['version']])
        assert [path.name for path in downloads.glob('*.whl')] == [wheel.name]
        package = folder / 'package'
        with zipfile.ZipFile(str(downloads / wheel.name)) as archive:
            archive.extractall(str(package))
        code = '''import sys
sys.path.insert(0,sys.argv[1])
if sys.argv[2]=='math-first':
    import gz.math7
import sdformat13,gz.math7
m=sdformat13.Model()
m.set_raw_pose(gz.math7.Pose3d(1,2,3,0,0,0))
assert m.raw_pose().pos()==gz.math7.Vector3d(1,2,3)
'''
        for order in ('sdf-first', 'math-first'):
            run('isolated bindings: ' + order, [sys.executable, '-I', '-S', '-c', code, str(package), order])
        environment['PYTHONPATH'] = str(package)
        run('native conversion, fixed joint, Unicode and asset relocation',
            [sys.executable, str(REPO / 'tests/native_smoke.py'), '--sdf-python', sys.executable])
    assert importlib.util.find_spec('sdformat13') is None
    print('PASS: system Python remains unchanged')


if __name__ == '__main__':
    main()
