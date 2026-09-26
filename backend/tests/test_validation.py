import numpy as np
import pytest

from app.services.validation import error_metrics, idw_points, leave_one_out


def test_idw_e_exato_sobre_a_estacao():
    xy = np.array([[0, 0], [10, 0], [0, 10]])
    z = np.array([5.0, 20.0, 40.0])
    assert idw_points(xy, z, np.array([[10, 0]]), 2, 3)[0] == pytest.approx(20.0)


def test_valor_conferido_a_mao():
    # O alvo fica a 1 e a 3 unidades das estações: com power 2, pesos 1 e 1/9.
    xy = np.array([[0, 0], [4, 0]])
    z = np.array([10.0, 50.0])
    esperado = (10 * 1 + 50 / 9) / (1 + 1 / 9)
    assert idw_points(xy, z, np.array([[1, 0]]), 2, 2)[0] == pytest.approx(esperado)


def test_vizinhos_limitam_a_busca():
    # Com um vizinho só, o IDW vira "vizinho mais próximo": a estação
    # distante, com 999 mm, não pode puxar a estimativa.
    xy = np.array([[0, 0], [4, 0], [100, 0]])
    z = np.array([10.0, 50.0, 999.0])
    assert idw_points(xy, z, np.array([[1, 0]]), 2, 1)[0] == pytest.approx(10.0)


def test_leave_one_out_tira_a_propria_estacao():
    xy = np.array([[0, 0], [1, 0], [2, 0]])
    z = np.array([10.0, 20.0, 30.0])
    estimado = leave_one_out(xy, z, power=2, neighbors=2)
    # Estação 0 vê a 1 (d=1) e a 2 (d=2): (20·1 + 30·¼) / 1,25 = 22.
    assert estimado.tolist() == pytest.approx([22.0, 20.0, 18.0])


def test_estacoes_coincidentes_usam_o_valor_medido():
    xy = np.array([[0, 0], [0, 0], [5, 5]])
    z = np.array([10.0, 12.0, 99.0])
    estimado = leave_one_out(xy, z, power=2, neighbors=2)
    assert estimado[:2].tolist() == pytest.approx([12.0, 10.0])


def test_metricas_usam_estimado_menos_observado():
    # Exemplo do projeto: observado 38, estimado 34, erro -4.
    m = error_metrics(np.array([38.0, 10.0]), np.array([34.0, 12.0]))
    assert m["bias"] == pytest.approx(-1.0)
    assert m["mae"] == pytest.approx(3.0)
    assert m["rmse"] == pytest.approx(np.sqrt((16 + 4) / 2))
