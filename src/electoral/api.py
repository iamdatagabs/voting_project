from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .analytics import summary, leaders
app=FastAPI(title="U.S. Electoral Observatory API",version="0.1.0",description="Provenance-aware election data and coverage.")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["GET"],allow_headers=["*"])
@app.get("/health")
def health(): return {"status":"ok","service":"electoral-observatory-api"}
@app.get("/v1/summary")
def get_summary(): return summary()
@app.get("/v1/results")
def get_results(year:int|None=Query(default=None,ge=1788,le=2200),office:str|None=None):
    allowed={"president","senate","house","governor","state_house","state_senate"}
    if office and office not in allowed: raise HTTPException(422,"Unsupported office")
    return {"items":leaders(year,office)}
@app.get("/v1/coverage")
def coverage():
    return {"levels":[{"level":"federal_national","offices":["president"]},{"level":"federal_state","offices":["senate"]},{"level":"federal_district","offices":["house"]},{"level":"state_executive","offices":["governor"]},{"level":"state_legislative","offices":["state_house","state_senate"]}],"data_loaded":summary()["available"]}
