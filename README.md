# Food Delivery Lakehouse

Lakehouse local de Engenharia de Dados que reproduzirá, com containers Docker, uma arquitetura moderna inspirada em **AWS e Databricks** para a operação de uma empresa de delivery de grande porte.

O projeto combinará processamento streaming e batch para acompanhar a jornada dos pedidos, reconstruir estados operacionais, tratar eventos duplicados ou fora de ordem e reconciliar pagamentos com provedores externos.

Kafka, Spark Structured Streaming, Delta Lake e um armazenamento compatível com S3 formarão o núcleo da plataforma. Airflow coordenará os processos batch, enquanto Trino e dbt transformarão os dados em produtos analíticos consumidos pelo Superset.

> Status: planejamento concluído e implementação ainda não iniciada.

## Objetivo

Construir uma plataforma robusta, reproduzível e inspirada em produção, com escopo compatível com uma máquina de 16 GB de RAM.

A carga-alvo será de pelo menos **1 milhão de pedidos** e aproximadamente **10 a 15 milhões de eventos** em um dia lógico de operação.

## AWS e Databricks em ambiente local

Cada componente local reproduzirá uma responsabilidade que poderia ser assumida por serviços AWS e Databricks em um ambiente de produção:

| Ambiente local | Equivalente em AWS e Databricks |
|---|---|
| Apache Kafka | Amazon MSK |
| Apicurio Registry | AWS Glue Schema Registry |
| AIStor compatível com S3 | Amazon S3 |
| Spark Standalone | Databricks Compute |
| Spark Structured Streaming | Databricks Structured Streaming |
| Delta Lake | Delta Lake no Databricks |
| Hive Metastore | Unity Catalog |
| Trino | Databricks SQL Warehouse |
| dbt-trino | dbt-databricks |
| Apache Airflow | Amazon MWAA |
| PostgreSQL | Amazon RDS for PostgreSQL |
| Prometheus e Grafana | Amazon CloudWatch e Amazon Managed Grafana |
| Apache Superset | camada de BI e consumo analítico |

## Stack principal

- Python
- PySpark
- Apache Spark Structured Streaming
- Apache Kafka
- Delta Lake
- Apache Airflow
- dbt
- Trino
- Docker
- armazenamento compatível com S3
- PostgreSQL
- SQL

## Roadmap

- [ ] Criar a estrutura inicial do repositório e os padrões de desenvolvimento
- [ ] Definir os contratos CloudEvents e JSON Schema
- [ ] Construir o simulador determinístico dos domínios
- [ ] Configurar Kafka e Apicurio Registry
- [ ] Configurar o armazenamento S3 local, Delta Lake e Hive Metastore
- [ ] Implementar a ingestão streaming da camada Bronze
- [ ] Implementar qualidade, deduplicação, Silver e Quarantine
- [ ] Construir o estado dos pedidos com event time, watermark e RocksDB
- [ ] Implementar Landing e reconciliação financeira batch
- [ ] Configurar Trino, dbt, Gold e Serving
- [ ] Orquestrar os processos batch com Airflow
- [ ] Implementar observabilidade e geração de evidências
- [ ] Construir os dashboards no Superset
- [ ] Implementar CI, segurança e testes de recuperação
- [ ] Executar o benchmark final
- [ ] Validar o Terraform offline e finalizar runbooks e documentação
