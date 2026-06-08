"""Entry point — runs the Streamlit app."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    app = Path(__file__).parent / "app" / "main.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app)],
        check=True,
    )
