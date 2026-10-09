import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import housekeeping as h
import story_clicker as s
import auto_dialogue as a


class HousekeepingTests(unittest.TestCase):
    def test_only_abandoned_owned_temporary_files_are_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ('settings.json','picture.png','status.tmp','settings.tmp'):
                (root/name).write_bytes(b'keep or delete by identity')
            os.utime(root/'status.tmp',(0,0))
            self.assertEqual(h.cleanup_runtime(root),['status.tmp'])
            for name in ('settings.json','picture.png','settings.tmp'):
                self.assertTrue((root/name).exists())

    def test_screenshot_handle_is_closed_and_removed_once(self):
        screen=Mock()
        s._capture_local.screen=screen
        s.close_capture();s.close_capture()
        screen.close.assert_called_once()
        self.assertFalse(hasattr(s._capture_local,'screen'))

    def test_unchanged_status_does_not_write_every_second(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(a,'DATA',Path(temp)):
            w=a.Watcher();w.enabled=False
            w.publish(100)
            snapshot=(Path(temp)/'status.json').stat().st_mtime_ns
            for stamp in (101,102,110,129):w.publish(stamp)
            self.assertEqual(w.last_snapshot,100)
            self.assertEqual((Path(temp)/'status.json').stat().st_mtime_ns,snapshot)
            w.publish(130)
            self.assertEqual(w.last_snapshot,130)


if __name__=='__main__':unittest.main()
