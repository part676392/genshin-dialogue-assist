"""Compact Windows UI. Qt/Fluent controls; never activates the game or cursor."""
from __future__ import annotations
import ctypes as C
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QApplication, QWidget, QLabel
from qfluentwidgets import (PrimaryPushButton, TransparentToolButton, SwitchButton,
    SegmentedWidget, PushButton, Slider, FluentIcon as FI, setTheme, setThemeColor, Theme, setFont, setCustomStyleSheet)

import story_clicker as s

BG='#f2f0e9'
INK='#243d38'
MUTED='#6c7971'
GREEN='#3f7263'
LINE='#dcded4'


def label(parent, text, x, y, w, h, size=13, color=INK, weight=QFont.Normal):
    widget=QLabel(text,parent)
    font=QFont('Yu Gothic UI');font.setPixelSize(size);font.setWeight(weight)
    widget.setFont(font)
    widget.setStyleSheet(f'color:{color};background:transparent;')
    widget.setGeometry(x,y,w,h)
    return widget


class Book(QWidget):
    """A small vector illustration, drawn at the display's native resolution."""
    def __init__(self,parent):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.mode='waiting'

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen);p.setBrush(QColor('#ecf0e5'))
        p.drawEllipse(QRectF(7,8,94,83))
        p.setBrush(QColor('#dce3d2'));p.drawEllipse(QRectF(16,84,81,6))
        # A hardbound book with separate leaves, a spine, and a ribbon.
        path=QPainterPath();path.moveTo(14,33);path.cubicTo(30,29,40,34,54,39)
        path.cubicTo(68,31,84,29,99,32);path.lineTo(99,80)
        path.cubicTo(84,77,68,80,54,87);path.cubicTo(39,80,27,77,14,80);path.closeSubpath()
        p.setBrush(QColor('#668574'));p.setPen(QPen(QColor('#4b6a59'),1.2));p.drawPath(path)
        path=QPainterPath();path.moveTo(18,29);path.cubicTo(32,27,41,31,54,36)
        path.cubicTo(69,29,81,26,95,28);path.lineTo(95,74)
        path.cubicTo(81,72,67,76,54,81);path.cubicTo(42,75,31,73,18,75);path.closeSubpath()
        p.setBrush(QColor('#fffcf3'));p.setPen(QPen(QColor('#adbaa2'),1));p.drawPath(path)
        p.setPen(QPen(QColor('#c9cfb9'),1));p.drawLine(54,37,54,80)
        for y in (43,51,59,67):
            p.drawLine(25,y,45,y+3);p.drawLine(63,y+2,86,y-2)
        path=QPainterPath();path.moveTo(76,28);path.lineTo(84,27);path.lineTo(84,52)
        path.lineTo(80,48);path.lineTo(76,54);path.closeSubpath()
        p.setBrush(QColor('#c5a15e'));p.setPen(Qt.NoPen);p.drawPath(path)
        # A single four-point glint; quieter when paused.
        if self.mode!='paused':
            path=QPainterPath();path.moveTo(23,9);path.lineTo(25,15);path.lineTo(31,17)
            path.lineTo(25,19);path.lineTo(23,25);path.lineTo(21,19)
            path.lineTo(15,17);path.lineTo(21,15);path.closeSubpath()
            p.setBrush(QColor('#c5a15e'));p.drawPath(path)
        if self.mode=='attention':
            p.setBrush(QColor('#a6603d'));p.drawEllipse(QRectF(85,65,22,22))
            p.setPen(QColor('white'));f=QFont('Segoe UI');f.setPixelSize(16);f.setBold(True);p.setFont(f)
            p.drawText(QRectF(85,65,22,22),Qt.AlignCenter,'!')


def native_snapshot():
    clip=s.W.RECT();point=s.W.POINT()
    s.U.GetClipCursor(C.byref(clip));s.U.GetCursorPos(C.byref(point))
    return dict(foreground=s.foreground(),clip=[clip.left,clip.top,clip.right,clip.bottom],
                cursor=[point.x,point.y])


class Panel(QWidget):
    def __init__(self,watcher,data,preview=False):
        super().__init__(None,Qt.Window|Qt.FramelessWindowHint|Qt.WindowDoesNotAcceptFocus)
        self.watcher,self.data,self.preview=watcher,data,preview
        self.previous={key:bool(s.key_state(key)&0x8000) for key in (0x77,0x78)}
        self.drag=None;self.last_view=None;self.closing=False
        self.setup_pool=None;self.setup_future=None
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(490,442)
        self.setWindowTitle('原神 会話アシスト')
        self.setWindowIcon(QIcon(str(Path(__file__).parent/'assets'/'dialogue-assist.ico')))
        self.setStyleSheet('QWidget{font-family:"Yu Gothic UI";}')

        self.brand=label(self,'会話アシスト',54,15,180,27,17,INK,QFont.DemiBold)
        self.setup_button=PushButton('USB設定',self)
        self.setup_button.setGeometry(271,16,77,27)
        setFont(self.setup_button,11)
        self.setup_button.setToolTip('初回のみWindowsに入力用ドライバーを追加します。\n設定中はUSB機器が一時的に再接続されることがあります。\n初回設定後はWindowsを一度再起動してください。自動再起動はしません。')
        self.setup_button.clicked.connect(self.setup_usb)
        self.setup_button.setEnabled(not preview and watcher.backend is not None)
        label(self,'原神',360,18,40,22,11,MUTED)
        self.minimize=TransparentToolButton(FI.REMOVE,self)
        self.minimize.setGeometry(405,13,30,30)
        self.minimize.setAccessibleName('最小化')
        self.minimize.clicked.connect(self.minimize_quietly)
        self.close_button=TransparentToolButton(FI.CLOSE,self)
        self.close_button.setGeometry(447,13,30,30)
        self.close_button.setAccessibleName('終了（F9）')
        self.close_button.clicked.connect(self.close)

        self.badge=label(self,'会話を探しています · F送信停止',49,72,310,22,11,GREEN,QFont.DemiBold)
        self.heading=label(self,'次の会話を待機中',34,102,328,32,22,INK,QFont.DemiBold)
        self.detail=label(self,'会話が始まると、自動で送ります。',35,143,313,35,12,MUTED)
        self.detail.setWordWrap(True);self.detail.setAlignment(Qt.AlignTop|Qt.AlignLeft)
        self.book=Book(self);self.book.setGeometry(353,79,112,100)
        self.input_state=label(self,'F送信停止 · 累計 0 回',24,185,440,20,11,MUTED)

        self.toggle_button=PrimaryPushButton(FI.PAUSE,'一時停止',self)
        self.toggle_button.setGeometry(20,201,292,40)
        setFont(self.toggle_button,14,QFont.DemiBold)
        setCustomStyleSheet(self.toggle_button,'PrimaryPushButton{border-radius:9px;}',
            'PrimaryPushButton{border-radius:9px;}')
        self.toggle_button.clicked.connect(self.toggle)
        self.toggle_button.setAccessibleName('会話の自動検知を一時停止・再開（F8）')
        label(self,'通知音',333,209,56,23,12)
        self.sound=SwitchButton(self)
        self.sound.setOnText('');self.sound.setOffText('')
        self.sound.setChecked(watcher.sound)
        self.sound.setGeometry(412,210,44,23)
        self.sound.setAccessibleName('通知音のオン・オフ')
        self.sound.checkedChanged.connect(self.sound_changed)

        label(self,'画面が止まったら通知',24,257,209,27,12,MUTED)
        self.delay=SegmentedWidget(self)
        self.delay.setGeometry(307,256,159,30)
        self.delay.addItem('30','30 秒',lambda:self.delay_changed(30))
        self.delay.addItem('60','60 秒',lambda:self.delay_changed(60))
        self.delay.setCurrentItem(str(watcher.policy.notify_after))
        for child in self.delay.items.values():
            child.setFixedSize(79,30);setFont(child,12)
        self.delay.setAccessibleName('停止通知までの時間')
        label(self,'入力間隔',24,300,120,24,12,MUTED)
        self.timing_mode=SegmentedWidget(self)
        self.timing_mode.setGeometry(240,298,226,30)
        self.timing_mode.addItem('fixed','一定',lambda:self.timing_changed(False))
        self.timing_mode.addItem('random','ランダム',lambda:self.timing_changed(True))
        self.timing_mode.setCurrentItem('random' if watcher.random_timing else 'fixed')
        for child in self.timing_mode.items.values():child.setFixedSize(112,30);setFont(child,12)
        self.timing_mode.setAccessibleName('入力間隔を一定またはランダムに切り替える')
        self.interval_slider=Slider(Qt.Horizontal,self)
        self.interval_slider.setGeometry(24,338,310,24)
        self.interval_slider.setRange(watcher.min_interval_ms,watcher.max_interval_ms)
        self.interval_slider.setValue(watcher.interval_ms)
        self.interval_slider.setSingleStep(1)
        self.interval_slider.setAccessibleName(f'一定の入力間隔、{watcher.min_interval_ms}から{watcher.max_interval_ms}ミリ秒')
        self.interval_slider.valueChanged.connect(self.interval_changed)
        self.interval_value=label(self,'',344,335,122,27,13,INK)
        self.interval_value.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        label(self,f'{watcher.min_interval_ms} ms',24,363,90,18,10,MUTED)
        label(self,f'{watcher.max_interval_ms} ms',289,363,60,18,10,MUTED)
        self.refresh_timing()
        label(self,f'v{watcher.version} · USB入力 · AI 送信なし',24,394,235,17,10,MUTED)
        label(self,'F8  一時停止・再開     /     F9  終了',270,394,208,17,10,MUTED)
        # Give the explicit input indicator its own row below the card.
        for child in self.findChildren(QWidget,options=Qt.FindDirectChildrenOnly):
            if child is not self.input_state and child.y() >= 201:
                child.move(child.x(),child.y()+22)
        watcher.before_input=self.prepare_input
        # Controls retain mouse interaction without taking keyboard focus from the game.
        for child in self.findChildren(QWidget):child.setFocusPolicy(Qt.NoFocus)
        self.timer=QTimer(self);self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.poll);self.timer.start(10)
        screen=min(QApplication.screens(),key=lambda sc:sc.geometry().x())
        area=screen.availableGeometry()
        self.move(area.x()+90,area.y()+140)
        self.update_view()

    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(),QColor(BG))
        p.setPen(QPen(QColor('#cdd2c6'),1));p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(.5,.5,self.width()-1,self.height()-1),12,12)
        # An app mark rather than a text-only title bar.
        p.setPen(Qt.NoPen);p.setBrush(QColor(INK));p.drawRoundedRect(QRectF(21,18,23,23),6,6)
        p.setPen(QPen(QColor('#f3f0df'),1.5,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
        path=QPainterPath();path.moveTo(27,25);path.lineTo(32,25);path.lineTo(34,27)
        path.lineTo(38,27);path.lineTo(38,34);path.lineTo(33,34)
        path.lineTo(31,32);path.lineTo(27,32);path.closeSubpath();p.drawPath(path)
        p.setPen(QPen(QColor(LINE),1));p.setBrush(QColor('#fcfcf7'))
        p.drawRoundedRect(QRectF(20.5,61.5,449,122),13,13)
        mode=self.watcher.mode
        color='#a6603d' if mode=='attention' else MUTED if not self.watcher.enabled else GREEN
        p.setPen(Qt.NoPen);p.setBrush(QColor(color));p.drawEllipse(QRectF(35,81,5,5))
        p.setPen(QPen(QColor(LINE),1));p.drawLine(24,316,466,316)

    def show_quietly(self):
        before=native_snapshot()
        hwnd=int(self.winId())
        get=s.bind(s.U,'GetWindowLongPtrW',C.c_ssize_t,s.W.HWND,C.c_int)
        put=s.bind(s.U,'SetWindowLongPtrW',C.c_ssize_t,s.W.HWND,C.c_int,C.c_ssize_t)
        put(hwnd,-20,(get(hwnd,-20)|0x08000000|0x40000)&~0x8&~0x80)
        # Windows 11 corners; no custom floating overlay or topmost window.
        pref=C.c_int(2)
        C.windll.dwmapi.DwmSetWindowAttribute(s.W.HWND(hwnd),33,C.byref(pref),4)
        self.show()
        self.data.mkdir(parents=True,exist_ok=True)
        (self.data/'window.json').write_text(json.dumps(dict(
            pid=__import__('os').getpid(),hwnd=hwnd,before=before,after=native_snapshot(),
            exstyle=get(hwnd,-20),preview=self.preview),ensure_ascii=False,indent=2),encoding='utf-8')

    def nativeEvent(self,event_type,message):
        if bytes(event_type) in (b'windows_generic_MSG',b'windows_dispatcher_MSG'):
            msg=s.W.MSG.from_address(int(message))
            if msg.message==0x0021:return True,3  # WM_MOUSEACTIVATE / MA_NOACTIVATE
            if msg.message==0x8001:
                s.bind(s.U,'ShowWindow',s.W.BOOL,s.W.HWND,C.c_int)(int(self.winId()),4)
                s.bind(s.U,'SetWindowPos',s.W.BOOL,s.W.HWND,s.W.HWND,C.c_int,C.c_int,C.c_int,C.c_int,s.W.UINT)(
                    int(self.winId()),0,0,0,0,0,0x0010|0x0001|0x0002)
                return True,0
        return super().nativeEvent(event_type,message)

    def mousePressEvent(self,event):
        if event.button()==Qt.LeftButton and event.position().y()<56:
            self.drag=event.globalPosition().toPoint()-self.frameGeometry().topLeft()

    def mouseMoveEvent(self,event):
        if self.drag is not None and event.buttons()&Qt.LeftButton:
            self.move(event.globalPosition().toPoint()-self.drag)

    def mouseReleaseEvent(self,event):self.drag=None

    def minimize_quietly(self):
        s.bind(s.U,'ShowWindow',s.W.BOOL,s.W.HWND,C.c_int)(int(self.winId()),7)

    def save_settings(self):
        if self.preview:return
        self.data.mkdir(parents=True,exist_ok=True)
        temp=self.data/'settings.tmp'
        temp.write_text(json.dumps(dict(sound=self.watcher.sound,
            notify_after=self.watcher.policy.notify_after,interval_ms=self.watcher.interval_ms,
            random_timing=self.watcher.random_timing)),encoding='utf-8')
        temp.replace(self.data/'settings.json')

    def refresh_timing(self):
        w=self.watcher
        self.interval_slider.setEnabled(not w.random_timing)
        self.interval_value.setText(f'{w.min_interval_ms}～{w.max_interval_ms} ms' if w.random_timing else f'{w.interval_ms} ms')
        self.interval_slider.setToolTip('「一定」に切り替えると間隔を調整できます。' if w.random_timing
                                      else '小さい数値ほど速く送ります。')

    def timing_changed(self,random_timing):
        self.watcher.configure_timing(self.watcher.interval_ms,random_timing)
        self.timing_mode.setCurrentItem('random' if random_timing else 'fixed')
        self.refresh_timing();self.save_settings()

    def interval_changed(self,value):
        self.watcher.configure_timing(value,self.watcher.random_timing)
        self.refresh_timing();self.save_settings()

    def sound_changed(self,value):
        self.watcher.sound=value;self.save_settings()

    def delay_changed(self,value):
        self.watcher.policy.notify_after=value;self.watcher.policy.suspend();self.save_settings()

    def toggle(self):
        self.watcher.toggle()
        if not self.preview:self.watcher.tick()
        else:self.watcher.mode='waiting' if self.watcher.enabled else 'paused'
        self.update_view()

    def setup_usb(self):
        if self.setup_future is not None or self.preview:return
        from hid_input import driver_installed, install_driver
        w=self.watcher
        w.setup_in_progress=True;w.policy.suspend();w.next_at=0
        self.setup_button.setEnabled(False);self.toggle_button.setEnabled(False)
        self.setup_pool=ThreadPoolExecutor(max_workers=1,thread_name_prefix='usb-setup')
        def work():
            w.backend.close()
            if not driver_installed():install_driver(self.data)
            w.backend.try_connect()
        self.setup_future=self.setup_pool.submit(work)

    def update_view(self):
        w=self.watcher
        sending=w.enabled and w.mode=='dialogue' and not w.observe_only
        self.input_state.setText(f'F送信対象 · 累計 {w.count} 回 · 最終 {w.last_input_at or "なし"}' if sending
                                else f'F送信停止 · 累計 {w.count} 回 · 最終 {w.last_input_at or "なし"}')
        key=(w.mode,w.enabled,w.title,w.detail)
        if key==self.last_view:return
        self.last_view=key
        self.badge.setText({'waiting':'会話を探しています · F送信停止','dialogue':'会話を検知しました',
            'paused':'自動検知を停止中','attention':'お知らせ','setup':'USB入力の準備'}.get(w.mode,'自動検知中'))
        title={'waiting':'次の会話を待機中','dialogue':'会話を送っています',
            'paused':'一時停止しています','attention':'画面をご確認ください'}.get(w.mode,w.title)
        detail={'waiting':'会話を確認できるまで、Fは送りません。',
                'dialogue':'会話が終わると、自動で入力を止めます。',
                'paused':'再開すると、会話の自動検知に戻ります。'}.get(w.mode,w.detail)
        if w.title=='原神を待っています':title='原神の起動を待機中'
        if w.title=='見守りを待機しています':title='自動検知を待機中'
        self.heading.setText(title);self.detail.setText(detail)
        self.detail.setToolTip(w.detail)
        self.toggle_button.setText('一時停止' if w.enabled else '自動検知を再開')
        self.toggle_button.setIcon(FI.PAUSE if w.enabled else FI.PLAY)
        self.book.mode=w.mode;self.book.update();self.update()

    def prepare_input(self):
        w=self.watcher
        if self.closing or not w.enabled or w.mode!='dialogue' or w.setup_in_progress:
            return False
        self.update_view()
        self.repaint()
        return True

    def poll(self):
        if self.setup_future is not None and self.setup_future.done():
            try:self.setup_future.result()
            except Exception as exc:self.watcher.backend.error=str(exc)
            self.setup_pool.shutdown(wait=False);self.setup_pool=None;self.setup_future=None
            self.watcher.setup_in_progress=False;self.watcher.next_at=0
            self.setup_button.setEnabled(True);self.toggle_button.setEnabled(True)
        if (self.data/'stop.flag').exists():self.close();return
        if not self.preview:
            for vk in self.previous:
                pressed=bool(s.key_state(vk)&0x8000);rising=pressed and not self.previous[vk]
                self.previous[vk]=pressed
                if rising and vk==0x78:self.close();return
                if rising and vk==0x77:self.watcher.toggle('F8')
            self.watcher.tick()
        self.update_view()

    def closeEvent(self,event):
        if self.setup_future is not None:
            # Let the bounded installer finish before tearing down its keyboard.
            self.hide()
            (self.data/'stop.flag').touch()
            event.ignore();return
        if not self.closing:
            self.closing=True;self.timer.stop()
            self.watcher.enabled=False;self.watcher.mode='closed'
            if self.watcher.backend is not None:self.watcher.backend.close()
            if not self.preview:self.watcher.publish(time.monotonic()+2)
        event.accept()


def run(watcher,data,preview=False,screenshot=None,quit_after=None):
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('原神 会話アシスト')
    setTheme(Theme.LIGHT);setThemeColor(GREEN)
    panel=Panel(watcher,data,preview)
    panel.show_quietly()
    if screenshot:
        path=Path(screenshot);path.parent.mkdir(parents=True,exist_ok=True)
        QTimer.singleShot(600,lambda:panel.grab().save(str(path)))
    if quit_after:QTimer.singleShot(quit_after,panel.close)
    return app.exec()
