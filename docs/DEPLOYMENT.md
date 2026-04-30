# Deployment Guide

The maintained deployment guide now lives at [`deploy/README.md`](../deploy/README.md).

This compatibility page is kept because older docs and bookmarks pointed to `docs/DEPLOYMENT.md`.

Use the current guide for:

- Fly.io, Render, Railway, DigitalOcean App Platform, and VPS Docker deployment
- Required environment variables
- `/health` and `/mcp` endpoint verification
- Reverse-proxy notes

The v0.1.0 server no longer requires an embeddings/vector-extension stack. PostgreSQL is optional and used only for FTS-based metadata search when `DATABASE_URL` is configured.
