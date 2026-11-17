"""Qt-free four-press PageUp/PageDown launcher for the EXISTING shuriken flight.

Only distinct, same-direction physical key presses in the Files List count.
An ordinary page press must still go through Qt.  This class never scrolls,
starts a timer, or changes the selected file; it only recognizes the gesture.
"""
import time

PAGE_FLIGHT_PRESSES = 4
PAGE_FLIGHT_MAX_GAP_S = 0.48
PAGE_FLIGHT_WINDOW_S = 1.35


class PageKeyShurikenGate:
    def __init__(self):
        self.reset()

    def reset(self):
        self._direction = 0
        self._context = None
        self._count = 0
        self._first = None
        self._last = None

    def pending(self, *, context=None, now=None):
        if self._count == 0:
            return False
        t = time.monotonic() if now is None else float(now)
        if (t < self._last or t - self._last > PAGE_FLIGHT_MAX_GAP_S
                or t - self._first > PAGE_FLIGHT_WINDOW_S
                or (context is not None and context != self._context)):
            self.reset()
            return False
        return True

    def feed(self, direction, *, context, now=None, auto_repeat=False):
        """Return direction (+1=PageUp, -1=PageDown) exactly on press #4.

        Keyboard auto-repeat does NOT simulate a four-key tap.  Count only
        actual presses; retain the partial gesture until it times out.
        """
        if direction not in (-1, 1):
            self.reset()
            return 0
        t = time.monotonic() if now is None else float(now)
        if auto_repeat:
            self.pending(context=context, now=t)
            return 0
        if (not self.pending(context=context, now=t)
                or direction != self._direction):
            self.reset()
            self._first = t
        self._direction = direction
        self._context = context
        self._count += 1
        self._last = t
        if self._count >= PAGE_FLIGHT_PRESSES:
            self.reset()
            return direction
        return 0
