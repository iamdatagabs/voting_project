# U.S. Electoral Observatory

[![CI](https://github.com/iamdatagabs/voting_project/actions/workflows/ci.yml/badge.svg)](https://github.com/iamdatagabs/voting_project/actions/workflows/ci.yml) [![Pages](https://github.com/iamdatagabs/voting_project/actions/workflows/pages.yml/badge.svg)](https://github.com/iamdatagabs/voting_project/actions/workflows/pages.yml)

Plataforma aberta de engenharia de dados e análise estatística eleitoral dos Estados Unidos. Escopo: **Presidência, Senado, Câmara dos Representantes, governadores e legislativos estaduais**.

> Núcleo de engenharia e dashboard publicados. Os conectores aceitam CSV no contrato canônico. Não declaramos uma base nacional de 2026 completa: resultados variam entre preliminares e certificados conforme jurisdição. Ausência de dados nunca é tratada como zero.

## Arquitetura
Fontes públicas → Raw (bytes + SHA-256) → Bronze (normalizado) → Silver (validado) → Gold (Parquet) → DuckDB → FastAPI → dashboard estático (GitHub Pages).

- Python 3.11, Pydantic, pandas/PyArrow, DuckDB, FastAPI.
- Dashboard desacoplado; GitHub Pages não hospeda API Python.
- Cada observação mantém fonte, URL, manifesto, data de extração e status de apuração.
- PostgreSQL fica reservado para futura escrita concorrente/autenticação multiusuário.

## Quatro níveis eleitorais
| Nível | Disputas | Geografia |
|---|---|---|
| Federal nacional | Presidente | país, estado, county, precinct |
| Federal estadual | Senado | estado |
| Federal distrital | Câmara | congressional district |
| Estadual executivo | Governador | estado |
| Estadual legislativo | State House / State Senate | distrito estadual |

O domínio também admite eleições especiais e ciclos não coincidentes.

## Início rápido
Python 3.11+:
```bash
python -m venv .venv
pip install -e ".[dev]"
pytest
uvicorn electoral.api:app --reload
```
API: http://127.0.0.1:8000/docs

## Ingestão
```bash
electoral ingest --url "https://host/data.csv" --source-id "provider.dataset.v1" --election-year 2024 --office president --geography county --status certified
electoral build
```
O CSV deve seguir [contrato de dados](docs/data-contract.md); não há adivinhação silenciosa de cabeçalhos.

## Fontes prioritárias
- [MIT Election Lab](https://electionlab.mit.edu/data): retornos presidenciais, House, Senate e dados locais.
- [FEC](https://www.fec.gov/introduction-campaign-finance/election-and-voting-information/): compilações federais oficiais.
- [U.S. Election Assistance Commission](https://www.eac.gov/research-and-data).
- [Secretarias eleitorais estaduais](https://www.usa.gov/state-election-office): certificação e disputas estaduais.
- [MIT County Presidential Returns 2000–2024](https://dataverse.harvard.edu/): série histórica versionada.

Para 2026, registrar preliminary/certified/estimated e datas de publicação/extração. Publicação de apuração não equivale a certificação.

## Rigor estatístico
Margem em pontos percentuais, concentração HHI, swing comparável, competitividade, eficiência votos-assentos, PCA/MDS e modelos espaciais com diagnósticos. Não calcular turnout sem denominador elegível; não comparar distritos sem harmonização de limites; não inferir comportamento individual de agregados; não confundir associação com causalidade. Ver [metodologia](docs/methodology.md).

A matriz `Voting NJ Congressmen.csv` e os scripts/gráficos R permanecem como estudo legado de dissimilaridade entre parlamentares. Não são retornos eleitorais e não entram no pipeline.

## Estrutura
`apps/web` dashboard · `src/electoral` pacote/API · `config` catálogo · `docs` arquitetura e método · `tests` testes · `data/{raw,bronze,silver,gold}` camadas locais (ignoradas pelo Git).

Licença GPL-3.0.


## Séries temporais e dados integrados

O dashboard inclui um explorador de séries presidenciais 2000–2024, com seleção de território (Estados Unidos ou estado) e métrica (votos absolutos ou participação partidária). A fonte inicial é o MIT Election Data and Science Lab via Harvard Dataverse, DOI 10.7910/DVN/VOQCHQ, licença CC0 1.0.

O workflow Refresh electoral datasets resolve a versão mais recente pelo DOI, preserva o arquivo bruto durante a execução, valida checksum MD5 do publisher e SHA-256 local, normaliza para Parquet e gera JSON agregado para o GitHub Pages. O denominador é deduplicado por county e ciclo antes da agregação. Ausências de votos não são imputadas como zero. A participação nos votos não deve ser interpretada como turnout da população elegível.

A primeira integração cobre apenas Presidência. Senate, House, governadores e legislativos estaduais permanecem no escopo arquitetural e dependem de conectores e validações próprios; não serão apresentados como dados disponíveis antes da ingestão efetiva. Consulte [proveniência e transformações](docs/data-sources.md).
