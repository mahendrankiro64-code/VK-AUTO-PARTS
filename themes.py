"""Preset color themes for VK Auto Parts.

Picking a theme from the Settings page recolors the nav bar, primary
buttons, and the whole Point-of-Sale screen everywhere in the app -- it's
just a stored setting, so it takes effect immediately for every user, on
every page, with no CSS editing or redeploying needed.
"""

THEMES = {
    "vk_blue": {
        "label": "Ocean Blue (Default)",
        "primary": "#0d6efd",
        "primary_dark": "#0b5ed7",
        "accent": "#0dcaf0",
        "navbar": "#12263a",
        "surface": "#f4f6f9",
    },
    "vk_charcoal_gold": {
        "label": "Charcoal & Gold (Premium)",
        "primary": "#c9973a",
        "primary_dark": "#a67a25",
        "accent": "#e6c675",
        "navbar": "#1b1b1d",
        "surface": "#f7f5ef",
    },
    "vk_emerald": {
        "label": "Emerald Green",
        "primary": "#1f9d63",
        "primary_dark": "#177a4c",
        "accent": "#3fe2a8",
        "navbar": "#0e2f22",
        "surface": "#f2f9f5",
    },
    "vk_maroon": {
        "label": "Maroon & Steel",
        "primary": "#9c2b2b",
        "primary_dark": "#7c2020",
        "accent": "#c9a227",
        "navbar": "#241111",
        "surface": "#f8f3f2",
    },
}

DEFAULT_THEME = "vk_blue"


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return ", ".join(str(int(hex_color[i:i + 2], 16)) for i in (0, 2, 4))


def get_theme(key):
    """Always returns a valid theme dict (falls back to the default if the
    stored key is missing or no longer exists), with an added primary_rgb
    string ready to drop into a CSS rgba()/var() expression."""
    theme = dict(THEMES.get(key, THEMES[DEFAULT_THEME]))
    theme["key"] = key if key in THEMES else DEFAULT_THEME
    theme["primary_rgb"] = hex_to_rgb(theme["primary"])
    return theme
