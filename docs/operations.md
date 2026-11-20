# Operação

## Dashboard
Em Settings → Pages, selecionar GitHub Actions como source. O workflow publica `apps/web`. Sem API configurada, o site exibe modo demonstração. Para dados dinâmicos, definir `window.ELECTORAL_API` em configuração carregada antes de `app.js`, apontando para API HTTPS; restringir CORS ao domínio Pages.

## API
`uvicorn electoral.api:app --host 0.0.0.0 --port 8000`. Health check: `/health`; OpenAPI: `/docs`.

## Pipeline
1. Selecionar dataset e versão; verificar licença, cobertura e dicionário.
2. Mapear explicitamente cabeçalhos para contrato canônico.
3. Executar `electoral ingest` com status e metadados corretos.
4. Revisar manifesto, checksum, validações e contagem.
5. Executar `electoral build`; conferir API.

Falha de esquema exige adaptador, não afrouxar validações. Divergências devem preservar versões, certificação e datas de referência.
