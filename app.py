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
    ColourScheme(c("303A2B"), c("C1BDDB"), c("FF99C9")),
    ColourScheme(c("00916E"), c("FEEFE5"), c("FA003F")),
    ColourScheme(c("3C0000"), c("774936"), c("F5D0C5")),
    ColourScheme(c("FF9B71"), c("FFFD82"), c("ED217C")),
    ColourScheme(c("38023B"), c("A288E3"), c("CEFDFF")),
    ColourScheme(c("F1F2EB"), c("4A4A48"), c("566246")),
    ColourScheme(c("FEEFE5"), c("EE6123"), c("FFCF00")),
]


def lerp(t, c1, c2):
    return tuple(v1 + (v2 - v1) * t for v1, v2 in zip(c1, c2))


def draw_clockface(ctx, centre, radius, minor, major, c):
    cx, cy = centre

    ctx.save()

    ctx.rgb(*c)
    ctx.arc(cx, cy, radius, 0, 2 * maths.pi, True).stroke()

    ctx.begin_path()

    for i in range(minor):
        r1 = radius * (0.8 if i % major == 0 else 0.9)
        r2 = radius * 1.0
        a = maths.pi / 2 - 2 * maths.pi * i / minor

        ctx.move_to(cx + r1 * maths.cos(a), cy - r1 * maths.sin(a))
        ctx.line_to(cx + r2 * maths.cos(a), cy - r2 * maths.sin(a))

    ctx.stroke()

    ctx.restore()


def draw_clockhand(ctx, centre, r, w, f, c):
    cx, cy = centre
    a = maths.pi / 2 - f * 2 * maths.pi

    ctx.save()
    ctx.rgb(*c)

    x = cx + r * maths.cos(a)
    y = cy - r * maths.sin(a)

    dx = w * maths.cos(a - maths.pi / 2)
    dy = -w * maths.sin(a - maths.pi / 2)
    
    ctx.begin_path()
    ctx.move_to(cx, cy)
    ctx.line_to(cx + dx, cy + dy)
    ctx.line_to(x + dx, y + dy)
    ctx.line_to(x - dx, y - dy)
    ctx.line_to(cx - dx, cy - dy)
    ctx.close_path()
    ctx.fill()

    ctx.arc(cx, cy, w, 0, 2 * maths.pi, True).fill()
    ctx.arc(x, y, w, 0, 2 * maths.pi, True).fill()

    ctx.restore()


class Overlay:
    def __init__(self):
        self.enabled = True
        self.scheme = SCHEMES[0]

    def update(self, delta):
        pass

    def draw(self, ctx):
        if self.enabled:
            self.draw_enabled(ctx)


class ClockOverlay(Overlay):
    def __init__(self):
        super().__init__()
        self.hour = 0
        self.minute = 0
        self.second = 0

    def update(self, delta):
        year, month, mday, hour, minute, second, weekday, yearday = time.localtime()
        self.hour = hour
        self.minute = minute
        self.second = second

    def draw_enabled(self, ctx):
        draw_clockface(ctx, (0, 0), SCREEN_RADIUS, 12, 3, self.scheme.fg)
        draw_clockhand(ctx, (0, 0), 0.5 * SCREEN_RADIUS, 3, (self.hour + (self.minute / 60)) / 12 % 1, self.scheme.fg)
        draw_clockhand(ctx, (0, 0), 0.8 * SCREEN_RADIUS, 1, (self.minute + (self.second / 60)) / 60, self.scheme.fg)
        draw_clockhand(ctx, (0, 0), 0.8 * SCREEN_RADIUS, .5, self.second / 60, self.scheme.accent)


class MonthOverlay(Overlay):
    def __init__(self):
        super().__init__()
        self.month = 0

    def update(self, delta):
        year, month, mday, hour, minute, second, weekday, yearday = time.localtime()
        self.month = month

    def draw_enabled(self, ctx):
        a = maths.pi / 2 - 2 * maths.pi / 3
        x = SCREEN_RADIUS / 2 * maths.cos(a)
        y = -SCREEN_RADIUS / 2 * maths.sin(a)

        c = lerp(0.5, self.scheme.bg, self.scheme.fg)
        draw_clockface(ctx, (x, y), SCREEN_RADIUS / 4, 12, 12, c)
        draw_clockhand(ctx, (x, y), SCREEN_RADIUS / 5, 2, self.month / 12, c)


class ButtonIndicator(Overlay):
    def __init__(self, button):
        super().__init__()
        self.button = button
        self.t = 1000
        self.l = 0.66
        self.enabled = False

    def fire(self):
        self.t = 0
        self.enabled = True

    def update(self, delta):
        self.t += delta / 1000
        if self.t >= self.l:
            self.enabled = False

    def draw_enabled(self, ctx):
        a = maths.pi / 2 - 2 * maths.pi * self.button / 6
        cx = (SCREEN_RADIUS + 20) * maths.cos(a)
        cy = -(SCREEN_RADIUS + 20) * maths.sin(a)
        
        ctx.save()
        ctx.rgb(*self.scheme.accent)

        f = 1 - (1 - self.t / self.l) ** 2
        ctx.arc(cx, cy, 30 + 10 * f, 0, 2 * maths.pi, True).fill()
        ctx.restore()


def get_monthdays(year, month):
    assert 1 <= month <= 12

    days = [31, None, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    if month == 2:
        if year % 4 == 0 and year % 100 == 0 and year % 400 != 0:
            return 29
        else:
            return 28
    else:
        return days[month - 1]



class DayOverlay(Overlay):
    def __init__(self):
        super().__init__()
        self.year = 0
        self.month = 0
        self.mday = 0

    def update(self, delta):
        year, month, mday, hour, minute, second, weekday, yearday = time.localtime()
        self.year = year
        self.month = month
        self.mday = mday

    def draw_enabled(self, ctx):
        a = maths.pi / 2 - 4 * maths.pi / 3
        x = SCREEN_RADIUS / 2 * maths.cos(a)
        y = -SCREEN_RADIUS / 2 * maths.sin(a)

        minor = get_monthdays(self.year, self.month)
        c = lerp(0.5, self.scheme.bg, self.scheme.fg)
        draw_clockface(ctx, (x, y), SCREEN_RADIUS / 4, minor, minor, c)
        draw_clockhand(ctx, (x, y), SCREEN_RADIUS / 5, 2, self.mday / minor, c)


class ClockApp(app.App):
    def __init__(self):
        super().__init__()

        self.button_states = Buttons(self)
        self.fetched = False
        self.last_fetched = None
        self.clock = ClockOverlay()
        self.month = MonthOverlay()
        self.day = DayOverlay()
        self.button_indicators = [ButtonIndicator(i) for i in range(6)]
        self.notification = Notification("Initialized!")
        self.scheme_i = 0

        self.overlays.append(self.month)
        self.overlays.append(self.day)
        self.overlays.append(self.clock)
        self.overlays.append(self.notification)
        self.overlays.extend(self.button_indicators)

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
            self.button_indicators[5].fire()
            eventbus.emit(PatternEnable())
            self.minimise()

        if self.button_states.get(BUTTON_TYPES["CONFIRM"]):
            self.button_states.clear()
            self.button_indicators[2].fire()
            self.scheme_i = (self.scheme_i + 1) % len(SCHEMES)
            for overlay in self.overlays:
                overlay.scheme = SCHEMES[self.scheme_i]

        for overlay in self.overlays:
            overlay.update(delta)

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

        self.draw_overlays(ctx)

        colours = [scheme.bg for _ in range(12)]

        colours[minute // 5] = lerp(0.5, scheme.bg, scheme.fg)
        colours[hour % 12] = scheme.fg

        i = second // 5
        t = max(min(1, second / 5 - i), 0)
        colours[i] = lerp(t, colours[i], scheme.accent)
        t2 = 1 - t
        colours[i - 1 % 12] = lerp(t2, colours[i - 1 % 12], scheme.accent)

        for i in range(1, 13):
            tildagonos.leds[i] = tuple(int(255 * colours[i - 1][j]) for j in range(3))


__app_export__ = ClockApp
