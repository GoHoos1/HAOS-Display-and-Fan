#!/usr/bin/env bash
set -euo pipefail

export OPTIONS_PATH="${OPTIONS_PATH:-/data/options.json}"

if command -v bashio >/dev/null 2>&1; then
  bashio::log.info "Starting HA Pi Panel"
  if bashio::services.available "mqtt"; then
    export MQTT_HOST="$(bashio::services mqtt host)"
    export MQTT_PORT="$(bashio::services mqtt port)"
    export MQTT_USERNAME="$(bashio::services mqtt username)"
    export MQTT_PASSWORD="$(bashio::services mqtt password)"
    bashio::log.info "MQTT service discovered at ${MQTT_HOST}:${MQTT_PORT}"
  else
    bashio::log.warning "MQTT service is not available; MQTT discovery will stay disabled unless MQTT variables are provided."
  fi
fi

exec python3 -m app.main
