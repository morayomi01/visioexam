"""
Theme definitions for VisioExam UI.
Provides colour + font tokens for each contrast theme.
All foreground/background pairs meet WCAG 2.1 Level AA (≥ 4.5:1 contrast ratio).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str           # main background
    fg: str           # primary text
    accent: str       # focused element highlight
    accent_fg: str    # text on accent
    surface: str      # card / panel background
    border: str       # border / separator colour
    error: str        # error / alert colour
    muted: str        # secondary / muted text
    font_family: str  = "Arial"


THEMES: dict[str, Theme] = {
    "light": Theme(
        name="Light",
        bg="#FFFFFF",
        fg="#1A1A1A",
        accent="#1565C0",
        accent_fg="#FFFFFF",
        surface="#F5F5F5",
        border="#CCCCCC",
        error="#C62828",
        muted="#555555",
    ),
    "dark": Theme(
        name="Dark",
        bg="#121212",
        fg="#E8E8E8",
        accent="#90CAF9",
        accent_fg="#000000",
        surface="#1E1E1E",
        border="#444444",
        error="#EF9A9A",
        muted="#AAAAAA",
    ),
    "hcyob": Theme(
        name="High-Contrast Yellow on Black",
        bg="#000000",
        fg="#FFFF00",
        accent="#FFFF00",
        accent_fg="#000000",
        surface="#000000",
        border="#FFFF00",
        error="#FF4444",
        muted="#FFCC00",
    ),
}


def get_theme(name: str) -> Theme:
    """Return a Theme by key. Defaults to 'light' if unknown."""
    return THEMES.get(name, THEMES["light"])
