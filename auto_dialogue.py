"""Local dialogue assistance. No AI/upload, cursor moves, or focus changes."""
from __future__ import annotations

import argparse
from collections import deque
import ctypes as C
import json
import os
from pathlib import Path
import sys
import time

import winsound

import numpy as np
from PIL import Image
import story_clicker as s

BASE = Path(__file__).resolve().parent
DATA = Path(os.environ['LOCALAPPDATA']) / 'GenshinDialogue'
TITLE = '原神 会話アシスト'
VERSION = '2.0.0'
# Explicit user setting after trying 500 ms and reporting it too slow.
# A 250 ms target is not a measured game minimum or an evasion claim.
TAP_PERIOD = .250
KEY_HOLD = .025
IDLE_PERIOD = .150


def signature(frame, dialogue=False):
    image = frame if frame.size==(1920,1080) else frame.resize((1920, 1080))
    if dialogue:
        image = image.crop((240, 400, 1820, 990))
    else:
        image = image.crop((70, 100, 1830, 1000))
    return np.asarray(image.convert('L').resize((160, 90)), dtype=np.int16)


def caption_signature(frame):
    frame = frame if frame.size==(1920,1080) else frame.resize((1920,1080))
    pixels = np.asarray(frame.crop((250, 835, 1670, 985)))
    r,g,b=pixels[:,:,0],pixels[:,:,1],pixels[:,:,2]
    lo=np.minimum(np.minimum(r,g),b);hi=np.maximum(np.maximum(r,g),b)
    white = (lo > 210) & (hi-lo < 30)
    return np.asarray(Image.fromarray(white.astype('uint8') * 255).resize((284, 30)), dtype=np.int16)


def changed(current, previous, threshold=6):
    if previous is None:
        return True
    delta = np.abs(current - previous)
    return float(delta.mean()) > threshold


class DialoguePolicy:
    """Screen/timer decisions, tested with real captured fixtures and a fake clock."""
    def __init__(self, notify_after=60, detector=None):
        self.detector = detector or s.DialogueDetector()
        self.notify_after = notify_after
        self.state = None
        self.confirmations = 0
        self.had_dialogue = False
        self.anchor = None
        self.progress_at = None
        self.notified = False
        self.last_detection = None

    def suspend(self):
        self.state = None
        self.confirmations = 0
        self.anchor = None
        self.progress_at = None
        self.notified = False

    def inspect(self, frame, now):
        self.last_detection = self.detector.inspect(frame)
        state = self.last_detection['state']
        active = state in ('dialogue', 'choice')
        if state != self.state:
            self.state = state
            self.confirmations = 1
            self.anchor = None
            self.progress_at = now
            self.notified = False
        else:
            self.confirmations += 1
        if active:
            self.had_dialogue = True
            sample = caption_signature(frame)
            # Options may change while the narrator caption stays the same.
            if state == 'choice':
                sample = signature(frame, dialogue=True)
            threshold = 1.5 if state == 'dialogue' else 6
        else:
            sample, threshold = signature(frame), 6
        if changed(sample, self.anchor, threshold):
            self.anchor = sample
            self.progress_at = now
            self.notified = False
        seconds = now - self.progress_at
        stalled = self.had_dialogue and seconds >= self.notify_after
        notify = stalled and not self.notified
        if notify:
            self.notified = True
        action = None
        if active and self.confirmations >= 2 and not stalled:
            action = 'F'
        return dict(state=state, action=action, notify=notify, stalled=stalled,
                    stable_seconds=int(seconds))


def tap_key(hwnd, name, backend=None):
    """Send a short keyboard tap; never touch cursor position or confinement."""
    if name != 'F':
        raise ValueError('会話送りの入力はFだけです。')
    vk = 0x46
    left, top, right, bottom = s.bounds(hwnd)
    s.guard(hwnd, (left + right)//2, (top + bottom)//2)
    if any(s.key_state(key) & 0x8000 for key in (vk,0x01,0x10,0x11,0x12)):
        return False
    if backend is not None:
        return backend.tap_f(KEY_HOLD)
    scan = s.bind(s.U, 'MapVirtualKeyW', s.W.UINT, s.W.UINT, s.W.UINT)(vk, 0)
    down, up = s.INPUT(), s.INPUT()
    down.type = up.type = 1
    down.data.ki.wScan = up.data.ki.wScan = scan
    down.data.ki.dwFlags, up.data.ki.dwFlags = 8, 10
    assert C.sizeof(s.INPUT) == 40
    sent = s.send_input(1, C.byref(down), C.sizeof(s.INPUT))
    try:
        if sent != 1:
            raise RuntimeError('キーを送れませんでした。管理者として起動し直してください。')
        time.sleep(KEY_HOLD)
    finally:
        released = s.send_input(1, C.byref(up), C.sizeof(s.INPUT))
    if released != 1:
        raise RuntimeError('キーの解放を確認できませんでした。')
    return True


class Watcher:
    def __init__(self, notify_after=60, sound=True, observe_only=False, backend=None):
        self.policy = DialoguePolicy(notify_after)
        self.enabled, self.sound, self.observe_only = True, sound, observe_only
        self.title, self.detail = '会話を待っています', '原神の会話が始まったら、自動で送ります。'
        self.mode, self.count, self.alerts = 'waiting', 0, 0
        self.next_at = 0
        self.target = None
        self.events = deque(maxlen=120)
        self.last_snapshot = 0
        self.last_mode = None
        self.input_times = deque(maxlen=40)
        self.pause_reason = None
        self.backend = backend
        self.setup_in_progress = False

    def toggle(self, reason='button'):
        self.enabled = not self.enabled
        self.pause_reason = reason if not self.enabled else None
        self.events.append(dict(at=time.strftime('%H:%M:%S'),control=reason,enabled=self.enabled))
        self.policy.suspend()
        self.next_at = 0

    def status(self):
        times=[stamp for stamp in self.input_times if time.monotonic()-stamp<=5]
        rate=(len(times)-1)/(times[-1]-times[0]) if len(times)>1 and times[-1]>times[0] else 0
        return dict(pid=os.getpid(), enabled=self.enabled, mode=self.mode, title=self.title,
                    detail=self.detail, inputs=self.count, alerts=self.alerts,
                    notify_after=self.policy.notify_after, sound=self.sound,
                    ai_calls=0, observe_only=self.observe_only, foreground=s.foreground(),
                    target=self.target, events=list(self.events),version=VERSION,input_key='F',
                    target_interval_ms=round(TAP_PERIOD*1000),recent_inputs_per_second=round(rate,2),
                    updated_at=time.strftime('%Y-%m-%dT%H:%M:%S'),pause_reason=self.pause_reason,
                    input_backend=self.backend.kind if self.backend else 'sendinput',
                    input_ready=self.backend.ready if self.backend else True,
                    input_error=self.backend.error if self.backend else '',
                    last_detection=self.policy.last_detection)

    def publish(self, now):
        if self.mode != self.last_mode:
            self.events.append(dict(at=time.strftime('%H:%M:%S'), mode=self.mode, inputs=self.count))
            self.last_mode = self.mode
        if now - self.last_snapshot >= 1:
            DATA.mkdir(parents=True, exist_ok=True)
            temp = DATA/'status.tmp'
            temp.write_text(json.dumps(self.status(), ensure_ascii=False, indent=2), encoding='utf-8')
            temp.replace(DATA/'status.json')
            self.last_snapshot = now

    def tick(self):
        now = time.monotonic()
        if now < self.next_at:
            return
        self.next_at = now + IDLE_PERIOD
        try:
            if self.setup_in_progress:
                self.policy.suspend()
                self.mode, self.title, self.detail = 'setup', 'USB入力を準備中', '初回設定には少し時間がかかります。'
                return
            if self.backend is not None and not self.backend.ready and not self.observe_only:
                self.policy.suspend()
                self.mode, self.title, self.detail = 'setup', 'USB入力の設定が必要です', self.backend.error
                return
            if not self.enabled:
                self.mode, self.title, self.detail = 'paused', 'ひと休み中', 'F8 または下のボタンで、見守りを再開。'
                return
            try:
                hwnd, pid = s.game_window()
            except RuntimeError:
                self.policy.suspend()
                self.target = None
                self.mode, self.title, self.detail = 'waiting', '原神を待っています', '原神を開くと、会話の見守りが始まります。'
                return
            if s.foreground() != hwnd or s.is_iconic(hwnd):
                self.policy.suspend()
                self.mode, self.title, self.detail = 'waiting', '会話を待っています', '原神に戻ると、自動で見守りを再開します。'
                return
            if self.target != (hwnd, pid):
                self.policy.suspend()
                if not self.observe_only and self.backend is None:
                    s.require_matching_privilege(pid)
                self.target = (hwnd, pid)
            # Stop keys are handled by the panel; an Esc press simply skips this sample.
            if any(s.key_state(vk) & 0x8000 for vk in (0x1B, 0x77, 0x78)):
                self.policy.suspend()
                return
            left, top, right, bottom = s.bounds(hwnd)
            s.guard(hwnd, (left+right)//2, (top+bottom)//2)
            frame = s.capture(hwnd)
            if s.foreground() != hwnd:
                self.policy.suspend()
                return
            decision = self.policy.inspect(frame, now)
            if decision['notify']:
                self.alerts += 1
                self.events.append(dict(at=time.strftime('%H:%M:%S'), alert=decision['state']))
                if self.sound and not self.observe_only:
                    winsound.PlaySound(str(BASE/'assets'/'attention.wav'), winsound.SND_FILENAME | winsound.SND_ASYNC)
            if decision['stalled']:
                self.mode, self.title = 'attention', '画面の確認が必要です'
                self.detail = f'{self.policy.notify_after}秒ほど画面が進んでいません。'
            elif decision['state'] in ('dialogue', 'choice'):
                self.mode, self.title = 'dialogue', '会話を送っています'
                self.detail = '会話も選択肢も F で進めています。'
            else:
                self.mode, self.title, self.detail = 'waiting', '会話を待っています', '探索や戦闘はそのまま。次の会話で再開します。'
            if decision['action'] and not self.observe_only:
                # Reobserve immediately before every input, including transitions.
                fresh = s.capture(hwnd)
                if s.foreground() != hwnd or s.game_window() != (hwnd,pid):
                    self.policy.suspend()
                    return
                if self.policy.detector.inspect(fresh)['state'] != decision['state']:
                    self.policy.suspend()
                    return
                sent = (tap_key(hwnd, decision['action'], self.backend) if self.backend is not None
                        else tap_key(hwnd, decision['action']))
                if sent:
                    self.count += 1
                    self.input_times.append(time.monotonic())
            # Include capture, classification, and key hold in the period budget.
            # An overrun never causes a catch-up burst of unobserved key taps.
            period=TAP_PERIOD if decision['action'] else IDLE_PERIOD
            self.next_at = max(now+period,time.monotonic())
        except Exception as exc:
            self.policy.suspend()
            self.mode, self.title, self.detail = 'attention', '見守りを待機しています', str(exc)
            self.next_at = now + 1
        finally:
            self.publish(now)


def main():
    global DATA
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--observe-only',action='store_true')
    parser.add_argument('--notify-after',type=int,choices=(30,60),default=60)
    parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--screenshot',type=Path)
    parser.add_argument('--quit-after',type=int)
    args=parser.parse_args()
    if args.data_dir:
        DATA=args.data_dir
    mutex=None
    if not args.preview:
        mutex=s.bind(s.K,'CreateMutexW',s.W.HANDLE,s.W.LPVOID,s.W.BOOL,s.W.LPCWSTR)(None,False,'Local\\GenshinDialogueClicker')
        if not mutex or C.get_last_error()==183:
            existing=s.find_window(None,TITLE)
            if existing:s.bind(s.U,'PostMessageW',s.W.BOOL,s.W.HWND,s.W.UINT,s.W.WPARAM,s.W.LPARAM)(existing,0x8001,0,0)
            if mutex:s.close_handle(mutex)
            return
    backend=None
    try:
        C.windll.shell32.SetCurrentProcessExplicitAppUserModelID('godca.GenshinDialogue.Local')
        if not args.preview:(DATA/'stop.flag').unlink(missing_ok=True)
        if not args.preview:
            DATA.mkdir(parents=True,exist_ok=True)
            (DATA/'startup.json').write_text(json.dumps(dict(pid=os.getpid(),version=VERSION,
                at=time.strftime('%Y-%m-%dT%H:%M:%S'),data_dir=str(DATA))),encoding='utf-8')
        settings={}
        if not args.preview:
            try:settings=json.loads((DATA/'settings.json').read_text(encoding='utf-8'))
            except (OSError,ValueError):pass
        delay=settings.get('notify_after',args.notify_after)
        from hid_input import VirtualKeyboard
        backend=VirtualKeyboard()
        if not args.preview and not args.observe_only:
            backend.try_connect()
        watcher=Watcher(delay if delay in (30,60) else 60,sound=bool(settings.get('sound',True)),
                        observe_only=args.observe_only,backend=backend)
        from assist_ui import run
        run(watcher,DATA,args.preview,args.screenshot,args.quit_after)
    finally:
        if backend is not None:backend.close()
        if mutex:s.close_handle(mutex)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        DATA.mkdir(parents=True,exist_ok=True)
        (DATA/'error.txt').write_text(str(exc),encoding='utf-8')
        if sys.stderr:print(str(exc),file=sys.stderr)
        raise
