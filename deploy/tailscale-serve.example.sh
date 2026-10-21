#!/bin/sh
# EXAMPLE ONLY. Run manually on your own PC AFTER approving private test hosting.
# Do not run this in the managed Codex cloud environment.
# In terminal 1, from the PushPull checkout:
#   python3 scripts/build_release.py --output dist/releases/test-001
#   python3 scripts/serve_test.py --directory dist/releases/test-001 --port 8000
# In terminal 2, after installing/signing in to Tailscale and enabling HTTPS:
#   tailscale serve --bg --https=443 http://127.0.0.1:8000
#   tailscale serve status
# Confirm the result says "Available within your tailnet". Never use Funnel.
# Use the exact stable HTTPS URL printed by Tailscale on Android.
# Verify tailnet access policy before sharing with any other account/device.
# To stop this mapping later, after checking existing Serve configuration:
#   tailscale serve --https=443 off
# Do not run "serve reset" blindly: it can remove other services on that PC.
printf '%s\n' 'This file contains instructions only; no hosting was started.'
