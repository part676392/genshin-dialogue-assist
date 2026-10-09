"""Genshin dialogue click helper. Windows UI input only; explicit, bounded runs."""
from __future__ import annotations

import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import threading

import cv2
import numpy as np
from PIL import Image, ImageGrab
from mss import mss

BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
EVIDENCE = Path(tempfile.gettempdir()) / "genshin-click-probe"
U = C.WinDLL("user32", use_last_error=True)
K = C.WinDLL("kernel32", use_last_error=True)
A = C.WinDLL("advapi32", use_last_error=True)


class MOUSEINPUT(C.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", C.c_size_t)]


class KEYBDINPUT(C.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", C.c_size_t)]


class INPUTUNION(C.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(C.Structure):
    _fields_ = [("type", W.DWORD), ("data", INPUTUNION)]


def bind(dll, name, result, *args):
    fn = getattr(dll, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


find_window = bind(U, "FindWindowW", W.HWND, W.LPCWSTR, W.LPCWSTR)
foreground = bind(U, "GetForegroundWindow", W.HWND)
set_foreground = bind(U, "SetForegroundWindow", W.BOOL, W.HWND)
get_client_rect = bind(U, "GetClientRect", W.BOOL, W.HWND, C.POINTER(W.RECT))
client_to_screen = bind(U, "ClientToScreen", W.BOOL, W.HWND, C.POINTER(W.POINT))
window_pid = bind(U, "GetWindowThreadProcessId", W.DWORD, W.HWND, C.POINTER(W.DWORD))
window_at = bind(U, "WindowFromPoint", W.HWND, W.POINT)
ancestor = bind(U, "GetAncestor", W.HWND, W.HWND, W.UINT)
cursor_get = bind(U, "GetCursorPos", W.BOOL, C.POINTER(W.POINT))
cursor_set = bind(U, "SetCursorPos", W.BOOL, C.c_int, C.c_int)
send_input = bind(U, "SendInput", W.UINT, W.UINT, C.POINTER(INPUT), C.c_int)
key_state = bind(U, "GetAsyncKeyState", W.SHORT, C.c_int)
is_iconic = bind(U, "IsIconic", W.BOOL, W.HWND)
open_process = bind(K, "OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
close_handle = bind(K, "CloseHandle", W.BOOL, W.HANDLE)
process_path = bind(K, "QueryFullProcessImageNameW", W.BOOL, W.HANDLE, W.DWORD,
                    W.LPWSTR, C.POINTER(W.DWORD))
open_token = bind(A, "OpenProcessToken", W.BOOL, W.HANDLE, W.DWORD, C.POINTER(W.HANDLE))
token_info = bind(A, "GetTokenInformation", W.BOOL, W.HANDLE, C.c_int, W.LPVOID,
                  W.DWORD, C.POINTER(W.DWORD))
try:
    bind(U, "SetProcessDpiAwarenessContext", W.BOOL, W.HANDLE)(C.c_void_p(-4))
except AttributeError:
    bind(U, "SetProcessDPIAware", W.BOOL)()


def elevated(pid):
    process = open_process(0x1000, False, pid)
    token = W.HANDLE()
    value, size = W.DWORD(), W.DWORD()
    try:
        if not process or not open_token(process, 8, C.byref(token)):
            raise C.WinError(C.get_last_error())
        if not token_info(token, 20, C.byref(value), C.sizeof(value), C.byref(size)):
            raise C.WinError(C.get_last_error())
        return bool(value.value)
    finally:
        if token:
            close_handle(token)
        if process:
            close_handle(process)


def game_window():
    for title in ("原神", "Genshin Impact"):
        hwnd = find_window(None, title)
        if not hwnd:
            continue
        pid = W.DWORD()
        window_pid(hwnd, C.byref(pid))
        process = open_process(0x1000, False, pid.value)
        if not process:
            continue
        try:
            buf, size = C.create_unicode_buffer(32768), W.DWORD(32768)
            if process_path(process, 0, buf, C.byref(size)):
                if Path(buf.value).name.lower() in ("genshinimpact.exe", "yuanshen.exe"):
                    return hwnd, pid.value
        finally:
            close_handle(process)
    raise RuntimeError("原神のウィンドウが見つかりません。")


def bounds(hwnd):
    rect, point = W.RECT(), W.POINT()
    if is_iconic(hwnd) or not get_client_rect(hwnd, C.byref(rect)):
        raise RuntimeError("原神の画面を表示してください。")
    if not client_to_screen(hwnd, C.byref(point)):
        raise C.WinError(C.get_last_error())
    width, height = rect.right, rect.bottom
    if width < 640 or height < 360 or abs(width / height - 16 / 9) > 0.05:
        raise RuntimeError("この試作版は16:9の画面で使用してください。")
    return point.x, point.y, point.x + width, point.y + height


_capture_local = threading.local()


def capture(hwnd):
    # Reuse the native capture DC and copy only the game's client rectangle.
    # This is a normal desktop capture, with no game hooks or process injection.
    if not hasattr(_capture_local, 'screen'):
        _capture_local.screen = mss(with_cursor=False)
    shot = _capture_local.screen.grab(bounds(hwnd))
    return Image.frombytes('RGB', shot.size, shot.bgra, 'raw', 'BGRX')


def gray(image):
    return cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)


def region(image, box, resample=Image.Resampling.LANCZOS):
    """Read a reference-resolution ROI without resizing the whole game frame."""
    if image.size == (1920, 1080):
        return image.crop(box)
    xscale, yscale = image.width / 1920, image.height / 1080
    source = (box[0]*xscale, box[1]*yscale, box[2]*xscale, box[3]*yscale)
    return image.resize((box[2]-box[0], box[3]-box[1]), resample, box=source)


class DialogueDetector:
    def __init__(self):
        self.history = gray(Image.open(ASSETS / "history.png"))
        # The surrounding translucent circle changes with the scene behind it.
        # Compare the list glyph in the centre, keeping the same strict score.
        self.history_glyph = self.history[6:-6, 6:-6]
        self.eye = gray(Image.open(ASSETS / "eye.png"))
        # Like history, the eye's outer circle is translucent. Match its glyph
        # so scene brightness cannot switch dialogue detection on and off.
        self.eye_glyph = self.eye[6:-6, 6:-6]
        self.choice = gray(Image.open(ASSETS / "choice.png"))

    @staticmethod
    def match(region, template):
        return float(cv2.minMaxLoc(cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED))[1])

    def inspect(self, image, detect_choice=True):
        # "再生中" is shorter than "オート再生" and moves these icons left.
        header = gray(region(image, (185,20,387,85)))
        history_full = self.match(header[:, :125], self.history)
        history = self.match(header[:, :125], self.history_glyph)
        eye_full = self.match(header[:, 80:], self.eye)
        eye = self.match(header[:, 80:], self.eye_glyph)
        name = np.asarray(region(image, (550,835,1370,900)))
        yellow = int(np.sum((name[:, :, 0] > 190) & (name[:, :, 1] > 140)
                            & (name[:, :, 2] < 110)))
        text = np.asarray(region(image, (250,902,1670,985)))
        r,g,b=text[:,:,0],text[:,:,1],text[:,:,2]
        lo=np.minimum(np.minimum(r,g),b)
        hi=np.maximum(np.maximum(r,g),b)
        white = int(np.sum((lo > 215) & (hi-lo < 25)))
        dialogue = history > 0.94 and eye > 0.94 and (yellow > 60 or white > 80)
        choice = self.match(gray(region(image, (1030,390,1850,850))),self.choice) if dialogue and detect_choice else 0
        state = "choice" if dialogue and choice > 0.88 else "dialogue" if dialogue else "unknown"
        return {"state": state, "history": round(history, 4), "history_full": round(history_full,4), "eye": round(eye, 4), "eye_full": round(eye_full,4),
                "choice": round(choice, 4), "yellow": yellow, "white": white}

    def choice_point(self, image):
        g = gray(image.resize((1920, 1080), Image.Resampling.LANCZOS))
        scores = cv2.matchTemplate(g[390:850, 1030:1850], self.choice, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(scores > .88)
        if not len(ys):
            raise RuntimeError('会話の選択肢が見つかりません。')
        first = int(np.lexsort((xs, ys))[0])
        return ((1030 + int(xs[first]) + self.choice.shape[1] + 70) / 1920,
                (390 + int(ys[first]) + self.choice.shape[0] / 2) / 1080)


def guard(hwnd, x, y):
    if foreground() != hwnd:
        raise RuntimeError("原神からフォーカスが外れたため停止しました。")
    if ancestor(window_at(W.POINT(x, y)), 2) != hwnd:
        raise RuntimeError("クリック位置が別ウィンドウで覆われているため停止しました。")
    if key_state(0x77) & 0x8000 or key_state(0x78) & 0x8000 or key_state(0x1B) & 0x8000:
        raise RuntimeError("停止キーが押されました。")


def click(hwnd, rx=0.5, ry=0.91):
    left, top, right, bottom = bounds(hwnd)
    x, y = left + round((right - left) * rx), top + round((bottom - top) * ry)
    guard(hwnd, x, y)
    if key_state(0x01) & 0x8000:
        raise RuntimeError("マウスを手動で押しているため停止しました。")
    if not cursor_set(x, y):
        raise C.WinError(C.get_last_error())
    time.sleep(0.10)
    point = W.POINT()
    if not cursor_get(C.byref(point)) or abs(point.x - x) > 3 or abs(point.y - y) > 3:
        raise RuntimeError("カーソル位置が変わったため停止しました。")
    guard(hwnd, x, y)
    down, up = INPUT(), INPUT()
    down.data.mi.dwFlags, up.data.mi.dwFlags = 2, 4
    sent_down = send_input(1, C.byref(down), C.sizeof(INPUT))
    try:
        if sent_down != 1:
            raise RuntimeError(f"クリック送信失敗: down={sent_down}, error={C.get_last_error()}")
        time.sleep(0.08)
    finally:
        sent_up = send_input(1, C.byref(up), C.sizeof(INPUT))
    if sent_up != 1:
        raise RuntimeError(f"クリック解放失敗: up={sent_up}, error={C.get_last_error()}")
    return {"x": x, "y": y, "down": sent_down, "up": sent_up}


def require_matching_privilege(pid):
    if elevated(pid) and not elevated(os.getpid()):
        raise RuntimeError("原神が管理者権限です。同梱の「起動」ショートカットを使ってください。")


def choose_f(hwnd):
    left, top, right, bottom = bounds(hwnd)
    guard(hwnd, (left + right) // 2, (top + bottom) // 2)
    if key_state(0x46) & 0x8000:
        return False
    scan = bind(U, 'MapVirtualKeyW', W.UINT, W.UINT, W.UINT)(0x46, 0)
    down, up = INPUT(), INPUT()
    down.type = up.type = 1
    down.data.ki.wScan = up.data.ki.wScan = scan
    down.data.ki.dwFlags, up.data.ki.dwFlags = 8, 10
    sent = send_input(1, C.byref(down), C.sizeof(INPUT))
    try:
        if sent != 1:
            raise RuntimeError('Fキー入力が拒否されました。')
        time.sleep(.07)
    finally:
        released = send_input(1, C.byref(up), C.sizeof(INPUT))
    if released != 1:
        raise RuntimeError('Fキーを解放できませんでした。')
    return True


def activate_game(hwnd):
    """Transfer input focus once, on explicit start; never during the click loop."""
    if foreground() == hwnd:
        return True
    if is_iconic(hwnd):
        bind(U, 'ShowWindow', W.BOOL, W.HWND, C.c_int)(hwnd, 9)
    set_foreground(hwnd)
    for _ in range(4):
        if foreground() == hwnd:
            return True
        time.sleep(.05)
    current_thread = bind(K, 'GetCurrentThreadId', W.DWORD)()
    attach = bind(U, 'AttachThreadInput', W.BOOL, W.DWORD, W.DWORD, W.BOOL)
    threads = {window_pid(foreground(), None), window_pid(hwnd, None)} - {0, current_thread}
    attached = []
    try:
        for thread_id in threads:
            if attach(current_thread, thread_id, True):
                attached.append(thread_id)
        bind(U, 'BringWindowToTop', W.BOOL, W.HWND)(hwnd)
        set_foreground(hwnd)
        bind(U, 'SetFocus', W.HWND, W.HWND)(hwnd)
    finally:
        for thread_id in reversed(attached):
            attach(current_thread, thread_id, False)
    for _ in range(6):
        if foreground() == hwnd:
            return True
        time.sleep(.05)
    return False


def probe(report):
    """One click only, gated by the exact dialogue the user asked us to test."""
    result = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "input_size": C.sizeof(INPUT)}
    try:
        hwnd, pid = game_window()
        result.update(game_pid=pid, elevated=elevated(os.getpid()), game_elevated=elevated(pid))
        require_matching_privilege(pid)
        if not set_foreground(hwnd):
            raise RuntimeError("原神を前面にできませんでした。入力していません。")
        time.sleep(0.6)
        before = capture(hwnd)
        before.save(EVIDENCE / "admin-before.png")
        result["screen"] = DialogueDetector().inspect(before)
        normalized = before.resize((1920, 1080))
        expected = gray(Image.open(ASSETS / "probe-dialogue.png"))
        current = gray(normalized.crop((750, 910, 1170, 945)))
        similarity = float(cv2.matchTemplate(current, expected, cv2.TM_CCOEFF_NORMED)[0, 0])
        result["expected_dialogue_similarity"] = round(similarity, 4)
        if result["screen"]["state"] != "choice" or similarity < 0.95:
            raise RuntimeError("確認済みの会話画面から変化したため単発テストを中止しました。")
        result["click"] = click(hwnd, 1550 / 1920, 730 / 1080)
        time.sleep(2)
        capture(hwnd).save(EVIDENCE / "admin-after.png")
        result["status"] = "sent_one_click_check_screenshots"
    except Exception as exc:
        result.update(status="stopped", error=str(exc))
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


class Session:
    def __init__(self, seconds=30):
        if not 1 <= seconds <= 30:
            raise ValueError("実行時間は1〜30秒です。")
        self.hwnd, self.pid = game_window()
        require_matching_privilege(self.pid)
        self.detector = DialogueDetector()
        if not activate_game(self.hwnd):
            raise RuntimeError("入力先を切り替えられませんでした。原神内を1回クリックし、F8を押してください。")
        self.next_at = time.monotonic() + 0.7
        self.end_at = self.next_at + seconds
        self.events = []
        self.count = 0
        self.done = False
        self.message = "原神の会話画面を確認しています。"

    def stop(self, reason):
        self.done, self.message = True, reason

    def tick(self):
        if self.done:
            return
        now = time.monotonic()
        if now >= self.end_at:
            self.stop("時間になったため停止しました。")
            return
        if now < self.next_at:
            return
        try:
            if key_state(0x1B) & 0x8000:
                raise RuntimeError("Escで停止しました。")
            if game_window() != (self.hwnd, self.pid) or foreground() != self.hwnd:
                raise RuntimeError("原神からフォーカスが外れたため停止しました。")
            frame = capture(self.hwnd)
            state = self.detector.inspect(frame)
            self.events.append({"screen": state})
            if state["state"] == "choice":
                self.stop("選択肢で停止しました。選んだ後にF8で再開できます。")
            elif state["state"] != "dialogue":
                self.stop("会話画面を確認できないため停止しました。")
            else:
                self.events[-1]["click"] = click(self.hwnd)
                self.count += 1
                self.message = f"会話送り中: {self.count}回 / 残り{max(0, int(self.end_at - now))}秒"
                self.next_at = time.monotonic() + 1.0
        except Exception as exc:
            self.stop(str(exc))


def burst(seconds, report):
    result = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": seconds}
    try:
        session = Session(seconds)
        capture(session.hwnd).save(EVIDENCE / "burst-before.png")
        while not session.done:
            session.tick()
            time.sleep(0.05)
        time.sleep(1)
        capture(session.hwnd).save(EVIDENCE / "burst-after.png")
        result.update(status="stopped", clicks=session.count, reason=session.message, events=session.events)
    except Exception as exc:
        result.update(status="stopped", error=str(exc))
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def gui(*args, **kwargs):
    from launch_current import launch
    launch()


def main():
    if '--inspect' in sys.argv:
        hwnd,pid=game_window()
        print(json.dumps(dict(pid=pid,elevated=elevated(os.getpid()),game_elevated=elevated(pid),
            bounds=bounds(hwnd),screen=DialogueDetector().inspect(capture(hwnd))),ensure_ascii=False))
    else:
        from launch_current import launch
        launch()


if __name__=='__main__':main()
