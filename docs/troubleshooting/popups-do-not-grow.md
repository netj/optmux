# Popups don't grow when the terminal gets wider

## Problem

OPTMUX eXtract, Find and the tips screen open as tmux popups (`display-popup -w 100% -h 60%`). Make the terminal narrower while one is open and it follows; make it wider again and it stays as wide as when it opened.

## Cause

tmux turns the percentage into a fixed size when the popup opens. A resize only shrinks a popup that no longer fits, and never grows it back. fzf inside simply fills what it is given, so there is nothing OPTMUX can do from within the popup.

## Workaround

Close the popup and open it again after resizing.
