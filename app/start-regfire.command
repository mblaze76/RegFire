#!/bin/zsh
# Run from any working directory; keep this Terminal window open while using RegFire.
cd -- "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print "RegFire's local Python environment is missing. See README.md for setup."
  exit 1
fi
exec .venv/bin/python server.py --port 8768
