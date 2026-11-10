# Local release notes

## 0.3.4 — Opt-in isolated sorting checks (2026-11-10)

- Dedicated Ubuntu WSL2 distro and Docker store on F:, with Windows mounts and interop disabled in the distro; Docker Engine 29.1.3, containerd 2.2.1 and runc 1.3.4 from Ubuntu HTTPS updates.
- Pinned Python 3.14 container runner with no network, no host mounts, read-only root, non-root user, resource quotas and wall-clock/output limits.
- Chat can preview and manually test a complete single-block sorting function against five reviewed inputs. Other responses are marked not automatically testable.
- Docker is a bounded local diagnostic tool, not a hardened boundary against deliberately hostile code. Test results cover only the stated fixture and are not yet saved to chat exports.
