# Food Delivery Lakehouse

Lakehouse local de Engenharia de Dados que reproduzirá, com containers Docker, uma arquitetura moderna inspirada em **AWS e Databricks** para a operação de uma empresa de delivery de grande porte.

O projeto combinará processamento streaming e batch para acompanhar a jornada dos pedidos, reconstruir estados operacionais, tratar eventos duplicados ou fora de ordem e reconciliar pagamentos com provedores externos.

No caminho streaming, Kafka e Spark Structured Streaming conduzirão os eventos de Bronze/Raw até a Silver operacional, pronta para consumo em tempo quase real. No caminho batch, arquivos externos passarão por Landing, Bronze e Silver antes de o dbt construir Gold e Serving. Airflow coordenará o batch e as operações finitas; OpenMetadata concentrará catálogo, linhagem e governança.

> Status: fundação do projeto e contratos de eventos concluídos; simulador determinístico em construção.

## Objetivo

Construir uma plataforma robusta, reproduzível e inspirada em produção, com escopo compatível com uma máquina de 16 GB de RAM.

A carga-alvo será de pelo menos **1 milhão de pedidos** e aproximadamente **10 a 15 milhões de eventos** em um dia lógico de operação.

## AWS e Databricks em ambiente local

Cada componente local reproduzirá uma responsabilidade que poderia ser assumida por serviços AWS e Databricks em um ambiente de produção:

| Ambiente local | Destino em produção | Estratégia |
|---|---|---|
| Apache Kafka | Amazon MSK | substituído por serviço gerenciado |
| Apicurio Registry | AWS Glue Schema Registry | substituído por serviço gerenciado |
| AIStor compatível com S3 | Amazon S3 | substituído; objetos e tabelas migram para S3 |
| Spark Standalone | Databricks Compute | runtime local substituído |
| Spark Structured Streaming | Databricks Structured Streaming | código e conceitos permanecem, com adaptações de ambiente |
| Delta Lake | Delta Lake em S3 | formato e tabelas permanecem |
| Hive Metastore + OpenMetadata | Unity Catalog | catálogo e governança locais são absorvidos principalmente pelo Unity Catalog |
| Trino | Databricks SQL Warehouse | engine local substituída |
| dbt-trino | dbt-databricks | modelos permanecem; adapter e configuração mudam |
| Apache Airflow | Amazon MWAA ou Airflow corporativo | DAGs e regras operacionais permanecem em runtime gerenciado |
| PostgreSQL | Amazon RDS for PostgreSQL | usado apenas pelos serviços que ainda exigirem banco relacional |
| Prometheus e Grafana | Amazon CloudWatch e Amazon Managed Grafana | stack local substituída ou integrada |
| Apache Superset | Databricks AI/BI | consumo local substituído no alvo de referência |
| Docker Compose | serviços gerenciados e IaC | usado somente para reprodução local |

## Stack principal

- Python
- PySpark
- Apache Spark Structured Streaming
- Apache Kafka
- Delta Lake
- Apache Airflow
- OpenMetadata
- dbt
- Trino
- Docker
- armazenamento compatível com S3
- PostgreSQL
- SQL

## Roadmap

- [x] Criar a estrutura inicial do repositório e os padrões de desenvolvimento
- [x] Definir os contratos CloudEvents e JSON Schema
- [ ] Construir o simulador determinístico dos domínios
- [ ] Configurar Kafka e Apicurio Registry
- [ ] Configurar o armazenamento S3 local, Delta Lake e Hive Metastore
- [ ] Implementar a ingestão streaming da camada Bronze
- [ ] Implementar qualidade, deduplicação, Silver e Quarantine
- [ ] Construir o estado dos pedidos com event time, watermark e RocksDB
- [ ] Implementar Landing, Bronze batch, Silver batch e reconciliação financeira
- [ ] Configurar Trino, dbt, Gold e Serving
- [ ] Orquestrar batch, backfills, reparos e manutenção com Airflow
- [ ] Implementar catálogo, linhagem e governança com OpenMetadata
- [ ] Implementar observabilidade e geração de evidências
- [ ] Construir os dashboards no Superset
- [ ] Implementar CI, segurança e testes de recuperação
- [ ] Executar o benchmark final
- [ ] Validar o Terraform offline e finalizar runbooks e documentação
