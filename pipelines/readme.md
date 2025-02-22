# PipelineExecutor

Executor for pipelines.

## Setup
`docker build -t pipeline_executor .`

`docker run -p 8080:8080 --name <name> pipeline_executor`

## Config
.env file is responsible for the app settings.
### App settings
| Variable | Description |
|---|---------------|
|`int` <br/> `default: 15` <br/> HEARTBEAT_TIMEOUT | How often heartbeat checker goes to the db, seconds. |
|`int` <br/> `default: 10` <br/> HEARTBEAT_THRESHOLD_MUL| Set maximum timedelta of last heartbeat. More than HEARTBEAT_TIMEOUT * HEARTBEAT_THRESHOLD_MUL = heartbeat is dead. |
|`int` <br/> `default: 5` <br/> RUNNER_TIMEOUT | How often pipeline runner check pending tasks in the db, seconds. |
|`int` <br/> `default: 15` <br/> MAX_WORKERS| Maximum concurrent pipeline executions. |
|`str` <br/> `default: ""` <br/> ANNOTATION_URI| Annotation Manager annotation endpoint. |
|`str` <br/> `default: ""` <br/> POSTPROCESSING_URI| Postprocessor postprocessing endpoint. |
|`bool` <br/> `default: False` <br/> DEBUG_MERGE| Models inference data deletion in Minio after pipeline execution. Don't delete if True. |

### SQLAlchemy settings
| Variable | Description |
|---|---------------|
|`int` <br/> `default: 0` <br/> SA_POOL_SIZE | Limit of the open connections. If 0, no limit. |

### PostgreSQL settings
| Variable | Description |
|---|---------------|
|`str` <br/> `default: postgres` <br/> DB_USERNAME| Server username. |
|`str` <br/> `default: admin` <br/> DB_PASSWORD| Server password. |
|`str` <br/> `default: localhost` <br/> DB_HOST| Server host. |
|`int` <br/> `default: 5432` <br/> DB_PORT| Server port. |
|`int` <br/> `default: pipelines` <br/> DB_NAME| Database name. |

### Minio settings
Necessary for proper result merger work.

| Variable | Description |
|---|---------------|
|`str` <br/> `default: ""` <br/> MINIO_URI| Minio storage URI. |
|`str` <br/> `default: minioadmin` <br/> MINIO_ACCESS_KEY| Minio storage user ID. |
|`str` <br/> `default: minioadmin` <br/> MINIO_SECRET_KEY| Minio storage password. |
