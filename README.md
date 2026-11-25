# U.S. Electoral Observatory

[![CI](https://github.com/iamdatagabs/voting_project/actions/workflows/ci.yml/badge.svg)](https://github.com/iamdatagabs/voting_project/actions/workflows/ci.yml) [![Pages](https://github.com/iamdatagabs/voting_project/actions/workflows/pages.yml/badge.svg)](https://github.com/iamdatagabs/voting_project/actions/workflows/pages.yml)

Plataforma aberta de engenharia de dados e análise estatística eleitoral dos Estados Unidos. Escopo: **Presidência, Senado, Câmara dos Representantes, governadores e legislativos estaduais**.

> Núcleo de engenharia e dashboard publicados. Os conectores aceitam CSV no contrato canônico. Não declaramos uma base nacional de 2026 completa: resultados variam entre preliminares e certificados conforme jurisdição. Ausência de dados nunca é tratada como zero.

**Dashboard:** [GitHub Pages](https://iamdatagabs.github.io/voting_project/) · **Portfolio:** [Gabriel Passos](https://iamdatagabs.github.io/iamdatagabs/portfolio/)\n\n## Arquitetura
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

O domínio também admite eleições especiais e ciclos não coincidentes. O campo `contest_id` identifica ano, cargo, território e atributos da disputa; `source_row_id` preserva a linha da fonte quando necessário.

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

As integrações atuais cobrem Presidência, House, Senate e eleições estaduais de 2024 para governadores, State House e State Senate, a partir de arquivos precinct-level por estado. A série estadual ainda não é uma série histórica multi-ciclo. Consulte [proveniência e transformações](docs/data-sources.md).


## Publicação no GitHub Pages

O workflow publica o conteúdo de `apps/web` pelo GitHub Actions e também é acionado após uma atualização de dados bem-sucedida. Na primeira publicação, o proprietário do repositório precisa habilitar Pages em **Settings → Pages → Build and deployment → Source: GitHub Actions**. A integração GitHub conectada ao ChatGPT não possui permissão administrativa para criar o site Pages; após habilitar, execute novamente o workflow **Publish dashboard**. O artefato de dados já é versionado em `apps/web/data/presidential-timeseries.json`.


## Dados efetivamente integrados

- **Presidência (2000–2024):** retornos por county, 7 ciclos eleitorais.
- **Câmara dos Representantes (1976–2024):** retornos por distrito congressional, incluindo eleições especiais no Silver. O agregado público de voto popular estadual usa somente eleições gerais regulares.
- **Senado (1976–2024):** retornos estaduais, incluindo eleições especiais e runoffs no Silver; o agregado público seleciona eleições gerais regulares.
- **Governadores, State House e State Senate (2024):** resultados precinct-level agregados por estado e distrito, com cobertura condicionada aos cargos efetivamente disputados e às observações publicadas.

A integração House usa o dataset MEDSL, DOI [10.7910/DVN/IG0UN2](https://doi.org/10.7910/DVN/IG0UN2), CC0 1.0. O pipeline fixa a versão do espelho, valida atribuição/licença, calcula SHA-256 e preserva Raw/Bronze/Silver e manifesto como artefatos de Actions. O modelo canônico identifica cada disputa por `contest_id`, evitando colidir eleições regulares, especiais, primárias e runoffs no mesmo distrito. Consulte [proveniência House](docs/data-sources.md).


A integração Senate usa o dataset MEDSL, DOI [10.7910/DVN/PEJ5QU](https://doi.org/10.7910/DVN/PEJ5QU), Harvard Dataverse V8, CC0 1.0. O conector utiliza exclusivamente as linhas `mode=TOTAL` para impedir que totais e subtotais por modo de votação sejam somados juntos. O `contest_id` distingue ano, estado, etapa e eleição especial; especiais e runoffs permanecem no Silver, mas não entram no agregado comparativo de eleições gerais regulares. Consulte [proveniência Senate](docs/data-sources.md).


A integração estadual utiliza o dataset MIT MEDSL *State Precinct-Level Returns 2024* (DOI [10.7910/DVN/DODOBJ](https://doi.org/10.7910/DVN/DODOBJ)), CC0 1.0, distribuído em 51 arquivos ZIP (50 estados + DC) no repositório [MEDSL/2024-elections-official](https://github.com/MEDSL/2024-elections-official). O pipeline fixa o commit, valida cada ZIP pelo Git blob SHA-1, registra SHA-256 e agrega apenas linhas `mode=TOTAL`. Os resultados de governador são estaduais; os de State House e State Senate são distritais. A cobertura é específica de 2024 e depende de quais cargos foram disputados em cada estado.
