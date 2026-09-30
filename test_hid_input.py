"""USB transport cleanup and input-isolation tests; no driver or game needed."""
import ctypes as C
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import auto_dialogue as a
import hid_input as h
import story_clicker as s


class FakeLibrary:
    def __init__(self):
        self.states=[]
        self.removed=[]
        self.closed=[]
        self.fail_release=False
        self.raise_remove=False
        self.allocated_buses=set()
        self.removed_buses=[]
        self.fail_create_bus=False

    def NewUSBServer(self, config, out, callback):
        self.address=C.cast(config,C.POINTER(h.USBServerConfig)).contents.addr
        C.cast(out,C.POINTER(C.c_size_t))[0]=10
        return True

    def CreateUSBBus(self, server, out):
        C.cast(out,C.POINTER(C.c_uint32))[0]=1
        if self.fail_create_bus or 1 in self.allocated_buses:return False
        self.allocated_buses.add(1)
        return True

    def RemoveUSBBus(self, server, bus):
        self.removed_buses.append(bus.value)
        self.allocated_buses.remove(bus.value)
        return True

    def CreateKeyboardDevice(self, server, out, bus, attach, vid, pid):
        C.cast(out,C.POINTER(C.c_size_t))[0]=20
        return True

    def SetKeyboardDeviceState(self, handle, state):
        self.states.append(bytes(state))
        return not (self.fail_release and bytes(state)==bytes(33))

    def RemoveKeyboardDevice(self, handle):
        self.removed.append(handle.value)
        if self.raise_remove:raise OSError('removal failed')
        return True

    def CloseUSBServer(self, handle):
        self.closed.append(handle.value)
        return True


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.lib=FakeLibrary()
        self.keyboard=h.VirtualKeyboard(self.lib)
        self.keyboard.connect()
        self.addCleanup(self.keyboard.close)

    def test_f_report_and_release_have_no_other_keys(self):
        self.assertEqual(C.sizeof(h.KeyboardState),33)
        with patch.object(h.time,'sleep'):
            self.keyboard.tap_f()
        self.assertEqual(self.lib.states[-2],bytes([0,0,2])+bytes(30))
        self.assertEqual(self.lib.states[-1],bytes(33))
        self.assertEqual(self.lib.address,b'127.0.0.1:0')

    def test_exception_during_hold_still_releases(self):
        with patch.object(h.time,'sleep',side_effect=RuntimeError('interrupted')):
            with self.assertRaises(RuntimeError):self.keyboard.tap_f()
        self.assertEqual(self.lib.states[-1],bytes(33))

    def test_failed_release_detaches_device_and_stops_input(self):
        self.lib.fail_release=True
        with patch.object(h.time,'sleep'):
            with self.assertRaises(RuntimeError):self.keyboard.tap_f()
        self.assertFalse(self.keyboard.ready)
        self.assertEqual(self.lib.removed,[20])
        self.assertEqual(self.lib.closed,[10])
        with self.assertRaises(RuntimeError):self.keyboard.tap_f()

    def test_cleanup_continues_if_remove_raises_and_is_idempotent(self):
        self.lib.raise_remove=True
        self.keyboard.close();self.keyboard.close()
        self.assertEqual(self.lib.closed,[10])
        self.assertEqual(self.lib.removed,[20])
        self.assertEqual(self.lib.removed_buses,[1])

    def test_device_failure_also_closes_server(self):
        self.keyboard.close()
        self.lib.CreateKeyboardDevice=lambda *args:False
        self.assertFalse(self.keyboard.try_connect())
        self.assertFalse(self.keyboard.ready)
        self.assertEqual(self.lib.closed,[10,10])
        self.assertEqual(self.lib.allocated_buses,set())

    def test_reconnect_releases_bus_in_same_library(self):
        callback=self.keyboard._log_callback
        for _ in range(4):
            self.keyboard.close()
            self.assertEqual(self.lib.allocated_buses,set())
            self.assertTrue(self.keyboard.try_connect(),self.keyboard.error)
            self.assertIs(self.keyboard._log_callback,callback)

    def test_failed_keyboard_attach_then_retry_recovers(self):
        self.keyboard.close()
        with patch.object(self.lib,'CreateKeyboardDevice',return_value=False):
            self.assertFalse(self.keyboard.try_connect())
        self.assertEqual(self.lib.allocated_buses,set())
        self.assertTrue(self.keyboard.try_connect(),self.keyboard.error)

    def test_failed_bus_creation_does_not_remove_unowned_bus(self):
        self.keyboard.close()
        self.lib.removed_buses.clear();self.lib.fail_create_bus=True
        self.assertFalse(self.keyboard.try_connect())
        self.assertEqual(self.lib.removed_buses,[])


@unittest.skipUnless(os.environ.get('GENSHIN_TEST_USB')=='1',
                     'Set GENSHIN_TEST_USB=1 for real driver reconnect checks; no keys sent')
class NativeReconnectTests(unittest.TestCase):
    def test_same_loaded_dll_reconnects_five_times(self):
        keyboard=h.VirtualKeyboard()
        self.addCleanup(keyboard.close)
        for attempt in range(5):
            with self.subTest(attempt=attempt):
                self.assertTrue(keyboard.try_connect(),keyboard.error)
                self.assertTrue(keyboard.ready)
                keyboard.close()
                self.assertFalse(keyboard.ready)


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.backend=SimpleNamespace(kind='usb-hid',ready=True,error='',tap_f=Mock(return_value=True))
        self.w=a.Watcher(backend=self.backend)
        self.w.policy=Mock()
        self.w.policy.notify_after=60
        self.w.policy.last_detection=None
        self.w.policy.inspect.return_value=dict(state='dialogue',action='F',notify=False,stalled=False)
        self.w.policy.detector.inspect.return_value=dict(state='dialogue')
        targets=[patch.object(a,'DATA',Path(self.temp.name)),
                 patch.object(s,'game_window',return_value=(10,20)),
                 patch.object(s,'foreground',return_value=10),
                 patch.object(s,'is_iconic',return_value=False),
                 patch.object(s,'key_state',return_value=0),
                 patch.object(s,'bounds',return_value=(0,0,1920,1080)),
                 patch.object(s,'guard'),patch.object(s,'capture',return_value=object()),
                 patch.object(s,'send_input'),patch.object(s,'cursor_set'),patch.object(s,'activate_game')]
        self.m=[p.start() for p in targets]
        self.addCleanup(lambda:[p.stop() for p in reversed(targets)])

    def test_detected_dialogue_uses_usb_only(self):
        self.w.tick()
        self.backend.tap_f.assert_called_once_with(a.KEY_HOLD)
        self.assertEqual(self.w.count,1)
        for mock in self.m[8:]:mock.assert_not_called()

    def test_missing_usb_blocks_capture_and_never_falls_back(self):
        self.backend.ready=False;self.backend.error='setup required'
        self.w.tick()
        self.assertEqual(self.w.mode,'setup')
        self.backend.tap_f.assert_not_called()
        self.m[7].assert_not_called();self.m[8].assert_not_called()

    def test_focus_change_before_input_blocks_usb(self):
        self.m[2].side_effect=[10,10,99,99]
        self.w.tick()
        self.backend.tap_f.assert_not_called()

    def test_pause_and_modifier_never_send(self):
        self.w.enabled=False;self.w.tick()
        self.backend.tap_f.assert_not_called()
        self.w.enabled=True;self.w.next_at=0
        self.m[4].side_effect=lambda key:0x8000 if key==0x11 else 0
        self.w.tick()
        self.backend.tap_f.assert_not_called()

    def test_transport_exception_does_not_fall_back(self):
        self.backend.tap_f.side_effect=RuntimeError('disconnected')
        self.w.tick()
        self.assertEqual(self.w.mode,'attention')
        self.assertEqual(self.w.count,0)
        self.m[8].assert_not_called()


if __name__=='__main__':unittest.main()
