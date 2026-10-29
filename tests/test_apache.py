"""Run an isolated, unprivileged Apache; never touches system configuration.

Requires make, apxs, openssl, Apache modules, and Python h2 for HTTP/2 tests.
"""
import importlib.util
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import time
import unittest

from test_ja4 import ParserHarness, ROOT


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class TLSClient:
    def __init__(self, context, port, session=None, hostname='localhost'):
        self.socket = socket.create_connection(('127.0.0.1', port), timeout=5)
        self.incoming, self.outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.tls = context.wrap_bio(self.incoming, self.outgoing,
                                   server_hostname=hostname, session=session)
        self.wire = bytearray()
        while True:
            try:
                self.tls.do_handshake()
                self.flush()
                break
            except ssl.SSLWantReadError:
                self.flush()
                self.receive()

    def flush(self):
        data = self.outgoing.read()
        self.wire.extend(data)
        self.socket.sendall(data)

    def receive(self):
        data = self.socket.recv(65536)
        if not data:
            raise EOFError('Apache closed the connection')
        self.incoming.write(data)

    def write(self, data):
        self.tls.write(data)
        self.flush()

    def read(self):
        while True:
            try:
                data = self.tls.read(65536)
                self.flush()
                return data
            except ssl.SSLWantReadError:
                self.flush()
                self.receive()

    def client_hello(self):
        wire = bytes(self.wire)
        handshake = b''
        while len(wire) >= 5:
            n = int.from_bytes(wire[3:5], 'big')
            if wire[0] == 22:
                handshake += wire[5:5+n]
                if len(handshake) >= 4:
                    size = 4 + int.from_bytes(handshake[1:4], 'big')
                    if len(handshake) >= size:
                        return handshake[:size]
            wire = wire[5+n:]
        raise AssertionError('No complete ClientHello sent')

    def request(self, host='localhost'):
        self.write(f'GET / HTTP/1.1\r\nHost: {host}\r\nConnection: keep-alive\r\n\r\n'.encode())
        response = b''
        while b'\r\n\r\n' not in response:
            response += self.read()
        head, body = response.split(b'\r\n\r\n', 1)
        lines = head.decode().split('\r\n')
        headers = dict(line.lower().split(': ', 1) for line in lines[1:])
        while len(body) < int(headers['content-length']):
            body += self.read()
        return lines[0], headers, body

    def close(self):
        self.socket.close()


class ApacheTests(ParserHarness):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.serverdir = tempfile.TemporaryDirectory(prefix='mod-ja4-apache-')
        cls.directory = Path(cls.serverdir.name)
        cls.port, cls.plain_port = free_port(), free_port()
        modules = subprocess.check_output(['apxs', '-q', 'LIBEXECDIR'], text=True).strip()
        cls.modules = Path(modules)
        (cls.directory / 'index.html').write_text('ok\n')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(cls.directory / 'key.pem'), '-out',
                        str(cls.directory / 'cert.pem'), '-days', '1', '-subj', '/CN=localhost'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        loads = ['mpm_event', 'authz_core', 'authz_host', 'ssl', 'socache_shmcb',
                 'headers', 'dir', 'mime']
        cls.have_h2 = (cls.modules / 'mod_http2.so').exists() and importlib.util.find_spec('h2')
        if cls.have_h2:
            loads.append('http2')
        config = f'''
ServerRoot "{cls.directory}"
DefaultRuntimeDir "{cls.directory}"
PidFile "{cls.directory}/httpd.pid"
ServerName localhost
Listen 127.0.0.1:{cls.port}
Listen 127.0.0.1:{cls.plain_port}
'''
        for name in loads:
            config += f'LoadModule {name}_module "{cls.modules}/mod_{name}.so"\n'
        config += f'''
LoadModule ja4_module "{ROOT}/.libs/mod_ja4.so"
ErrorLog "{cls.directory}/error.log"
LogLevel warn
TypesConfig /etc/mime.types
DocumentRoot "{cls.directory}"
DirectoryIndex index.html
<Directory "{cls.directory}">
    Require all granted
</Directory>
Header always set X-JA4 "%{{JA4}}e"
Header always set X-JA4-Raw "%{{JA4_RAW}}e"
Header always set X-JA4-Note "expr=%{{note:ja4}}"
<VirtualHost 127.0.0.1:{cls.port}>
    ServerName localhost
    SSLEngine on
    SSLCertificateFile "{cls.directory}/cert.pem"
    SSLCertificateKeyFile "{cls.directory}/key.pem"
    SSLProtocol -all +TLSv1.2 +TLSv1.3
    SSLOpenSSLConfCmd Curves P-256
    Protocols h2 http/1.1
</VirtualHost>
<VirtualHost 127.0.0.1:{cls.port}>
    ServerName second.local
    SSLEngine on
    SSLCertificateFile "{cls.directory}/cert.pem"
    SSLCertificateKeyFile "{cls.directory}/key.pem"
    Header always set X-Vhost second
</VirtualHost>
<VirtualHost 127.0.0.1:{cls.port}>
    ServerName hrr.local
    SSLEngine on
    SSLCertificateFile "{cls.directory}/cert.pem"
    SSLCertificateKeyFile "{cls.directory}/key.pem"
    SSLOpenSSLConfCmd Curves P-256
</VirtualHost>
'''
        cls.config = cls.directory / 'httpd.conf'
        cls.config.write_text(config)
        cls.process = subprocess.Popen(['/usr/sbin/apache2', '-f', str(cls.config), '-DFOREGROUND'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            if cls.process.poll() is not None:
                raise RuntimeError(cls.process.stderr.read().decode())
            try:
                with socket.create_connection(('127.0.0.1', cls.port), timeout=.1):
                    break
            except OSError:
                time.sleep(.05)
        else:
            raise RuntimeError('Apache failed to listen')

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        cls.process.wait(timeout=10)
        stderr = cls.process.stderr.read().decode()
        cls.process.stderr.close()
        log = (cls.directory / 'error.log').read_text()
        cls.serverdir.cleanup()
        super().tearDownClass()
        if cls.process.returncode != 0:
            raise AssertionError(stderr + log)

    def context(self, version=None, alpn=('http/1.1',)):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_alpn_protocols(list(alpn))
        if version:
            ctx.minimum_version = ctx.maximum_version = version
        return ctx

    def test_https_and_keepalive(self):
        for version in [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3]:
            with self.subTest(version=version):
                client = TLSClient(self.context(version), self.port)
                try:
                    expected = self.compute(client.client_hello())
                    for _ in range(2):
                        status, headers, body = client.request()
                        self.assertIn('200', status)
                        self.assertEqual(body, b'ok\n')
                        self.assertEqual(headers['x-ja4'], expected[0])
                        self.assertEqual(headers['x-ja4-raw'], expected[1])
                        self.assertEqual(headers['x-ja4-note'], expected[0])
                finally:
                    client.close()

    def test_sni_and_no_sni(self):
        for hostname, flag in [('second.local', 'd'), (None, 'i')]:
            client = TLSClient(self.context(), self.port, hostname=hostname)
            try:
                _, headers, _ = client.request(host=hostname or 'localhost')
                self.assertEqual(headers['x-ja4'][3], flag)
                if hostname:
                    self.assertEqual(headers['x-vhost'], 'second')
            finally:
                client.close()

    def test_session_resumption(self):
        context = self.context(ssl.TLSVersion.TLSv1_2)
        client = TLSClient(context, self.port)
        try:
            client.request()
            session = client.tls.session
        finally:
            client.close()
        client = TLSClient(context, self.port, session=session)
        try:
            self.assertTrue(client.tls.session_reused)
            _, headers, _ = client.request()
            self.assertEqual(headers['x-ja4'], self.compute(client.client_hello())[0])
        finally:
            client.close()

    def test_plain_http_has_no_fingerprint(self):
        with socket.create_connection(('127.0.0.1', self.plain_port), timeout=5) as s:
            s.sendall(b'GET / HTTP/1.0\r\nHost: localhost\r\n\r\n')
            response = s.recv(65536)
        self.assertIn(b'X-JA4: (null)', response)

    def test_hello_retry_request_keeps_initial_fingerprint(self):
        client = TLSClient(self.context(ssl.TLSVersion.TLSv1_3), self.port, hostname='hrr.local')
        try:
            wire = bytes(client.wire)
            hellos = []
            while len(wire) >= 5:
                n = int.from_bytes(wire[3:5], 'big')
                if wire[0] == 22 and wire[5] == 1:
                    hellos.append(wire[5:5+n])
                wire = wire[5+n:]
            self.assertEqual(len(hellos), 2, 'Server must trigger HelloRetryRequest')
            _, headers, _ = client.request(host='hrr.local')
            self.assertEqual(headers['x-ja4'], self.compute(hellos[0])[0])
            self.assertEqual(headers['x-ja4-raw'], self.compute(hellos[0])[1])
        finally:
            client.close()

    def test_http2_multiple_streams(self):
        if not self.have_h2:
            self.skipTest('mod_http2 and Python h2 required')
        from h2.connection import H2Connection
        from h2.events import ResponseReceived, StreamEnded
        client = TLSClient(self.context(alpn=['h2', 'http/1.1']), self.port)
        try:
            self.assertEqual(client.tls.selected_alpn_protocol(), 'h2')
            expected = self.compute(client.client_hello())
            h2 = H2Connection()
            h2.initiate_connection()
            for stream in [1, 3]:
                h2.send_headers(stream, [(':method', 'GET'), (':scheme', 'https'),
                                        (':authority', 'localhost'), (':path', '/')], end_stream=True)
            client.write(h2.data_to_send())
            ended, received = set(), set()
            while len(ended) < 2:
                for event in h2.receive_data(client.read()):
                    if isinstance(event, ResponseReceived):
                        headers = dict(event.headers)
                        self.assertEqual(headers[b':status'], b'200')
                        self.assertEqual(headers[b'x-ja4'].decode(), expected[0])
                        self.assertEqual(headers[b'x-ja4-raw'].decode(), expected[1])
                        received.add(event.stream_id)
                    elif isinstance(event, StreamEnded):
                        ended.add(event.stream_id)
                pending = h2.data_to_send()
                if pending:
                    client.write(pending)
            self.assertEqual(received, {1, 3})
        finally:
            client.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
