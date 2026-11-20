import typer
from .ingestion import ingest_csv
from .analytics import refresh_gold
app=typer.Typer(help="U.S. Electoral Observatory data operations")
@app.command()
def ingest(url:str,source_id:str,election_year:int,office:str,geography:str,status:str="preliminary"):
    """Download a canonical CSV, preserve raw bytes and validate records."""
    typer.echo(ingest_csv(url,source_id,election_year,office,geography,status))
@app.command()
def build():
    """Build Gold Parquet from validated Silver datasets."""
    typer.echo(refresh_gold())
