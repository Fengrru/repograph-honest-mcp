# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1.0 | :x:                |

## Reporting a vulnerability

If you discover a security issue, please email the maintainers directly rather
than opening a public issue. We will respond as quickly as possible and work
with you to assess and address the problem responsibly.

Email: **security@repograph-honest.example** (replace with a real address when
available).

Please include:

- A description of the vulnerability.
- Steps to reproduce or a proof-of-concept.
- The version of RepoGraph-Honest you are using.
- Your Python version and operating system.

## Sandbox security note

`execute_code` is designed to catch accidental mistakes and infinite loops, not
to contain malicious code. It runs in a subprocess with a temporary working
directory and optional Unix resource limits, but it does not provide full
isolation. Do not use it to execute untrusted code without additional sandboxing
such as a container or dedicated virtual machine.
