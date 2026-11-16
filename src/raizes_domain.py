"""
Módulo de domínio simulado para validação de regras de negócio e qualidade (QA)
do sistema integrado da Rede Raízes do Nordeste.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import uuid


class ErroNegocio(Exception):
    """Exceção base para violações de regra de negócio."""


class EstoqueInsuficienteError(ErroNegocio):
    pass


class ItemSazonalIndisponivelError(ErroNegocio):
    pass


class ConsentimentoObrigatorioError(ErroNegocio):
    pass


class AcessoNegadoUnidadeError(ErroNegocio):
    pass


class TransicaoEstadoInvalidaError(ErroNegocio):
    pass


class StatusPedido(str, Enum):
    AGUARDANDO_CONFIRMACAO = "AGUARDANDO_CONFIRMACAO"
    CONFIRMADO = "CONFIRMADO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    NAO_PAGO = "NAO_PAGO"
    CANCELADO = "CANCELADO"


TRANSICOES_VALIDAS = {
    StatusPedido.AGUARDANDO_CONFIRMACAO: {StatusPedido.CONFIRMADO, StatusPedido.NAO_PAGO, StatusPedido.CANCELADO},
    StatusPedido.CONFIRMADO: {StatusPedido.EM_PREPARO, StatusPedido.CANCELADO},
    StatusPedido.EM_PREPARO: {StatusPedido.PRONTO, StatusPedido.CANCELADO},
    StatusPedido.PRONTO: {StatusPedido.ENTREGUE},
    StatusPedido.ENTREGUE: set(),
    StatusPedido.NAO_PAGO: set(),
    StatusPedido.CANCELADO: set(),
}


@dataclass
class ItemCardapio:
    item_id: str
    nome: str
    preco: float
    mes_sazonal: int | None = None  # Ex.: 6 para itens juninos


@dataclass
class ClienteFidelidade:
    cliente_id: str
    nome: str
    telefone: str
    aceite_privacidade: bool
    opt_in_marketing: bool = False
    faixa_etaria: str | None = None
    pontos: int = 0
    anonimizado: bool = False


@dataclass
class Pedido:
    pedido_id: str
    unidade_id: str
    canal: str
    item_id: str
    quantidade: int
    valor_total: float
    chave_idempotencia: str
    status: StatusPedido
    criado_em: str = field(default_factory=lambda: datetime.now().isoformat())


class GatewayPagamentoMock:
    """Simulador desacoplado de gateway externo de pagamento."""

    def __init__(self, modo: str = "APROVADO"):
        if modo not in {"APROVADO", "RECUSADO", "TIMEOUT"}:
            raise ValueError("Modo de simulacao invalido.")
        self.modo = modo
        self.chamadas = 0

    def cobrar(self, valor: float, chave_idempotencia: str) -> str:
        self.chamadas += 1
        return self.modo


class SistemaRaizesQA:
    """Orquestrador de regras de negócio para testes automatizados."""

    def __init__(self, gateway: GatewayPagamentoMock | None = None):
        self.gateway = gateway or GatewayPagamentoMock("APROVADO")
        self.cardapio: dict[str, ItemCardapio] = {}
        self.estoque_por_unidade: dict[str, dict[str, int]] = {}
        self.pedidos_por_chave: dict[str, Pedido] = {}
        self.clientes: dict[str, ClienteFidelidade] = {}
        self.auditoria: list[dict] = []

    def cadastrar_item(self, item: ItemCardapio) -> None:
        self.cardapio[item.item_id] = item

    def definir_estoque(self, unidade_id: str, item_id: str, quantidade: int) -> None:
        self.estoque_por_unidade.setdefault(unidade_id, {})[item_id] = quantidade

    def consultar_estoque(self, unidade_id: str, item_id: str) -> int:
        return self.estoque_por_unidade.get(unidade_id, {}).get(item_id, 0)

    def realizar_pedido(
        self,
        unidade_id: str,
        canal: str,
        item_id: str,
        quantidade: int,
        chave_idempotencia: str,
        mes_atual: int = 11,
        desconto_percentual: float = 0.0,
        gerente_autorizador: str | None = None,
    ) -> Pedido:
        if chave_idempotencia in self.pedidos_por_chave:
            return self.pedidos_por_chave[chave_idempotencia]

        item = self.cardapio[item_id]
        if item.mes_sazonal is not None and item.mes_sazonal != mes_atual:
            raise ItemSazonalIndisponivelError("Item indisponivel fora do periodo sazonal.")

        saldo = self.consultar_estoque(unidade_id, item_id)
        if saldo < quantidade or quantidade <= 0:
            raise EstoqueInsuficienteError("Produto esgotado nesta unidade.")

        # Reserva atômica de estoque antes da chamada externa
        self.estoque_por_unidade[unidade_id][item_id] = saldo - quantidade

        valor_bruto = item.preco * quantidade
        valor_final = round(valor_bruto * (1.0 - desconto_percentual / 100.0), 2)

        if desconto_percentual > 0:
            self.auditoria.append({
                "tipo": "DESCONTO_MANUAL",
                "unidade_id": unidade_id,
                "autorizador": gerente_autorizador or "NAO_INFORMADO",
                "valor_original": valor_bruto,
                "desconto_percentual": desconto_percentual,
                "data_hora": datetime.now().isoformat(),
            })

        retorno = self.gateway.cobrar(valor_final, chave_idempotencia)
        if retorno == "APROVADO":
            status = StatusPedido.CONFIRMADO
        elif retorno == "RECUSADO":
            # Libera a reserva quando o pagamento falha
            self.estoque_por_unidade[unidade_id][item_id] += quantidade
            status = StatusPedido.NAO_PAGO
        else:
            status = StatusPedido.AGUARDANDO_CONFIRMACAO

        pedido = Pedido(
            pedido_id=f"PED-{uuid.uuid4().hex[:8].upper()}",
            unidade_id=unidade_id,
            canal=canal,
            item_id=item_id,
            quantidade=quantidade,
            valor_total=valor_final,
            chave_idempotencia=chave_idempotencia,
            status=status,
        )
        self.pedidos_por_chave[chave_idempotencia] = pedido
        return pedido

    def atualizar_status_pedido(self, chave_idempotencia: str, novo_status: StatusPedido) -> Pedido:
        pedido = self.pedidos_por_chave[chave_idempotencia]
        if novo_status not in TRANSICOES_VALIDAS[pedido.status]:
            raise TransicaoEstadoInvalidaError(
                f"Transicao invalida de {pedido.status.value} para {novo_status.value}."
            )
        pedido.status = novo_status
        return pedido

    def cadastrar_cliente_fidelidade(
        self,
        nome: str,
        telefone: str,
        aceite_privacidade: bool,
        opt_in_marketing: bool = False,
        faixa_etaria: str | None = None,
    ) -> ClienteFidelidade:
        if not aceite_privacidade:
            raise ConsentimentoObrigatorioError("Consentimento explicito da LGPD e obrigatorio.")
        cliente_id = f"CLI-{uuid.uuid4().hex[:8].upper()}"
        cliente = ClienteFidelidade(
            cliente_id=cliente_id,
            nome=nome,
            telefone=telefone,
            aceite_privacidade=aceite_privacidade,
            opt_in_marketing=opt_in_marketing,
            faixa_etaria=faixa_etaria,
        )
        self.clientes[cliente_id] = cliente
        return cliente

    def anonimizar_cliente(self, cliente_id: str) -> ClienteFidelidade:
        cliente = self.clientes[cliente_id]
        digest = hashlib.sha256(cliente_id.encode("utf-8")).hexdigest()[:12]
        cliente.nome = f"ANONIMIZADO_{digest}"
        cliente.telefone = "00000000000"
        cliente.opt_in_marketing = False
        cliente.anonimizado = True
        return cliente

    def listar_contatos_campanha(self) -> list[ClienteFidelidade]:
        return [c for c in self.clientes.values() if c.opt_in_marketing and not c.anonimizado]

    def consultar_relatorio_unidade(self, unidade_token: str, unidade_alvo: str) -> dict:
        if unidade_token != unidade_alvo and unidade_token != "MATRIZ":
            raise AcessoNegadoUnidadeError("Acesso negado a relatorios de outra unidade.")
        pedidos_unidade = [
            p for p in self.pedidos_por_chave.values()
            if p.unidade_id == unidade_alvo and p.status != StatusPedido.NAO_PAGO
        ]
        return {
            "unidade": unidade_alvo,
            "total_pedidos": len(pedidos_unidade),
            "faturamento": round(sum(p.valor_total for p in pedidos_unidade), 2),
        }
