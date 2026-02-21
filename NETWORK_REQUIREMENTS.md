# IPAM FastAPI — Network / Firewall Requirements

> **Context**: Closed-network deployment.  
> All outbound connections from the Docker host (and containers) require explicit firewall rules or an approved HTTP proxy.

---

## 1. Build-Time Requirements (Docker Image Build)

These destinations are needed **only during `docker build`**. Once images are built they can be transferred offline; no runtime access is required.

| # | Destination | Port | Protocol | Purpose |
|---|------------|------|----------|---------|
| 1 | `registry-1.docker.io` / `index.docker.io` | 443 | HTTPS | Pull base images (`python:3.11-slim`, `nginx:alpine`, `postgres:16`) |
| 2 | `auth.docker.io` | 443 | HTTPS | Docker Hub authentication |
| 3 | `production.cloudflare.docker.com` | 443 | HTTPS | Docker Hub CDN layer downloads |
| 4 | `deb.debian.org` | 80 | HTTP | Debian APT packages (`gcc`, `postgresql-client`) for `python:3.11-slim` |
| 5 | `security.debian.org` | 80 | HTTP | Debian security updates |
| 6 | `pypi.org` | 443 | HTTPS | Python package index (metadata) |
| 7 | `files.pythonhosted.org` | 443 | HTTPS | Python package downloads (wheels / sdists) |

> [!TIP]
> **Offline alternative**: Build images on a network-connected machine, export with `docker save`, transfer to the closed network, and load with `docker load`. This eliminates all build-time firewall rules.

---

## 2. Runtime Requirements (Application)

These destinations must be reachable **while containers are running**.

### 2.1 Internal (Docker-Network-Only, No Firewall Rules Needed)

These connections stay within the `ipam-network` Docker bridge and do **not** traverse the host firewall.

| # | Source → Destination | Port | Protocol | Purpose |
|---|---------------------|------|----------|---------|
| 1 | `nginx` → `app` | 8000 | HTTP | Reverse-proxy to FastAPI |
| 2 | `app` → `db` | 5432 | TCP (PostgreSQL) | Application database |

### 2.2 External — OIDC / SSO Provider (Conditional)

Required **only if** OIDC/SSO authentication is enabled (`OIDC_DISCOVERY_URL` is set).  
The exact domain depends on your identity provider.

| # | Destination (example) | Port | Protocol | Purpose |
|---|----------------------|------|----------|---------|
| 1 | `<OIDC_PROVIDER_DOMAIN>` (e.g. `login.microsoftonline.com`, `accounts.google.com`, `auth.omnissa.com`) | 443 | HTTPS | OIDC Discovery (`/.well-known/openid-configuration`) |
| 2 | `<OIDC_PROVIDER_DOMAIN>` | 443 | HTTPS | JWKS endpoint (public key retrieval for token validation) |
| 3 | `<OIDC_PROVIDER_DOMAIN>` | 443 | HTTPS | Authorization, token exchange, and userinfo endpoints |

> [!IMPORTANT]
> Replace `<OIDC_PROVIDER_DOMAIN>` with the actual hostname from your `OIDC_DISCOVERY_URL` environment variable. Multiple hostnames may be involved if the provider uses separate token / JWKS domains.

### 2.3 External — Google Fonts CDN (Optional)

The UI loads the **Inter** font family from Google Fonts. This is cosmetic — the app functions without it (falls back to system fonts).

| # | Destination | Port | Protocol | Purpose |
|---|------------|------|----------|---------|
| 1 | `fonts.googleapis.com` | 443 | HTTPS | Font CSS stylesheet |
| 2 | `fonts.gstatic.com` | 443 | HTTPS | Font file downloads (WOFF2) |

> [!TIP]
> **Offline alternative**: Download the Inter font files, place them in `app/static/fonts/`, and update `modern.css` to use a local `@font-face` rule instead of the `@import` URL. This removes the need for these two firewall rules entirely.

---

## 3. Host-Level Inbound Rules

Ports exposed to end-users / upstream load balancers on the Docker host.

| # | Host Port | Protocol | Purpose |
|---|-----------|----------|---------|
| 1 | **80** | HTTP | Nginx — redirects to HTTPS |
| 2 | **443** | HTTPS | Nginx — serves the application (TLS terminated here) |
| 3 | 5433 | TCP | PostgreSQL exposed to host (for admin tools; **remove in production** if not needed) |

---

## 4. Summary Firewall Rule Table

| Direction | Source | Destination | Port | Protocol | Phase | Required? |
|-----------|--------|-------------|------|----------|-------|-----------|
| Outbound | Docker Host | `registry-1.docker.io`, `auth.docker.io`, `production.cloudflare.docker.com` | 443 | HTTPS | Build | Yes (or use offline images) |
| Outbound | Docker Host | `deb.debian.org`, `security.debian.org` | 80 | HTTP | Build | Yes (or use offline images) |
| Outbound | Docker Host | `pypi.org`, `files.pythonhosted.org` | 443 | HTTPS | Build | Yes (or use offline images) |
| Outbound | `app` container | `<OIDC_PROVIDER_DOMAIN>` | 443 | HTTPS | Runtime | Only if OIDC enabled |
| Outbound | Client browser | `fonts.googleapis.com`, `fonts.gstatic.com` | 443 | HTTPS | Runtime | Optional (cosmetic) |
| Inbound | End users | Docker Host | 80, 443 | HTTP/S | Runtime | Yes |
| Inbound | Admin tools | Docker Host | 5433 | TCP | Runtime | Optional |

---

> [!NOTE]
> If **no OIDC** is configured and Google Fonts are self-hosted, the application has **zero outbound runtime dependencies** — it operates fully air-gapped after container images are built/loaded.
