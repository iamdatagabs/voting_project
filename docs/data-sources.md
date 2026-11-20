# Proveniência e ingestão — MIT County Presidential Returns

## Fonte e resolução de versão

- Dataset: MIT Election Data and Science Lab, *County Presidential Election Returns 2000–2024*.
- Identificador persistente: DOI 10.7910/DVN/VOQCHQ.
- Repositório: Harvard Dataverse.
- Licença declarada: CC0 1.0.
- O conector consulta um espelho versionado que declara a atribuição MIT/Harvard Dataverse e validação da fonte. A cada execução, lê os metadados, exige validação `pass`, confirma o DOI e baixa a versão explicitamente fixada na URL. O espelho publica versão, licença e atribuição da fonte; o SHA-256 local identifica exatamente os bytes baixados.

## Execução reproduzível

```bash
python -m pip install pandas pyarrow httpx
python scripts/ingest_mit_countypres.py
```

O workflow `.github/workflows/data-refresh.yml` executa semanalmente e também aceita execução manual. Ele baixa o arquivo original, calcula SHA-256 local, valida a atribuição e o estado de validação do espelho, valida o esquema e a consistência do denominador por unidade/ciclo, e gera:
- `data/raw/mit_election_lab.county_president/`: bytes originais;
- `data/silver/mit_county_president_2000_2024.parquet`: observações canônicas;
- `data/silver/mit_county_president_2000_2024.manifest.json`: manifesto de proveniência;
- `apps/web/data/presidential-timeseries.json`: agregados estaduais e nacionais para o Pages.

As camadas brutas e Parquet são artefatos de execução, não são commitadas. O JSON publicado contém agregados e metadados de origem.

## Regras de transformação

1. O arquivo de origem é tab-delimited; colunas de FIPS são lidas como texto para preservar zeros à esquerda.
2. Contagens de votos são convertidas numericamente; contagens nulas de candidato são excluídas e contabilizadas no manifesto, nunca imputadas como zero.
3. A chave territorial usa o identificador county quando disponível; unidades sem county ID recebem identificador determinístico a partir de estado e unit_id. O contrato distingue county de outras unidades de reporte.
4. O denominador `total_votes` é deduplicado por county e ciclo antes de agregar para estado e país. A repetição do total em cada linha de candidato não pode inflar o denominador.
5. Uma inconsistência de denominador dentro do mesmo county/ciclo interrompe a ingestão.
6. A participação partidária é `Σ votos do partido / Σ total_votes dos counties`. Não é taxa de comparecimento eleitoral da população elegível.
7. A série é esparsa nos ciclos em que um partido não possui observação; ausência não equivale a zero.

## Limites de interpretação

A primeira integração cobre somente a eleição presidencial e os retornos por county publicados na fonte. Ela não preenche automaticamente Senate, House, governadores ou legislativos estaduais. A cobertura adicional requer conectores específicos, identificação de contests, district crosswalks e validação independente. A fonte é um espelho versionado e atribuído ao MIT Election Data and Science Lab/Harvard Dataverse; a validação do espelho e o hash do download são registrados. O status `certified` representa a classificação do retorno histórico na fonte e não substitui consulta a certificados oficiais de cada jurisdição.

O arquivo bruto usado no pipeline é servido por uma API versionada de distribuição, com versão e validação expostas em metadados. O conteúdo é atribuído ao dataset original do MIT; o hash local registra a cópia efetivamente processada. A API de distribuição não é o publisher original.

## Citação

MIT Election Data and Science Lab, 2018, "County Presidential Election Returns 2000-2024", https://doi.org/10.7910/DVN/VOQCHQ, Harvard Dataverse, V20. Licença CC0 1.0.
