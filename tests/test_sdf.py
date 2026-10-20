import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

from sw2urdf.core import convert_package
from sw2urdf.sdf import SdfConverter, SdfError


class SdfTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name).resolve() / '模型 with spaces'
        self.folder.mkdir()
        self.urdf = self.folder / 'robot.urdf'
        self.urdf.write_text('''<robot name="demo"><link name="base"/><link name="tip"/>
          <joint name="mount" type="fixed"><parent link="base"/><child link="tip"/></joint>
          <link name="mesh"><visual><geometry><mesh filename="package://demo/meshes/visual/a.STL"/></geometry></visual></link>
          </robot>''', encoding='utf-8')
        self.output = self.folder / 'robot.sdf'

    def test_native_worker_preserves_fixed_joint_and_portable_uris(self):
        def worker(command, **options):
            self.assertFalse(options.get('shell', False))
            self.assertEqual(Path(command[0]), Path('C:/Runtime With Spaces/python.exe'))
            input_path = Path(command[-2])
            robot = ET.parse(str(input_path)).getroot()
            self.assertEqual(robot.find('joint').get('type'), 'fixed')
            self.assertEqual(robot.find('gazebo/preserveFixedJoint').text, 'true')
            Path(command[-1]).write_text('''<sdf version="1.12"><model name="demo">
              <link name="base"><visual name="v"><geometry><mesh>
              <uri>model://demo/meshes/visual/a.STL</uri></mesh></geometry></visual></link>
              <link name="tip"/><joint name="mount" type="fixed"/>
              </model></sdf>''', encoding='utf-8')
            return subprocess.CompletedProcess(command, 0, '', '')
        before = self.urdf.read_bytes()
        with patch('sw2urdf.sdf.subprocess.run', side_effect=worker):
            SdfConverter('python', 'C:/Runtime With Spaces/python.exe').convert(self.urdf, self.output)
        root = ET.parse(str(self.output)).getroot()
        self.assertEqual(root.find('.//uri').text, '../meshes/visual/a.STL')
        self.assertEqual(root.find('.//joint').get('type'), 'fixed')
        self.assertEqual(self.urdf.read_bytes(), before)

    def test_cli_passes_arguments_without_a_shell(self):
        xml = '<sdf version="1.9"><model name="demo"><joint name="mount" type="fixed"/></model></sdf>'
        with patch('sw2urdf.sdf.shutil.which', return_value='C:/Gazebo Bin/gz.exe'), \
                patch('sw2urdf.sdf.subprocess.run', return_value=subprocess.CompletedProcess([], 0, xml, '')) as run:
            SdfConverter('gz').convert(self.urdf, self.output)
        command = run.call_args.args[0]
        self.assertEqual(command[:3], ['C:/Gazebo Bin/gz.exe', 'sdf', '-p'])
        self.assertNotIn('>', command)
        self.assertFalse(run.call_args.kwargs.get('shell', False))

    def test_invalid_sdf_and_lost_fixed_joints_are_errors(self):
        for output in ('invalid', '<sdf version="1.9"><model name="demo"/></sdf>'):
            with self.subTest(output=output), \
                    patch('sw2urdf.sdf.shutil.which', return_value='gz'), \
                    patch('sw2urdf.sdf.subprocess.run', return_value=subprocess.CompletedProcess([], 0, output, '')), \
                    self.assertRaises(SdfError):
                SdfConverter('gz').convert(self.urdf, self.output)

    def test_auto_falls_back_only_for_missing_bindings(self):
        xml = '<sdf version="1.9"><model name="demo"><joint name="mount" type="fixed"/></model></sdf>'
        responses = [subprocess.CompletedProcess([], 3, '', 'bindings missing'),
                     subprocess.CompletedProcess([], 0, xml, '')]
        backend = SdfConverter()
        with patch('sw2urdf.sdf.shutil.which', return_value='gz'), \
                patch('sw2urdf.sdf.subprocess.run', side_effect=responses):
            backend.convert(self.urdf, self.output)
        self.assertEqual(backend.selected_backend, 'gz')
        with patch('sw2urdf.sdf.subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'invalid input')), \
                patch('sw2urdf.sdf.shutil.which') as executable, self.assertRaisesRegex(SdfError, 'invalid input'):
            SdfConverter().convert(self.urdf, self.output)
        executable.assert_not_called()

    def test_backend_failure_preserves_existing_output(self):
        class FailedBackend:
            def convert(self, source, target):
                raise SdfError('fixture conversion failed')
        source = self.folder / 'source'
        (source / 'urdf').mkdir(parents=True)
        (source / 'urdf/test.urdf').write_text('<robot name="test"><link name="base"/></robot>', encoding='utf-8')
        target = self.folder / 'robot_description'
        target.mkdir()
        existing = target / 'package.xml'
        existing.write_text('keep', encoding='utf-8')
        with self.assertRaises(SdfError):
            convert_package(source, target, generate_sdf=True, sdf_converter=FailedBackend())
        self.assertEqual(existing.read_text(encoding='utf-8'), 'keep')
        self.assertEqual([p.name for p in target.iterdir()], ['package.xml'])


if __name__ == '__main__':
    unittest.main()
