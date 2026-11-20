from fastapi.testclient import TestClient
from electoral.api import app
client=TestClient(app)
def test_health():
    r=client.get("/health"); assert r.status_code==200 and r.json()["status"]=="ok"
def test_all_electoral_levels():
    levels=client.get("/v1/coverage").json()["levels"]
    offices={office for level in levels for office in level["offices"]}
    assert offices=={"president","senate","house","governor","state_house","state_senate"}
