"""Monta um ZIP de demonstracao com CSV real + dicionario de dados.

Uso:  uv run python spike/montar_zip_demo.py
"""

from __future__ import annotations

import zipfile
from pathlib import Path

NFE = Path(r"C:\Users\pbena\Documents\Cursos\Insurminds\NFe")
RAIZ = Path(__file__).resolve().parents[1]
SAIDA = RAIZ / "data" / "demo_nfe.zip"


def main() -> None:
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    csv = NFE / "202505_NFe_NotaFiscal.csv"
    dic = RAIZ / "tests" / "fixtures" / "dicionario.json"
    if not csv.exists() or not dic.exists():
        raise SystemExit(f"Arquivo faltando: {csv.exists()=} {dic.exists()=}")

    with zipfile.ZipFile(SAIDA, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(csv, "nf_cabecalho.csv")
        z.write(dic, "dicionario.json")
    print(f"ZIP criado: {SAIDA} ({SAIDA.stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
