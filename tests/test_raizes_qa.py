"""
Suíte de testes automatizados (Pytest) cobrindo os cenários críticos
definidos no Plano de Testes da Rede Raízes do Nordeste.
"""

import pytest
from src.raizes_domain import (
    AcessoNegadoUnidadeError,
    ConsentimentoObrigatorioError,
    EstoqueInsuficienteError,
    GatewayPagamentoMock,
    ItemCardapio,
    ItemSazonalIndisponivelError,
    SistemaRaizesQA,
    StatusPedido,
    TransicaoEstadoInvalidaError,
)


@pytest.fixture
def sistema_base():
    sistema = SistemaRaizesQA(gateway=GatewayPagamentoMock("APROVADO"))
    sistema.cadastrar_item(ItemCardapio("TAPIOCA-CARNE", "Tapioca Carne de Sol", 18.0))
    sistema.cadastrar_item(ItemCardapio("CUSCUZ-ESP", "Cuscuz Recheado", 16.0))
    sistema.cadastrar_item(ItemCardapio("CANJICA-JUN", "Canjica Junina", 12.0, mes_sazonal=6))
    sistema.definir_estoque("REC-01", "TAPIOCA-CARNE", 10)
    sistema.definir_estoque("REC-01", "CUSCUZ-ESP", 1)
    sistema.definir_estoque("REC-01", "CANJICA-JUN", 20)
    return sistema


def test_ct01_pedido_completo_app_pickup(sistema_base):
    pedido = sistema_base.realizar_pedido("REC-01", "APP_PICKUP", "TAPIOCA-CARNE", 1, "KEY-001")
    assert pedido.status == StatusPedido.CONFIRMADO
    assert pedido.valor_total == 18.0
    assert sistema_base.consultar_estoque("REC-01", "TAPIOCA-CARNE") == 9


def test_ct03_bloqueio_item_sazonal_fora_de_epoca(sistema_base):
    with pytest.raises(ItemSazonalIndisponivelError):
        sistema_base.realizar_pedido("REC-01", "TOTEM", "CANJICA-JUN", 1, "KEY-002", mes_atual=11)


def test_ct04_concorrencia_ultima_unidade_estoque(sistema_base):
    pedido1 = sistema_base.realizar_pedido("REC-01", "APP", "CUSCUZ-ESP", 1, "KEY-003")
    assert pedido1.status == StatusPedido.CONFIRMADO
    with pytest.raises(EstoqueInsuficienteError):
        sistema_base.realizar_pedido("REC-01", "BALCAO", "CUSCUZ-ESP", 1, "KEY-004")


def test_ct05_pagamento_recusado_libera_estoque():
    sistema = SistemaRaizesQA(gateway=GatewayPagamentoMock("RECUSADO"))
    sistema.cadastrar_item(ItemCardapio("TAPIOCA-CARNE", "Tapioca Carne de Sol", 18.0))
    sistema.definir_estoque("REC-01", "TAPIOCA-CARNE", 5)

    pedido = sistema.realizar_pedido("REC-01", "APP", "TAPIOCA-CARNE", 2, "KEY-005")
    assert pedido.status == StatusPedido.NAO_PAGO
    assert sistema.consultar_estoque("REC-01", "TAPIOCA-CARNE") == 5


def test_ct06_timeout_gateway_mantem_aguardando_confirmacao():
    sistema = SistemaRaizesQA(gateway=GatewayPagamentoMock("TIMEOUT"))
    sistema.cadastrar_item(ItemCardapio("TAPIOCA-CARNE", "Tapioca Carne de Sol", 18.0))
    sistema.definir_estoque("REC-01", "TAPIOCA-CARNE", 5)

    pedido = sistema.realizar_pedido("REC-01", "TOTEM", "TAPIOCA-CARNE", 1, "KEY-006")
    assert pedido.status == StatusPedido.AGUARDANDO_CONFIRMACAO


def test_ct07_idempotencia_clique_duplo_nao_duplica(sistema_base):
    p1 = sistema_base.realizar_pedido("REC-01", "APP", "TAPIOCA-CARNE", 1, "KEY-DUP")
    p2 = sistema_base.realizar_pedido("REC-01", "APP", "TAPIOCA-CARNE", 1, "KEY-DUP")

    assert p1.pedido_id == p2.pedido_id
    assert sistema_base.gateway.chamadas == 1
    assert sistema_base.consultar_estoque("REC-01", "TAPIOCA-CARNE") == 9


def test_ct08_cadastro_bloqueado_sem_consentimento_lgpd(sistema_base):
    with pytest.raises(ConsentimentoObrigatorioError):
        sistema_base.cadastrar_cliente_fidelidade("Maria Silva", "81999990000", aceite_privacidade=False)


def test_ct09_anonimizacao_e_filtro_marketing_lgpd(sistema_base):
    c1 = sistema_base.cadastrar_cliente_fidelidade("Maria", "81999990001", True, opt_in_marketing=True)
    c2 = sistema_base.cadastrar_cliente_fidelidade("Joao", "81999990002", True, opt_in_marketing=False)

    assert len(sistema_base.listar_contatos_campanha()) == 1
    sistema_base.anonimizar_cliente(c1.cliente_id)
    assert c1.anonimizado is True
    assert c1.telefone == "00000000000"
    assert len(sistema_base.listar_contatos_campanha()) == 0
    assert c2.cliente_id != c2.telefone


def test_ct10_bloqueio_acesso_cruzado_entre_unidades(sistema_base):
    sistema_base.realizar_pedido("REC-01", "APP", "TAPIOCA-CARNE", 1, "KEY-010")
    relatorio_ok = sistema_base.consultar_relatorio_unidade("REC-01", "REC-01")
    assert relatorio_ok["total_pedidos"] == 1

    with pytest.raises(AcessoNegadoUnidadeError):
        sistema_base.consultar_relatorio_unidade("FOR-02", "REC-01")


def test_ct11_auditoria_desconto_e_transicao_estado(sistema_base):
    sistema_base.realizar_pedido(
        "REC-01", "BALCAO", "TAPIOCA-CARNE", 1, "KEY-011",
        desconto_percentual=20.0, gerente_autorizador="GER-CARLOS"
    )
    assert len(sistema_base.auditoria) == 1
    assert sistema_base.auditoria[0]["autorizador"] == "GER-CARLOS"

    sistema_base.atualizar_status_pedido("KEY-011", StatusPedido.CANCELADO)
    with pytest.raises(TransicaoEstadoInvalidaError):
        sistema_base.atualizar_status_pedido("KEY-011", StatusPedido.EM_PREPARO)
