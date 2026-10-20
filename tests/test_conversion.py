import hashlib
import os
import runpy
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from sw2urdf.core import ConversionError, convert_package


ROBOT = '''<robot name="assembly">
  <link name="base_link">
    <inertial><mass value="1"/><inertia ixx="1" ixy="0" ixz="0" iyy="1" iyz="0" izz="1"/></inertial>
    <visual><geometry><mesh filename="package://old_package/meshes/nested/base.STL"/></geometry></visual>
    <collision><geometry><mesh filename="../meshes/nested/base.STL"/></geometry></collision>
    <visual><geometry><box size="1 1 1"/></geometry><material name="paint"><texture filename="../textures/paint.png"/></material></visual>
  </link>
  <link name="tip"><inertial><mass value="1"/><inertia ixx="1" ixy="0" ixz="0" iyy="1" iyz="0" izz="1"/></inertial></link>
  <joint name="mount" type="fixed"><parent link="base_link"/><child link="tip"/><origin xyz="0 0 1" rpy="0 0 0"/></joint>
</robot>'''


def snapshot(path):
    return {
        p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in path.rglob('*') if p.is_file()
    }


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / 'SolidWorks 匯出'
        (self.source / 'urdf').mkdir(parents=True)
        (self.source / 'meshes/nested').mkdir(parents=True)
        (self.source / 'textures').mkdir()
        (self.source / 'urdf/assembly.urdf').write_text(ROBOT, encoding='utf-8')
        (self.source / 'meshes/nested/base.STL').write_bytes(b'mesh')
        (self.source / 'textures/paint.png').write_bytes(b'texture')
        self.target = self.root / 'output folder' / 'robot_description'

    def test_complete_package_preserves_source_and_geometry(self):
        before = snapshot(self.source)
        result = convert_package(self.source, self.target, generate_sdf=False)
        self.assertEqual(snapshot(self.source), before)
        self.assertEqual(result.package_name, 'robot_description')
        self.assertEqual(result.urdf_path, self.target / 'urdf/assembly.urdf')
        root = ET.parse(str(result.urdf_path)).getroot()
        self.assertEqual(root.find('joint').get('type'), 'fixed')
        self.assertEqual(root.find('joint/origin').get('xyz'), '0 0 1')
        self.assertEqual(root.find('link/inertial/mass').get('value'), '1')
        self.assertEqual(root.find('.//visual/geometry/mesh').get('filename'),
                         'package://robot_description/meshes/visual/nested/base.STL')
        self.assertEqual(root.find('.//collision/geometry/mesh').get('filename'),
                         'package://robot_description/meshes/collision/nested/base.STL')
        for path in ('robot_description/__init__.py', 'resource/robot_description',
                     'setup.py', 'setup.cfg', 'package.xml', 'launch/launch.py',
                     'rviz/view.rviz', 'meshes/visual/nested/base.STL',
                     'meshes/collision/nested/base.STL', 'textures/paint.png'):
            self.assertTrue((self.target / path).is_file(), path)
        manifest = (self.target / 'package.xml').read_text(encoding='utf-8')
        self.assertNotIn('ros_gz', manifest)
        self.assertFalse((self.target / 'urdf/robot.sdf').exists())
        self.assertIn('base_link', (self.target / 'rviz/view.rviz').read_text(encoding='utf-8'))

    def test_repeat_conversion_is_stable_and_preserves_unrelated_files(self):
        convert_package(self.source, self.target, generate_sdf=False)
        custom = self.target / 'notes.txt'
        custom.write_text('keep', encoding='utf-8')
        before = snapshot(self.target)
        convert_package(self.source, self.target, generate_sdf=False)
        self.assertEqual(snapshot(self.target), before)

    def test_missing_mesh_fails_before_touching_output(self):
        (self.source / 'meshes/nested/base.STL').unlink()
        with self.assertRaisesRegex(ConversionError, 'base.STL'):
            convert_package(self.source, self.target, generate_sdf=False)
        self.assertFalse(self.target.exists())

    def test_multiple_urdfs_require_selection(self):
        (self.source / 'urdf/second.urdf').write_text(ROBOT, encoding='utf-8')
        with self.assertRaisesRegex(ConversionError, 'URDF'):
            convert_package(self.source, self.target, generate_sdf=False)
        result = convert_package(self.source, self.target, urdf_name='second.urdf', generate_sdf=False)
        self.assertEqual(result.urdf_path.name, 'second.urdf')

    def test_package_name_can_differ_from_output_and_input_names(self):
        result = convert_package(self.source, self.target, package_name='custom_arm', generate_sdf=False)
        self.assertEqual(result.package_name, 'custom_arm')
        self.assertTrue((self.target / 'resource/custom_arm').is_file())

    def test_source_and_destination_must_be_separate(self):
        for target in (self.source, self.source / 'generated', self.source.parent):
            with self.subTest(target=target), self.assertRaises(ConversionError):
                convert_package(self.source, target, generate_sdf=False)

    def test_recursive_setup_data_survives_relocation(self):
        convert_package(self.source, self.target, generate_sdf=False)
        original_directory = Path.cwd()
        try:
            os.chdir(str(self.target))
            with patch('setuptools.setup') as setup:
                runpy.run_path(str(self.target / 'setup.py'))
            data = setup.call_args.kwargs['data_files']
            installed = {filename for _, filenames in data for filename in filenames}
            self.assertIn('meshes/visual/nested/base.STL', installed)
            self.assertIn('meshes/collision/nested/base.STL', installed)
            self.assertIn('textures/paint.png', installed)
        finally:
            os.chdir(str(original_directory))
        for p in self.target.rglob('*.py'):
            compile(p.read_text(encoding='utf-8'), str(p), 'exec')


if __name__ == '__main__':
    unittest.main()
