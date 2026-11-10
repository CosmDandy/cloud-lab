#!/usr/bin/env bash
# Push GitHub Actions secrets from .github/secrets.sops.yaml.
#
# SOPS is the source of truth and GitHub holds a copy: a secret lost, rotated
# or wiped on the GitHub side comes back by re-running this. Key names in the
# file are the secret names in GitHub (TF_API_TOKEN, ...).
#
# Plaintext never touches disk: sops decrypts to a pipe that gh reads as
# dotenv. Needs a gh token with "Secrets: read and write" on the repository.
#
#   scripts/push-github-secrets.sh                      # repo of the checkout
#   scripts/push-github-secrets.sh -R CosmDandy/cloud-lab
set -euo pipefail
shopt -s inherit_errexit
cd "$(git rev-parse --show-toplevel)"
sops -d --output-type dotenv .github/secrets.sops.yaml | gh secret set -f - "$@"
gh secret list "$@"
