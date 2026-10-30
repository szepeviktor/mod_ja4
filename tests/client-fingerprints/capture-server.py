"""Native-client loopback HTTPS fixture; save the initial ClientHello."""
from pathlib import Path
import socket
import ssl
import sys

directory = Path(sys.argv[1])
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(directory / 'server.pem', directory / 'server-key.pem')
context.set_alpn_protocols(['http/1.1'])


def capture(connection, direction, version, content_type, message_type, data):
    if direction == 'read' and content_type == 22 and message_type == 1:
        path = directory / 'clienthello.bin'
        if not path.exists():
            path.write_bytes(data)


# CPython diagnostic callback returns complete handshake messages, including
# the four-byte header expected by ja4_compute; TLS records may be fragmented.
context._msg_callback = capture
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 8443))
    listener.listen()
    listener.settimeout(60)
    (directory / 'ready').write_text('ready')
    connection, _ = listener.accept()
    with context.wrap_socket(connection, server_side=True) as tls:
        tls.settimeout(30)
        request = b''
        while b'\r\n\r\n' not in request:
            data = tls.recv(8192)
            if not data or len(request) > 65536:
                raise RuntimeError('Incomplete or oversized HTTP request')
            request += data
        (directory / 'request.txt').write_bytes(request)
        tls.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Length: 3\r\nConnection: close\r\n\r\nok\n')
