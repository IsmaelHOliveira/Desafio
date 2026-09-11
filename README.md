# Roteamento online e busca adversarial

Projeto em Python para rotear demandas de banda em redes capacitadas. A entrega contém dois experimentos: uma heurística que decide cada rota no momento da chegada e uma busca por instâncias pequenas em que essa heurística se distancia de um ótimo offline exato.

O código usa somente a biblioteca padrão, mantém cargas e capacidades com aritmética exata e produz resultados determinísticos.

## Desafios implementados

### Desafio 1

Processa demandas na ordem de chegada e compara duas estratégias:

- baseline de menor caminho viável;
- heurística online que equilibra número de saltos e congestionamento projetado.

Cada estratégia começa com uma rede vazia e recebe a mesma sequência. Demandas aceitas permanecem alocadas; rejeições informam se faltou conectividade ou capacidade residual.

### Desafio 2

Procura automaticamente instâncias adversariais e compara a mesma heurística com um ótimo offline. Também avalia uma família parametrizada por tamanho da rede para observar experimentalmente a evolução da razão heurística/ótimo.

O resultado é experimental. “Pior instância” significa a pior encontrada pela busca configurada, não um pior caso matemático provado.

## Como a solução funciona

A topologia JSON lista nós, enlaces e capacidades. Os enlaces são não direcionados por padrão; em redes direcionadas, arcos opostos têm capacidades independentes. O arquivo de demandas é uma lista JSON, e sua ordem define as chegadas.

O baseline usa BFS somente sobre enlaces que comportam a demanda, encontrando o menor caminho viável em número de saltos. A heurística enumera até `k` caminhos simples viáveis e minimiza:

```text
score = alpha * hops + beta * projected_max_utilization
```

`projected_max_utilization` é o maior valor `(carga atual + banda) / capacidade` nos enlaces do candidato. Empates usam menos saltos e depois a ordem lexicográfica dos nós.

O comportamento é online porque cada decisão recebe apenas a demanda atual e o estado criado por decisões anteriores. O roteador não recebe demandas futuras e não desfaz escolhas. O leitor valida o arquivo completo antes da simulação, mas não entrega essa lista ao algoritmo.

No Desafio 2, o objetivo global é minimizar a utilização máxima, roteando todas as demandas. O ótimo enumera todos os caminhos simples e usa branch-and-bound sobre as combinações. Ele é exato nas instâncias avaliadas, porém exponencial e destinado apenas a casos pequenos. A busca adversarial pode conhecer a instância inteira; a heurística reutilizada continua online.

## Estrutura do projeto

```text
online_routing/
  data_reader.py    leitura e validação dos arquivos
  models.py         topologia, enlaces, demandas e valores exatos
  network.py        carga, capacidade residual e alocação atômica
  algorithms.py     baseline e heurística online
  metrics.py        métricas do Desafio 1
  evaluation.py     comparação do Desafio 1
  offline.py        ótimo offline exato para instâncias pequenas
  adversarial.py    geradores aleatório e parametrizado
  challenge2.py     experimentos e artefatos do Desafio 2
examples/           dados sintéticos do Desafio 1
results/            resultados reproduzidos do Desafio 2
tests/              testes unitários, oráculos e integração
```

## Requisitos

- Python `3.12.13`, fixado em `.python-version` e `pyproject.toml`;
- `uv 0.11.3` para o fluxo reproduzível documentado;
- nenhuma biblioteca Python de terceiros em execução ou testes.

O arquivo `requirements.txt` registra explicitamente a ausência de pacotes externos. O `uv.lock` fixa o ambiente do projeto.

## Instalação

1. Instale Python 3.12.13 a partir de <https://www.python.org/downloads/>.
2. Abra um terminal e entre na raiz deste repositório.
3. Instale a versão usada do gerenciador:

```bash
python -m pip install uv==0.11.3
```

4. Crie e sincronize o ambiente usando o lockfile:

```bash
uv sync --frozen --cache-dir .uv-cache
```

O `uv` também pode baixar a versão fixada do Python quando ela não estiver instalada. `.uv-cache` e `.venv` são locais e ignorados pelo Git.

## Como executar o Desafio 1

Na raiz do repositório:

```bash
uv run --frozen --cache-dir .uv-cache python -m online_routing --topology examples/topology.json --demands examples/demands.json --alpha 1 --beta 5 --candidates 8
```

O comando escreve no terminal um JSON UTF-8 com configuração, ordem de processamento, decisões, explicações e métricas dos dois algoritmos. O Desafio 1 não cria arquivos automaticamente; redirecione a saída se quiser preservá-la.

Para usar dados próprios, substitua os caminhos após `--topology` e `--demands`. O formato completo está exemplificado em [topology.json](examples/topology.json) e [demands.json](examples/demands.json): capacidades e bandas são números positivos, IDs de demanda são únicos e todos os nós referenciados devem existir.

## Como executar o Desafio 2

```bash
uv run --frozen --cache-dir .uv-cache python -m online_routing.challenge2
```

O comando reproduz a busca com seed `20260910`, 80 candidatos aleatórios e a família `n=4,6,...,20`. Ele sobrescreve deterministicamente:

- `results/challenge2_summary.csv`: resumo e pior razão encontrada;
- `results/challenge2_search.csv`: todos os candidatos aleatórios, inclusive excluídos;
- `results/challenge2_family.csv`: resultado por tamanho;
- `results/challenge2_worst_instance.json`: topologia, demandas e rotas da pior instância encontrada.

## Testes

Execute toda a suíte com:

```bash
uv run --frozen --cache-dir .uv-cache python -m unittest discover -s tests -v
```

Os testes incluem casos calculados manualmente, independência de demandas futuras, capacidade exata, determinismo entre processos, arquivos externos, comparação de caminhos com oráculos independentes e validação do solver offline.

## Configuração

No Desafio 1:

- `--alpha`: peso dos saltos, padrão `1`;
- `--beta`: peso da utilização projetada, padrão `5`;
- `--candidates`: número máximo de caminhos completos avaliados, padrão `8`;
- `--topology` e `--demands`: arquivos de entrada obrigatórios.

No Desafio 2:

- `--seed`: seed do gerador, padrão `20260910`;
- `--trials`: candidatos aleatórios, padrão `80`;
- `--family-sizes`: tamanhos separados por vírgula, padrão `4,6,...,20`;
- `--output-dir`: diretório dos artefatos, padrão `results`;
- `--alpha`, `--beta` e `--candidates`: configuração da heurística reutilizada.

Pesos devem ser finitos e não negativos, com pelo menos um positivo. A quantidade de candidatos deve ser um inteiro positivo.

## Métricas

O Desafio 1 registra demandas aceitas e rejeitadas, total e média de saltos das aceitas e utilização máxima final. Saltos não são ponderados pela banda; rejeições não entram na média.

No Desafio 2, tanto a heurística quanto o ótimo usam a utilização máxima como resultado. Para soluções viáveis:

```text
ratio = maximum_utilization_heuristic / maximum_utilization_optimum
```

Como a métrica é minimizada, valores maiores são piores. Se a heurística rejeita e o ótimo roteia todas, a razão é `+infinito`. JSON e CSV registram esse caso explicitamente sem gravar um número não padrão.

## Resultados reproduzidos

Desafio 1, com os arquivos de `examples/`:

| Algoritmo | Aceitas | Rejeitadas | Saltos | Média | Utilização máxima |
|---|---:|---:|---:|---:|---:|
| Caminho mínimo | 3 | 1 | 4 | 1,3333 | 100% |
| Heurística | 3 | 1 | 5 | 1,6667 | 60% |

Desafio 2, com a configuração padrão:

| Resultado | Valor observado |
|---|---|
| Pior instância encontrada | `random(trial=18)`, 5 nós, 7 enlaces, 5 demandas |
| Pior razão encontrada | `+infinito`: heurística rejeitou e ótimo roteou todas |
| Ótimo dessa instância | utilização máxima `1` |
| Família parametrizada | razão `1` até n=10; `2` de n=12 a 18; `3` em n=20 |

Os detalhes estão nos relatórios e em `results/`. Esses números vêm das execuções padrão e são verificados pelos testes de integração.

## Reprodutibilidade e origem dos dados

Todos os dados foram gerados especificamente para este projeto; não há dataset ou topologia externa. `examples/` contém uma instância sintética fixa. No Desafio 2, `random_instance` gera candidatos com `random.Random(seed)`, e `family_instance(n)` é inteiramente determinística.

Vizinhos, candidatos e desempates têm ordenação explícita. Os testes comparam saídas entre processos com sementes de hash diferentes e repetem a geração dos arquivos. Os dois comandos acima recriam todos os resultados publicados.

## Limitações

- O ótimo offline é exato apenas no sentido de correção, não de escala: tempo e memória podem crescer exponencialmente.
- A busca aleatória é uma amostra de 80 instâncias para uma seed; não prova um pior caso absoluto.
- A família mede especificamente o efeito do limite de candidatos e não prova crescimento ilimitado ou teto teórico.
- A razão do Desafio 2 usa utilização máxima e exige todas as demandas; saltos não fazem parte desse objetivo global.
- A enumeração da heurística também pode crescer muito em grafos densos, pois `k` limita caminhos completos, não caminhos parciais.
- O score usa ponto flutuante; empates extremamente próximos podem sofrer arredondamento. Capacidade e carga permanecem exatas.
- Demandas são indivisíveis, não expiram e não são rerroteadas. Não há enlaces paralelos, mudanças dinâmicas ou persistência.
- Não foram implementados ótimo offline escalável para instâncias grandes, análise de falha por enlace nem gráfico automático da família. O gráfico era opcional; os CSVs contêm os dados.
- A entrada é carregada em memória antes da simulação; a decisão é online, mas a leitura não é streaming.

## Relatórios

- [Relatório do Desafio 1](REPORT.md)
- [Relatório do Desafio 2](REPORT_CHALLENGE2.md)

## Licença

Distribuído sob a licença MIT. Consulte [LICENSE](LICENSE).
