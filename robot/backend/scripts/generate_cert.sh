#!/usr/bin/env bash
# Shell script to generate TLS certificates for Raspberry Pi host (192.168.4.1)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/generate_cert.py"
