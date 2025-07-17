# Notator TTY-Version Rewritten Fully with prompt_toolkit
# Core structure only using prompt_toolkit

from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
import os


class NotatorApp:
    def __init__(self):
        self.filename = "untitled.txt"
        self.clipboard = ""
        self.text_area = TextArea(text=self.load_from_file(self.filename), scrollbar=True, line_numbers=True)
        self.layout = Layout(HSplit([Frame(self.text_area, title="Notator TTY")]))
        self.kb = self.setup_keybindings()
        self.application = Application(layout=self.layout, key_bindings=self.kb, full_screen=True)

    def setup_keybindings(self):
        kb = KeyBindings()

        @kb.add("c-s")
        def _(event):
            self.save_to_file()

        @kb.add("c-c")
        def _(event):
            self.copy_selection()

        @kb.add("c-v")
        def _(event):
            self.paste_clipboard()

        @kb.add("c-q")
        def _(event):
            event.app.exit()

        return kb

    def copy_selection(self):
        buffer = self.text_area.buffer
        document = buffer.document
        if document.selection:
            self.clipboard = document.selection.text

    def paste_clipboard(self):
        self.text_area.buffer.insert_text(self.clipboard)

    def save_to_file(self):
        with open(self.filename, 'w') as f:
            f.write(self.text_area.text)

    def load_from_file(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return f.read()
        return ""

    def run(self):
        self.application.run()


if __name__ == "__main__":
    app = NotatorApp()
    app.run()
