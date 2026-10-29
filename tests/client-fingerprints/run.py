"""Capture HTTPS client fingerprints on an isolated Docker bridge network."""
import html
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
CLIENTS = Path(__file__).resolve().parent
RESULTS = ROOT / 'fingerprint-results'
NETWORK = 'mod-ja4-fingerprint-lab'
SERVER = 'mod-ja4-fingerprint-server'
SERVER_IMAGE = 'mod-ja4-fingerprint-server:local'

# Runtime/base versions are explicit. Digests and actual TLS versions are saved.
# These measure the chosen HTTPS API, not an intrinsic property of a language.
CASES = [
    ('c', 'C', 'gcc:14-bookworm', 'OpenSSL BIO',
     'apt-get update >&2; apt-get install -y --no-install-recommends libssl-dev >&2; '
     'gcc -Wall -Wextra -Werror /clients/client.c -lssl -lcrypto -o /tmp/client; /tmp/client c'),
    ('cpp', 'C++', 'gcc:14-bookworm', 'OpenSSL BIO',
     'apt-get update >&2; apt-get install -y --no-install-recommends libssl-dev >&2; '
     'g++ -Wall -Wextra -Werror /clients/client.c -lssl -lcrypto -o /tmp/client; /tmp/client cpp'),
    ('python', 'Python', 'python:3.13-bookworm', 'urllib.request / ssl',
     'python3 /clients/client.py'),
    ('php', 'PHP', 'php:8.4-cli-bookworm', 'HTTPS stream wrapper',
     'php /clients/client.php'),
    ('ruby', 'Ruby', 'ruby:3.4-bookworm', 'Net::HTTP / OpenSSL',
     'ruby /clients/client.rb'),
    ('node', 'Node.js', 'node:22-bookworm', 'https',
     'node /clients/client.js'),
    ('go', 'Go', 'golang:1-bookworm', 'net/http / crypto/tls',
     'go run /clients/client.go'),
    ('rust', 'Rust', 'rust:1-bookworm', 'reqwest / rustls (default TLS)',
     'cp -R /clients/rust /tmp/rust; cd /tmp/rust; rustc --version; cargo run --quiet; '
     'cp Cargo.lock /results/rust-Cargo.lock'),
]


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def cell(value):
    return html.escape(str(value)).replace('|', '&#124;').replace('\n', '<br>')


def report(rows, error=None):
    log = RESULTS / 'requests.tsv'
    captured = {}
    if log.exists():
        for line in log.read_text().splitlines():
            parts = line.split('\t')
            if len(parts) == 4:
                captured[parts[0]] = parts[1:]
    lines = [
        '# HTTPS client JA4 fingerprints', '',
        'Measured by a local Apache HTTPS server running this checkout of `mod_ja4`.',
        'C and C++ are measured separately. All clients verify the server certificate '
        'and hostname using the local test CA as a trust anchor. '
        'No external HTTPS target is contacted.', '',
        '| Language | Official Docker image | HTTPS API | Runtime / TLS | JA4 | Result |',
        '| --- | --- | --- | --- | --- | --- |',
    ]
    failed = bool(error)
    records = []
    for row in rows:
        key, language, image, api, runtime, succeeded = row
        status, ja4, raw = captured.get(f'/{key}.txt', ('-', '-', '-'))
        valid = succeeded and status == '200' and bool(re.fullmatch(
            r't[0-9a-z]{2}[di][0-9]{4}[0-9A-Za-z]{2}_[0-9a-f]{12}_[0-9a-f]{12}', ja4))
        failed |= not valid
        lines.append('| ' + ' | '.join(map(cell, [language, image, api, runtime,
                                                  ja4, 'OK' if valid else 'FAILED'])) + ' |')
        records.append(dict(language=language, image=image, api=api, runtime=runtime,
                            ja4=ja4, ja4_raw=raw, success=valid))
    lines += ['', '## Raw fingerprints', '']
    for record in records:
        lines += [f"### {record['language']}", '', '```text', record['ja4_raw'], '```', '']
    lines += [
        'The image digests, client stdout/stderr, Apache access log and JSON results '
        'are attached as the `https-client-fingerprints` workflow artifact.', '',
        'Different image tags, library versions or TLS options may produce different '
        'fingerprints. These results do not prove the implementation language of an '
        'unknown client, and do not force OpenSSL 1.1.1.', '',
    ]
    if error:
        lines += ['## Collection error', '', html.escape(str(error)), '']
    (RESULTS / 'summary.md').write_text('\n'.join(lines))
    (RESULTS / 'results.json').write_text(json.dumps(records, indent=2) + '\n')
    return failed


def main():
    RESULTS.mkdir(exist_ok=True)
    rows, digests, error = [], {}, None
    network_created = server_started = False
    try:
        run(['docker', 'network', 'create', NETWORK])
        network_created = True
        run(['docker', 'build', '--pull', '-t', SERVER_IMAGE, '-f',
             str(CLIENTS / 'Dockerfile'), str(ROOT)], timeout=600)
        run(['docker', 'run', '-d', '--name', SERVER, '--network', NETWORK,
             '--network-alias', 'ja4-server', '-v', f'{RESULTS}:/results', SERVER_IMAGE])
        server_started = True
        run(['docker', 'cp', f'{SERVER}:/etc/ssl/certs/ja4-ca.crt',
             str(RESULTS / 'ca.pem')])
        for _ in range(30):
            ready = subprocess.run(['docker', 'exec', SERVER, 'bash', '-c',
                                    'exec 3<>/dev/tcp/127.0.0.1/443'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError('Apache did not start listening within 30 seconds')
        for key, language, image, api, command in CASES:
            print(f'Collecting {language} using {image}', flush=True)
            succeeded, stdout = False, ''
            client_name = f'{SERVER}-{key}'
            try:
                with (RESULTS / f'{key}.stdout.txt').open('w') as out, \
                     (RESULTS / f'{key}.stderr.txt').open('w') as err:
                    run(['docker', 'run', '--rm', '--name', client_name, '--network', NETWORK,
                         '-v', f'{CLIENTS}:/clients:ro', '-v', f'{RESULTS}:/results',
                         '-v', f'{RESULTS / "ca.pem"}:/fixture/ca.pem:ro',
                         image, 'bash', '-euc', command], stdout=out, stderr=err, timeout=600)
                succeeded = True
            except (subprocess.SubprocessError, OSError) as exc:
                print(f'{language} failed: {exc}', flush=True)
            finally:
                subprocess.run(['docker', 'rm', '-f', client_name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stdout = (RESULTS / f'{key}.stdout.txt').read_text().strip()
            rows.append((key, language, image, api, stdout, succeeded))
            digest = subprocess.run(['docker', 'image', 'inspect', image,
                                     '--format', '{{json .RepoDigests}}'],
                                    capture_output=True, text=True)
            digests[image] = digest.stdout.strip()
    except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
        error = exc
        print(f'Collection failed: {exc}', flush=True)
    finally:
        if server_started:
            subprocess.run(['docker', 'stop', SERVER], stdout=subprocess.DEVNULL)
            with (RESULTS / 'server.log').open('w') as out:
                subprocess.run(['docker', 'logs', SERVER], stdout=out, stderr=subprocess.STDOUT)
            subprocess.run(['docker', 'rm', SERVER], stdout=subprocess.DEVNULL)
        if network_created:
            subprocess.run(['docker', 'network', 'rm', NETWORK], stdout=subprocess.DEVNULL)
        (RESULTS / 'image-digests.json').write_text(json.dumps(digests, indent=2) + '\n')
        failed = report(rows, error)
    return int(failed or len(rows) != len(CASES))


if __name__ == '__main__':
    raise SystemExit(main())
