#!/usr/bin/env bash
# Generate the contest demo shared key and a TLS certificate.
#
# The key is random and printed once. It is never committed: ops/demo/secrets
# and ops/demo/certs are gitignored.
#
#   ops/scripts/generate-demo-credentials.sh              # key + self-signed cert
#   ops/scripts/generate-demo-credentials.sh --key-only
#   ops/scripts/generate-demo-credentials.sh --user judge2
#
# For a judge-facing public hostname, replace the self-signed certificate with
# the real one issued for that hostname. See
# docs/current/demo-hardening-backlog.md section 4.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECRETS_DIR="$REPO_ROOT/ops/demo/secrets"
CERTS_DIR="$REPO_ROOT/ops/demo/certs"
HTPASSWD="$SECRETS_DIR/htpasswd"
HOSTNAME="${PROJECT_N3_DEMO_HOSTNAME:-r2s-demo.local}"

# HTTP Basic auth always requires user:password; nginx rejects an entry with an
# empty username (verified: a correct key still returns 401). So the username is
# a FIXED, non-secret constant and the KEY is the only secret. Judges are given
# one string, never a username of their own.
# See docs/current/naming-migration.md and docs/guides/security-deployment.md.
FIXED_USER="r2s"

KEY_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --key-only) KEY_ONLY=1; shift ;;
    -h|--help)  sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *)          echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

mkdir -p "$SECRETS_DIR" "$CERTS_DIR"
chmod 700 "$SECRETS_DIR" "$CERTS_DIR"

if ! command -v openssl >/dev/null 2>&1; then
  echo "openssl is required but was not found on PATH." >&2
  exit 1
fi

# ---------------------------------------------------------------- shared key

if [ -f "$HTPASSWD" ] && [ "$KEY_ONLY" -eq 0 ]; then
  echo "htpasswd already exists at ops/demo/secrets/htpasswd — leaving it alone."
  echo "Delete it first if you intend to rotate the key."
else
  KEY="$(openssl rand -base64 18 | tr -d '\n/+=' | cut -c1-22)"
  # APR1 via openssl passwd; nginx accepts any crypt() format htpasswd uses.
  HASH="$(openssl passwd -apr1 "$KEY")"
  printf '%s:%s\n' "$FIXED_USER" "$HASH" > "$HTPASSWD"
  chmod 600 "$HTPASSWD"

  # nginx workers drop to uid 101 inside the container and re-read this file on
  # every authenticated request. Grant that single uid read access via an ACL.
  # `chgrp 101` would need root, and 0644 would make the hash world-readable.
  if command -v setfacl >/dev/null 2>&1; then
    setfacl -m u:101:r-- "$HTPASSWD"
  else
    echo "warning: setfacl not found. The gateway worker (uid 101) will not be" >&2
    echo "         able to read the credential and will return 500 on login." >&2
    echo "         Install acl, or run: setfacl -m u:101:r-- $HTPASSWD" >&2
  fi

  echo
  echo "=============================================================="
  echo " Contest demo KEY (username is fixed: $FIXED_USER)"
  echo "=============================================================="
  echo "   $KEY"
  echo
  echo " Share ONLY this string with judges."
  echo " Browser prompt: username '$FIXED_USER'  password <the key above>"
  echo " One-line form:   $FIXED_USER:<the key above>"
  echo " curl:            curl -u '$FIXED_USER:<the key>' https://project-n3.hahuy.cloud/"
  echo " This is shown ONCE. It is not recoverable from the hash."
  echo " Store it in your password manager now."
  echo "=============================================================="
  echo
fi

# ----------------------------------------------------------------- TLS cert

if [ "$KEY_ONLY" -eq 0 ]; then
  if [ -f "$CERTS_DIR/fullchain.pem" ]; then
    echo "Certificate already present — leaving it alone."
  else
    echo "Generating a self-signed certificate for $HOSTNAME."
    echo "This is for LAN/initial testing only. Judges will see a browser warning."
    openssl req -x509 -newkey rsa:2048 -sha256 -days 30 -nodes \
      -keyout "$CERTS_DIR/privkey.pem" \
      -out    "$CERTS_DIR/fullchain.pem" \
      -subj   "/CN=$HOSTNAME" \
      -addext "subjectAltName=DNS:$HOSTNAME,DNS:localhost,IP:127.0.0.1" \
      2>/dev/null
    chmod 600 "$CERTS_DIR/privkey.pem"
    chmod 644 "$CERTS_DIR/fullchain.pem"
    echo "Written to ops/demo/certs/{fullchain,privkey}.pem"
  fi
fi

echo
echo "Next:  docker compose -f compose.demo.yml up -d --build"
echo "Then:  curl -k -u \"$FIXED_USER:<key>\" https://127.0.0.1:\${PROJECT_N3_DEMO_HTTPS_PORT:-8443}/api/health"
