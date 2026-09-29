"""Behavioral checks for dialogue boundaries, focus isolation, and one-shot alerts."""
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import auto_dialogue as a
import story_clicker as s

FIXTURES = Path(os.environ.get('GENSHIN_TEST_FIXTURES', str(s.ASSETS/'fixtures')))

def frame(name):
    return Image.open(FIXTURES/name).convert('RGB')

@unittest.skipUnless((FIXTURES/'admin-after.png').exists(), 'Private gameplay fixtures are not distributed')
class PolicyTests(unittest.TestCase):
    def test_user_reported_dim_history_and_short_subtitle_start_f(self):
        for filename in ('user-dim-history.png','user-short-subtitle.png'):
            with self.subTest(filename=filename):
                p=a.DialoguePolicy();image=frame(filename)
                self.assertIsNone(p.inspect(image,0)['action'])
                self.assertEqual(p.inspect(image,.15)['action'],'F')

    def test_cinematic_without_dialogue_controls_waits_then_resumes(self):
        p=a.DialoguePolicy()
        talk=frame('user-short-subtitle.png');cinematic=frame('user-cinematic-no-ui.png')
        p.inspect(talk,0);self.assertEqual(p.inspect(talk,.15)['action'],'F')
        self.assertIsNone(p.inspect(cinematic,.3)['action'])
        self.assertIsNone(p.inspect(cinematic,.5)['action'])
        self.assertIsNone(p.inspect(talk,1)['action'])
        self.assertEqual(p.inspect(talk,1.15)['action'],'F')

    def test_dialogue_starts_then_stops_and_resumes_without_manual_restart(self):
        p=a.DialoguePolicy(30)
        talk=frame('admin-after.png'); game=frame('task-current.png')
        self.assertIsNone(p.inspect(game,0)['action'])
        self.assertIsNone(p.inspect(talk,1)['action'])
        self.assertEqual(p.inspect(talk,1.5)['action'],'F')
        self.assertIsNone(p.inspect(game,2)['action'])
        self.assertFalse(p.inspect(game,31)['notify'])
        self.assertTrue(p.inspect(game,32)['notify'])
        self.assertFalse(p.inspect(game,65)['notify'])
        self.assertIsNone(p.inspect(talk,66)['action'])
        self.assertEqual(p.inspect(talk,66.5)['action'],'F')

    def test_choice_uses_f_only_while_recognized(self):
        p=a.DialoguePolicy()
        choice=frame('drink-dialogue-4.png')
        self.assertIsNone(p.inspect(choice,0)['action'])
        self.assertEqual(p.inspect(choice,1)['action'],'F')
        self.assertIsNone(p.inspect(frame('task-current.png'),2)['action'])

    def test_idle_before_first_dialogue_does_not_notify(self):
        p=a.DialoguePolicy(30); game=frame('task-current.png')
        p.inspect(game,0)
        self.assertFalse(p.inspect(game,300)['notify'])

    def test_stalled_dialogue_alerts_and_stops_taps_until_progress(self):
        p=a.DialoguePolicy(30); talk=frame('admin-after.png')
        p.inspect(talk,0)
        result=p.inspect(talk,30)
        self.assertTrue(result['notify']);self.assertIsNone(result['action'])
        self.assertFalse(p.inspect(talk,31)['notify'])
        self.assertEqual(p.inspect(frame('drink-serve-scene.png'),32)['action'],'F')

    def test_camera_change_restarts_stall_timer(self):
        p=a.DialoguePolicy(30)
        p.inspect(frame('admin-after.png'),0)
        p.inspect(frame('task-current.png'),1)
        black=Image.new('RGB',(1920,1080),'black')
        p.inspect(black,25)
        self.assertFalse(p.inspect(black,54)['notify'])
        self.assertTrue(p.inspect(black,55)['notify'])

    def test_focus_absence_does_not_count_toward_stall(self):
        p=a.DialoguePolicy(30); talk=frame('admin-after.png')
        p.inspect(talk,0);p.suspend()
        result=p.inspect(talk,300)
        self.assertFalse(result['notify']);self.assertIsNone(result['action'])

    def test_gameplay_and_loading_never_trigger_input(self):
        for image in [frame('task-current.png'),frame('user-menu.png'),Image.new('RGB',(1920,1080),'black'),
                      Image.new('RGB',(1920,1080),'white')]:
            p=a.DialoguePolicy()
            for now in (0,1,2):self.assertIsNone(p.inspect(image,now)['action'])

@unittest.skipUnless((FIXTURES/'admin-after.png').exists(), 'Private gameplay fixtures are not distributed')
class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.patches=[patch.object(a,'DATA',Path(self.temp.name)),
            patch.object(s,'game_window',return_value=(123,456)),
            patch.object(s,'foreground',return_value=123),patch.object(s,'is_iconic',return_value=False),
            patch.object(s,'require_matching_privilege'),patch.object(s,'guard'),
            patch.object(s,'key_state',return_value=0),patch.object(s,'bounds',return_value=(0,0,1920,1080)),
            patch.object(s,'capture',return_value=frame('admin-after.png')),
            patch.object(a,'tap_key',return_value=True),patch.object(s,'cursor_set'),
            patch.object(s,'activate_game'),patch.object(a.winsound,'PlaySound')]
        self.m=[p.start() for p in self.patches]
        self.addCleanup(lambda:[p.stop() for p in reversed(self.patches)])
        self.w=a.Watcher()

    def step(self):
        self.w.next_at=0;self.w.tick()

    def test_other_app_never_captured_or_controlled_and_return_resumes(self):
        self.m[2].return_value=999
        self.step();self.m[8].assert_not_called();self.m[9].assert_not_called()
        self.m[2].return_value=123
        self.step();self.step()
        self.m[9].assert_called_once_with(123,'F')
        self.m[10].assert_not_called();self.m[11].assert_not_called()

    def test_second_observation_blocks_input_after_dialogue_ends(self):
        self.step()
        self.m[8].side_effect=[frame('admin-after.png'),frame('task-current.png')]
        self.step();self.m[9].assert_not_called()

    def test_choice_does_not_move_mouse(self):
        self.m[8].return_value=frame('drink-dialogue-4.png')
        for _ in range(4):self.step()
        self.assertEqual(self.m[9].call_count,3)
        self.assertTrue(all(call.args==(123,'F') for call in self.m[9].call_args_list))
        self.m[10].assert_not_called();self.m[11].assert_not_called()

    def test_pause_is_quiet(self):
        self.w.toggle();self.step()
        self.m[8].assert_not_called();self.m[9].assert_not_called();self.m[12].assert_not_called()

    def test_observe_only_has_no_inputs_or_sounds(self):
        self.w.observe_only=True
        self.step();self.step()
        self.m[9].assert_not_called();self.m[12].assert_not_called()

    def test_processing_is_inside_period_and_early_tick_cannot_repeat_input(self):
        clock=[100.0]
        with patch.object(a.time,'monotonic',side_effect=lambda:clock[0]):
            self.step()
            clock[0]=101.0
            def input_with_processing(*args):
                clock[0]+=0.12
                return True
            self.m[9].side_effect=input_with_processing
            self.step()
            self.assertAlmostEqual(self.w.next_at,101.0+a.TAP_PERIOD)
            self.w.tick()
            self.m[9].assert_called_once_with(123,'F')

class NativeTapTests(unittest.TestCase):
    def test_held_modifier_blocks_key_injection(self):
        for modifier in (0x10,0x11,0x12):
            with patch.object(s,'bounds',return_value=(0,0,1920,1080)), \
                 patch.object(s,'guard'), \
                 patch.object(s,'key_state',side_effect=lambda key:0x8000 if key==modifier else 0), \
                 patch.object(s,'send_input') as send:
                self.assertFalse(a.tap_key(123,'F'))
                send.assert_not_called()

if __name__=='__main__':unittest.main()
