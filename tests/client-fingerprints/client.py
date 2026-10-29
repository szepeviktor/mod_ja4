import ssl
import sys
import urllib.request

print(f"Python {sys.version.split()[0]}; {ssl.OPENSSL_VERSION}")
# Only the local HTTPS fixture is contacted.
with urllib.request.urlopen(
    'https://ja4-server/python.txt',
    context=ssl.create_default_context(cafile='/fixture/ca.pem'), timeout=15
) as response:
    assert response.status == 200
    assert response.read() == b'ok\n'
