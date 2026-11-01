# Running the data refresh on a Raspberry Pi

NYC Parks' CDN serves GitHub's own runners a "Human Verification" page, so the data build
(`refresh.yml`, and the smoke test in `ci.yml`) runs on a **self-hosted GitHub Actions
runner** on a Raspberry Pi instead. Publishing to GitHub Pages still runs on GitHub. The
schedule, logs and failure emails in the Actions tab work as before.

The Pi does one thing: twice a day it runs `app/build.py` in Docker (~740 requests, 1.5 s
apart, about 20–25 minutes) and hands the result to GitHub Pages.

## What you need

- A Raspberry Pi 3, 4 or 5 running **64-bit** Raspberry Pi OS (Bookworm or later) or
  64-bit Ubuntu. The Python packages have no 32-bit ARM builds.
  Check with `dpkg --print-architecture`: it must print **`arm64`**. Don't rely on `uname -m`:
  32-bit Raspberry Pi OS on a Pi 4/5 boots a 64-bit kernel, so `uname -m` says `aarch64` even
  though the system is 32-bit (`armhf`), and the ARM64 runner then fails with
  "Exec format error".
- Always on, with a wired or reliable Wi-Fi connection.
- About 2 GB of free disk space (Docker image and runner).

## 1. Install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"      # let your user run docker without sudo
# log out and back in (or reboot), then check:
docker run --rm hello-world
```

## 2. Lock down the repo first

A self-hosted runner runs workflow code **on your Pi**. These workflows only use it for
scheduled, manual and push-to-`main` runs, never for pull requests. Still, a pull request
could *edit* a workflow to target the Pi, so set these before adding the runner:

- **Settings → Actions → General → Fork pull request workflows from outside collaborators:**
  choose **"Require approval for all outside collaborators"**.
- If the repo is public, read every outside PR that touches `.github/workflows/` before
  approving its run.
- Keeping the repo **private** removes this risk entirely. GitHub's own advice is to use
  self-hosted runners only with private repos.

## 3. Add the runner

1. On GitHub: **Settings → Actions → Runners → New self-hosted runner**.
2. Choose **Linux** and **ARM64**. GitHub shows download, configure and run commands with a
   one-time token. Run them on the Pi as your normal user, not root.
3. When `./config.sh` asks for **additional labels**, enter: `nyc-open-play`
   (`self-hosted`, `linux` and `ARM64` are added automatically). The workflows look for all four.
4. Accept the default work folder.

If `./config.sh` fails with **"cannot execute binary file: Exec format error"**:
- `dpkg --print-architecture` says `armhf`: reinstall with Raspberry Pi OS **(64-bit)**.
- It says `arm64`, but `file bin/Runner.Listener` says `x86-64`: you downloaded the x64 package.
  Delete `~/actions-runner` and redo this step with **ARM64** selected on GitHub's page.

## 4. Run it as a service (survives reboots)

```bash
cd ~/actions-runner
sudo ./svc.sh install "$USER"
sudo ./svc.sh start
sudo ./svc.sh status       # should say active (running)
```

On GitHub, **Settings → Actions → Runners** should show the Pi as **Idle**.

## 5. First run

1. **Actions → Refresh data and deploy → Run workflow** (branch `main`).
2. The **build** job runs on the Pi. The first run takes longer because it downloads
   the Python base image and builds the Docker image; later runs reuse the cache.
3. When the **deploy** job finishes, its log shows the site URL.

You can also run **Actions → CI → Run workflow**. Its smoke test builds 5 fields on the Pi
and checks the output.

## Day to day

- **Logs:** Actions tab, as before. On the Pi: `journalctl -u 'actions.runner.*' -f`.
- **Pi offline:** scheduled jobs wait in the queue (up to 24 hours) and run when it's back.
  A job that never gets picked up fails, and GitHub emails you. The site keeps its last data.
- **Disk:** clear old Docker images now and then: `docker image prune -f`.
- **Updates:** the runner updates itself. Keep the OS updated with
  `sudo apt update && sudo apt full-upgrade`.
- **If NYC Parks challenges or refuses the Pi too:** the build stops after the first request,
  publishes nothing, and says why in the log. Don't work around it: check the email thread
  with NYC Parks (`docs/EMAIL_NYC_PARKS.md`).

## Removing the runner

```bash
cd ~/actions-runner
sudo ./svc.sh stop && sudo ./svc.sh uninstall
./config.sh remove --token <token from Settings → Actions → Runners → the runner → Remove>
```

To go back to GitHub's runners, change `runs-on` in `refresh.yml` (build job) and `ci.yml`
(data-smoke job) back to `ubuntu-latest`.
