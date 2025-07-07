# Fresh Note App

This project contains a minimal note-taking application written with [Textual](https://textual.textualize.io/). The interface lets you type notes in a `TextArea` while an optional countdown timer can help manage your time.

## Usage

1. Install dependencies with `pip install textual`.
2. Run the app using `python main.py`.
3. Toggle the timer menu with `Ctrl+T`.
4. Use the arrow keys to move between the timer options and press `Enter` to
   select a preset or submit a custom value (e.g. `90` or `2m`). The menu
   closes automatically when a time is chosen.
   Press `Escape` to dismiss the menu without starting a timer. The menu occupies less screen height for a cleaner look.
5. Press `Ctrl+R` to restart the timer. Press it again within two seconds to stop the countdown.
6. Save your notes with `Ctrl+S`. The status bar at the bottom shows whether your notes are saved or have unsaved changes.
   The window title also displays an asterisk when unsaved changes are present.
7. Toggle **Hemmingway mode** with `Ctrl+Y` to disable deleting and moving the cursor backwards.

Default shortcuts for `Ctrl+H`, `Ctrl+K` and `Ctrl+M` are disabled with high priority so they no longer trigger Textual's built-in commands.

All styling can be changed in `style.css`. The default sheet now uses muted
earth tones with a dusty green timer bar. Toast notifications feature a subtle
border and you can tweak the palette to suit your taste.
