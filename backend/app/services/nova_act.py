"""Nova Act wrapper with mock-data fallback.

Always implement fallback so the app works even when Nova Act is unavailable.
Never pass passwords through act() — use Playwright directly for auth flows.
"""
import logging
import os

logger = logging.getLogger(__name__)

NOVA_ACT_AVAILABLE = False
try:
    from nova_act import NovaAct  # type: ignore
    NOVA_ACT_AVAILABLE = True
except ImportError:
    logger.warning("nova-act not installed — browser automation will use mock fallback")
