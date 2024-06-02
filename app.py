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


SCREEN_RADIUS = 120

FG = (1, 1, 1)
BG = (0, 0, 0)
AC = (1, 0, 0)


def set_time():
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
    else:
        print("Error!", response.json())


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
        # set_time()
        print("asodifhoaisnf")
        self.button_states = Buttons(self)
        self.fetched = False
        eventbus.emit(PatternDisable())
        eventbus.on(RequestForegroundPushEvent, self._on_fg, self)
        wifi.connect()

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

    def background_update(self, delta):
        if not self.fetched:
            if wifi.status():
                set_time()
                self.fetched = True

    def draw(self, ctx):
        ctx.save()
        ctx.rgb(*BG).rectangle(-SCREEN_RADIUS, -SCREEN_RADIUS, 2 * SCREEN_RADIUS, 2 * SCREEN_RADIUS).fill()
        ctx.restore()

        draw_clockface(ctx, FG)
        
        year, month, mday, hour, minute, second, weekday, yearday = time.localtime()

        draw_clockhand(ctx, 0.5 * SCREEN_RADIUS, 3, (hour + (minute / 60)) / 12 % 1, FG)
        draw_clockhand(ctx, 0.8 * SCREEN_RADIUS, 1, (minute + (second / 60)) / 60, FG)
        draw_clockhand(ctx, 0.8 * SCREEN_RADIUS, .5, second / 60, AC)

        COLOURS = [(0, 0, 0) for _ in range(12)]

        COLOURS[minute // 5] = tuple(FG[j] / 4 for j in range(3))
        COLOURS[hour % 12] = FG

        i = second // 5
        t = max(min(1, second / 5 - i), 0)
        COLOURS[i] = tuple(COLOURS[i][j] + (AC[j] - COLOURS[i][j]) * t for j in range(3))
        t2 = 1 - t
        COLOURS[i - 1 % 12] = tuple(COLOURS[i - 1 % 12][j] + (AC[j] - COLOURS[i - 1 % 12][j]) * t2 for j in range(3))

        for i in range(1, 13):
            tildagonos.leds[i] = tuple(int(255 * COLOURS[i - 1][j]) for j in range(3))

        # label = f"{hour:02d}:{minute:02d}:{second:02d}"
        # ctx.rgb(1,0,0).move_to(-80,0).text(label)



__app_export__ = ClockApp
