"""Testes dos helpers de status da UI (badge do header e aviso de sessao reiniciada).

Cobre a logica pura extraida de app/presentation/ui.py:
- `_status_header`: deriva o texto/classe do badge a partir do estado.
- `_aviso_sessao_reiniciada`: decide se deve exibir o aviso de sessao reiniciada.

Regra de negocio: o badge so fica verde (carregado) APOS o processamento do
arquivo; apenas selecionar o ZIP no uploader nao muda o status.
"""

from app.presentation.ui import _aviso_sessao_reiniciada, _status_header


def test_status_header_sem_nada():
    assert _status_header(False) == (False, "Nenhum arquivo carregado", "warn")


def test_status_header_com_dataset():
    assert _status_header(True) == (True, "Dados carregados", "ok")


def test_aviso_sessao_falso_quando_dataset_carregado():
    assert _aviso_sessao_reiniciada(True, False, True) is False


def test_aviso_sessao_falso_quando_arquivo_presente():
    assert _aviso_sessao_reiniciada(False, True, True) is False


def test_aviso_sessao_falso_sem_carga_anterior():
    assert _aviso_sessao_reiniciada(False, False, False) is False


def test_aviso_sessao_verdadeiro_somente_no_reset():
    assert _aviso_sessao_reiniciada(False, False, True) is True