"""Bounded desktop-only USB keyboard check. Never sends input outside its own window."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from hid_input import VirtualKeyboard

U=C.WinDLL('user32',use_last_error=True)


class RawDevice(C.Structure):
    _fields_=[('page',W.USHORT),('usage',W.USHORT),('flags',W.DWORD),('target',W.HWND)]


class RawHeader(C.Structure):
    _fields_=[('type',W.DWORD),('size',W.DWORD),('device',W.HANDLE),('wparam',W.WPARAM)]


class RawKeyboard(C.Structure):
    _fields_=[('make',W.USHORT),('flags',W.USHORT),('reserved',W.USHORT),
             ('vkey',W.USHORT),('message',W.UINT),('extra',W.ULONG)]


U.GetForegroundWindow.restype=W.HWND
U.SetForegroundWindow.argtypes=[W.HWND]
U.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
U.GetWindowThreadProcessId.restype=W.DWORD
U.AttachThreadInput.argtypes=[W.DWORD,W.DWORD,W.BOOL]
U.SetFocus.argtypes=[W.HWND]
U.RegisterRawInputDevices.argtypes=[C.POINTER(RawDevice),W.UINT,W.UINT]
U.GetRawInputData.argtypes=[W.HANDLE,W.UINT,W.LPVOID,C.POINTER(W.UINT),W.UINT]
U.GetRawInputData.restype=W.UINT
U.GetRawInputDeviceInfoW.argtypes=[W.HANDLE,W.UINT,W.LPVOID,C.POINTER(W.UINT)]
U.GetRawInputDeviceInfoW.restype=W.UINT


class Probe(QWidget):
    def __init__(self):
        super().__init__()
        self.keyboard=VirtualKeyboard();self.keyboard.connect()
        self.events=[];self.sent=[];self.errors=[];self.finishing=False
        self.setWindowTitle('Dialogue Assist — bounded USB input test')
        self.resize(460,160);self.setFocusPolicy(Qt.StrongFocus)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel('USB keyboard test: 12 F taps, then close.\nInput is sent only while this test window is active.'))
        self.show();self.activateWindow();self.setFocus()
        self.hwnd=int(self.winId())
        dev=RawDevice(1,6,0,self.hwnd)
        if not U.RegisterRawInputDevices(C.byref(dev),1,C.sizeof(dev)):
            raise C.WinError(C.get_last_error())
        # Desktop probe only: temporarily join the foreground queue, then detach.
        # The shipping application never calls this activation helper.
        foreground_thread=U.GetWindowThreadProcessId(U.GetForegroundWindow(),None)
        own_thread=C.windll.kernel32.GetCurrentThreadId()
        attached=U.AttachThreadInput(own_thread,foreground_thread,True) if own_thread!=foreground_thread else False
        try:
            U.SetForegroundWindow(self.hwnd);U.SetFocus(self.hwnd)
        finally:
            if attached:U.AttachThreadInput(own_thread,foreground_thread,False)
        self.timer=QTimer(self);self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.step)
        QTimer.singleShot(1500,lambda:self.timer.start(250))
        QTimer.singleShot(10000,self.finish)

    def step(self):
        if U.GetForegroundWindow()!=self.hwnd:
            self.errors.append('foreground changed; input blocked');self.finish();return
        if len(self.sent)>=12:
            self.finish();return
        try:
            self.sent.append(time.perf_counter());self.keyboard.tap_f()
        except Exception as exc:
            self.errors.append(str(exc));self.finish()

    def nativeEvent(self,event_type,message):
        msg=W.MSG.from_address(int(message))
        if msg.message==0x00FF:
            size=W.UINT()
            U.GetRawInputData(msg.lParam,0x10000003,None,C.byref(size),C.sizeof(RawHeader))
            buffer=C.create_string_buffer(size.value)
            if U.GetRawInputData(msg.lParam,0x10000003,buffer,C.byref(size),C.sizeof(RawHeader))!=0xFFFFFFFF:
                header=RawHeader.from_buffer(buffer)
                if header.type==1:
                    key=RawKeyboard.from_buffer(buffer,C.sizeof(RawHeader))
                    n=W.UINT(1024);name=C.create_unicode_buffer(1024)
                    U.GetRawInputDeviceInfoW(header.device,0x20000007,name,C.byref(n))
                    self.events.append(dict(key=key.vkey,up=bool(key.flags&1),device=name.value))
        return super().nativeEvent(event_type,message)

    def finish(self):
        if self.finishing:return
        self.finishing=True;self.timer.stop();self.keyboard.close()
        f=[e for e in self.events if e['key']==0x46]
        intervals=[round((b-a)*1000,2) for a,b in zip(self.sent,self.sent[1:])]
        result=dict(sent=len(self.sent),raw_down=sum(not e['up'] for e in f),
                    raw_up=sum(e['up'] for e in f),devices=sorted(set(e['device'] for e in f)),
                    intervals_ms=intervals,errors=self.errors,
                    passed=len(self.sent)==12 and len(f)==24 and sum(e['up'] for e in f)==12
                           and all(e['device'] for e in f) and not self.errors)
        Path(sys.argv[1]).write_text(json.dumps(result,indent=2),encoding='utf-8')
        self.close()

    def closeEvent(self,event):
        if not self.finishing:self.finish()
        event.accept()


if __name__=='__main__':
    app=QApplication([])
    probe=Probe()
    sys.exit(app.exec())
