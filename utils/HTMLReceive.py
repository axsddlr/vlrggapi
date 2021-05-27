import asyncio
import platform
from pyppeteer import launch


async def receive(url: str):
    if platform.system() == "Windows":
        browser = await launch(
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
            headless=True,
            args=[
                "--no-sandbox",
                "--disabled-setuid-sandbox",
                "--disable-dev-profile",
            ],
        )
    else:
        browser = await launch(
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
            headless=True,
            executablePath="/usr/bin/chromium-browser",
            args=[
                "--no-sandbox",
                "--disabled-setuid-sandbox",
                "--disable-dev-profile",
            ],
        )
    page = await browser.newPage()
    await page.goto(f"{url}")

    html = await page.evaluate(
        """() => {
    return document.body.innerHTML;
  }"""
    )

    await page.close()
    await browser.close()
    print(platform.system())
    return html


def r(url: str, loop):
    asyncio.set_event_loop(loop)
    task = loop.create_task(receive(url))
    value = loop.run_until_complete(task)
    loop.close()
    return value
