import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import httpx, pandas as pd
from .config import DATA_DIR
from .quality import REQUIRED_COLUMNS, validate_records
def ingest_csv(url: str, source_id: str, election_year: int, office: str, geography: str, status: str, timeout: float = 60) -> dict:
    response = httpx.get(url, timeout=timeout, follow_redirects=True); response.raise_for_status()
    payload=response.content; digest=hashlib.sha256(payload).hexdigest(); stamp=datetime.now(timezone.utc).isoformat()
    raw_dir=DATA_DIR/"raw"/source_id.replace("/","_"); raw_dir.mkdir(parents=True,exist_ok=True)
    filename=Path(urlparse(url).path).name or "source.csv"; raw_path=raw_dir/f"{digest[:12]}-{filename}"; raw_path.write_bytes(payload)
    frame=pd.read_csv(raw_path,dtype=str)
    defaults={"election_year":election_year,"election_type":"general","office":office,"geography_type":geography,"result_status":status,"source_id":source_id,"source_url":url,"source_published_at":None,"extracted_at":stamp}
    for column,value in defaults.items():
        if column not in frame.columns: frame[column]=value
    if "votes" in frame: frame["votes"]=pd.to_numeric(frame["votes"].str.replace(",","",regex=False),errors="raise").astype(int)
    if "total_votes" in frame: frame["total_votes"]=pd.to_numeric(frame["total_votes"].str.replace(",","",regex=False),errors="coerce").astype("Int64")
    missing=REQUIRED_COLUMNS-set(frame.columns)
    if missing: raise ValueError(f"CSV missing canonical columns: {sorted(missing)}")
    records=validate_records(frame.where(pd.notna(frame),None).to_dict("records")); clean=pd.DataFrame(records)
    for layer in ("bronze","silver"):
        clean.to_parquet(DATA_DIR/layer/f"{source_id.replace('/','_')}-{election_year}-{office}.parquet",index=False)
    manifest={"source_id":source_id,"url":url,"sha256":digest,"raw_path":str(raw_path),"rows":len(clean),"extracted_at":stamp,"status":status,"office":office,"geography":geography}
    (DATA_DIR/"bronze"/f"{source_id.replace('/','_')}-{election_year}-{office}.manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest
