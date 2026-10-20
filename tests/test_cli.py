import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / 'conversion_urdf_ros_2_ros2.py'


class CliTests(unittest.TestCase):
    def test_headless_conversion_from_another_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'source export'
            (source / 'urdf').mkdir(parents=True)
            (source / 'urdf/assembly.urdf').write_text('<robot name="assembly"><link name="base"/></robot>', encoding='utf-8')
            target = root / 'output with spaces'
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(target),
                                     '--package-name', 'robot_description', '--urdf-only'],
                                    cwd=str(root), capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / 'setup.py').is_file())
            self.assertFalse((target / 'urdf/robot.sdf').exists())

    def test_dependency_error_is_actionable_and_does_not_create_package(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            source = root / 'source'
            (source / 'urdf').mkdir(parents=True)
            (source / 'urdf/assembly.urdf').write_text('<robot name="assembly"><link name="base"/></robot>', encoding='utf-8')
            target = root / 'robot_description'
            env = dict(os.environ, PATH='')
            result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(target), '--sdf-backend', 'gz'],
                                    capture_output=True, text=True, timeout=15, env=env)
            self.assertEqual(result.returncode, 1)
            self.assertIn('gz', result.stderr)
            self.assertFalse(target.exists())

    def test_declined_collision_reports_error_without_creating_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source'
            (source / 'urdf').mkdir(parents=True)
            urdf = source / 'urdf/assembly.urdf'
            urdf.write_text('<robot name="assembly"><link name="tip"/><joint name="tip" type="fixed"/></robot>', encoding='utf-8')
            before = urdf.read_bytes()
            for answer in ('NO\n', ''):
                with self.subTest(answer=answer):
                    target = root / 'robot_description'
                    result = subprocess.run([sys.executable, str(SCRIPT), str(source), str(target)],
                                            input=answer, capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn('tip -> tip_joint', result.stderr)
                    self.assertIn('cancelled', result.stderr)
                    self.assertFalse(target.exists())
                    self.assertEqual(urdf.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
