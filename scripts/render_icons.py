"""Rasterize the approved SVG without redesigning its geometry or colours."""
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
    svg=(ROOT/'icon.svg').read_text()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH') or shutil.which('chromium'),args=['--no-sandbox'])
        try:
            for size,maskable in [(192,False),(512,False),(512,True)]:
                page=browser.new_page(viewport={'width':size,'height':size},device_scale_factor=1)
                sized=svg.replace('<svg ',f'<svg width="{size}" height="{size}" ')
                background='#182b4b' if maskable else 'transparent'
                page.set_content(f'<html><body style="margin:0;background:{background}">{sized}</body></html>')
                name='icon-maskable-512.png' if maskable else f'icon-{size}.png'
                page.screenshot(path=str(ROOT/'icons'/name),omit_background=not maskable)
                page.close()
        finally:browser.close()

if __name__=='__main__':main()
