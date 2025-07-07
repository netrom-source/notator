from __future__ import annotations

# ---------------------------------------------------------------------------
# Simple note-taking application with an integrated timer
# ---------------------------------------------------------------------------
#
# The code in this file defines a Textual based program where the user can type
# notes while optionally running a countdown timer.  The timer can be opened
# with ``Ctrl+T``.  When a time is chosen either from one of the preset buttons
# or by entering a custom value, the countdown starts automatically.  The timer
# may be reset with ``Ctrl+R`` and stopped by pressing ``Ctrl+R`` again within
# two seconds.  All user interface styling is provided via ``style.css`` so the
# appearance can be customised without modifying the Python code.
#
# The program is thoroughly annotated with comments so that it is easy to
# understand and extend.


import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual import events
from textual.widgets import (
    Button,
    Input,
    Static,
    TextArea,
    TabbedContent,
    TabPane,
)

# Name of the file used to store notes on disk. ``Path`` is used so it works
# across different operating systems and makes future modifications easy.
NOTE_FILES = {
    "tab1": Path("notes1.txt"),
    "tab2": Path("notes2.txt"),
}

# Base title shown in the window. An asterisk is added when notes are modified
# to provide a quick visual cue about unsaved work.
APP_TITLE = "NoteApp"


def parse_time_spec(value: str) -> Optional[int]:
    # Convert a textual time specification to seconds.
    #
    # The value may be a plain number, meaning seconds, or it can end with
    # ``m`` to indicate minutes (for example ``"2m"`` is two minutes).  Any
    # whitespace around the value is ignored.  If parsing fails the function
    # returns ``None`` so the caller can react accordingly.
    #
    # ``value`` -- the text provided by the user.

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
    # Keep track of the current countdown.

    duration: int = 0  # total duration in seconds
    remaining: int = 0  # seconds left
    last_started: float = 0.0  # time when timer was last started


class TimerDisplay(Static):
    # Widget that shows the remaining time in ``mm:ss`` format.

    def update_time(self, seconds: int) -> None:
        minutes, secs = divmod(max(0, seconds), 60)
        self.update(f"⏱ {minutes:02d}:{secs:02d}")


class NoteInput(Input):
    # Input widget without conflicting control-key shortcuts.

    # Filter out bindings that would otherwise consume Ctrl+H, Ctrl+K or
    # Ctrl+M. These shortcuts are removed so they can't trigger Textual's
    # built-in commands and will instead be handled (or ignored) by the
    # application itself.
    BINDINGS = [
        b
        for b in Input.BINDINGS
        if "ctrl+h" not in b.key and "ctrl+k" not in b.key and "ctrl+m" not in b.key
    ]


class NoteTextArea(TextArea):
    # Text area widget with custom key bindings.

    # Like ``NoteInput`` remove bindings for Ctrl+H, Ctrl+K and Ctrl+M. This
    # prevents them from triggering delete or other commands that might
    # conflict with the application's own shortcuts. All other default
    # behaviour is left intact.
    BINDINGS = [
        b
        for b in TextArea.BINDINGS
        if "ctrl+h" not in b.key and "ctrl+k" not in b.key and "ctrl+m" not in b.key
    ]

    async def _on_key(self, event: events.Key) -> None:
        """Handle key events for the note area.

        This override removes the ``Ctrl+H``, ``Ctrl+K`` and ``Ctrl+M``
        shortcuts so they don't trigger Textual's default behaviours. All
        other keys are passed through to ``TextArea`` for normal processing.
        """

        # Check for the control key combinations we want to ignore.
        if event.key in {"ctrl+h", "ctrl+k", "ctrl+m"}:
            # Stop the event so nothing else reacts to it.
            event.stop()
            return

        # Defer to the base ``TextArea`` implementation for everything else
        # to keep all standard text editing features intact.
        await super()._on_key(event)


class TimerMenu(Vertical):
    # The pop-up menu with preset buttons and a custom input field.

    # Allow navigating the menu using the arrow keys. Each key is bound to an
    # action method defined below. These actions will move focus between the
    # buttons and the input widget.
    BINDINGS = [
        ("up", "focus_up", "Focus previous item"),
        ("down", "focus_down", "Focus next item"),
        ("escape", "close_menu", "Close menu"),
    ]

    class SetTime(Message):
        # Message sent when the user selects a duration.

        def __init__(self, seconds: int) -> None:
            super().__init__()
            self.seconds = seconds

    def compose(self) -> ComposeResult:
        yield Button("30s", id="t30")
        yield Button("3m", id="t180")
        yield Button("7m", id="t420")
        yield Button("11m", id="t660")
        yield NoteInput(placeholder="Custom (e.g. 90, 2m)", id="custom")

    def on_mount(self) -> None:
        # Cache child widgets for focus handling and focus the first item.
        self._items = [
            self.query_one("#t30", Button),
            self.query_one("#t180", Button),
            self.query_one("#t420", Button),
            self.query_one("#t660", Button),
            self.query_one("#custom", NoteInput),
        ]
        self._selected = 0
        self._items[0].focus()

    def action_focus_up(self) -> None:
        # Move focus to the previous widget in the menu.
        self._selected = (self._selected - 1) % len(self._items)
        self._items[self._selected].focus()

    def action_focus_down(self) -> None:
        # Move focus to the next widget in the menu.
        self._selected = (self._selected + 1) % len(self._items)
        self._items[self._selected].focus()

    def action_close_menu(self) -> None:
        # Close the timer menu via the Escape key.
        self.app.action_toggle_menu()

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        # The button IDs are formatted as ``t<seconds>`` so strip the leading
        # character and convert the rest to an integer. ``SetTime`` will be sent
        # back to the parent application.
        seconds = int(event.button.id[1:])
        self.post_message(self.SetTime(seconds))

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        # Attempt to parse the user input. ``parse_time_spec`` returns ``None``
        # if it can't interpret the value. In that case we ring the terminal
        # bell to provide feedback.
        seconds = parse_time_spec(event.value)
        if seconds is not None:
            self.post_message(self.SetTime(seconds))
        else:
            self.app.bell()


class NoteApp(App[None]):
    # Main application class.

    CSS_PATH = "style.css"

    BINDINGS = [
        ("ctrl+t", "toggle_menu", "Timer Menu"),
        ("ctrl+r", "reset_timer", "Reset/Stop Timer"),
        ("ctrl+s", "save_notes", "Save Notes"),
        ("ctrl+g", "toggle_hemmingway", "Hemmingway Mode"),
        Binding("ctrl+h", "noop", "", show=False, priority=True),
        Binding("ctrl+k", "noop", "", show=False, priority=True),
        Binding("ctrl+m", "noop", "", show=False, priority=True),
        ("escape", "close_menu", "Close Menu"),
        ("ctrl+pageup", "prev_tab", "Previous Tab"),
        ("ctrl+pagedown", "next_tab", "Next Tab"),
    ]

    countdown = reactive(CountdownState())
    menu_visible = reactive(False)
    unsaved = reactive(False)
    hemingway = reactive(False)

    def __init__(self) -> None:
        super().__init__()
        # Track unsaved state for each tab individually
        self.unsaved_map: dict[str, bool] = {}

    def compose(self) -> ComposeResult:
        # Create child widgets.
        self.timer_display = TimerDisplay(id="timer_display")
        yield self.timer_display
        with Container(id="notes_container"):
            with TabbedContent(initial="tab1", id="tabs"):
                yield TabPane("Note 1", NoteTextArea(id="notes_tab1", classes="notes"), id="tab1")
                yield TabPane("Note 2", NoteTextArea(id="notes_tab2", classes="notes"), id="tab2")
        self.menu = TimerMenu(id="timer_menu")
        self.menu.visible = False
        yield self.menu
        self.status = Static(id="status_display")
        yield self.status

    def on_mount(self) -> None:
        # Load notes for all tabs and focus the active one.
        self.tabs = self.query_one("#tabs", TabbedContent)
        # Load each note file into its tabbed text area
        for tab_id, path in NOTE_FILES.items():
            textarea = self.tabs.get_pane(tab_id).query_one(NoteTextArea)
            try:
                with path.open("r", encoding="utf-8") as f:
                    textarea.text = f.read()
            except FileNotFoundError:
                pass
            self.unsaved_map[tab_id] = False
        # Focus the text area in the initial tab
        active = self.tabs.active or "tab1"
        self.tabs.get_pane(active).query_one(NoteTextArea).focus()
        self.status.update("Saved")
        self.title = APP_TITLE

    def watch_countdown(self, countdown: CountdownState) -> None:
        # Update the timer display whenever the countdown changes.
        self.timer_display.update_time(countdown.remaining)
        self.timer_display.display = (
            self.menu_visible or countdown.remaining > 0
        )

    def watch_unsaved(self, unsaved: bool) -> None:
        # Update the status bar whenever the save state changes.
        if unsaved:
            self.status.update("Unsaved changes")
            self.status.add_class("modified")
            # Add an asterisk to the window title to indicate unsaved changes.
            self.title = APP_TITLE + "*"
        else:
            self.status.update("Saved")
            self.status.remove_class("modified")
            self.title = APP_TITLE

    def on_key(self, event: events.Key) -> None:
        # Handle global key behaviour and Hemingway restrictions.
        if event.key in {"ctrl+h", "ctrl+k", "ctrl+m"}:
            # Explicitly swallow these shortcuts so Textual's defaults don't run
            event.stop()
            return
        if self.hemingway and event.key in {"backspace", "delete", "left"}:
            event.prevent_default()
            event.stop()

    def action_toggle_menu(self) -> None:
        # Show or hide the timer menu.
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
            active = self.tabs.active or "tab1"
            self.tabs.get_pane(active).query_one(NoteTextArea).focus()

    def action_close_menu(self) -> None:
        # Close the timer menu if it is currently visible.
        if self.menu_visible:
            self.action_toggle_menu()

    def action_reset_timer(self) -> None:
        # Reset or stop the timer depending on how quickly this action is called.
        now = time.time()
        # If the timer is running and we pressed reset less than two seconds ago
        # we interpret that as a request to stop the countdown entirely.
        if (
            self.countdown.remaining > 0
            and now - self.countdown.last_started < 2
        ):
            self.stop_timer()
            return
        if self.countdown.duration:
            self.start_timer(self.countdown.duration)

    def action_save_notes(self) -> None:
        # Save the current notes to disk.
        # TextArea stores the current content in the ``text`` attribute.
        # Using ``text`` ensures compatibility with future versions of
        # Textual and avoids attribute errors.
        active = self.tabs.active or "tab1"
        textarea = self.tabs.get_pane(active).query_one(NoteTextArea)
        text = textarea.text
        path = NOTE_FILES[active]
        with path.open("w", encoding="utf-8") as f:
            f.write(text)
        self.unsaved_map[active] = False
        self.unsaved = False
        self.notify("Notes saved")

    def action_toggle_hemmingway(self) -> None:
        # Toggle Hemingway mode, which disables deletions and backtracking.
        self.hemingway = not self.hemingway
        state = "ON" if self.hemingway else "OFF"
        self.notify(f"Hemmingway mode {state}")

    def action_noop(self) -> None:
        # An action that intentionally does nothing.
        pass

    def action_prev_tab(self) -> None:
        # Activate the previous note tab.
        tabs = list(NOTE_FILES.keys())
        active = self.tabs.active or tabs[0]
        index = tabs.index(active)
        new_active = tabs[(index - 1) % len(tabs)]
        self.tabs.active = new_active

    def action_next_tab(self) -> None:
        # Activate the next note tab.
        tabs = list(NOTE_FILES.keys())
        active = self.tabs.active or tabs[0]
        index = tabs.index(active)
        new_active = tabs[(index + 1) % len(tabs)]
        self.tabs.active = new_active

    def start_timer(self, seconds: int) -> None:
        # Begin counting down from the given number of seconds.
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
        # Remove any previous blink class in case the timer is restarted
        self.timer_display.remove_class("blink")

    def stop_timer(self) -> None:
        # Stop the timer and hide the display if the menu isn't open.
        if hasattr(self, "_tick_handle"):
            self._tick_handle.stop()
        self.countdown.remaining = 0
        self.timer_display.update_time(0)
        self.timer_display.display = self.menu_visible
        self.timer_display.remove_class("blink")
        self.notify("Timer stopped")

    def tick(self) -> None:
        # Called every second to update the countdown.
        # Reduce the remaining time and update the display. When the countdown
        # reaches zero a blink effect is applied and the timer is stopped.
        if self.countdown.remaining > 0:
            self.countdown.remaining -= 1
            self.timer_display.update_time(self.countdown.remaining)
            if self.countdown.remaining == 0:
                self.timer_display.add_class("blink")
                self.notify("Time's up!")
        else:
            # Once the countdown reaches zero keep showing the timer only if
            # the menu is visible and stop further updates.
            self.timer_display.display = self.menu_visible
            if hasattr(self, "_tick_handle"):
                self._tick_handle.stop()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:  # type: ignore[override]
        # Mark the current tab as modified when its content changes.
        active = self.tabs.active or "tab1"
        self.unsaved_map[active] = True
        self.unsaved = True

    def on_timer_menu_set_time(self, message: TimerMenu.SetTime) -> None:
        # Handle the duration chosen in the timer menu.
        #
        # Starting the timer here ensures the countdown begins immediately after
        # the user selects a preset or enters a custom time.  If the menu is
        # currently visible it is hidden again so focus returns to the notes.

        self.start_timer(message.seconds)
        if self.menu_visible:
            self.action_toggle_menu()

    def on_tabbed_content_tab_activated(self, message: TabbedContent.TabActivated) -> None:
        # Update status when switching tabs.
        active = message.pane.id
        self.unsaved = self.unsaved_map.get(active, False)
        message.pane.query_one(NoteTextArea).focus()


if __name__ == "__main__":
    app = NoteApp()
    app.run()
