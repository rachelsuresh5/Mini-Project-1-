"""Run the whole pipeline end to end: clean -> load into SQL -> SQL queries -> notebooks.

Usage (from the project root):
    python run_pipeline.py            # everything
    python run_pipeline.py --skip-eda # skip re-executing the notebook
Then launch the dashboard with:
    streamlit run dashboard/Home.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def step(title: str, cmd: list[str]) -> None:
    print(f"\n=== {title} ===")
    subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    py = sys.executable
    step("1/4 Clean raw CSVs", [py, "src/clean.py"])
    step("2/4 Load into SQLite with SQLAlchemy + test JOIN", [py, "src/build_db.py"])
    step("3/4 Run SQL analysis queries", [py, "src/run_queries.py"])
    if "--skip-eda" not in sys.argv:
        print("\n=== 4/4 Execute notebooks and export HTML reports ===")
        for nb, out in [("00_load_clean_and_sql", "load_clean_report"), ("01_eda", "eda_report")]:
            subprocess.run([py, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
                            "--inplace", f"notebooks/{nb}.ipynb"], cwd=ROOT, check=True)
            subprocess.run([py, "-m", "jupyter", "nbconvert", "--to", "html",
                            f"notebooks/{nb}.ipynb", "--output-dir", "reports", "--output", out],
                           cwd=ROOT, check=True)
    print("\nDone. Start the dashboard with:  streamlit run dashboard/Home.py")
