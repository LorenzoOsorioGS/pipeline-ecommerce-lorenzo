import sys
from pathlib import Path

# os testes importam o pacote "pipeline" do mesmo jeito que o src/main.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
