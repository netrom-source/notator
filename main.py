"""Simple note-taking app with a timer, built from scratch.

This module implements a Textual application that lets users write notes in a
text area while optionally running a countdown timer. The timer menu can be
toggled with ``Ctrl+T`` and offers a few preset durations as well as a custom
input field. ``Ctrl+R`` resets the timer or stops it if pressed twice quickly.

The application is fully standalone and heavily commented so that it is easy to
understand and extend.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
        1kkj4s-codex/design-python-baseret-notesystem-med-timer
from textual.message import Message
from textual.reactive import reactive

from textual.events import Key
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
        main
from textual.widgets import Button, Input, Static, TextArea


def parse_time_spec(value: str) -> Optional[int]:
    """Convert a time specification to seconds.

    The parser accepts values like ``"90"`` or ``"2m"``. If the value ends with a
    ``"m"`` it is interpreted as minutes, otherwise as seconds.

    Args:
        value: Text entered by the user.

    Returns:
        The number of seconds represented by the value or ``None`` if it is not
        valid.
    """

    match = re.fullmatch(r"(\d+)(m?)", value.strip().lower())
    if not match:
        return None
    amount, minutes = match.groups()
    seconds = int(amount)
    if minutes:
        seconds *= 60
    return seconds


@dataclass
class CountdownState:
    """Keep track of the current countdown."""

    duration: int = 0  # total duration in seconds
    remaining: int = 0  # seconds left
    last_started: float = 0.0  # time when timer was last started


class TimerDisplay(Static):
    """Widget that shows the remaining time in ``mm:ss`` format."""

    def update_time(self, seconds: int) -> None:
        minutes, secs = divmod(max(0, seconds), 60)
        self.update(f"⏱ {minutes:02d}:{secs:02d}")


class TimerMenu(Vertical):
    """The pop-up menu with preset buttons and a custom input field."""

    class SetTime(Message):
        """Message sent when the user selects a duration."""

        1kkj4s-codex/design-python-baseret-notesystem-med-timer
        def __init__(self, seconds: int) -> None:
            super().__init__()

        def __init__(self, sender: Widget, seconds: int) -> None:
            super().__init__(sender)
        main
            self.seconds = seconds

    def compose(self) -> ComposeResult:
        yield Button("30s", id="t30")
        yield Button("3m", id="t180")
        yield Button("7m", id="t420")
        yield Button("11m", id="t660")
        yield Input(placeholder="Custom (e.g. 90, 2m)", id="custom")

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        seconds = int(event.button.id[1:])
        1kkj4s-codex/design-python-baseret-notesystem-med-timer
        self.post_message(self.SetTime(seconds))

        self.post_message(self.SetTime(self, seconds))
        main

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        seconds = parse_time_spec(event.value)
        if seconds is not None:
        1kkj4s-codex/design-python-baseret-notesystem-med-timer
            self.post_message(self.SetTime(seconds))

            self.post_message(self.SetTime(self, seconds))
        main
        else:
            self.app.bell()


class NoteApp(App[None]):
    """Main application class."""

    CSS_PATH = "style.css"

    BINDINGS = [
        ("ctrl+t", "toggle_menu", "Timer Menu"),
        ("ctrl+r", "reset_timer", "Reset/Stop Timer"),
    ]

    countdown = reactive(CountdownState())
    menu_visible = reactive(False)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        self.timer_display = TimerDisplay(id="timer_display")
        yield self.timer_display
        yield Container(TextArea(id="notes"))
        self.menu = TimerMenu(id="timer_menu")
        self.menu.visible = False
        yield self.menu

    def watch_countdown(self, countdown: CountdownState) -> None:
        """Update the UI whenever the countdown changes."""
        self.timer_display.update_time(countdown.remaining)
        self.timer_display.display = (
            self.menu_visible or countdown.remaining > 0
        )

    def action_toggle_menu(self) -> None:
        """Show or hide the timer menu."""
        self.menu_visible = not self.menu_visible
        self.menu.visible = self.menu_visible
        self.timer_display.display = self.menu_visible or self.countdown.remaining > 0

    def action_reset_timer(self) -> None:
        """Reset or stop the timer depending on how quickly this action is called."""
        now = time.time()
        # If the timer is running and we pressed reset less than 2s ago -> stop
        if (
            self.countdown.remaining > 0
            and now - self.countdown.last_started < 2
        ):
            self.stop_timer()
            return
        if self.countdown.duration:
            self.start_timer(self.countdown.duration)

    def start_timer(self, seconds: int) -> None:
        """Begin counting down from the given number of seconds."""
        self.countdown = CountdownState(
            duration=seconds,
            remaining=seconds,
            last_started=time.time(),
        )
        # Cancel any existing timer and create a new one
        if hasattr(self, "_tick_handle"):
            self._tick_handle.stop()
        self._tick_handle = self.set_interval(1, self.tick)
        self.notify("Timer started")

    def stop_timer(self) -> None:
        """Stop the timer and hide the display if the menu isn't open."""
        if hasattr(self, "_tick_handle"):
            self._tick_handle.stop()
        self.countdown.remaining = 0
        self.timer_display.update_time(0)
        self.timer_display.display = self.menu_visible
        self.notify("Timer stopped")

    def tick(self) -> None:
        """Called every second to update the countdown."""
        if self.countdown.remaining > 0:
            self.countdown.remaining -= 1
            self.timer_display.update_time(self.countdown.remaining)
            if self.countdown.remaining == 0:
                self.timer_display.animate("blink")
                self.notify("Time's up!")
        else:
            self.timer_display.display = self.menu_visible
            if hasattr(self, "_tick_handle"):
                self._tick_handle.stop()

    def on_timer_menu_set_time(self, message: TimerMenu.SetTime) -> None:
        """Start the timer when the user picks a duration."""
        self.start_timer(message.seconds)
        if not self.menu_visible:
            self.action_toggle_menu()


if __name__ == "__main__":
    app = NoteApp()
    app.run()
