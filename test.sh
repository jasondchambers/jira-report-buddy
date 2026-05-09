#!/usr/bin/env bash
#
# Run all tests and quality checks for the Cylera CLI.
#

set -e

lint_python() {
  uvx --no-build ruff==0.15.12 check . || exit 1
}

check_types() {
  uvx --no-build basedpyright==1.39.3 . || exit 1
}

lint_shellscripts() {
  shellcheck ./*.sh*
}

check_app_security() {
  uvx --no-build bandit==1.9.4 -c bandit.yaml ./*.py
}

check_software_supply_chain_security() {
  uv export --no-hashes | uvx --no-build --python 3.13 pip-audit==2.10.0 -r /dev/stdin
}

echo "******** Running ruff check (linter)  **********"
lint_python
echo "******** Running basedpyright (checking types) **********"
check_types
echo "******** Running shellcheck **********"
lint_shellscripts
echo "******** Running bandit (security) **********"
check_app_security
echo "******** Running pip-audit (security scanning packages) *******"
check_software_supply_chain_security

echo ""
echo "=== All checks passed! ==="
