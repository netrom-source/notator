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
    Input,
    Static,
    TextArea,
    TabbedContent,
    TabPane,
    OptionList,
    Button,
)
from textual.widgets.option_list import Option

# Initial note files stored on disk. ``Path`` works across operating systems
# and makes future modifications easy. These are loaded on startup.
INITIAL_FILES = {
    "tab1": Path("notes1.txt"),
    "tab2": Path("notes2.txt"),
}

# Base title shown in the window. An asterisk is added when notes are modified
# to provide a quick visual cue about unsaved work.
APP_TITLE = "NoteApp"

# File storing the list of open tabs between sessions. This lets the
# application restore the previous state when launched again.
TAB_STATE_FILE = Path("tabs_state.json")

# Lines shown in sequence when attempting to delete a note.
HAIKU_LINES = [
    "Hvad vil du fortrænge?\nHvad hvis det var begyndelse –\nikke en fejlskrift?",
    "Du trykker for slet.\nMen hvem var du, da du skrev?\nEr han stadig her?",
    "Hver linje du skrev\nbar en drøm i forklædning.\nEr du træt af den?",
    "Hvis du nu forlod\ndette fragment af din stemme –\nhvem vil finde den?",
    "Glemsel er let nok,\nmen har du givet mening\ntil det, du vil fjerne?",
    "Skriv ikke forbi.\nSkriv en grav for ordene –\nog gå den i møde.",
    "Den tavse cursor spør’:\nSkal jeg fortsætte alene?\nEller med din hånd?",
    "Et klik, og det går –\nmen før du lader det ske,\nsig hvad det var værd.",
    "Afsked uden ord\ner bare fortrængningens dans.\nGiv det rytme først.",
    "Du skrev det i hast –\nvil du også slette det\nsådan? Eller i haiku?",
    "Måske var det grimt.\nMen var det ikke også dig?\nÉn dag i dit liv.",
    "Dette var engang\net sted du tænkte frit i.\nGår du nu forbi?",
    "Du trykker på slet.\nMen vil du virkelig forlade\ndig selv i mørket?",
    "Lad ikke din frygt\nblive sletterens skygge.\nSkriv med åbne øjne.",
    "Hvis du kan digte,\nså kan du også forlade –\nmed hjertet åbent.",
    "Hvad flygter du fra?\nOrdene, du selv har valgt –\neller det, de ser?",
    "Du skrev dette ned.\nVar det ikke sandt engang?\nHvor blev det af dig?",
    "Hvis du sletter nu,\nhvem er det så, du forsøger\nat tie ihjel?",
    "Der var en grund før –\nen tanke, en følelse.\nHar den fortjent glemsel?",
    "Er du færdig nu?\nEller bare utålmodig\nefter at glemme?",
    "Du bærer en stemme\nind i mørket, uden spor.\nEr du sikker nu?",
    "Nogle ord skal væk.\nMen først må du fortælle\nhvad de gjorde ved dig.",
    "Du har set forbi –\nmen hvad var det, du så her?\nSkriv det i et vers.",
    "Slet kun det, du har\nmodet til at huske på\nnår tavsheden står.",
]


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
        if (
            "ctrl+h" not in b.key
            and "ctrl+k" not in b.key
            and "ctrl+m" not in b.key
            and "ctrl+w" not in b.key
            and "ctrl+delete" not in b.key
        )
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
        if (
            "ctrl+h" not in b.key
            and "ctrl+k" not in b.key
            and "ctrl+m" not in b.key
            and "ctrl+w" not in b.key
        )
    ]

    def _on_key(self, event: events.Key) -> None:
        """Handle key events for the note area.

        This override removes the ``Ctrl+H``, ``Ctrl+K``, ``Ctrl+M`` and ``Ctrl+W``
        shortcuts so they don't trigger Textual's default behaviours. All
        other keys are passed through to ``TextArea`` for normal processing.
        """

        # Check for the control key combinations we want to ignore.
        if event.key in {"ctrl+h", "ctrl+k", "ctrl+m", "ctrl+w"}:
            # Ignore these shortcuts entirely
            event.stop()
            return
        if event.key == "ctrl+delete":
            # Trigger the deletion prompt instead of deleting text
            event.stop()
            self.app.action_prompt_delete()
            return

        # Defer to the base ``TextArea`` implementation for everything else
        # to keep all standard text editing features intact.

        # Defer to Textual's TextArea for all other key handling.
        super()._on_key(event)


class TimerOptionList(OptionList):
    """Option list that hands off focus to the custom input when needed."""

    def action_cursor_down(self) -> None:
        """Move highlight down or jump to the input when at the end."""
        if self.highlighted == len(self.options) - 1:
            # Focus the input widget in the parent menu
            self.parent.query_one(NoteInput).focus()
        else:
            super().action_cursor_down()


class TimerMenu(Vertical):
    """Popup with preset durations and a custom input field.

    The menu appears just below the timer display and is fully keyboard
    navigable. Use the arrow keys to change the highlighted option and press
    ``Enter`` to start the timer. The ``escape`` key closes the menu without
    starting a countdown.
    """

    # Escape closes the menu. Navigation keys are provided by ``OptionList``.
    BINDINGS = [("escape", "close_menu", "Close menu")]

    class SetTime(Message):
        """Message sent when the user selects a duration."""

        def __init__(self, seconds: int) -> None:
            super().__init__()
            self.seconds = seconds

    def compose(self) -> ComposeResult:
        # ``OptionList`` isn't a container, so the options are passed in via
        # its constructor. Arrow key navigation is handled by the widget
        # automatically. ``TimerOptionList`` is used to jump to the input when
        # the user presses the down arrow on the last option.
        yield TimerOptionList(
            Option("30s", id="t30"),
            Option("3m", id="t180"),
            Option("7m", id="t420"),
            Option("11m", id="t660"),
            id="timer_options",
        )
        yield NoteInput(placeholder="Custom (e.g. 90, 2m)", id="custom")

    def on_mount(self) -> None:
        # Start hidden and focus the option list when the menu appears.
        self.display = False
        option_list = self.query_one(TimerOptionList)
        option_list.compact = True
        option_list.focus()

    def show_menu(self) -> None:
        """Fade the menu in and focus the options."""
        self.visible = True
        self.display = True
        self.styles.opacity = 0
        self.styles.animate("opacity", 1.0, duration=0.2)
        self.query_one(TimerOptionList).focus()

    def hide_menu(self) -> None:
        """Fade the menu out and hide it when done."""
        def _hide() -> None:
            self.display = False
            self.visible = False

        self.styles.animate("opacity", 0.0, duration=0.2, on_complete=_hide)

    def action_close_menu(self) -> None:
        # Close the timer menu via Escape.
        self.app.action_toggle_menu()

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        """Handle selection from the preset list."""

        seconds = int(event.option.id[1:])
        self.post_message(self.SetTime(seconds))

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        # Parse custom duration and send ``SetTime`` if valid.
        seconds = parse_time_spec(event.value)
        if seconds is not None:
            self.post_message(self.SetTime(seconds))
            # Clear the input so previous values don't remain
            event.input.value = ""
        else:
            self.app.bell()

    def on_key(self, event: events.Key) -> None:
        """Handle keys within the timer menu."""

        # When the custom input has focus and the user presses the up arrow,
        # move focus back to the preset options so the user isn't trapped in the
        # input field.
        if self.query_one(NoteInput).has_focus and event.key == "up":
            option_list = self.query_one(TimerOptionList)
            option_list.highlighted = len(option_list.options) - 1
            option_list.focus()
            event.stop()


class FileOpenMenu(Vertical):
    """Overlay menu that lists ``.txt`` files to open."""

    BINDINGS = [
        ("escape", "close_menu", "Cancel"),
    ]

    class OpenFile(Message):
        """Message sent with the chosen file path."""

        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def compose(self) -> ComposeResult:
        # ``OptionList`` gives us keyboard navigation automatically.
        self.file_list = OptionList(id="open_files")
        yield self.file_list

    def on_mount(self) -> None:
        # Populate list and focus when shown.
        self.refresh_files()
        self.file_list.focus()

    def refresh_files(self) -> None:
        """Load ``.txt`` files in the current directory into the list."""
        self.file_list.clear_options()
        for path in sorted(Path(".").glob("*.txt")):
            # Show the file name without extension for a cleaner look
            self.file_list.add_option(Option(path.stem, id=str(path)))

    def action_close_menu(self) -> None:
        # Hide the menu without opening a file
        self.app.action_toggle_open_menu()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Send the chosen path back to the main application
        self.post_message(self.OpenFile(event.option.id))


class SaveAsMenu(Vertical):
    """Prompt the user to name the current note file."""

    BINDINGS = [("escape", "close_menu", "Cancel")]

    class SaveAs(Message):
        """Message containing the chosen filename."""

        def __init__(self, path: str) -> None:
            super().__init__()
            self.path = path

    def compose(self) -> ComposeResult:
        yield NoteInput(placeholder="File name", id="save_as_path")

    def on_mount(self) -> None:
        # Focus the input so the user can type immediately
        self.query_one(NoteInput).focus()

    def action_close_menu(self) -> None:
        # Close the menu without saving
        self.app.action_toggle_save_menu()

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        # Send the filename back to the application if not empty
        if event.value:
            self.post_message(self.SaveAs(event.value))
        else:
            self.app.bell()


class NotificationBar(Static):
    """Simple message bar that fades out after a short delay."""

    def on_mount(self) -> None:
        # Begin hidden
        self.display = False
        self.styles.opacity = 0

    def show(self, message: str, duration: float = 2.0) -> None:
        """Display ``message`` briefly at the bottom of the screen."""

        self.update(message)
        self.display = True
        self.styles.opacity = 1.0

        def fade_out() -> None:
            self.styles.animate("opacity", 0.0, duration=0.3, on_complete=self._hide)

        self.set_timer(duration, fade_out)

    def _hide(self) -> None:
        self.display = False
        self.styles.opacity = 0


class HaikuPrompt(Vertical):
    """Modal shown to confirm deletion with a haiku."""

    BINDINGS = [("escape", "cancel", "Cancel")]  # allow closing with Esc

    class Confirm(Message):
        """Sent when the user submits a valid haiku."""

        def __init__(self) -> None:
            super().__init__()

    def __init__(self, lines: list[str], **kwargs) -> None:
        """Store the rotating lines displayed under the heading."""
        super().__init__(**kwargs)
        self.lines = lines
        self.index = 0  # which line to show next
        self.step = 1  # track whether we're on the accept screen or inputs

    def compose(self) -> ComposeResult:
        # Heading with the fixed introduction plus a changing line
        self.message = Static(id="haiku_message")
        yield self.message
        # Three inputs for the 5-7-5 poem. They are only shown after the user
        # accepts the initial warning message.
        self.line1 = NoteInput(placeholder="5 stavelser", id="haiku1")
        self.line2 = NoteInput(placeholder="7 stavelser", id="haiku2")
        self.line3 = NoteInput(placeholder="5 stavelser", id="haiku3")
        yield self.line1
        yield self.line2
        yield self.line3
        # Submit button, initially disabled until the haiku passes validation.
        self.submit = Button(
            "I overflod, beriges man af afsked!",
            id="haiku_submit",
            disabled=True,
        )
        yield self.submit
        # Buttons used on the first step: "Slet alligevel!" and "Annuller".
        with Container(id="haiku_buttons"):
            self.accept = Button("Slet alligevel!", id="haiku_accept")
            yield self.accept
            self.cancel_btn = Button("Annuller", id="haiku_cancel")
            yield self.cancel_btn

    def on_mount(self) -> None:
        self.display = False
        self.visible = False
        self.load_line()

    def load_line(self) -> None:
        """Update the changing line from the rotating list."""
        text = (
            "Denne maskine er skabt for at skrive, ikke slette.\n\n"
            + self.lines[self.index]
        )
        self.message.update(text)
        self.index = (self.index + 1) % len(self.lines)

    def show_prompt(self) -> None:
        """Display the modal."""
        self.load_line()
        self.step = 1
        self.visible = True
        self.display = True
        self.styles.opacity = 1.0
        # Show the message and hide the input fields until accepted
        self.message.display = True
        # Start with only the accept button visible
        self.line1.display = False
        self.line2.display = False
        self.line3.display = False
        self.submit.display = False
        self.accept.display = True
        self.accept.focus()

    def hide_prompt(self) -> None:
        self.visible = False
        self.display = False
        self.step = 1

    def start_inputs(self) -> None:
        """Switch from the accept screen to the input fields."""
        self.step = 2
        self.line1.display = True
        self.line2.display = True
        self.line3.display = True
        self.submit.display = True
        self.accept.display = False
        # Show instruction heading for the haiku input stage
        self.message.update("Skriv et haiku for at slette!")
        self.message.display = True
        self.line1.value = ""
        self.line2.value = ""
        self.line3.value = ""
        self.validate()
        self.line1.focus()

    def validate(self) -> None:
        """Enable the submit button when the input contains 5/7/5 words."""

        def count_words(text: str) -> int:
            # Split on whitespace to count words; ignore extra spaces
            return len(text.strip().split())

        valid = (
            count_words(self.line1.value) == 5
            and count_words(self.line2.value) == 7
            and count_words(self.line3.value) == 5
        )
        self.submit.disabled = not valid

    def on_input_changed(self, event: Input.Changed) -> None:  # type: ignore[override]
        self.validate()

    def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        if not self.submit.disabled:
            self.post_message(self.Confirm())

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        if event.button.id == "haiku_accept":
            self.start_inputs()
        elif event.button.id == "haiku_submit" and not self.submit.disabled:
            self.post_message(self.Confirm())
        elif event.button.id == "haiku_cancel":
            self.hide_prompt()

    def action_cancel(self) -> None:
        self.hide_prompt()

class NoteApp(App[None]):
    # Main application class.

    CSS_PATH = "style.css"

    BINDINGS = [
        ("ctrl+t", "toggle_menu", "Timer Menu"),
        ("ctrl+r", "reset_timer", "Reset/Stop Timer"),
        ("ctrl+s", "save_notes", "Save Notes"),
        ("ctrl+g", "toggle_hemmingway", "Hemmingway Mode"),
        ("ctrl+n", "new_tab", "New Tab"),
        ("ctrl+o", "open_file", "Open File"),
        Binding("ctrl+w", "close_tab", "Close Tab", priority=True),
        ("ctrl+b", "toggle_tab_bar", "Toggle Tabs"),
        Binding("ctrl+h", "noop", "", show=False, priority=True),
        Binding("ctrl+k", "noop", "", show=False, priority=True),
        Binding("ctrl+m", "noop", "", show=False, priority=True),
        ("ctrl+delete", "prompt_delete", "Delete File"),
        ("escape", "close_menu", "Close Menu"),
        ("ctrl+pageup", "prev_tab", "Previous Tab"),
        ("ctrl+pagedown", "next_tab", "Next Tab"),
    ]

    countdown = reactive(CountdownState())
    menu_visible = reactive(False)
    open_menu_visible = reactive(False)
    save_menu_visible = reactive(False)
    haiku_visible = reactive(False)
    unsaved = reactive(False)
    hemingway = reactive(False)
    tab_bar_visible = reactive(True)

    def __init__(self) -> None:
        super().__init__()
        # Track unsaved state for each tab individually
        self.unsaved_map: dict[str, bool] = {}
        # Map tab id to file path (None for new unsaved files)
        self.file_map: dict[str, Path | None] = {}
        # Keep a reference to each NoteTextArea widget by tab id so we can
        # reliably focus them without querying, which may fail before the
        # widgets are fully mounted.
        self.textareas: dict[str, NoteTextArea] = {}
        # Counter for generating unique tab ids
        self.tab_counter = 2
        # Track when Ctrl+S was last pressed to support rename on double press
        self._last_save_time = 0.0

    def compose(self) -> ComposeResult:
        # Create child widgets.
        self.timer_display = TimerDisplay(id="timer_display")
        yield self.timer_display
        # Timer menu sits directly below the display and spans the width of the screen.
        self.menu = TimerMenu(id="timer_menu")
        self.menu.visible = False
        yield self.menu
        # Notes container holds the tabbed content widget. Individual panes
        # are added later in ``on_mount`` when we know which files to load.
        with Container(id="notes_container"):
            yield TabbedContent(id="tabs")
        self.open_menu = FileOpenMenu(id="open_menu")
        self.open_menu.visible = False
        yield self.open_menu
        self.save_menu = SaveAsMenu(id="save_menu")
        self.save_menu.visible = False
        yield self.save_menu
        self.haiku_prompt = HaikuPrompt(HAIKU_LINES, id="haiku_overlay")
        self.haiku_prompt.visible = False
        yield self.haiku_prompt
        self.status = Static(id="status_display")
        yield self.status
        self.notification = NotificationBar(id="notification_bar")
        yield self.notification

    def on_mount(self) -> None:
        """Load tabs from the previous session or the default files."""

        self.tabs = self.query_one("#tabs", TabbedContent)
        data = None
        if TAB_STATE_FILE.exists():
            try:
                import json
                with TAB_STATE_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None

        if data and data.get("tabs"):
            # Recreate tabs as recorded in the state file
            for info in data["tabs"]:
                tab_id = info["id"]
                title = info.get("title", tab_id)
                # Strip the .txt extension from stored titles for display
                if title.endswith(".txt"):
                    title = Path(title).stem
                path_str = info.get("file")
                path = Path(path_str) if path_str else None
                text = ""
                if path and path.exists():
                    try:
                        with path.open("r", encoding="utf-8") as f:
                            text = f.read()
                    except FileNotFoundError:
                        pass
                note_area = NoteTextArea(text=text, classes="notes")
                pane = TabPane(title, note_area, id=tab_id)
                self.tabs.add_pane(pane)
                self.file_map[tab_id] = path
                self.unsaved_map[tab_id] = False
                self.textareas[tab_id] = note_area
            # Determine the highest numerical tab id so new tabs get unique IDs
            self.tab_counter = max(
                int(info["id"][3:]) for info in data["tabs"] if info["id"].startswith("tab")
            )
            active = data.get("active", data["tabs"][0]["id"])
            self.tabs.active = active
        else:
            # No previous state; load default files
            for tab_id, path in INITIAL_FILES.items():
                text = ""
                if path.exists():
                    with path.open("r", encoding="utf-8") as f:
                        text = f.read()
                note_area = NoteTextArea(text=text, classes="notes")
                pane = TabPane(f"Note {tab_id[-1]}", note_area, id=tab_id)
                self.tabs.add_pane(pane)
                self.unsaved_map[tab_id] = False
                self.file_map[tab_id] = path
                self.textareas[tab_id] = note_area
            self.tab_counter = max(
                int(tid[3:]) for tid in INITIAL_FILES.keys() if tid.startswith("tab")
            )
            self.tabs.active = "tab1"

        # Focus the active tab's text area
        active = self.tabs.active
        if active and active in self.textareas:
            # Focus after mount to avoid "NoMatches" errors
            self.call_later(self.textareas[active].focus)
        self.status.update("Saved")
        self.title = APP_TITLE
        from textual.widgets._tabbed_content import ContentTabs
        self.tab_bar = self.tabs.query_one(ContentTabs)
        self.tab_bar.visible = True

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

    def watch_tab_bar_visible(self, visible: bool) -> None:
        # Show or hide the tab bar widget without leaving a blank area.
        self.tab_bar.display = visible
        self.tab_bar.visible = visible

    def watch_open_menu_visible(self, visible: bool) -> None:
        # Display or hide the open-file menu.
        self.open_menu.visible = visible
        self.open_menu.display = visible
        if visible:
            self.open_menu.refresh_files()
            self.open_menu.file_list.focus()

    def watch_save_menu_visible(self, visible: bool) -> None:
        # Display or hide the save-as menu.
        self.save_menu.visible = visible
        self.save_menu.display = visible

    def watch_haiku_visible(self, visible: bool) -> None:
        # Show or hide the haiku deletion prompt.
        self.haiku_prompt.visible = visible
        self.haiku_prompt.display = visible

    def save_tab_state(self) -> None:
        """Write the current open tabs to ``TAB_STATE_FILE``."""

        import json
        data = {
            "active": self.tabs.active,
            "tabs": [
                {
                    "id": tab_id,
                    "title": str(self.tabs.get_pane(tab_id)._title.plain),
                    "file": str(path) if path else None,
                }
                for tab_id, path in self.file_map.items()
            ],
        }
        with TAB_STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump(data, f)

    def on_key(self, event: events.Key) -> None:
        # Handle global key behaviour and Hemingway restrictions.
        if event.key in {"ctrl+h", "ctrl+k", "ctrl+m", "ctrl+w"}:
            # Explicitly swallow these shortcuts so Textual's defaults don't run
            event.stop()
            return
        if self.hemingway and event.key in {"backspace", "delete", "left"}:
            event.prevent_default()
            event.stop()

    def action_toggle_menu(self) -> None:
        # Show or hide the timer menu.
        self.menu_visible = not self.menu_visible
        self.timer_display.display = self.menu_visible or self.countdown.remaining > 0
        if self.menu_visible:
            # Fade the menu in and focus it
            self.menu.show_menu()
        else:
            # Fade the menu out and return focus to the notes
            self.menu.hide_menu()
            active = self.tabs.active or "tab1"
            note_area = self.textareas.get(active)
            if note_area:
                note_area.focus()

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
        """Save the current notes, prompting for a name when needed."""

        now = time.time()
        active = self.tabs.active or "tab1"
        textarea = self.textareas.get(active)
        if textarea is None:
            return
        path = self.file_map.get(active)
        double = now - self._last_save_time < 2
        self._last_save_time = now

        # If the note has no filename or the user double-pressed Ctrl+S,
        # open the Save As menu so a name can be chosen or changed.
        if path is None or double:
            if not self.save_menu_visible:
                self.save_menu_visible = True
                input_widget = self.save_menu.query_one(NoteInput)
                # Show the file name without extension while editing
                input_widget.value = path.stem if path else ""
                input_widget.focus()
            return

        # Write the text to the existing file
        with path.open("w", encoding="utf-8") as f:
            f.write(textarea.text)
        self.unsaved_map[active] = False
        self.unsaved = False
        self.notification.show("Notes saved")

    def action_toggle_hemmingway(self) -> None:
        # Toggle Hemingway mode, which disables deletions and backtracking.
        self.hemingway = not self.hemingway
        state = "ON" if self.hemingway else "OFF"
        self.notification.show(f"Hemmingway mode {state}")

    def action_noop(self) -> None:
        # An action that intentionally does nothing.
        pass

    def action_prompt_delete(self) -> None:
        """Show the haiku confirmation prompt if a file is attached."""
        active = self.tabs.active or "tab1"
        path = self.file_map.get(active)
        if path is None:
            self.notification.show("Ingen fil at slette")
            return
        self.haiku_visible = True
        self.haiku_prompt.show_prompt()

    def action_prev_tab(self) -> None:
        # Activate the previous note tab.
        tabs = list(self.file_map.keys())
        active = self.tabs.active or tabs[0]
        index = tabs.index(active)
        new_active = tabs[(index - 1) % len(tabs)]
        self.tabs.active = new_active

    def action_next_tab(self) -> None:
        # Activate the next note tab.
        tabs = list(self.file_map.keys())
        active = self.tabs.active or tabs[0]
        index = tabs.index(active)
        new_active = tabs[(index + 1) % len(tabs)]
        self.tabs.active = new_active

    def action_new_tab(self) -> None:
        """Create a new empty tab."""
        from datetime import datetime
        self.tab_counter += 1
        tab_id = f"tab{self.tab_counter}"
        # Name new tabs by creation time without seconds but with day and month
        timestamp = datetime.now().strftime("%H%M-%d%m")
        note_area = NoteTextArea(classes="notes")
        pane = TabPane(f"Note {timestamp}", note_area, id=tab_id)
        self.tabs.add_pane(pane)
        self.file_map[tab_id] = None
        self.unsaved_map[tab_id] = False
        self.textareas[tab_id] = note_area
        self.tabs.active = tab_id
        # Focusing the widget instance avoids query errors before it is mounted.
        note_area.focus()
        self.save_tab_state()

    def action_open_file(self) -> None:
        """Prompt for a file path to open in a new tab."""
        if not self.open_menu_visible:
            self.open_menu.refresh_files()
            self.open_menu_visible = True
            self.open_menu.file_list.focus()

    def action_toggle_open_menu(self) -> None:
        """Hide the open-file menu."""
        self.open_menu_visible = False

    def action_toggle_save_menu(self) -> None:
        """Hide the save-as menu."""
        self.save_menu_visible = False

    def on_file_open_menu_open_file(self, message: FileOpenMenu.OpenFile) -> None:
        """Create a new tab from the given file path."""
        path = Path(message.path)
        text = ""
        try:
            with path.open("r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            self.notification.show("File not found", duration=2)
            self.open_menu_visible = False
            return
        self.tab_counter += 1
        tab_id = f"tab{self.tab_counter}"
        # Create the text area separately to focus it after adding the pane.
        note_area = NoteTextArea(text=text, classes="notes")
        # Use the base file name for the tab label
        pane = TabPane(path.stem, note_area, id=tab_id)
        self.tabs.add_pane(pane)
        self.file_map[tab_id] = path
        self.unsaved_map[tab_id] = False
        self.textareas[tab_id] = note_area
        self.tabs.active = tab_id
        note_area.focus()
        self.open_menu_visible = False
        self.save_tab_state()

    def on_save_as_menu_save_as(self, message: SaveAsMenu.SaveAs) -> None:
        """Save the active note to the chosen filename."""
        active = self.tabs.active or "tab1"
        path = Path(message.path)
        # Ensure the extension .txt exists for simplicity
        if path.suffix == "":
            path = path.with_suffix(".txt")
        textarea = self.textareas.get(active)
        if textarea is None:
            return
        with path.open("w", encoding="utf-8") as f:
            f.write(textarea.text)
        self.file_map[active] = path
        self.unsaved_map[active] = False
        self.unsaved = False
        # Update the tab title to match the new filename
        pane = self.tabs.get_pane(active)
        pane._title = pane.render_str(path.stem)
        self.tabs.get_tab(active).label = path.stem
        self.save_menu_visible = False
        self.notification.show(f"Saved as {path.stem}")
        self.save_tab_state()

    def on_haiku_prompt_confirm(self, message: HaikuPrompt.Confirm) -> None:
        """Delete the current file after haiku confirmation."""
        active = self.tabs.active or "tab1"
        path = self.file_map.get(active)
        if path and path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        self.file_map[active] = None
        self.unsaved_map[active] = False
        self.unsaved = False
        self.haiku_visible = False
        self.notification.show("Ordene falder. Tomheden vinder.")

    def action_close_tab(self) -> None:
        """Close the currently active tab if more than one is open."""
        if self.tabs.tab_count <= 1:
            return
        active = self.tabs.active or "tab1"
        panes = list(self.file_map.keys())
        index = panes.index(active)
        self.tabs.remove_pane(active)
        self.unsaved_map.pop(active, None)
        self.file_map.pop(active, None)
        self.textareas.pop(active, None)
        # Choose which tab becomes active after closing
        if panes:
            panes.remove(active)
            new_index = index - 1 if index > 0 else 0
            new_active = panes[new_index]
            self.tabs.active = new_active
            note_area = self.textareas.get(new_active)
            if note_area:
                note_area.focus()
        self.notification.show("Tab closed")
        self.save_tab_state()

    def action_toggle_tab_bar(self) -> None:
        """Toggle visibility of the tab bar."""
        self.tab_bar_visible = not self.tab_bar_visible

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
        self.notification.show("Timer started")
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
        self.notification.show("Timer stopped")

    def tick(self) -> None:
        # Called every second to update the countdown.
        # Reduce the remaining time and update the display. When the countdown
        # reaches zero a blink effect is applied and the timer is stopped.
        if self.countdown.remaining > 0:
            self.countdown.remaining -= 1
            self.timer_display.update_time(self.countdown.remaining)
            if self.countdown.remaining == 0:
                self.timer_display.add_class("blink")
                self.notification.show("Time's up!")
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
        note_area = self.textareas.get(active)
        if note_area:
            note_area.focus()


if __name__ == "__main__":
    app = NoteApp()
    app.run()
