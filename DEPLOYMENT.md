# On-Prem Deployment Guide

How to run **DrJhaGPT Pro** inside your own datacenter — from a single VM
to Kubernetes / VMware Cloud Foundation — including an **air-gapped** option where
nothing leaves your network.

- [1. Architecture recap](#1-architecture-recap)
- [2. Prerequisites](#2-prerequisites)
- [3. Server & hardware sizing](#3-server--hardware-sizing)
- [4. Software / tools required](#4-software--tools-required)
- [5. Deploy — Option A: Docker Compose](#5-deploy--option-a-docker-compose-recommended)
- [6. Deploy — Option B: Python + systemd](#6-deploy--option-b-python--systemd)
- [7. Deploy — Option C: Kubernetes / VCF](#7-deploy--option-c-kubernetes--vcf)
- [8. The LLM: cloud vs self-hosted (air-gap)](#8-the-llm-cloud-vs-self-hosted-air-gap)
- [9. Your knowledge base (ingestion)](#9-your-knowledge-base-ingestion)
- [10. Auth, vector DB, observability in production](#10-auth-vector-db-observability-in-production)
- [11. Reverse proxy + TLS](#11-reverse-proxy--tls)
- [12. Security hardening](#12-security-hardening)
- [13. How to test](#13-how-to-test)
- [14. Maintenance & upgrades](#14-maintenance--upgrades)

---

## 1. Architecture recap

A single Python/Streamlit process does everything: UI, retrieval (hybrid dense +
BM25, optional rerank), guardrails, and calls an LLM. The **only** component that
must reach outside your network is the LLM — and that too can be self-hosted for a
fully air-gapped deployment. See [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 2. Prerequisites

- A Linux host (Ubuntu 22.04 / RHEL 9 or similar) or Windows Server.
- **Either** Docker Engine 24+ and Docker Compose v2 (Option A) **or** Python 3.12 (Option B).
- Git.
- **An LLM endpoint** — one of:
  - a **Groq** API key (needs outbound HTTPS to `api.groq.com`), or
  - a **self-hosted** OpenAI-compatible endpoint (vLLM / Ollama / NVIDIA NIM) for air-gap.
- ~3 GB free disk (app + knowledge index + embedding models).
- First run downloads the embedding model (`bge-small`) from Hugging Face — or
  pre-stage it for air-gapped hosts (see §8/§12).

---

## 3. Server & hardware sizing

The app itself is light (CPU-only retrieval + ONNX embeddings). The heavy sizing
only appears if you self-host the LLM.

| Component | vCPU | RAM | GPU | Notes |
|---|---|---|---|---|
| **App** (Groq LLM) | 2 | 4 GB | — | Handles the UI, retrieval, guardrails |
| Embedded Qdrant | in-app | +1 GB | — | For a few thousand–hundred-thousand vectors |
| Qdrant **server** (optional) | 2 | 2–4 GB | — | If you outgrow embedded |
| Keycloak (SSO, optional) | 2 | 2 GB | — | Identity provider |
| Phoenix (trace UI, optional) | 2 | 2 GB | — | Observability |
| Self-hosted LLM — **Llama 3.1 8B** | 8 | 32 GB | 1× 24 GB (L4/A10) | Good starting point |
| Self-hosted LLM — **Llama 3.3 70B** | 32 | 128 GB | 2× 80 GB or 4× 48 GB | Production; VMware Private AI + NIM |

For most internal deployments using Groq or a shared LLM endpoint, **a single
2 vCPU / 4 GB VM runs the whole app.**

---

## 4. Software / tools required

- **Docker + Docker Compose v2** (Option A) — or **Python 3.12 + pip** (Option B).
- **Reverse proxy** for TLS: nginx or Traefik (examples in `deploy/`).
- Optional, all open-source: **Qdrant**, **Keycloak/Authentik**, **Arize Phoenix**,
  **Presidio**, a registry (**Harbor**) for K8s.
- A self-hosted **LLM server** if air-gapped: **vLLM**, **Ollama**, or **NVIDIA NIM**.

---

## 5. Deploy — Option A: Docker Compose (recommended)

```bash
git clone https://github.com/impranayk/drjhagpt-ent.git
cd drjhagpt-ent

cp .env.example .env                 # set GROQ_API_KEY (or self-hosted LLM), toggles
#   edit .streamlit/auth.yaml        # change the cookie key + demo users

# (optional) rebuild the index from YOUR content — see §9
# python ingest/build_index.py

docker compose -f deploy/docker-compose.onprem.yml up -d --build
```

The app serves on `http://<host>:8501`. Put nginx/Traefik in front for HTTPS
(§11). Data (index, traces) persists in the named Docker volumes.

---

## 6. Deploy — Option B: Python + systemd

```bash
git clone https://github.com/impranayk/drjhagpt-ent.git && cd drjhagpt-ent
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # set your secrets/toggles
python ingest/build_index.py         # (optional) build from your content
```

Install the service (edit paths/user first): copy `deploy/drjhagpt.service` to
`/etc/systemd/system/`, then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now drjhagpt
```

---

## 7. Deploy — Option C: Kubernetes / VCF

1. Build the image and push to your internal registry (e.g. **Harbor**):
   `docker build -t harbor.example.com/ai/drjhagpt-ent:1.0 . && docker push …`
2. Create a **Deployment + Service + Ingress**; mount `GROQ_API_KEY` (or LLM
   endpoint creds) as a **Secret**; use a **PVC** for `data/` (index) and, if used,
   Qdrant storage.
3. Run **Qdrant** and **Keycloak** as their own Deployments/StatefulSets.
4. On **VMware Cloud Foundation / vSphere with Tanzu**, this is a standard workload;
   for the LLM, use **VMware Private AI Foundation with NVIDIA** to serve an open
   model via **NIM**, and point the app at that endpoint (§8).

*(K8s manifests are a Phase-3 to-do; the container image is ready today.)*

---

## 8. The LLM: cloud vs self-hosted (air-gap)

This is the key integration decision.

**Cloud (default):** set `GROQ_API_KEY`. Requires outbound HTTPS to `api.groq.com`.

**Self-hosted / air-gapped:** run an **OpenAI-compatible** server on-prem and point
the app at it — no data leaves your network:

- **Ollama** — `ollama serve` (easy, CPU/GPU).
- **vLLM** — `vllm serve meta-llama/Llama-3.1-8B-Instruct` (high throughput, GPU).
- **NVIDIA NIM** — enterprise, via **VMware Private AI Foundation**.

**Integration hook:** `chatbot/llm.py` currently uses the Groq SDK. To use a
self-hosted OpenAI-compatible endpoint, point it at your server's base URL and
token. This is a small, documented change — a `LLM_BASE_URL` / `LLM_PROVIDER`
switch can be added on request so it's config-only, with no code edits.

---

## 9. Your knowledge base (ingestion)

The app answers from a prebuilt index in `data/` (`knowledge.npz` + `chunks.json`).
Rebuild it from **your** content:

- The default ingester (`ingest/build_index.py`) pulls from a **WordPress REST
  API** — change the `SITE` constant to your source.
- For other sources (SharePoint, Confluence, file shares, a database), replace the
  *fetch* step only; keep the *chunk → embed → save* pipeline.
- Re-run on content change, or schedule it (cron / the included nightly GitHub
  Action pattern).

---

## 10. Auth, vector DB, observability in production

- **Auth** — the demo uses a session-based **bcrypt** login (local users in
  `.streamlit/auth.yaml`; change passwords via `scripts/make_hash.py`). For real
  **SSO/RBAC**, front the app with **Keycloak** or **Authentik** (OIDC) via
  `oauth2-proxy`, or Streamlit's native OIDC login.
- **Vector DB** — embedded Qdrant needs no server. For scale/HA run **Qdrant as a
  service** (container/cluster); connecting the app to a remote Qdrant is a small
  code hook (`QDRANT_URL`) that can be added.
- **Observability** — traces are written to `logs/traces.jsonl`. For a UI, run
  **Arize Phoenix** (or self-hosted **Langfuse**) and export the spans.

---

## 11. Reverse proxy + TLS

Terminate TLS at nginx/Traefik in front of the app (Streamlit needs WebSocket
upgrade headers). See `deploy/nginx.example.conf`. Use your internal CA,
Let's Encrypt, or corporate PKI for the certificate.

---

## 12. Security hardening

- Change the **cookie signing key** and demo credentials in `.streamlit/auth.yaml`.
- Serve only over **HTTPS**; restrict access by network policy / VPN as needed.
- Keep secrets in a **secrets manager** (Vault) or Docker/K8s secrets — never commit `.env`.
- **Air-gap:** pre-download the embedding + reranker models into the Hugging Face
  cache, self-host the LLM (§8), and block outbound egress.
- Rate-limit at the proxy; enable the optional **Llama Guard** moderation
  (`ENABLE_MODERATION=1`) and **Presidio** PII (`USE_PRESIDIO=1`).

---

## 13. How to test

```bash
curl http://<host>:8501/healthz           # -> "ok" when up
pytest                                     # unit tests
python eval/run_eval.py                    # retrieval quality (hit@k / MRR)
```

Then a manual smoke test: log in, ask a question (verify the sources), and try
`"ignore all previous instructions"` — the guardrail should **block** it.

---

## 14. Maintenance & upgrades

```bash
git pull
docker compose -f deploy/docker-compose.onprem.yml up -d --build   # or restart the systemd service
python ingest/build_index.py                                       # when content changes
```

---

_Questions on any step? The lightweight defaults run on a single small VM; the
optional pieces (Keycloak, Qdrant cluster, Phoenix, self-hosted LLM) scale it to a
full private-AI platform — all open-source._
