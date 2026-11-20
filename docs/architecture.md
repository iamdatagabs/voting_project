# Arquitetura

## Princípios
1. Proveniência é parte do dado: fonte, URL, checksum, extração e status.
2. Raw preserva bytes originais; transformações são reexecutáveis.
3. Eleição, cargo, geografia e status são dimensões distintas.
4. Ausência não equivale a zero.
5. Dados oficiais, preliminares e estimativas não são intercambiáveis.

## Lakehouse
- Raw: arquivo original identificado por SHA-256.
- Bronze: estrutura tabular com metadados de ingestão.
- Silver: contrato canônico validado e deduplicado.
- Gold: Parquet para consultas analíticas.
DuckDB consulta Parquet sem serviço dedicado. API FastAPI fornece leitura; GitHub Pages publica frontend estático desacoplado.

## Componentes e escala
Python 3.11, Pydantic, pandas/PyArrow, DuckDB, FastAPI. DuckDB é adequado a analytics single-node. PostgreSQL será necessário para escrita concorrente, autenticação e transações multiusuário. Pages não hospeda processos Python.

## Segurança e próximos passos
API atual é read-only para clientes HTTP; ingestão ocorre via CLI controlada. Antes de produção: restringir CORS, autenticar operações administrativas, limitar tamanho de download, allowlist de hosts e executar conectores em jobs isolados. Adicionar snapshots imutáveis e versionamento de esquema.
