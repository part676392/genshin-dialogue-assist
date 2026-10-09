"""Local dialogue assistance. No AI/upload, cursor moves, or focus changes."""
from __future__ import annotations

import argparse
from collections import deque
import ctypes as C
import json
import os
import random
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
VERSION = '3.0.1'
# User-selected timing range; not a measured game minimum or an evasion claim.
MIN_INTERVAL_MS = 350
MAX_INTERVAL_MS = 500
DEFAULT_INTERVAL_MS = 425
TAP_PERIOD = DEFAULT_INTERVAL_MS/1000
KEY_HOLD = .025
IDLE_PERIOD = .150


def signature(frame, dialogue=False):
    box = (240,400,1820,990) if dialogue else (70,100,1830,1000)
    xscale, yscale = frame.width/1920, frame.height/1080
    source = (box[0]*xscale,box[1]*yscale,box[2]*xscale,box[3]*yscale)
    return np.asarray(frame.convert('L').resize((160,90),box=source),dtype=np.int16)


def caption_signature(frame):
    pixels = np.asarray(s.region(frame,(250,835,1670,985),Image.Resampling.BICUBIC))
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
    min_interval_ms = MIN_INTERVAL_MS
    max_interval_ms = MAX_INTERVAL_MS

    def __init__(self, notify_after=60, sound=True, observe_only=False, backend=None,
                 interval_ms=DEFAULT_INTERVAL_MS, random_timing=False):
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
        self.version = VERSION
        self.setup_in_progress = False
        self.interval_ms = DEFAULT_INTERVAL_MS
        self.random_timing = False
        self.rng = random.SystemRandom()
        self.configure_timing(interval_ms,random_timing)
        self.last_interval_ms = self.interval_ms
        self.input_due_at = 0
        self.before_input = None
        self.last_input_at = None

    def configure_timing(self, interval_ms, random_timing):
        if type(interval_ms) is not int or not MIN_INTERVAL_MS <= interval_ms <= MAX_INTERVAL_MS:
            raise ValueError(f'入力間隔は{MIN_INTERVAL_MS}～{MAX_INTERVAL_MS}ミリ秒で設定してください。')
        self.interval_ms = interval_ms
        self.random_timing = bool(random_timing)

    def input_period(self):
        self.last_interval_ms = self.rng.randint(MIN_INTERVAL_MS,MAX_INTERVAL_MS) if self.random_timing else self.interval_ms
        return self.last_interval_ms/1000

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
                    target_interval_ms=None if self.random_timing else self.interval_ms,
                    timing_mode='random' if self.random_timing else 'fixed',
                    fixed_interval_ms=self.interval_ms,last_interval_ms=self.last_interval_ms,
                    interval_range_ms=[MIN_INTERVAL_MS,MAX_INTERVAL_MS] if self.random_timing else [self.interval_ms,self.interval_ms],
                    recent_inputs_per_second=round(rate,2),
                    updated_at=time.strftime('%Y-%m-%dT%H:%M:%S'),pause_reason=self.pause_reason,
                    input_backend=self.backend.kind if self.backend else 'sendinput',
                    input_ready=self.backend.ready if self.backend else True,
                    input_error=self.backend.error if self.backend else '',
                    last_detection=self.policy.last_detection,last_input_at=self.last_input_at)

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
            if decision['action'] and self.mode == 'dialogue' and not self.observe_only:
                # Paint the authorized state before sending, so the previous
                # "waiting" label cannot remain on screen during a first tap.
                if self.before_input is not None and not self.before_input():
                    self.policy.suspend()
                    return
                # Reobserve immediately before every input, including transitions.
                fresh = s.capture(hwnd)
                if s.foreground() != hwnd or s.game_window() != (hwnd,pid):
                    self.policy.suspend()
                    return
                # Both dialogue and choices use F. Recheck the dialogue controls
                # without repeating the expensive choice search or rejecting a
                # valid transition from a caption to a choice.
                checked = self.policy.detector.inspect(fresh,detect_choice=False)
                self.policy.last_detection = checked
                if checked['state'] not in ('dialogue','choice'):
                    self.policy.suspend()
                    self.mode, self.title, self.detail = 'waiting', '会話を待っています', '次の会話で自動的に再開します。'
                    return
                # A UI callback may pause the watcher; check again at dispatch.
                if not self.enabled or self.mode != 'dialogue' or self.setup_in_progress:
                    return
                input_started=time.monotonic()
                if input_started < self.input_due_at:
                    self.next_at=self.input_due_at
                    return
                sent = (tap_key(hwnd, decision['action'], self.backend) if self.backend is not None
                        else tap_key(hwnd, decision['action']))
                if sent:
                    self.count += 1
                    self.last_input_at=time.strftime('%H:%M:%S')
                    self.events.append(dict(at=self.last_input_at,input='F',inputs=self.count,
                                            mode=self.mode,detection=checked))
                    self.input_times.append(time.monotonic())
                    self.input_due_at=input_started+self.input_period()
            # Include capture, classification, and key hold in the period budget.
            # An overrun never causes a catch-up burst of unobserved key taps.
            period=self.last_interval_ms/1000 if decision['action'] else IDLE_PERIOD
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
    parser.add_argument('--start-paused',action='store_true',help='一時停止状態で起動する')
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
        interval=settings.get('interval_ms',DEFAULT_INTERVAL_MS)
        if type(interval) is not int:interval=DEFAULT_INTERVAL_MS
        interval=max(MIN_INTERVAL_MS,min(MAX_INTERVAL_MS,interval))
        from hid_input import VirtualKeyboard
        backend=VirtualKeyboard()
        if not args.preview and not args.observe_only:
            backend.try_connect()
        watcher=Watcher(delay if delay in (30,60) else 60,sound=bool(settings.get('sound',True)),
                        observe_only=args.observe_only,backend=backend,interval_ms=interval,
                        random_timing=bool(settings.get('random_timing',True)))
        if args.start_paused:watcher.toggle('startup')
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
