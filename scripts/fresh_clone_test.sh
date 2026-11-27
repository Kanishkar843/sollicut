#!/bin/sh
set -eu
# Run from a NEW independent clone. Keeps the server running for microphone testing.
test -f docker-compose.yml
docker compose up --build -d --wait --wait-timeout 180
sh scripts/smoke_test.sh
printf '%s\n' 'Rendering smoke passed. Real human microphone acceptance remains separate.'
