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
from textual.message import Message
from textual.reactive import reactive
from textual.events import Key
from textual.widget import Widget
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

    # Allow navigating the menu using the arrow keys. Each key is bound to an
    # action method defined below. These actions move focus between the buttons
    # and the input widget.
    BINDINGS = [
        ("up", "focus_up", "Focus previous item"),
        ("down", "focus_down", "Focus next item"),
    ]

    class SetTime(Message):
        """Message sent when the user selects a duration."""

        def __init__(self, sender: Widget, seconds: int) -> None:
            super().__init__(sender)
            self.seconds = seconds

    def compose(self) -> ComposeResult:
        yield Button("30s", id="t30")
        yield Button("3m", id="t180")
        yield Button("7m", id="t420")
        yield Button("11m", id="t660")
        yield Input(placeholder="Custom (e.g. 90, 2m)", id="custom")

    def on_mount(self) -> None:
        """Cache child widgets for focus handling and focus the first item."""
        self._items = [
            self.query_one("#t30", Button),
            self.query_one("#t180", Button),
            self.query_one("#t420", Button),
            self.query_one("#t660", Button),
            self.query_one("#custom", Input),
        ]
        self._selected = 0
        self._items[0].focus()

    def action_focus_up(self) -> None:
        """Move focus to the previous widget in the menu."""
        self._selected = (self._selected - 1) % len(self._items)
        self._items[self._selected].focus()

    def action_focus_down(self) -> None:
        """Move focus to the next widget in the menu."""
        self._selected = (self._selected + 1) % len(self._items)
        self._items[self._selected].focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        seconds = int(event.button.id[1:])
        self.post_message(self.SetTime(self, seconds))

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        seconds = parse_time_spec(event.value)
        if seconds is not None:
            self.post_message(self.SetTime(self, seconds))
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

    def on_mount(self) -> None:
        """Focus the notes area and detect terminal features."""
        self.blink_supported = not getattr(self.console, "legacy_windows", False)
        self.query_one("#notes", TextArea).focus()

    def blink_or_flash(self) -> None:
        """Trigger blinking text or use a fallback animation."""
        if self.blink_supported:
            self.timer_display.animate("blink")
            return
        self.flash_timer_display()

    def flash_timer_display(self) -> None:
        """Fallback animation that swaps timer colors repeatedly."""
        if hasattr(self, "_flash_handle"):
            self._flash_handle.stop()
        self._flash_state = False
        self._flash_remaining = 6  # number of color swaps
        self._flash_handle = self.set_interval(0.5, self._flash_step)

    def _flash_step(self) -> None:
        self._flash_state = not self._flash_state
        if self._flash_state:
            self.timer_display.styles.background = "white"
            self.timer_display.styles.color = "darkgreen"
        else:
            self.timer_display.styles.background = "darkgreen"
            self.timer_display.styles.color = "white"
        self._flash_remaining -= 1
        if self._flash_remaining <= 0:
            self.timer_display.styles.background = "darkgreen"
            self.timer_display.styles.color = "white"
            self._flash_handle.stop()

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
        # When the menu becomes visible, move focus to it so the user can
        # navigate with the arrow keys immediately. Otherwise return focus to
        # the notes area.
        if self.menu_visible:
            self.menu._selected = 0
            self.menu._items[0].focus()
        else:
            self.query_one("#notes", TextArea).focus()

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
                self.blink_or_flash()
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
