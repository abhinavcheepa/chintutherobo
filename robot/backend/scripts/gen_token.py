#!/usr/bin/env python3
"""Generates a cryptographically secure 256-bit token for Chintu supervisor authentication."""

import secrets
import sys

def generate_token() -> str:
    # 32 bytes urlsafe = 43+ chars (exceeds 32-char minimum entropy gate)
    return secrets.token_urlsafe(32)

if __name__ == "__main__":
    token = generate_token()
    if len(sys.argv) > 1 and sys.argv[1] == "--env":
        print(f"ROBOT_AUTH_TOKEN={token}")
    else:
        print(token)
