"""Avaliacao de qualidade: aplica a politica de severidade e decide publicacao.

- `blocking`: impede a publicacao do dataset (ex.: CSV ilegivel, coluna
  obrigatoria ausente, chave vazia).
- `warning`: reportado, mas nao bloqueia (ex.: item orfao, divergencia textual).
- `info`: apenas informativo.
"""

from __future__ import annotations

from app.contracts import Issue, QualityReport


class QualityEvaluator:
    """Consolida issues e metricas em um `QualityReport`."""

    def avaliar(
        self, issues: list[Issue], metricas: dict[str, int | float | str | None]
    ) -> QualityReport:
        return QualityReport(issues=issues, metricas=metricas)

    def pode_publicar(self, report: QualityReport) -> bool:
        """True se nao ha issues bloqueantes."""
        return not report.bloqueantes
