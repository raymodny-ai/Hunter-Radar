"""M2 启动层(etl/pipeline)测试。

聚焦:
- PipelineReport 数据类(纯)
- run_daily_pipeline 编排(全 mock,只验证调用次数 + stage 记录)
"""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from etl.load_short_volume import LoadResult
from etl.pipeline import PipelineReport, run_daily_pipeline


class TestPipelineReport:
    def test_ok_empty(self):
        r = PipelineReport(trade_date=date(2024, 2, 1))
        assert r.ok() is True
        assert "✅" in r.summary()

    def test_with_errors(self):
        r = PipelineReport(trade_date=date(2024, 2, 1))
        r.add_error("stage1", "boom")
        assert r.ok() is False
        assert "❌" in r.summary()
        assert "stage1" in r.summary()

    def test_stage(self):
        r = PipelineReport(trade_date=date(2024, 2, 1))
        r.stage("load_daily_price", attempted=10, inserted=8)
        r.stage("load_short_volume", inserted=5)
        assert "load_daily_price" in r.stages
        assert r.stages["load_daily_price"]["attempted"] == 10
        assert r.stages["load_short_volume"]["inserted"] == 5


def _ok_load_result(**kw) -> LoadResult:
    return LoadResult(attempted=kw.get("attempted", 0), inserted=kw.get("inserted", 0), skipped=kw.get("skipped", 0), failures=kw.get("failures", 0))


@pytest.mark.asyncio
async def test_run_daily_pipeline_smoke():
    """全部 ETL 子模块 mock 掉,只验证编排器正确串起 6 个 stage + status 灯。"""
    finra_rows = []
    options_rows = []
    dp_result = _ok_load_result(attempted=10, inserted=8)
    sv_result = _ok_load_result(attempted=5, inserted=4)
    oc_result = _ok_load_result(attempted=20, inserted=18)
    anomaly_result = MagicMock(attempted=20, candidates=4, hits=2, inserted=2)
    f4_result = MagicMock(attempted=3, inserted=2, skipped_etf=1, non_key_insider=0)
    bb_result = _ok_load_result(attempted=0, inserted=0)
    etf_result = MagicMock(attempted=3, inserted=3, signals={"SPY": "normal", "QQQ": "creation_likely"})

    with patch("etl.finra_short.run", new=AsyncMock(return_value=finra_rows)) as m_finra:
        with patch("etl.load_short_volume.load_short_volume", new=AsyncMock(return_value=sv_result)):
            with patch("etl.yfinance_pull.fetch_daily_bars", new=AsyncMock(return_value=[])) as m_dp:
                with patch("etl.load_daily_price.load_daily_price", new=AsyncMock(return_value=dp_result)):
                    with patch("etl.yfinance_pull.fetch_options_chain", new=AsyncMock(return_value=options_rows)):
                        with patch("etl.load_options_chain.load_options_chain", new=AsyncMock(return_value=oc_result)):
                            with patch("etl.load_options_chain.compute_option_anomaly", new=AsyncMock(return_value=anomaly_result)):
                                with patch("etl.sec_form4.run", new=AsyncMock(return_value=[])):
                                    with patch("etl.load_form4.load_form4", new=AsyncMock(return_value=f4_result)):
                                        with patch("etl.load_form4.load_buyback", new=AsyncMock(return_value=bb_result)):
                                            with patch("etl.load_etf_proxy.compute_etf_proxy", new=AsyncMock(return_value=etf_result)):
                                                with patch("etl.pipeline.mark_ready", new=AsyncMock()) as m_ready:
                                                    with patch("etl.pipeline.mark_failed", new=AsyncMock()):
                                                        with patch("etl.pipeline.mark_pending", new=AsyncMock()):
                                                            report = await run_daily_pipeline(date(2024, 2, 1))

    # 7 个 stage(6 个 ETL + 1 个 threat score 占位)
    assert "load_daily_price" in report.stages
    assert "load_short_volume" in report.stages
    assert "load_ats_short" in report.stages
    assert "load_options_chain" in report.stages
    assert "compute_option_anomaly" in report.stages
    assert "load_form4" in report.stages
    assert "load_buyback" in report.stages
    assert "compute_etf_proxy" in report.stages
    assert "compute_threat_score" in report.stages
    # 4 个 mark_ready(finra / yfinance_eod / yfinance_options / sec_form4)
    assert m_ready.await_count == 4
    # 全 mock OK,errors 列表应空
    assert report.errors == []
    assert report.ok()


@pytest.mark.asyncio
async def test_run_daily_pipeline_handles_errors():
    """FINRA 抛异常 → 流水线不中断,error 入栈 + mark_failed 触发。"""
    with patch("etl.finra_short.run", new=AsyncMock(side_effect=Exception("network"))):
        with patch("etl.load_short_volume.load_short_volume", new=AsyncMock()):
            with patch("etl.yfinance_pull.fetch_daily_bars", new=AsyncMock(return_value=[])):
                with patch("etl.load_daily_price.load_daily_price", new=AsyncMock(return_value=_ok_load_result())):
                    with patch("etl.yfinance_pull.fetch_options_chain", new=AsyncMock(return_value=[])):
                        with patch("etl.load_options_chain.load_options_chain", new=AsyncMock(return_value=_ok_load_result())):
                            with patch("etl.load_options_chain.compute_option_anomaly", new=AsyncMock(return_value=MagicMock(attempted=0, candidates=0, hits=0, inserted=0))):
                                with patch("etl.sec_form4.run", new=AsyncMock(return_value=[])):
                                    with patch("etl.load_form4.load_form4", new=AsyncMock(return_value=MagicMock(attempted=0, inserted=0, skipped_etf=0, non_key_insider=0))):
                                        with patch("etl.load_form4.load_buyback", new=AsyncMock(return_value=_ok_load_result())):
                                            with patch("etl.load_etf_proxy.compute_etf_proxy", new=AsyncMock(return_value=MagicMock(attempted=0, inserted=0, signals={}))):
                                                with patch("etl.pipeline.mark_ready", new=AsyncMock()):
                                                    with patch("etl.pipeline.mark_failed", new=AsyncMock()) as m_failed:
                                                        with patch("etl.pipeline.mark_pending", new=AsyncMock()):
                                                            report = await run_daily_pipeline(date(2024, 2, 1))

    assert not report.ok()
    assert any("load_short_volume" in e for e in report.errors)
    # FINRA 失败时 mark_failed 至少被调用 1 次
    assert m_failed.await_count >= 1
