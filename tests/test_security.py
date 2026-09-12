"""Regression checks for untrusted text and HTTPS authenticity."""
import asyncio
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import ssl
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import crawl_batch
from insights import summarize


class SecurityTests(unittest.TestCase):
    def test_malformed_brackets_complete_within_budget(self):
        subprocess.run([sys.executable, '-c',
            "from insights import source_units; u=source_units('['*500000+'Content words', 'https://example.com'); assert isinstance(u,list)"],
            cwd=Path(__file__).resolve().parents[1], timeout=8, check=True)
        result = asyncio.run(summarize('Useful content. ' * 40000, 'https://example.com'))
        self.assertIn('500,000', result.warning)

    def test_self_signed_https_is_rejected(self):
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'<html><title>Untrusted</title><p>Untrusted source content</p></html>')
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
            now = datetime.now(timezone.utc)
            cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                    .public_key(key.public_key()).serial_number(x509.random_serial_number())
                    .not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1))
                    .sign(key, hashes.SHA256()))
            (folder/'cert.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            (folder/'key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(folder/'cert.pem', folder/'key.pem')
            server.socket = context.wrap_socket(server.socket, server_side=True)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                pages = asyncio.run(crawl_batch([f'https://127.0.0.1:{server.server_port}'], folder, .5, 5, '', threading.Event(), lambda *_: None, retries=0))
                self.assertFalse(pages[0].success)
                self.assertIn('CERT', pages[0].error.upper())
            finally:
                server.shutdown()
                server.server_close()
