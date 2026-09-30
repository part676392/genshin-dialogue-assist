"""Local USB HID keyboard using unmodified libVIIPER and usbip-win2.

No manufacturer impersonation options or SendInput fallback are provided here.
The USB/IP listener is bound to loopback only. The application sends only F.
"""
from __future__ import annotations

import ctypes as C
import hashlib
from pathlib import Path
import subprocess
import threading
import time
import winreg

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / 'vendor'
INSTALLER_NAME = 'USBip-0.9.8.1-x64.exe'
INSTALLER_SHA256 = '38cad6d4432b52d5bb9409d9ad03b72fdffc4ada4cd3a48fbeca1a2752a8518a'
F_USAGE = 0x09


class USBServerConfig(C.Structure):
    _fields_ = [('addr', C.c_char_p), ('connection_timeout_ms', C.c_uint64),
                ('device_handler_connect_timeout_ms', C.c_uint64),
                ('write_batch_flush_interval_ms', C.c_uint32)]


class KeyboardState(C.Structure):
    _fields_ = [('Modifiers', C.c_uint8), ('KeyBitmap', C.c_uint8 * 32)]


def keyboard_state(pressed=False):
    state = KeyboardState()
    if pressed:
        state.KeyBitmap[F_USAGE // 8] = 1 << (F_USAGE % 8)
    return state


def driver_installed():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r'SYSTEM\CurrentControlSet\Services\usbip2_ude'):
            return True
    except FileNotFoundError:
        return False


class VirtualKeyboard:
    kind = 'usb-hid'
    label = 'USB キーボード'

    def __init__(self, library=None):
        self.lib = library
        self.server = C.c_size_t()
        self.bus = C.c_uint32()
        self.device = C.c_size_t()
        self.lock = threading.RLock()
        self.ready = False
        self.error = ''
        self._log_callback = None
        self._messages = []
        self._bus_created = False

    def connect(self):
        with self.lock:
            if self.ready:
                return
            if self.lib is None:
                if not driver_installed():
                    raise RuntimeError('右上の「USB設定」で初回セットアップを行ってください。')
                path = VENDOR / 'libVIIPER.dll'
                if not path.exists():
                    raise RuntimeError('入力用DLLがありません。ZIPをすべて展開してください。')
                self.lib = C.CDLL(str(path))
                signatures = {
                    'NewUSBServer': [C.POINTER(USBServerConfig), C.POINTER(C.c_size_t), C.c_void_p],
                    'CreateUSBBus': [C.c_size_t, C.POINTER(C.c_uint32)],
                    'RemoveUSBBus': [C.c_size_t, C.c_uint32],
                    'CreateKeyboardDevice': [C.c_size_t, C.POINTER(C.c_size_t), C.c_uint32,
                                             C.c_bool, C.c_uint16, C.c_uint16],
                    'SetKeyboardDeviceState': [C.c_size_t, KeyboardState],
                    'RemoveKeyboardDevice': [C.c_size_t],
                    'CloseUSBServer': [C.c_size_t],
                }
                for name, args in signatures.items():
                    function = getattr(self.lib, name)
                    function.argtypes, function.restype = args, C.c_bool
            callback_type = C.CFUNCTYPE(None, C.c_int, C.c_char_p)
            def record(level, message):
                if level >= 4:
                    self._messages.append((message or b'').decode('utf-8', errors='replace'))
                    self._messages[:] = self._messages[-8:]
            # Keep the same callback alive across reconnects: the previous
            # server's shutdown goroutine can log after CloseUSBServer returns.
            if self._log_callback is None:
                self._log_callback = callback_type(record)
            # Port 0 allocates an unused port. Native auto-attach uses that actual port.
            config = USBServerConfig(b'127.0.0.1:0', 30000, 5000, 1)
            try:
                if not self.lib.NewUSBServer(C.byref(config), C.byref(self.server), self._log_callback):
                    raise RuntimeError('ローカル入力サーバーを起動できませんでした。')
                if not self.lib.CreateUSBBus(self.server, C.byref(self.bus)):
                    raise RuntimeError('仮想USBバスを作成できませんでした。')
                self._bus_created = True
                # Keep upstream's default identifiers; do not impersonate an installed device.
                if not self.lib.CreateKeyboardDevice(self.server, C.byref(self.device),
                        self.bus, True, 0, 0):
                    detail = self._messages[-1] if self._messages else 'driver attach failed'
                    raise RuntimeError('USBキーボードを接続できません。再起動後にお試しください。 ' + detail)
                self.ready = True
                self.release()
                self.error = ''
            except Exception:
                self.close()
                raise

    def try_connect(self):
        try:
            self.connect()
            return True
        except Exception as exc:
            self.error = str(exc)
            return False

    def release(self):
        with self.lock:
            if self.device.value and not self.lib.SetKeyboardDeviceState(self.device, keyboard_state()):
                raise RuntimeError('USBキーの解放に失敗しました。入力を停止しました。')

    def tap_f(self, hold=.025):
        with self.lock:
            if not self.ready:
                raise RuntimeError(self.error or 'USBキーボードが接続されていません。')
            try:
                if not self.lib.SetKeyboardDeviceState(self.device, keyboard_state(True)):
                    raise RuntimeError('USBキー送信に失敗しました。')
                time.sleep(hold)
            finally:
                try:
                    self.release()
                except Exception:
                    # Remove the device if a key-up cannot be submitted.
                    self.close()
                    raise
            return True

    def close(self):
        with self.lock:
            self.ready = False
            errors = []
            if self.device.value:
                try:
                    self.lib.SetKeyboardDeviceState(self.device, keyboard_state())
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    try:
                        self.lib.RemoveKeyboardDevice(self.device)
                    except Exception as exc:
                        errors.append(str(exc))
                    finally:
                        self.device = C.c_size_t()
            if self.server.value:
                try:
                    # libVIIPER 0.8.1 CloseUSBServer closes only the listener.
                    # Release the process-wide bus allocation explicitly first,
                    # including a bus whose keyboard failed to auto-attach.
                    if self._bus_created:
                        self.lib.RemoveUSBBus(self.server, self.bus)
                except Exception as exc:
                    errors.append(str(exc))
                finally:
                    try:
                        self.lib.CloseUSBServer(self.server)
                    except Exception as exc:
                        errors.append(str(exc))
                    finally:
                        self.server = C.c_size_t()
                        self.bus = C.c_uint32()
                        self._bus_created = False
            if errors:
                self.error = '; '.join(errors)


def install_driver(log_dir):
    """Install the pinned upstream package; never restart Windows automatically."""
    installer = VENDOR / INSTALLER_NAME
    if not installer.exists():
        raise RuntimeError('セットアップ用ファイルがありません。配布ZIPを展開し直してください。')
    if hashlib.sha256(installer.read_bytes()).hexdigest() != INSTALLER_SHA256:
        raise RuntimeError('セットアップファイルの検証に失敗しました。再ダウンロードしてください。')
    if not C.windll.shell32.IsUserAnAdmin():
        raise RuntimeError('初回設定には管理者権限が必要です。アプリを管理者として起動してください。')
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES',
        '/NORESTART', '/SP-', '/TYPE=compact', '/TASKS=vcredist',
        '/LOG=' + str(log_dir / 'usb-driver-setup.log')],
        creationflags=subprocess.CREATE_NO_WINDOW, timeout=180, check=False)
    if result.returncode not in (0, 3010):
        raise RuntimeError(f'USB設定に失敗しました（コード {result.returncode}）。')
    return result.returncode
