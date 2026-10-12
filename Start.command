#!/bin/sh
cd "$(dirname "$0")" || exit 1
sh launch.sh
result=$?
if [ "$result" -ne 0 ]; then
    printf '\nPress Enter to close this window.'
    read -r answer
fi
exit "$result"
