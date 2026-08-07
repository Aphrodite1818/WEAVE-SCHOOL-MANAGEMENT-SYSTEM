"""Optional Sentry error monitoring for API and worker processes"""



from __future__ import annotations

import logging 
import os
from collections.abc import Mapping
from typing import Any 

import sentry_sdk
from pydantic import SecretStr
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration


from ap.config.logging import get_logger
from app.config.settings import settings



logger = get_logger(__name__)

