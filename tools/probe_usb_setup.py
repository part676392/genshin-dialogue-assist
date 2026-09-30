"""Exercise the actual USB setup button three times; observe-only, no keys sent."""
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from qfluentwidgets import setTheme, setThemeColor, Theme
import auto_dialogue as a
from assist_ui import Panel, GREEN
from hid_input import VirtualKeyboard


def main():
    result_path=Path(sys.argv[1])
    app=QApplication([])
    setTheme(Theme.LIGHT);setThemeColor(GREEN)
    with tempfile.TemporaryDirectory() as directory:
        a.DATA=Path(directory)
        keyboard=VirtualKeyboard()
        if not keyboard.try_connect():raise RuntimeError(keyboard.error)
        watcher=a.Watcher(observe_only=True,backend=keyboard)
        panel=Panel(watcher,a.DATA)
        panel.show_quietly()
        rounds=[]
        deadline=time.monotonic()+45
        started=False
        def poll():
            nonlocal started
            if time.monotonic()>deadline:
                rounds.append({'ok':False,'error':'setup timeout'})
                finish();return
            if not started:
                started=True;panel.setup_button.click();return
            if panel.setup_future is None:
                rounds.append({'ok':keyboard.ready,'error':keyboard.error})
                if not keyboard.ready or len(rounds)>=3:
                    finish();return
                panel.setup_button.click()
        def finish():
            timer.stop()
            result_path.parent.mkdir(parents=True,exist_ok=True)
            panel.grab().save(str(result_path.with_suffix('.png')))
            result={'version':a.VERSION,'rounds':rounds,'inputs':watcher.count,
                    'passed':len(rounds)==3 and all(r['ok'] for r in rounds) and watcher.count==0}
            result_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
            panel.close()
        timer=QTimer();timer.timeout.connect(poll);timer.start(100)
        app.exec()
        keyboard.close()
    return 0 if json.loads(result_path.read_text())['passed'] else 1


if __name__=='__main__':sys.exit(main())
