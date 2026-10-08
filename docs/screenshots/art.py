"""Render abstract cover art for the README mockups (no real album art is used).

Run with a Python that has Playwright and Chromium, for example:
    TMPDIR=/tmp /workspace/flow-render/.venv/bin/python docs/screenshots/art.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "art"
COVERS = [
    ("#f2b134", "#e2552d", "#2b1a3f"),
    ("#1fb8c9", "#3a4fd6", "#0f1630"),
    ("#ef6fa8", "#7a3ce0", "#1d1030"),
    ("#9ad94a", "#18a77b", "#0e2a22"),
    ("#f4e6c1", "#c9a46b", "#3a2a16"),
    ("#5b6cff", "#18bcf2", "#0b1a2e"),
]


def cover(light: str, mid: str, dark: str, index: int) -> str:
    x, y = 30 + index * 9, 70 - index * 7
    return (
        f'<div style="width:256px;height:256px;position:relative;overflow:hidden;'
        f'background:linear-gradient({35 + index * 50}deg,{dark},{mid} 60%,{light})">'
        f'<div style="position:absolute;left:{x}%;top:{y}%;width:150px;height:150px;border-radius:50%;'
        f'transform:translate(-50%,-50%);background:radial-gradient(circle,{light},transparent 70%);opacity:.85"></div>'
        f'<div style="position:absolute;inset:0;background:repeating-linear-gradient(90deg,'
        f'rgba(255,255,255,.05) 0 2px,transparent 2px 14px)"></div></div>'
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 256, "height": 256})
        for index, colors in enumerate(COVERS, start=1):
            page.set_content(f'<body style="margin:0">{cover(*colors, index)}</body>')
            page.locator("body > div").screenshot(path=str(OUT / f"cover-{index}.png"))
            print(f"Wrote cover-{index}.png")
        browser.close()


if __name__ == "__main__":
    main()
