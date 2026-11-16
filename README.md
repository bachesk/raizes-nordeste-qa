# Projeto Multidisciplinar — Trilha Qualidade de Software (Rede Raízes do Nordeste)

**Aluno:** Eduardo Bachesk  
**RU:** 5075213  
**Curso:** Tecnologia em Análise e Desenvolvimento de Sistemas (UNINTER)  

Este repositório reúne os artefatos práticos de apoio ao documento principal da disciplina, demonstrando a aplicação dos testes automatizados, simulação de carga, planilha de métricas e protótipo de interface com conformidade à LGPD.

## Estrutura do Repositório

- `src/raizes_domain.py`: Módulo com as regras de negócio simuladas (controle de estoque por unidade, filtro sazonal, chave de idempotência contra duplicidade, integração desacoplada com gateway mock, consentimento e anonimização LGPD e auditoria).
- `tests/test_raizes_qa.py`: Suíte de testes automatizados em `pytest` cobrindo os cenários críticos do Plano de Testes (CT-01 a CT-11).
- `load_tests/pedido_pico_k6.js`: Roteiro de teste de carga em `k6` simulando 500 usuários simultâneos no horário de pico.
- `metrics/planilha_metricas_qa.csv`: Planilha consolidada com os indicadores de qualidade (KPIs) e evolução nos três ciclos de homologação.
- `prototype/index.html`: Protótipo interativo (HTML/CSS/JS) demonstrando o consentimento explícito da LGPD (caixas desmarcadas por padrão e anonimização) e o checkout multicanal com simulação de gateway.

## Como Executar os Testes Automatizados

Requer Python 3.10+ e `pytest`:

```bash
pip install pytest pytest-cov
pytest -v --cov=src
```
