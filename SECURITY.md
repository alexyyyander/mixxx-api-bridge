# Security policy

## Deployment guidance

The HTTP server binds to loopback (`127.0.0.1`) by default. Keep it on
loopback unless an authenticated and network-isolated deployment is required.
If `MIXXX_API_TOKEN` is set, clients must send a matching Bearer token.

The bridge can write Mixxx ControlObjects, so do not expose the API directly
to an untrusted network. Use a firewall or a local reverse proxy with TLS and
authentication for any deliberate remote access.

## Reporting a vulnerability

Please report security issues privately through GitHub's Security Advisories
for this repository. Include reproduction steps, affected versions, and any
recommended mitigation. Do not publish credentials, MIDI captures containing
personal data, or an exploit before a fix is available.
