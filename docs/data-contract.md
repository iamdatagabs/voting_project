# Contrato canônico

Cada linha representa votos de um candidato em uma disputa e unidade geográfica.

| Campo | Semântica |
|---|---|
| election_year | ano do ciclo |
| election_type | general, primary, special etc. |
| office | president, senate, house, governor, state_house, state_senate |
| geography_type | country, state, county, precinct, congressional_district, state_legislative_district, other_reporting_unit |
| geography_id / geography_name | identificador e nome da unidade |
| state_fips | FIPS estadual de dois dígitos, se aplicável |
| district | distrito, quando aplicável |
| candidate / party | candidato e partido conforme fonte |
| votes | votos do candidato, inteiro não negativo |
| total_votes | total da disputa na geografia, se fornecido |
| result_status | preliminary, certified, estimated ou historical_final |
| source_id / source_url | identificador da fonte/versão e URL |
| source_published_at | data de publicação pela fonte |
| extracted_at | timestamp de captura pelo pipeline |

Adaptadores específicos normalizam os cabeçalhos do fornecedor. Não adivinhar equivalências. Ausência permanece nula, nunca zero.

Chave provisória de deduplicação: ano + cargo + tipo/ID geográfico + distrito + candidato + partido. Para produção, ampliar com election_id, contest_id e candidate_id da fonte: nomes não são identificadores universais.
