"""Pytest test configuration and environment setup.
Generates safe runtime tokens for test suite execution without hardcoded credentials.
"""

import os
import secrets

# Ensure tests have a safe, dynamically generated token at runtime
if "ROBOT_AUTH_TOKEN" not in os.environ:
    os.environ["ROBOT_AUTH_TOKEN"] = secrets.token_urlsafe(32)
if "ROBOT_ENVIRONMENT" not in os.environ:
    os.environ["ROBOT_ENVIRONMENT"] = "testing"
