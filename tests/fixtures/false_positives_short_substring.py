"""Functions that should NOT trigger email detection.

These use objects with 'session' in the name (which contains 'ses')
but are not related to AWS SES or email in any way.
"""


async def handle_cdp_event(cdp_session):
    """Chrome DevTools Protocol — not email."""
    await cdp_session.send("Page.navigate", {"url": "https://example.com"})


async def manage_browser(browser_session):
    """Browser session management — not email."""
    await browser_session.close()


async def cleanup(persistent_sessions_manager):
    """Session cleanup — not email."""
    await persistent_sessions_manager.clear()


def robot_handler(robot):
    """Robot handler — not a telegram bot."""
    robot.send("status_update")
