# Security Policy

## Scope

asiai is a local-only CLI tool. It makes **no network calls** except to inference engines running on localhost. It stores no secrets, tokens, or credentials.

## Supported Versions


| Version | Supported |
| ------- | --------- |
| latest  | Yes       |
| older   | No        |


## Reporting a Vulnerability

If you discover a security issue, please report it responsibly:

1. **Do not** open a public GitHub issue.
2. Email **[druide67@free.fr](mailto:druide67@free.fr)** with:
  - Description of the vulnerability
  - Steps to reproduce
  - Potential impact
3. You will receive a response within 48 hours.

## Security Design

- Zero runtime dependencies for core (minimizes supply chain risk)
- All subprocess calls use list arguments (no `shell=True`)
- All SQL queries use parameterized placeholders (no f-string interpolation)
- HTTP response bodies are bounded (10 MB max)
- No telemetry, no external network calls

