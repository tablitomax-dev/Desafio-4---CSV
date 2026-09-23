"""Publicacao do dataset: valida consistencia e gerencia o ciclo de vida da conexao.

O `DatasetPublisher` marca o contexto como `ready` (apos validar consistencia)
e, ao trocar o ativo, fecha a conexao do dataset anterior. A troca na UI deve
substituir o `DatasetContext` inteiro de uma vez.
"""

from __future__ import annotations

from app.dataset.context import DatasetContext


class DatasetPublisher:
    """Finaliza e troca o dataset ativo, fechando a conexao anterior."""

    def publicar(self, contexto: DatasetContext) -> DatasetContext:
        if not contexto.consistente():
            raise ValueError(
                "Contexto inconsistente: dataset_id divergente entre os objetos."
            )
        contexto.status = "ready"
        return contexto

    def trocar_ativo(
        self, atual: DatasetContext | None, novo: DatasetContext
    ) -> DatasetContext:
        """Publica o novo contexto e fecha a conexao do anterior (se houver)."""
        novo = self.publicar(novo)
        if atual is not None and atual.client is not novo.client:
            atual.status = "closed"
            atual.client.close()
        return novo
