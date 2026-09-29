"""Download unmodified pinned USB dependencies and verify their SHA-256 hashes."""
import hashlib
from pathlib import Path
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
VENDOR=ROOT/'vendor'
FILES=[
    ('https://github.com/Alia5/VIIPER/releases/download/v0.8.1/viiper-libVIIPER-windows-amd64.zip',
     'viiper-libVIIPER-windows-amd64.zip',
     'a87d2d5c5166da698189de3d1ed51d71c0b5faa94a11c3729d50ec037af3ceac'),
    ('https://github.com/vadimgrn/usbip-win2/releases/download/v.0.9.8.1/USBip-0.9.8.1-x64.exe',
     'USBip-0.9.8.1-x64.exe',
     '38cad6d4432b52d5bb9409d9ad03b72fdffc4ada4cd3a48fbeca1a2752a8518a'),
]


def main():
    VENDOR.mkdir(parents=True,exist_ok=True)
    for url,name,expected in FILES:
        path=VENDOR/name
        if not path.exists():
            request=urllib.request.Request(url,headers={'User-Agent':'DialogueAssist-build'})
            with urllib.request.urlopen(request,timeout=120) as response:
                path.write_bytes(response.read())
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('SHA-256 mismatch: '+name)
        if name.endswith('.zip'):
            with zipfile.ZipFile(path) as archive:
                for filename in ('libVIIPER.dll','libVIIPER.h','licenses.txt'):
                    entry=next(n for n in archive.namelist() if Path(n).name==filename)
                    (VENDOR/filename).write_bytes(archive.read(entry))
        print('Verified: '+name)


if __name__=='__main__':main()
