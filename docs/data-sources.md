# Proveniência e ingestão — MIT County Presidential Returns

## Fonte e resolução de versão

- Dataset: MIT Election Data and Science Lab, *County Presidential Election Returns 2000–2024*.
- Identificador persistente: DOI 10.7910/DVN/VOQCHQ.
- Repositório: Harvard Dataverse.
- Licença declarada: CC0 1.0.
- O conector consulta a API Dataverse pelo DOI em cada execução e resolve o arquivo associado a `latestVersion`; o identificador de arquivo não é fixado no código.

## Execução reproduzível

```bash
python -m pip install pandas pyarrow httpx
python scripts/ingest_mit_countypres.py
```

O workflow `.github/workflows/data-refresh.yml` executa semanalmente e também aceita execução manual. Ele baixa o arquivo original, verifica o MD5 informado pelo publisher (quando presente), calcula SHA-256 local, valida o esquema e a consistência do denominador por county/ciclo, e gera:
- `data/raw/mit_election_lab.county_president/`: bytes originais;
- `data/silver/mit_county_president_2000_2024.parquet`: observações canônicas;
- `data/silver/mit_county_president_2000_2024.manifest.json`: manifesto de proveniência;
- `apps/web/data/presidential-timeseries.json`: agregados estaduais e nacionais para o Pages.

As camadas brutas e Parquet são artefatos de execução, não são commitadas. O JSON publicado contém agregados e metadados de origem.

## Regras de transformação

1. O arquivo de origem é tab-delimited; colunas de FIPS são lidas como texto para preservar zeros à esquerda.
2. Contagens de votos são convertidas numericamente; contagens nulas de candidato são excluídas e contabilizadas no manifesto, nunca imputadas como zero.
3. A chave territorial usa county FIPS quando disponível; unidades sem FIPS recebem identificador determinístico composto por estado e nome da unidade.
4. O denominador `total_votes` é deduplicado por county e ciclo antes de agregar para estado e país. A repetição do total em cada linha de candidato não pode inflar o denominador.
5. Uma inconsistência de denominador dentro do mesmo county/ciclo interrompe a ingestão.
6. A participação partidária é `Σ votos do partido / Σ total_votes dos counties`. Não é taxa de comparecimento eleitoral da população elegível.
7. A série é esparsa nos ciclos em que um partido não possui observação; ausência não equivale a zero.

## Limites de interpretação

A primeira integração cobre somente a eleição presidencial e os retornos por county publicados na fonte. Ela não preenche automaticamente Senate, House, governadores ou legislativos estaduais. A cobertura adicional requer conectores específicos, identificação de contests, district crosswalks e validação independente. O status `certified` indica a natureza da série histórica publicada pelo dataset; não substitui a consulta a certificados oficiais de cada jurisdição.

## Citação

MIT Election Data and Science Lab, 2018, "County Presidential Election Returns 2000-2024", https://doi.org/10.7910/DVN/VOQCHQ, Harvard Dataverse, V20. Licença CC0 1.0.
