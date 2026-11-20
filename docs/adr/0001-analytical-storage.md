# ADR 0001 — Parquet e DuckDB
- Status: aceito para primeira versão.
- Contexto: analytics reprodutível e baixo custo operacional.
- Decisão: Parquet para camadas e DuckDB para consulta local.
- Consequência: simples e portável; sem escrita concorrente multiusuário. PostgreSQL entra quando requisitos transacionais justificarem.
