"""Cursor rod must never act while ANY visible window covers the pad."""
import ast
from pathlib import Path
import sys
from types import SimpleNamespace as NS
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from rod_occlusion import WindowInZOrder as W, is_uncovered_in_z_order, rectangles_intersect

PAD=(100,100,300,240)


def test_opaque_foreign_window_overlaps_small_far_corner_and_blocks_whole_pad():
    # Pointer can be left of center; a foreign window still covers right edge.
    assert not is_uncovered_in_z_order(1,PAD,[W(7,(285,225,400,300)),W(1,None)])
    assert not is_uncovered_in_z_order(1,PAD,[W(7,(120,120,230,230)),W(1,None)])


def test_non_overlapping_behind_or_hidden_does_not_block():
    assert is_uncovered_in_z_order(1,PAD,[W(7,(310,100,410,200)),W(1,None)])
    assert is_uncovered_in_z_order(1,PAD,[W(1,None),W(7,PAD)])
    assert is_uncovered_in_z_order(1,PAD,[W(7,PAD,visible=False),W(1,None)])
    assert is_uncovered_in_z_order(1,PAD,[W(7,PAD,minimized=True),W(1,None)])
    assert is_uncovered_in_z_order(1,PAD,[W(7,PAD,cloaked=True),W(1,None)])
    assert is_uncovered_in_z_order(1,PAD,[W(7,PAD,click_through=True),W(1,None)])
    assert is_uncovered_in_z_order(1,PAD,[W(7,PAD),W(1,None)],ignore_hwnds=(7,))


def test_invalid_owner_or_bounds_or_unavailable_window_geometry_fails_closed():
    assert not is_uncovered_in_z_order(0,PAD,[W(1,None)])
    assert not is_uncovered_in_z_order(1,PAD,[])
    assert not is_uncovered_in_z_order(1,PAD,[W(7,None),W(1,None)])
    assert not is_uncovered_in_z_order(1,(100,100,100,100),[W(1,None)])
    assert not rectangles_intersect(PAD,(300,120,400,180))


def _rod_method(name, scope=None):
    src=(ROOT/'src/mouse_pointer_rod.py').read_text('utf-8')
    cls=next(x for x in ast.parse(src).body if isinstance(x,ast.ClassDef)
             and x.name=='MousePointerRodPad')
    fn=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==name)
    ns={} if scope is None else scope
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'rod', 'exec'),ns)
    return ns[name]


def test_direct_native_and_wheel_actions_all_blocked_under_overlap():
    from types import ModuleType
    dispatch = _rod_method('_dispatch_tip_action')
    obj = NS(_enabled=True,_windows_click_mode=False,
             _launch_has_foreground=lambda:True,
             _operating_area_uncovered=Mock(return_value=False),
             parentWidget=lambda: NS(parent=lambda:'LAUNCH'),
             tip_global=lambda:(200,200))
    assert dispatch(obj,'select') is False
    obj._operating_area_uncovered.assert_called_with(force=True)
    # Native path must be blocked before trying to import its injector.
    obj._windows_click_mode=True
    assert dispatch(obj,'double') is False

    wheel=_rod_method('wheelEvent')
    event=NS(accept=Mock())
    obj2=NS(_cursor_on_blue=lambda:True,
            _operating_area_uncovered=lambda **kw:False,
            _stop_aiming=Mock())
    wheel(obj2,event)
    obj2._stop_aiming.assert_called_once()
    event.accept.assert_called_once()


def test_occlusion_watchdog_hides_rod_and_cancels_pending_click():
    fn=_rod_method('_watch_foreground')
    o=NS(_launch_has_foreground=lambda:True,
         _operating_area_uncovered=Mock(return_value=False),
         _cancel_pending_native_click=Mock(),_stop_aiming=Mock())
    fn(o)
    o._cancel_pending_native_click.assert_called_once()
    o._stop_aiming.assert_called_once()
    o._operating_area_uncovered.assert_called_once_with(force=True)
