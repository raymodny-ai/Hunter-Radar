"""Hunter Radar EOD V2 — BashOperator + etl_runner.sh 编排版。

2026-07-23 patch: V1 DAG (hunter_radar_eod.py) 14 个 task 全用 @task + from etl.app.xxx,
装在 airflow 容器内 SQLAlchemy 1.4 + app.core.database 用了 SQLAlchemy 2.0 API → 全部 ModuleNotFoundError。
V2 改成 BashOperator,实际 ETL 跑到 backend 容器 (SQLAlchemy 2.0 + asyncpg 全装好)。
airflow 容器只做编排,完全不动 app/etl 的代码。

依赖:
- /opt/airflow/scripts/etl_runner.py (mount 进来)
- /opt/airflow/dags/_ensure_etl_runner.sh (mount 进来)
- backend 容器内 /app/etl_runner.py (ensure 脚本每次 docker cp 同步)

流程 (14 task):
  pull_finra_short, pull_finra_ats, pull_yahoo_eod, pull_yahoo_options,
  pull_sec_form4, pull_sec_buyback
    ↓
  load_short_volume, load_daily_price, load_options_chain, load_form4
    ↓
  compute_option_anomaly, compute_etf_proxy
    ↓
  compute_threat_score
    ↓
  run_screener
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta

# 2026-07-23 patch: belt-and-suspenders
_AIRFLOW_HOME = "/opt/airflow"
if _AIRFLOW_HOME not in sys.path:
    sys.path.insert(0, _AIRFLOW_HOME)

from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator

log = logging.getLogger(__name__)


# ---- 默认参数 ----
default_args = {
    "owner": "hunter-radar",
    "depends_on_past": False,
    "email": ["ops@hunter-radar.example"],
    "email_on_failure": True,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

# ETL task 名称 (etl_runner.py 里的 registry keys)
PULL_TASKS = [
    "pull_finra_short",
    "pull_finra_ats",
    "pull_yahoo_eod",
    "pull_yahoo_options",
    "pull_sec_form4",
    "pull_sec_buyback",
]
LOAD_TASKS = [
    "load_short_volume",
    "load_daily_price",
    "load_options_chain",
    "load_form4",
]
COMPUTE_TASKS = [
    "compute_option_anomaly",
    "compute_etf_proxy",
    "compute_threat_score",
    "run_screener",
]


def _run_etl(task_name: str, trade_date: str) -> BashOperator:
    """单 ETL task 的 BashOperator: 先 ensure runner 同步, 再 docker exec 到 backend 跑。

    2026-07-23 patch: airflow 容器通过 group_add=994 获得 docker socket 权限,
    直接 docker exec 不再用 sg docker。
    """
    return BashOperator(
        task_id=task_name,
        bash_command=(
            "bash /opt/airflow/dags/_ensure_etl_runner.sh && "
            f"docker exec hunter_backend python3 /app/etl_runner.py "
            f"--task {task_name} --date {trade_date}"
        ),
        env={"PYTHONUNBUFFERED": "1"},
        do_xcom_push=True,
        execution_timeout=timedelta(minutes=15),
    )


@dag(
    dag_id="hunter_radar_eod_daily_v2",
    default_args=default_args,
    description="Hunter Radar 每日 EOD (V2: BashOperator + backend 容器 ETL)",
    schedule="0 22 * * 1-5",  # 美东 18:00 + 处理耗时 = UTC 22:00 触发
    start_date=datetime(2026, 6, 16),
    catchup=False,
    max_active_runs=1,
    tags=["hunter-radar", "etl", "eod", "v2"],
)
def hunter_radar_eod_v2() -> None:
    """EOD V2 流水线。"""

    trade_date = "{{ ds }}"

    # 6 个 pull task 并行
    finra_short = _run_etl("pull_finra_short", trade_date)
    finra_ats = _run_etl("pull_finra_ats", trade_date)
    yahoo_eod = _run_etl("pull_yahoo_eod", trade_date)
    yahoo_options = _run_etl("pull_yahoo_options", trade_date)
    sec_form4 = _run_etl("pull_sec_form4", trade_date)
    sec_buyback = _run_etl("pull_sec_buyback", trade_date)

    # 4 个 load task 依赖
    load_sv = _run_etl("load_short_volume", trade_date)
    load_dp = _run_etl("load_daily_price", trade_date)
    load_oc = _run_etl("load_options_chain", trade_date)
    load_f4 = _run_etl("load_form4", trade_date)

    # compute
    anomaly = _run_etl("compute_option_anomaly", trade_date)
    etf = _run_etl("compute_etf_proxy", trade_date)
    score = _run_etl("compute_threat_score", trade_date)
    screener = _run_etl("run_screener", trade_date)

    # 依赖连线
    [finra_short, finra_ats] >> load_sv
    yahoo_eod >> load_dp
    yahoo_options >> load_oc >> anomaly
    sec_form4 >> load_f4
    [load_sv, load_dp, anomaly, load_f4, etf, sec_buyback] >> score >> screener


dag_instance = hunter_radar_eod_v2()