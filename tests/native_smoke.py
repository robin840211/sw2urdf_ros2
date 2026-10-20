import argparse
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_conversion import ROBOT, snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdf-python', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='sw2urdf-native-smoke-') as temporary:
        folder = Path(temporary).resolve()
        source = folder / '來源 with spaces'
        (source / 'urdf').mkdir(parents=True)
        (source / 'meshes/nested').mkdir(parents=True)
        (source / 'textures').mkdir()
        (source / 'urdf/assembly.urdf').write_text(ROBOT, encoding='utf-8')
        shutil.copy2(str(ROOT / 'test_urdf/meshes/base_link.STL'), str(source / 'meshes/nested/base.STL'))
        (source / 'textures/paint.png').write_bytes(b'texture')
        before = snapshot(source)
        target = folder / '輸出 folder/robot_description'
        result = subprocess.run([sys.executable, str(ROOT / 'conversion_urdf_ros_2_ros2.py'),
                                 str(source), str(target), '--sdf-backend', 'python',
                                 '--sdf-python', args.sdf_python], cwd=str(folder),
                                capture_output=True, encoding='utf-8', timeout=60)
        assert result.returncode == 0, result.stderr
        assert 'Package: ' in result.stdout
        sdf = ET.parse(str(target / 'urdf/robot.sdf')).getroot()
        assert len(sdf.findall('model/link')) == 2
        joint = sdf.find('model/joint')
        assert joint.get('name') == 'mount' and joint.get('type') == 'fixed'
        assert joint.find('pose').text.split()[:3] == ['0', '0', '1']
        assert sdf.find('model/link/inertial/mass').text == '1'
        for uri in sdf.findall('.//mesh/uri'):
            assert uri.text.startswith('../meshes/') and (target / 'urdf' / uri.text).is_file(), uri.text
        assert snapshot(source) == before
        relocated = folder / 'relocated_package'
        shutil.move(str(target), str(relocated))
        for uri in sdf.findall('.//mesh/uri'):
            assert (relocated / 'urdf' / uri.text).is_file()
        config = ET.parse(str(relocated / 'model.config')).getroot()
        assert config.find('sdf').get('version') == sdf.get('version')
        assert (relocated / config.find('sdf').text).is_file()
        print('PASS: native SDF CLI, Chinese and spaced paths, fixed joint, mass/pose, source hashes and relocation')


if __name__ == '__main__':
    main()
