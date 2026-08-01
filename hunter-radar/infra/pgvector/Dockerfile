# Hunter Radar V1.6.0 — Postgres + pgvector
# 2026-07-22 patch: stack 的 postgres:16-alpine 缺 pgvector 扩展,
#   导致 03_v1.6.0_rag.sql 在 initdb 阶段 CREATE EXTENSION vector 失败,
#   容器 Exited (3)。替换为 pgvector 官方镜像。
#
# Build:   docker build -t hunter-postgres-pgvector infra/pgvector
# Replaces postgres:16-alpine in docker-compose.yml
#
# pgvector 是 pgvector/pgvector:pg16 的官方仓库 (ankane/pgvector fork),
# 与 postgres:16-alpine 完全兼容(同样的 ENTRYPOINT + env vars + 健康检查)。
FROM pgvector/pgvector:pg16

# 容器行为由 docker-compose.yml 的 environment/volume 控制,
# 这里只需保证 pgvector 扩展默认可用即可。
