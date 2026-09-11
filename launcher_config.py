"""Render the WSL launcher with paths independent of its install location."""

import re


def render_wsl_launcher(template: str, distro: str, widget: str, data: str) -> str:
    values = {"__WSL_DISTRO__": distro, "__WIDGET_PATH__": widget, "__DATA_PATH__": data}
    # VBScript escapes embedded quotes by doubling them. A single substitution
    # avoids interpreting placeholder-like text inside a user-supplied path.
    return re.sub(
        r"__WSL_DISTRO__|__WIDGET_PATH__|__DATA_PATH__",
        lambda match: values[match.group()].replace('"', '""'),
        template,
    )
