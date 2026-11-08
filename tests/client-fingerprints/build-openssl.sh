#!/usr/bin/env bash
# Runs inside the disposable gcc container; installs nothing on the runner/host.
set -euo pipefail

tag=$1
expected_commit=$2
client_key=$3
source_dir=/tmp/openssl-source

git clone --quiet --depth 1 --branch "$tag" https://github.com/openssl/openssl.git "$source_dir" >&2
cd "$source_dir"
actual_commit=$(git rev-parse HEAD)
if [[ "$actual_commit" != "$expected_commit" ]]; then
    printf 'OpenSSL source mismatch: expected %s, got %s\n' "$expected_commit" "$actual_commit" >&2
    exit 1
fi

# OpenSSL 1.1.0 imports File::Glob::glob, removed by current Perl. The :glob
# export tag supplies the same override. Only build scripts are patched, and
# the complete compatibility diff is retained with the measurement artifact.
if [[ "$tag" == OpenSSL_1_1_0 ]]; then
    perl -pi -e 's{qw/glob/}{qw/:glob/}g' Configure test/build.info
    git diff -- Configure test/build.info > "/results/${client_key}-build-compat.patch"
fi

# Avoid distribution OpenSSL configuration and dynamically linked libssl.
# Build only libraries, including for 1.0.2 (which predates the no-tests option).
export OPENSSL_CONF=/dev/null
./config no-shared --prefix=/tmp/openssl-install >&2
# The 1.0.2 recursive makefiles can concurrently update libcrypto.a from
# build_crypto/build_engines. Serialize that series to avoid missing objects.
case "$tag" in
    OpenSSL_1_0_2*) make -j1 build_libs >&2 ;;
    *) make -j2 build_libs >&2 ;;
esac
gcc -Wall -Wextra -Werror -I "$source_dir/include" \
    /clients/client-openssl.c "$source_dir/libssl.a" "$source_dir/libcrypto.a" \
    -ldl -pthread -o /tmp/openssl-probe

printf 'Source: %s %s\n' "$tag" "$actual_commit"
if [[ "$tag" == OpenSSL_1_1_0 ]]; then
    printf 'Build compatibility: File::Glob :glob imports; TLS source unchanged\n'
fi
/tmp/openssl-probe "$client_key"
