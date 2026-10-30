"""Capture Apple's native URLSession TLS stack on a macOS runner."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

CLIENTS = Path(__file__).resolve().parent
directory = Path('macos-capture').resolve()
directory.mkdir(exist_ok=True)


def run(args, **kwargs):
    return subprocess.run(args, check=True, timeout=120, **kwargs)


with tempfile.TemporaryDirectory() as temporary:
    private = Path(temporary)
    ca_key = private / 'ca.key'
    server_key = directory / 'server-key.pem'
    config = private / 'extensions.cnf'
    config.write_text('[req]\ndistinguished_name=dn\nx509_extensions=ca\nprompt=no\n'
                      '[dn]\nCN=JA4 fixture CA\n[ca]\nbasicConstraints=critical,CA:TRUE\n'
                      'keyUsage=critical,keyCertSign,cRLSign\n'
                      '[server]\nsubjectAltName=DNS:localhost\nbasicConstraints=critical,CA:FALSE\n'
                      'keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n')
    run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
         '-config', str(config), '-keyout', str(ca_key), '-out', str(directory / 'ca.pem')])
    run(['openssl', 'req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=localhost',
         '-keyout', str(server_key), '-out', str(private / 'server.csr')])
    run(['openssl', 'x509', '-req', '-in', str(private / 'server.csr'), '-days', '1',
         '-CA', str(directory / 'ca.pem'), '-CAkey', str(ca_key), '-CAcreateserial',
         '-extfile', str(config), '-extensions', 'server', '-out', str(directory / 'server.pem')])
    run(['openssl', 'x509', '-in', str(directory / 'ca.pem'), '-outform', 'DER',
         '-out', str(directory / 'ca.der')])
    executable = private / 'urlsession-client'
    run(['swiftc', str(CLIENTS / 'client.swift'), '-o', str(executable)])
    server = subprocess.Popen([sys.executable, str(CLIENTS / 'capture-server.py'), str(directory)])
    try:
        for _ in range(100):
            if (directory / 'ready').exists():
                break
            if server.poll() is not None:
                raise RuntimeError('HTTPS fixture exited before listening')
            time.sleep(0.1)
        else:
            raise RuntimeError('HTTPS fixture did not start')
        run([str(executable), str(directory / 'ca.der')])
        if server.wait(timeout=10) != 0:
            raise RuntimeError('HTTPS fixture failed')
        swift = run(['swift', '--version'], capture_output=True, text=True).stdout.strip()
        macos = run(['sw_vers'], capture_output=True, text=True).stdout.strip()
        (directory / 'metadata.json').write_text(json.dumps(dict(
            language='Swift / URLSession', image=os.environ.get('ImageOS', 'macos-15'),
            api='Foundation URLSession / Apple TLS', runtime=f'{swift}; {macos}', success=True), indent=2) + '\n')
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        server_key.unlink(missing_ok=True)
