# Isolated Python checks on this PC

PyForge v0.3.4 uses one dedicated Ubuntu 24.04 WSL2 distro named `PyForgeSandbox`, stored at `F:\pyforge_ai_2\local_runtime\wsl\PyForgeSandbox`. Its virtual disk has a 30 GB maximum. Docker's `/var/lib/docker` and the pinned Python test image are inside that F: backed disk. The Windows project files and Docker socket are not mounted into test containers.

The chat offers **Run Tests** only for a complete response with one Python code block containing a recognized one-argument sorting function (`sort_numbers`, `bubble_sort`, `sort_list`, `sort_array`, `sort_values`, or `sort`). Review the displayed code and fixture contract before clicking. The five checks require the function to return an ascending list for empty, singleton, ordinary, duplicate and negative inputs. They do not check other requirements or prove general correctness. Other answers remain analysis-only.

Ubuntu's HTTPS security repositories supplied Docker Engine 29.1.3, containerd 2.2.1 and runc 1.3.4 for this installation. Package indexes were refreshed and the services restarted before the final integration run. The dedicated distro sometimes emits `Failed to start the systemd user session for 'root'` and takes about 20 seconds on a cold start, although Docker and all integration checks complete; the runner gives Docker readiness a separate 40-second limit. This warning still needs investigation.

The container runner uses `python:3.14-slim` pinned to digest `sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f`. It starts without network or host mounts, as UID/GID 65534, with a read-only root and a 32 MB temporary filesystem, no Linux capabilities, no new privileges, 32 process, 256 MB memory and one CPU limits. Source and fixture inputs are each capped at 64 KiB; captured output is bounded; code has an eight-second wall-clock limit after a separate Docker readiness check. A timeout forcibly removes the named container. Docker on WSL2 is a bounded diagnostic backend, **not** a hardened boundary for intentionally hostile code. Do not use it to run untrusted code from unknown authors without further hardening.

The distro uses tracked `config/wsl-sandbox.conf` to disable Windows drive automount and interop and set the unprivileged default user. `config/wsl-ubuntu.sources` replaces the original HTTP package sources with HTTPS main/universe and security repositories. `config/wsl-apt-minimal.list` documents the initial bootstrap source; it is disabled in the live distro after the full source is applied. The WSL first-run account is `pyforge` (UID 1000); Docker is started by systemd and accessed from Windows through explicit `wsl.exe -d PyForgeSandbox -u root --exec docker ...` calls. The test container itself is never root.

Run the synthetic integration checks explicitly from the project root with PowerShell:

```powershell
$env:PYFORGE_SANDBOX_TEST = '1'
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_sandbox.py -v
Remove-Item Env:PYFORGE_SANDBOX_TEST
```

The normal repository test suite skips live container cases, so it can run without WSL. This first slice does not persist test results to chat exports or verify GUI programs. Next steps are additional reviewed task fixtures, disposable file/GUI fixtures, result provenance and stronger isolation before broader execution.
