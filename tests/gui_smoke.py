import sys
import tempfile
import threading
import time
import tkinter as tk
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sw2urdf.gui import ConversionApp


def main():
    with tempfile.TemporaryDirectory(prefix='sw2urdf-gui-smoke-') as temporary:
        folder = Path(temporary).resolve()
        source = folder / '貼上來源 with spaces'
        (source / 'urdf').mkdir(parents=True)
        urdf = source / 'urdf/assembly.urdf'
        urdf.write_text('<robot name="assembly"><link name="base"/></robot>', encoding='utf-8')
        target = folder / '貼上輸出/robot_description'
        root = tk.Tk()
        root.withdraw()
        try:
            app = ConversionApp(root)
            app.source.set('"' + str(source) + '"')
            app.target.set('"' + str(target) + '"')
            app.urdf_name.set('"' + str(urdf) + '"')
            app.generate_sdf.set(False)
            assert str(app.urdf_selection.cget('state')) == 'normal'
            with patch('sw2urdf.gui.filedialog.askdirectory') as browse, \
                    patch('sw2urdf.gui.messagebox.showerror') as error:
                app.convert_button.invoke()
                assert app.running
                deadline = time.monotonic() + 15
                while app.running and time.monotonic() < deadline:
                    root.update()
                    time.sleep(0.01)
                assert not app.running, 'GUI conversion did not finish'
                assert not error.called, error.call_args
                assert not browse.called
                assert app.status.get().startswith('Completed:')
                assert (target / 'urdf/assembly.urdf').is_file()
                assert not app.convert_button.instate(['disabled'])
            urdf.write_text('''<robot name="assembly"><link name="base"/><link name="tip"/>
              <joint name="tip" type="fixed"><parent link="base"/><child link="tip"/></joint></robot>''', encoding='utf-8')
            original = urdf.read_bytes()
            app.generate_sdf.set(True)
            main_thread = threading.get_ident()

            def fake_backend(backend, source_path, target_path):
                robot = ET.parse(str(source_path)).getroot()
                assert robot.find('joint').get('name') == 'tip_joint'
                target_path.write_text('<sdf version="1.12"><model name="assembly"><joint name="tip_joint" type="fixed"/></model></sdf>', encoding='utf-8')

            for answer in (False, True):
                output = folder / ('approved' if answer else 'declined') / 'robot_description'
                app.target.set(str(output))

                def confirm(*args, **kwargs):
                    assert threading.get_ident() == main_thread
                    assert 'tip -> tip_joint' in args[1]
                    return answer

                with patch('sw2urdf.gui.messagebox.askyesno', side_effect=confirm) as question, \
                        patch('sw2urdf.gui.messagebox.showerror') as error, \
                        patch('sw2urdf.sdf.SdfConverter._convert', new=fake_backend) as backend:
                    app.start_conversion()
                    deadline = time.monotonic() + 15
                    while app.running and time.monotonic() < deadline:
                        root.update()
                        time.sleep(0.01)
                    assert not app.running, 'GUI confirmation did not finish'
                    assert question.call_count == 1
                    assert urdf.read_bytes() == original
                    if answer:
                        assert not error.called, error.call_args
                        assert (output / 'urdf/robot.sdf').is_file()
                        assert ET.parse(str(output / 'urdf/assembly.urdf')).find('joint').get('name') == 'tip_joint'
                    else:
                        assert error.called and 'cancelled' in error.call_args.args[1]
                        assert not output.exists()
            print('PASS: GUI YES/NO confirmation on the main thread, consistent output joint names, cancellation and source preservation')
            print('PASS: real Tkinter GUI conversion using pasted quoted source/output/URDF paths, editable URDF field and worker completion')
        finally:
            root.destroy()


if __name__ == '__main__':
    main()
