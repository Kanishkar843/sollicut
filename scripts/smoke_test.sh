#!/bin/sh
set -eu
docker compose version
docker compose exec -T sollicut python -m scripts.smoke_test
