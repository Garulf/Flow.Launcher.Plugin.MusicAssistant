"""Render the plugin's PNG icons from inline SVG.

Run with a Python that has Playwright and Chromium, for example:
    TMPDIR=/tmp /workspace/flow-render/.venv/bin/python scripts/icons.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
COLOR = "#18BCF2"
STROKE = f'fill="none" stroke="{COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
FILL = f'fill="{COLOR}"'
SPEAKER = f'<path {FILL} d="M4 9h4l5-4v14l-5-4H4z"/>'
GLYPHS = {
    "play": f'<path {FILL} d="M8 5v14l11-7z"/>',
    "pause": f'<path {FILL} d="M6 5h4v14H6zM14 5h4v14h-4z"/>',
    "stop": f'<rect {FILL} x="6" y="6" width="12" height="12" rx="1.5"/>',
    "next": f'<path {FILL} d="M5 6l8.5 6L5 18zM15 6h2.5v12H15z"/>',
    "previous": f'<path {FILL} d="M19 6l-8.5 6L19 18zM6.5 6H9v12H6.5z"/>',
    "queue": f'<path {STROKE} d="M4 6h12M4 11h12M4 16h7M17 14v6M14 17h6"/>',
    "volume": SPEAKER + f'<path {STROKE} d="M16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11"/>',
    "mute": SPEAKER + f'<path {STROKE} d="M16.5 9.5l5 5M21.5 9.5l-5 5"/>',
    "speaker": f'<rect {STROKE} x="6" y="2.5" width="12" height="19" rx="2.5"/>'
               f'<circle {STROKE} cx="12" cy="14.5" r="3.5"/><circle {FILL} cx="12" cy="7" r="1.4"/>',
    "group": f'<rect {STROKE} x="2.5" y="5" width="8.5" height="15" rx="2"/>'
             f'<rect {STROKE} x="13" y="5" width="8.5" height="15" rx="2"/>'
             f'<circle {STROKE} cx="6.75" cy="14.5" r="2.3"/><circle {STROKE} cx="17.25" cy="14.5" r="2.3"/>',
    "music": f'<path {STROKE} d="M9 18V6l11-2v12"/><circle {FILL} cx="6.5" cy="18" r="2.8"/>'
             f'<circle {FILL} cx="17.5" cy="16" r="2.8"/>',
    "radio": f'<rect {STROKE} x="3" y="8" width="18" height="12" rx="2"/>'
             f'<path {STROKE} d="M7 8l10-5M6.5 12.5h4M6.5 16h4"/><circle {FILL} cx="16" cy="14" r="2.6"/>',
    "podcast": f'<rect {FILL} x="9" y="2.5" width="6" height="11" rx="3"/>'
               f'<path {STROKE} d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7"/>',
    "audiobook": f'<path {STROKE} d="M5 19.5V5a2 2 0 0 1 2-2h12v15H7a2 2 0 0 0-2 2 2 2 0 0 0 2 2h12"/>'
                 f'<path {FILL} d="M10 7.5v6l5-3z"/>',
    "warning": f'<path {STROKE} d="M12 3.5L2.5 20h19z"/><path {STROKE} d="M12 10v4.5"/>'
               f'<circle {FILL} cx="12" cy="17.3" r="1.1"/>',
    "settings": f'<path {STROKE} d="M4 7h9M19 7h1M4 17h3M13 17h7"/><circle {STROKE} cx="16" cy="7" r="2.5"/>'
                f'<circle {STROKE} cx="10" cy="17" r="2.5"/>',
}
APP_ICON = (
    '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
    '<stop offset="0" stop-color="#18BCF2"/><stop offset="1" stop-color="#0A7CC2"/></linearGradient></defs>'
    '<rect width="24" height="24" rx="5.5" fill="url(#g)"/>'
    '<path fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"'
    ' d="M9.6 16.6V7.4l8-1.6v8.8"/>'
    '<circle fill="#fff" cx="7.5" cy="16.7" r="2.3"/><circle fill="#fff" cx="15.5" cy="14.7" r="2.3"/>'
)


def svg(body: str, size: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="{size}" height="{size}">{body}</svg>'


def render(page, body: str, size: int, out: Path) -> None:
    page.set_viewport_size({"width": size, "height": size})
    page.set_content(f'<html><body style="margin:0;background:transparent">{svg(body, size)}</body></html>')
    page.locator("svg").screenshot(path=str(out), omit_background=True)
    print(f"Wrote {out.relative_to(ROOT)}")


def main() -> None:
    out_dir = ROOT / "data" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        for name, body in GLYPHS.items():
            render(page, body, 128, out_dir / f"{name}.png")
        render(page, APP_ICON, 256, ROOT / "data" / "icon.png")
        browser.close()


if __name__ == "__main__":
    main()
