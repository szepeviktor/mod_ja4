"""Parse a native-client capture using the module's C implementation on Linux."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as runner


class Result(ctypes.Structure):
    _fields_ = [('fingerprint', ctypes.c_char * 37), ('raw', ctypes.c_void_p)]


directory = Path(sys.argv[1])
with tempfile.TemporaryDirectory() as temporary:
    library = Path(temporary) / 'ja4.so'
    subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Wextra', '-Werror',
                    str(ROOT / 'ja4.c'), '-lcrypto', '-o', str(library)], check=True)
    parser = ctypes.CDLL(str(library))
    parser.ja4_compute.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(Result)]
    parser.ja4_compute.restype = ctypes.c_int
    libc = ctypes.CDLL(None)
    libc.free.argtypes = [ctypes.c_void_p]
    data = (directory / 'clienthello.bin').read_bytes()
    result = Result()
    if not parser.ja4_compute(data, len(data), ctypes.byref(result)):
        raise RuntimeError('Invalid captured ClientHello')
    try:
        record = json.loads((directory / 'metadata.json').read_text(encoding='utf-8-sig'))
        record.update(ja4=result.fingerprint.decode(), ja4_raw=ctypes.string_at(result.raw).decode())
    finally:
        libc.free(result.raw)
runner.RESULTS.mkdir(exist_ok=True)
raise SystemExit(runner.write_report([record]))
