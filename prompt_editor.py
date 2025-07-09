from __future__ import annotations

"""Custom text editor built on prompt_toolkit."""

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.clipboard import InMemoryClipboard, ClipboardData

from textual.widget import Widget
from textual import events
from textual.message import Message
from rich.text import Text


class NoteEditor(Widget):
    """A minimal multi-line text editor using *prompt_toolkit* buffers."""

    DEFAULT_CSS = "NoteEditor {border: none;}"

    # Allow the editor to take keyboard focus so it receives key events.
    can_focus = True

    class Changed(Message):
        """Posted when the text content changes."""
        def __init__(self, sender: "NoteEditor") -> None:
            self.sender = sender
            super().__init__()

    def __init__(self, text: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._clipboard = InMemoryClipboard()
        self._buffer = Buffer(document=Document(text, len(text)), multiline=True)
        self.cursor_blink = True


    def _copy(self, event: object) -> None:
        if data := self._buffer.copy_selection():
            # ``copy_selection`` already returns ``ClipboardData``
            # so it can be stored directly on the clipboard.
            self._clipboard.set_data(data)

    def _paste(self, event: object) -> None:
        if data := self._clipboard.get_data():
            self._buffer.paste_clipboard_data(data)

    def _cut(self, event: object) -> None:
        if data := self._buffer.cut_selection():
            self._clipboard.set_data(data)

    def _undo(self, event: object) -> None:
        self._buffer.undo()

    def _redo(self, event: object) -> None:
        self._buffer.redo()

    async def _on_key(self, event: events.Key) -> None:
        """Translate key presses to buffer operations."""
        key = event.key.lower()
        handled = True

        if key == "left":
            self._buffer.cursor_left()
        elif key == "right":
            self._buffer.cursor_right()
        elif key == "up":
            self._buffer.cursor_up()
        elif key == "down":
            self._buffer.cursor_down()
        elif key == "backspace":
            self._buffer.delete_before_cursor(1)
        elif key == "delete":
            self._buffer.delete()
        elif key == "ctrl+c":
            self._copy(None)
        elif key == "ctrl+v":
            self._paste(None)
        elif key == "ctrl+x":
            self._cut(None)
        elif key == "ctrl+z":
            self._undo(None)
        elif key == "ctrl+y":
            self._redo(None)
        elif key in {"enter", "return"}:
            self._buffer.insert_text("\n")
        elif event.character:
            self._buffer.insert_text(event.character)
        else:
            handled = False

        if handled:
            event.stop()
            self.post_message(self.Changed(self))
            self.refresh()


    def get_text(self) -> str:
        """Return the current text in the editor."""
        return self._buffer.text

    def set_text(self, value: str) -> None:
        """Replace the current text with ``value``."""
        self._buffer.document = Document(value, len(value))

    # Provide ``text`` attribute compatibility with the former TextArea widget.
    @property
    def text(self) -> str:  # pragma: no cover - simple getter
        return self.get_text()

    @text.setter
    def text(self, value: str) -> None:  # pragma: no cover - simple setter
        self.set_text(value)

    def render(self) -> Text:
        """Render the buffer with a visible cursor and soft wrapping."""
        width = self.size.width or 80
        doc = self._buffer.document
        text = doc.text
        cursor = doc.cursor_position

        lines: list[str] = []
        current = ""
        col = 0

        for i, ch in enumerate(text):
            if i == cursor:
                current += "▍"
            if ch == "\n":
                lines.append(current)
                current = ""
                col = 0
                continue
            current += ch
            col += 1
            if col >= width:
                lines.append(current)
                current = ""
                col = 0

        if cursor == len(text):
            current += "▍"
        lines.append(current)
        if not lines:
            lines.append("▍")

        return Text("\n".join(lines))
