from __future__ import annotations

"""Custom text editor built on prompt_toolkit."""

from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.document import Document
from prompt_toolkit.layout import Layout
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.clipboard import InMemoryClipboard, ClipboardData

from textual import events
from textual.widgets import TextArea


class NoteEditor(TextArea):
    """A ``TextArea`` with extra clipboard and undo/redo bindings."""

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

    def __init__(self, text: str = "", **kwargs: object) -> None:
        super().__init__(
            text=text,
            soft_wrap=True,
            cursor_blink=True,
            **kwargs,
        )
        # Underlying prompt_toolkit structures for advanced editing features
        self._clipboard = InMemoryClipboard()
        self._buffer = Buffer(document=Document(text, len(text)), multiline=True, enable_history=True)
        self._window = Window(BufferControl(buffer=self._buffer), wrap_lines=True)
        kb = KeyBindings()
        kb.add("c-c")(self._copy)
        kb.add("c-v")(self._paste)
        kb.add("c-x")(self._cut)
        kb.add("c-z")(self._undo)
        kb.add("c-y")(self._redo)
        self._pt_app = Application(layout=Layout(self._window), key_bindings=kb, full_screen=False)

    def _copy(self, event: object) -> None:
        if data := self._buffer.copy_selection():
            self._clipboard.set_data(ClipboardData(data))

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

    def _on_key(self, event: events.Key) -> None:
        if event.key in {"ctrl+h", "ctrl+k", "ctrl+m", "ctrl+w"}:
            event.stop()
            return
        if event.key == "ctrl+delete":
            event.stop()
            self.app.action_prompt_delete()
            return
        super()._on_key(event)

    def get_text(self) -> str:
        return self.text

    def set_text(self, value: str) -> None:
        self.text = value
        self._buffer.document = Document(value, len(value))
