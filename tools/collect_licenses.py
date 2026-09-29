"""Copy license notices from the installed build dependencies into licenses/."""
from importlib.metadata import distribution
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
NAMES=['PySide6','PySide6_Essentials','PySide6_Addons','shiboken6',
       'PySide6-Fluent-Widgets','PySideSix-Frameless-Window','darkdetect',
       'numpy','opencv-python','Pillow','mss','pyinstaller','pywin32','psutil',
       'charset-normalizer','typing-extensions','packaging']


def main():
    total=0
    for name in NAMES:
        package=distribution(name)
        for entry in package.files:
            filename=Path(str(entry)).name.lower()
            if filename.startswith(('license','licence','copying','copyright','notice')):
                source=package.locate_file(entry)
                if source.is_file():
                    # Preserve relative paths: NumPy and Qt ship several LICENSE files.
                    destination=ROOT/'licenses'/(name+'-'+package.version)/str(entry)
                    if not destination.resolve().is_relative_to((ROOT/'licenses').resolve()):
                        raise RuntimeError('Invalid license path: '+str(entry))
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,destination);total+=1
    shutil.copy2(Path(sys.base_prefix)/'LICENSE.txt',ROOT/'licenses'/'Python-LICENSE.txt')
    print('Copied license notices:',total)


if __name__=='__main__':main()
