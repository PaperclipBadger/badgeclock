import collections
import math as maths
import time

import app
import requests

import machine
import wifi
from tildagonos import tildagonos
from system.eventbus import eventbus
from system.patterndisplay.events import PatternDisable, PatternEnable
from system.scheduler.events import RequestForegroundPushEvent
from events.input import Buttons, BUTTON_TYPES

from app_components import Notification


SCREEN_RADIUS = 120


ColourScheme = collections.namedtuple("ColourScheme", ["bg", "fg", "accent"])


def c(s):
    return tuple(int(s[i : i + 2], 16) / 255 for i in range(0, 6, 2))


SCHEMES = [
    ColourScheme(c("000000"), c("FFFFFF"), c("FF0000")),
    ColourScheme(c("FFFFFF"), c("000000"), c("FF0000")),
    ColourScheme(c("03012C"), c("190E4F"), c("EA638C")),
    ColourScheme(c("002400"), c("273B09"), c("7B904B")),
    ColourScheme(c("3C0000"), c("774936"), c("F5D0C5")),
    ColourScheme(c("FF9B71"), c("FFFD82"), c("ED217C")),
]


def draw_clockface(ctx, c):
    ctx.save()

    ctx.rgb(*c)
    ctx.arc(0, 0, SCREEN_RADIUS, 0, 2 * maths.pi, True).stroke()

    ctx.begin_path()

    for i in range(12):
        r1 = SCREEN_RADIUS * (0.8 if i % 3 == 0 else 0.9)
        r2 = SCREEN_RADIUS * 1.0
        a = i / 6 * maths.pi

        ctx.move_to(r1 * maths.cos(a), r1 * maths.sin(a))
        ctx.line_to(r2 * maths.cos(a), r2 * maths.sin(a))

    ctx.stroke()

    ctx.restore()


def draw_clockhand(ctx, r, w, f, c):
    a = maths.pi / 2 - f * 2 * maths.pi

    ctx.save()
    ctx.rgb(*c)

    x = r * maths.cos(a)
    y = -r * maths.sin(a)

    dx = w * maths.cos(a - maths.pi / 2)
    dy = -w * maths.sin(a - maths.pi / 2)
    
    ctx.begin_path()
    ctx.move_to(0, 0)
    ctx.line_to(dx, dy)
    ctx.line_to(x + dx, y + dy)
    ctx.line_to(x - dx, y - dy)
    ctx.line_to(-dx, -dy)
    ctx.close_path()
    ctx.fill()

    ctx.arc(0, 0, w, 0, 2 * maths.pi, True).fill()
    ctx.arc(x, y, w, 0, 2 * maths.pi, True).fill()

    ctx.restore()


class ClockApp(app.App):
    def __init__(self):
        self.button_states = Buttons(self)
        self.fetched = False
        self.last_fetched = None
        self.notification = Notification("Initialized!")
        self.scheme_i = 0

        eventbus.emit(PatternDisable())
        eventbus.on(RequestForegroundPushEvent, self._on_fg, self)

    def _on_fg(self, event):
        if event.app == self:
            eventbus.emit(PatternDisable())

    def update(self, delta):
        if self.button_states.get(BUTTON_TYPES["CANCEL"]):
            # The button_states do not update while you are in the background.
            # Calling clear() ensures the next time you open the app, it stays open.
            # Without it the app would close again immediately.
            self.button_states.clear()
            eventbus.emit(PatternEnable())
            self.minimise()

        if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            self.scheme_i = (self.scheme_i + 1) % len(SCHEMES)

        if self.notification is not None:
            self.notification.update(delta)

    def background_update(self, delta):
        if not self.fetched and (self.last_fetched is None or time.time() - self.last_fetched > 60):
            self.last_fetched = time.time()
            try:
                response = requests.get("https://timeapi.io/api/Time/current/zone?timeZone=Europe%2FLondon")
                if response.status_code == 200:
                    data = response.json()
                    ttuple = (
                        data["year"],
                        data["month"],
                        data["day"],
                        data["dayOfWeek"],
                        data["hour"],
                        data["minute"],
                        data["seconds"],
                        data["milliSeconds"],
                    )
                    machine.RTC().datetime(ttuple)
                    self.fetched = True
                else:
                    raise ValueError(f"Status: {response.status_code}, Message: {response.json()}")
            except Exception as e:
                message = str(e)
                self.notification = Notification(message)

    def draw(self, ctx):
        year, month, mday, hour, minute, second, weekday, yearday = time.localtime()
        scheme = SCHEMES[self.scheme_i]

        ctx.save()
        ctx.rgb(*scheme.bg).rectangle(-SCREEN_RADIUS, -SCREEN_RADIUS, 2 * SCREEN_RADIUS, 2 * SCREEN_RADIUS).fill()

        # label = f"{mday:02d}-{month:02d}-{year:02d}"
        # ctx.rgb(*scheme.fg).move_to(-80,60).text(label)

        ctx.restore()

        draw_clockface(ctx, scheme.fg)
        draw_clockhand(ctx, 0.5 * SCREEN_RADIUS, 3, (hour + (minute / 60)) / 12 % 1, scheme.fg)
        draw_clockhand(ctx, 0.8 * SCREEN_RADIUS, 1, (minute + (second / 60)) / 60, scheme.fg)
        draw_clockhand(ctx, 0.8 * SCREEN_RADIUS, .5, second / 60, scheme.accent)

        colours = [(0, 0, 0) for _ in range(12)]

        colours[minute // 5] = tuple(scheme.fg[j] / 4 for j in range(3))
        colours[hour % 12] = scheme.fg

        i = second // 5
        t = max(min(1, second / 5 - i), 0)
        colours[i] = tuple(colours[i][j] + (scheme.accent[j] - colours[i][j]) * t for j in range(3))
        t2 = 1 - t
        colours[i - 1 % 12] = tuple(colours[i - 1 % 12][j] + (scheme.accent[j] - colours[i - 1 % 12][j]) * t2 for j in range(3))

        for i in range(1, 13):
            tildagonos.leds[i] = tuple(int(255 * colours[i - 1][j]) for j in range(3))

        if self.notification is not None:
            self.notification.draw(ctx)


__app_export__ = ClockApp
