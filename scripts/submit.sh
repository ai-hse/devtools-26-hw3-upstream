#!/usr/bin/env bash
curl --silent --form "file=@$2" "$1/reports" > "$3"
