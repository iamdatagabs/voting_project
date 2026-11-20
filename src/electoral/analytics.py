import duckdb
from .config import DATA_DIR, DB_PATH
def parquet_files(layer="silver"): return list((DATA_DIR/layer).glob("*.parquet"))
def connection():
    DB_PATH.parent.mkdir(parents=True,exist_ok=True)
    return duckdb.connect(str(DB_PATH),read_only=False)
def _union_sql(files):
    return " UNION ALL ".join(f"SELECT * FROM read_parquet('{str(p).replace(chr(39),chr(39)*2)}')" for p in files)
def summary():
    files=parquet_files()
    if not files: return {"available":False,"records":0,"years":[],"offices":[],"statuses":{},"message":"Base ainda não ingerida; execute electoral ingest."}
    con=connection()
    try:
        con.execute("CREATE OR REPLACE TEMP VIEW results AS "+_union_sql(files))
        records=con.execute("SELECT count(*) FROM results").fetchone()[0]
        years=[r[0] for r in con.execute("SELECT DISTINCT election_year FROM results ORDER BY 1").fetchall()]
        offices=[r[0] for r in con.execute("SELECT DISTINCT office FROM results ORDER BY 1").fetchall()]
        statuses=dict(con.execute("SELECT result_status,count(*) FROM results GROUP BY 1").fetchall())
        return {"available":True,"records":records,"years":years,"offices":offices,"statuses":statuses}
    finally: con.close()
def leaders(year=None,office=None):
    files=parquet_files()
    if not files:return []
    con=connection()
    try:
        con.execute("CREATE OR REPLACE TEMP VIEW results AS "+_union_sql(files))
        clauses=[]; params=[]
        if year is not None: clauses.append("election_year=?"); params.append(year)
        if office is not None: clauses.append("office=?"); params.append(office)
        where=" WHERE "+" AND ".join(clauses) if clauses else ""
        df=con.execute(f"""SELECT election_year,office,contest_id,geography_name,candidate,party,votes,result_status
        FROM results{where} QUALIFY row_number() OVER
        (PARTITION BY COALESCE(contest_id, CAST(election_year AS VARCHAR) || '-' || office || '-' || geography_id), candidate, party ORDER BY votes DESC)=1
        ORDER BY election_year DESC,office,geography_name,votes DESC LIMIT 500""",params).fetchdf()
        return df.to_dict("records")
    finally: con.close()
def refresh_gold():
    files=parquet_files()
    if not files:return {"rows":0,"message":"No validated datasets ingested."}
    target=DATA_DIR/"gold"/"election_results.parquet"
    con=connection()
    try:
        con.execute("COPY ("+_union_sql(files)+") TO ? (FORMAT PARQUET,COMPRESSION ZSTD)",[str(target)])
        return {"rows":con.execute("SELECT count(*) FROM read_parquet(?)",[str(target)]).fetchone()[0],"datasets":len(files)}
    finally:con.close()
