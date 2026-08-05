"""Entry point — runs the FastAPI voice app (server.py + static/).

This is the app that is deployed: uvicorn serves the API and the static
frontend from a single process, matching Procfile and render.yaml.

The older Streamlit chat UI still lives in app/main.py. It is not part of the
deployment and needs an extra dependency:

    pip install streamlit
    streamlit run app/main.py
"""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "server:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
            "--reload",
        ],
        check=True,
    )
