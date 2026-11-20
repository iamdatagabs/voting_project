# Proveniência e ingestão — MIT County Presidential Returns

## Fonte e resolução de versão

- Dataset: MIT Election Data and Science Lab, *County Presidential Election Returns 2000–2024*.
- Identificador persistente: DOI 10.7910/DVN/VOQCHQ.
- Repositório: Harvard Dataverse.
- Licença declarada: CC0 1.0.
- O conector consulta um espelho versionado que declara a atribuição MIT/Harvard Dataverse e validação da fonte. A cada execução, lê os metadados, exige validação `pass`, confirma o DOI e baixa a versão explicitamente fixada na URL. O espelho publica versão, licença e atribuição da fonte; o SHA-256 local identifica exatamente os bytes baixados. O hash do arquivo bruto upstream é registrado separadamente e não é confundido com o hash do CSV distribuído.

## Execução reproduzível

```bash
python -m pip install pandas pyarrow httpx
python scripts/ingest_mit_countypres.py
```

O workflow `.github/workflows/data-refresh.yml` executa semanalmente e também aceita execução manual. Ele baixa o CSV disponibilizado pelo espelho, calcula SHA-256 local, valida a atribuição e o estado de validação do espelho, valida o esquema e a consistência do denominador por unidade/ciclo, e gera:
- `data/raw/mit_election_lab.county_president/`: bytes originais;
- `data/bronze/mit_county_president_2000_2024.parquet`: registros de origem normalizados, preservando nulos;
- `data/silver/mit_county_president_2000_2024.parquet`: observações canônicas validadas;
- `data/silver/mit_county_president_2000_2024.manifest.json`: manifesto de proveniência;
- `apps/web/data/presidential-timeseries.json`: agregados estaduais e nacionais para o Pages.

As camadas brutas e Parquet são artefatos de execução, não são commitadas. O JSON publicado contém agregados e metadados de origem.
O workflow também publica um artefato de execução com Raw, Bronze, Silver e manifesto, retido por 90 dias no GitHub Actions. Somente o JSON agregado é commitado para o Pages; os arquivos brutos e Parquet não poluem o histórico Git.


## Regras de transformação

1. O arquivo distribuído é CSV delimitado por vírgulas; colunas de FIPS são lidas como texto para preservar zeros à esquerda.
2. Contagens de votos são convertidas numericamente; contagens nulas de candidato são excluídas e contabilizadas no manifesto, nunca imputadas como zero.
3. A chave territorial usa o identificador county quando disponível; unidades sem county ID recebem identificador determinístico a partir de estado e unit_id. O contrato distingue county de outras unidades de reporte.
4. O denominador `total_votes` é deduplicado por county e ciclo antes de agregar para estado e país. A repetição do total em cada linha de candidato não pode inflar o denominador.
5. Uma inconsistência de denominador dentro do mesmo county/ciclo interrompe a ingestão.
6. A participação partidária é `Σ votos do partido / Σ total_votes dos counties`. Não é taxa de comparecimento eleitoral da população elegível.
7. A série é esparsa nos ciclos em que um partido não possui observação; ausência não equivale a zero.

## Limites de interpretação

A primeira integração cobre somente a eleição presidencial e os retornos por county publicados na fonte. Ela não preenche automaticamente Senate, House, governadores ou legislativos estaduais. A cobertura adicional requer conectores específicos, identificação de contests, district crosswalks e validação independente. A fonte é um espelho versionado e atribuído ao MIT Election Data and Science Lab/Harvard Dataverse; a validação do espelho e o hash do download são registrados. O status `historical_final` representa retornos históricos finais conforme publicados no dataset, sem afirmar que o pipeline verificou individualmente certificados oficiais de cada jurisdição.

O arquivo bruto usado no pipeline é servido por uma API versionada de distribuição, com versão e validação expostas em metadados. O conteúdo é atribuído ao dataset original do MIT; o hash local registra a cópia efetivamente processada. A API de distribuição não é o publisher original.

## Citação

MIT Election Data and Science Lab, 2018, "County Presidential Election Returns 2000-2024", https://doi.org/10.7910/DVN/VOQCHQ, Harvard Dataverse, V20. Licença CC0 1.0.


## Segunda integração — U.S. House 1976–2024

- Dataset: MIT Election Data and Science Lab, *U.S. House 1976–2024*.
- DOI: 10.7910/DVN/IG0UN2; Harvard Dataverse, versão 15; licença CC0 1.0.
- Cobertura: retornos por distrito congressional, incluindo eleições especiais; cada linha representa um candidato em uma linha partidária (*ballot line*).
- O conector consulta os metadados do espelho versionado, exige validação `pass`, confere DOI/licença e fixa a versão no URL do download. O SHA-256 identifica os bytes baixados.
- O identificador `contest_id` incorpora ano, estado, distrito, etapa, eleição especial e runoff. `source_row_id` preserva a identificação da linha original. Isso evita colapsar eleições especiais e regulares no mesmo distrito.
- `candidatevotes` nulo é preservado em Bronze e excluído de Silver, com contagem no manifesto; não é convertido em zero. Linhas `unofficial` são marcadas como `preliminary`; as demais como `historical_final`.
- O explorador público agrega o voto por estado e partido apenas nas eleições gerais regulares, excluindo primárias, especiais e runoffs. O denominador `totalvotes` é contado uma vez por contest, não uma vez por candidato. A participação resultante é participação nos votos reportados, não turnout de eleitores elegíveis.
- Artefatos: `data/raw/mit_election_lab.us_house_1976_2024/`, `data/bronze/mit_us_house_1976_2024.parquet`, `data/silver/mit_us_house_1976_2024.parquet`, manifesto e `apps/web/data/house-timeseries.json`.

Citação recomendada: MIT Election Data and Science Lab, 2017, "U.S. House 1976–2024", https://doi.org/10.7910/DVN/IG0UN2, Harvard Dataverse, V15, UNF:6:cIJWG41N8qe3Kyf7oKuPdw== [fileUNF].

**Limite de cobertura:** a integração House é distrital e não contém retornos precinct-level. O dataset também inclui eleições especiais; a série comparativa publicada seleciona somente eleições gerais regulares para reduzir dupla contagem e não deve ser confundida com a totalidade das disputas ocorridas em cada ano.


## Terceira integração — U.S. Senate statewide 1976–2024

- Dataset: MIT Election Data and Science Lab, *U.S. Senate statewide 1976–2024*.
- DOI: 10.7910/DVN/PEJ5QU; Harvard Dataverse V8; licença CC0 1.0.
- Cobertura: retornos estaduais de candidatos ao Senado entre 1976 e 2024, incluindo eleições especiais e runoffs; os dados contêm linhas por candidato e ballot line/modo.
- O conector consulta metadados versionados, exige validação `pass`, confirma DOI e licença e fixa a versão no URL de download. O SHA-256 local identifica exatamente o arquivo processado.
- Somente linhas `mode=TOTAL` são usadas para a tabela canônica. Somar linhas TOTAL junto com subtotais de modos de votação produziria dupla contagem. A execução falha explicitamente se a fonte deixar de fornecer linhas TOTAL.
- `contest_id` incorpora ano, estado, etapa e indicador de eleição especial. Assim, a eleição regular, uma especial e eventual runoff não colidem. A etapa é preservada em `election_type`.
- Linhas sem votos de candidato são preservadas em Bronze e excluídas de Silver, com contagem no manifesto; ausência nunca é convertida em zero. Linhas sinalizadas como `unofficial` são classificadas como `preliminary`; as demais como `historical_final`.
- O explorador público agrega apenas disputas de eleição geral regulares (`stage=GEN`, não especiais). Especiais e runoffs continuam disponíveis nas camadas analíticas, mas não são somados ao comparativo estadual regular. O denominador `totalvotes` é contado uma vez por contest.
- Artefatos: `data/raw/mit_election_lab.us_senate_statewide_1976_2024/`, `data/bronze/mit_us_senate_1976_2024.parquet`, `data/silver/mit_us_senate_1976_2024.parquet`, manifesto e `apps/web/data/senate-timeseries.json`.

Citação recomendada: MIT Election Data and Science Lab, 2017, "U.S. Senate statewide 1976–2024", https://doi.org/10.7910/DVN/PEJ5QU, Harvard Dataverse, V8, UNF:6:jRgjMTzXKaB+psjQ9tTqMQ== [fileUNF].

**Limite de interpretação:** participação nos votos reportados não equivale a turnout da população elegível. A integração não faz validação independente dos certificados oficiais de cada estado; `historical_final` reflete o status da base histórica de origem.


## Quarta integração — eleições estaduais 2024

- Fonte: MIT Election Data and Science Lab, *State Precinct-Level Returns 2024*, DOI 10.7910/DVN/DODOBJ; licença CC0 1.0.
- Distribuição operacional: 51 ZIPs (50 estados + District of Columbia) no repositório [MEDSL/2024-elections-official](https://github.com/MEDSL/2024-elections-official), diretório `individual_states`. O conjunto publicado pelo MIT cobre mais de 54 mil candidatos, 12 mil cargos e 200 mil precincts; a heterogeneidade estadual é explicitada pelo próprio laboratório. <https://electionlab.mit.edu/articles/inside-2024-precinct-project>
- O pipeline resolve o commit do repositório, fixa os downloads nesse SHA e confere o Git blob SHA-1 de cada ZIP antes de processá-lo. Também grava SHA-256 local, tamanho, nome do arquivo e caminho Raw no manifesto.
- O adaptador filtra somente `GOVERNOR`, `STATE HOUSE` e `STATE SENATE`. Mantém observações brutas desses cargos em Bronze e seleciona `mode=TOTAL` para Silver, evitando dupla contagem quando o arquivo contém totais e modalidades separadas.
- Governador é agregado por estado; State House e State Senate são agregados por distrito legislativo. `contest_id` inclui ano, cargo, estado, distrito (quando aplicável) e data da eleição. Candidatos/linhas partidárias são agregados entre precincts antes da validação canônica.
- Votos ausentes (`*`) e negativos são preservados em Bronze e excluídos de Silver, com contagem explícita. Distritos legislativos ausentes também não são imputados; o adaptador os exclui do agregado distrital e registra essa limitação.
- O JSON público é um agregado de 2024 por cargo, estado, distrito e partido. Não é uma série temporal e não implica cobertura de todos os estados em todos os cargos.
- Artefatos: `data/raw/mit_medsl_state_precinct_2024/*.zip`, `data/bronze/mit_state_offices_precinct_2024.parquet`, `data/silver/mit_state_offices_2024.parquet`, manifesto e `apps/web/data/state-offices-2024.json`.

Citação: MIT Election Data and Science Lab, 2026, "State Precinct-Level Returns 2024", https://doi.org/10.7910/DVN/DODOBJ, Harvard Dataverse, V1. Distribuição por estado: "Precinct-Level Returns 2024 by Individual State", https://doi.org/10.7910/DVN/NYTPDU, Harvard Dataverse, V1.

**Caveats:** o MIT documenta heterogeneidade de fontes estaduais, dados suprimidos, casos de ausência de distrito, voto por fusão partidária em New York, e possíveis artefatos de correção. O painel mantém as linhas partidárias conforme MEDSL; a participação é calculada sobre os votos reportados no contest, não é turnout de eleitores elegíveis. Não há reconciliação independente com os certificados oficiais estaduais nesta integração. O filtro `mode=TOTAL` é deliberado para impedir dupla contagem; observações sem TOTAL não entram no comparativo.
