#!/usr/bin/env python3
"""
TLS Certificate Generator for Raspberry Pi Hotspot (192.168.4.1).
Generates self-signed certificates with IP and DNS Subject Alternative Names (SAN)
so browsers (Chrome Android, Safari iOS) accept secure context on local Wi-Fi.
"""

import sys
import subprocess
from pathlib import Path

CERTS_DIR = Path(__file__).resolve().parent.parent / "certs"
CERTS_DIR.mkdir(parents=True, exist_ok=True)

CERT_FILE = CERTS_DIR / "cert.pem"
KEY_FILE = CERTS_DIR / "key.pem"
OPENSSL_CONF = CERTS_DIR / "openssl.cnf"

CONF_CONTENT = """[req]
distinguished_name = req_distinguished_name
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
C = IN
ST = Robotics
L = Lab
O = Chintu
OU = Autonomous
CN = 192.168.4.1

[v3_req]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
IP.1 = 192.168.4.1
IP.2 = 127.0.0.1
DNS.1 = localhost
DNS.2 = chintu.local
"""

def generate():
    OPENSSL_CONF.write_text(CONF_CONTENT)
    print(f"Generating TLS certificate in {CERTS_DIR}...")
    
    # Try openssl via subprocess
    cmd = [
        "openssl", "req", "-x509", "-nodes", "-days", "3650",
        "-newkey", "rsa:2048",
        "-keyout", str(KEY_FILE),
        "-out", str(CERT_FILE),
        "-config", str(OPENSSL_CONF)
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Success! Certificate created:\n  Cert: {CERT_FILE}\n  Key:  {KEY_FILE}")
        return True
    except FileNotFoundError:
        print("openssl binary not found. Generating via Python cryptography module if installed...")
        try:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            import datetime
            import ipaddress

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME, "192.168.4.1"),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Chintu Robotics")
            ])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1))
                .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
                .add_extension(
                    x509.SubjectAlternativeName([
                        x509.IPAddress(ipaddress.IPv4Address("192.168.4.1")),
                        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                        x509.DNSName("localhost"),
                        x509.DNSName("chintu.local"),
                    ]),
                    critical=False,
                )
                .sign(key, hashes.SHA256())
            )

            KEY_FILE.write_bytes(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
            CERT_FILE.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            print(f"Success! Certificate created via cryptography module:\n  Cert: {CERT_FILE}\n  Key:  {KEY_FILE}")
            return True
        except ImportError:
            print("ERROR: Neither openssl nor python-cryptography is available.")
            print("Please install openssl or run: pip install cryptography")
            return False

if __name__ == "__main__":
    generate()
