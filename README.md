
This project contains a minimal note-taking application written with [Textual](https://textual.textualize.io/). Notes are edited using Textual's built-in `TextArea` widget with soft wrapping and clipboard shortcuts. An optional countdown timer can help manage your time.
All interface labels and notifications are in Danish for localization.

## Usage

1. Install dependencies with `pip install textual`.
2. From the project folder run the app using `python main.py`.
3. Create additional tabs with `Ctrl+N` or open an existing file with `Ctrl+O`.
   Close the active tab with `Ctrl+W` and hide/show the tab bar with `Ctrl+B`.
   Switch between tabs by clicking the labels or pressing `Ctrl+PageUp`/`Ctrl+PageDown`.
4. Toggle the timer menu with `Ctrl+T`.
5. Use the arrow keys (or left/right) to move between the timer options and
   press `Enter` to select a preset or submit a custom value (e.g. `90` or `2m`).
   The menu closes automatically when a time is chosen. Press `Escape` to
   dismiss the menu without starting a timer.
6. Press `Ctrl+R` to restart the timer. Press it again within two seconds to stop the countdown.
7. Save your notes with `Ctrl+S`. If the note has never been saved (or you press
   `Ctrl+S` twice quickly) you will be prompted for a file name. The status bar
   indicates whether the current tab has unsaved changes and the window title
   shows an asterisk when modifications are pending.
8. Toggle **Hemmingway mode** med `Ctrl+G` for at forhindre sletning og tilbagel\u00f8b.
9. Toggle **fokus på s\u00e6tning** med `Ctrl+J` for kun at vise den aktive s\u00e6tning i klar hvid farve, mens tidligere s\u00e6tninger bliver m\u00f8rkegr\u00e5.
10. Press `Ctrl+Delete` to delete the active note. A warning message is shown
  first. After accepting it, compose a short haiku (3–5 words, 4–7 words,
  3–5 words) before the file is removed. The input fields are labelled
  "5 stavelser", "7 stavelser" and "5 stavelser" to hint at the rhythm.
  Use the arrow keys to move between the lines and down to the confirmation
  button.
11. In the first step you can switch between "Slet alligevel!" and "Annuller"
    with the arrow keys.
12. Open and save prompts appear as slim bars above the status line. When opening files, available documents are listed without the `.txt` extension for a cleaner look.
13. Tabs reopen automatically from the previous session so your work continues where you left off.
14. Press `Ctrl+L` to view a random quote from `data/quotes.txt`. Quotes appear once each until all have been shown. When the list is exhausted you can choose to start over.
    Opening the quote viewer repeatedly shows a gentle reminder if used too often.

Each tab stores its text in a separate file (`data/notes1.txt` and `data/notes2.txt`). Switching tabs updates the save indicator accordingly.

Default shortcuts for `Ctrl+H`, `Ctrl+K` and `Ctrl+M` are disabled with high priority so they no longer trigger Textual's built-in commands.

All styling can be changed in `style.css`. The default sheet now uses muted
earth tones with a dusty green timer bar. Notification messages slide up from the
bottom and fade away after a short delay. Adjust the palette and animations inthe CSS as you see fit.
