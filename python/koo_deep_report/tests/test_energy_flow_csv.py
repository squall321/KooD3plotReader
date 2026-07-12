# energy_flow_edges.csv writer 검증 — 합성 binout → CSV 계약 파일
import csv

from koo_deep_report.core.binout_reader import (
    BinoutData, MatSumData, RcforcInterface,
)
from koo_deep_report.core.energy_flow_csv import write_energy_flow_csv


def _make_binout():
    matsum = MatSumData(
        part_ids=[1, 2, 3],
        t=[0.0, 1.0, 2.0],
        kinetic_energy=[[100.0, 0.0, 0.0], [60.0, 20.0, 5.0], [40.0, 30.0, 15.0]],
        internal_energy=[[0.0, 0.0, 0.0], [0.0, 10.0, 2.0], [0.0, 20.0, 8.0]],
        x_rbvelocity=[[10.0, 0.0, 0.0], [8.0, 2.0, 1.0], [6.0, 4.0, 2.0]],
        y_rbvelocity=[[0.0, 0.0, 0.0]] * 3,
        z_rbvelocity=[[0.0, 0.0, 0.0]] * 3,
    )
    rcforc = [
        RcforcInterface(interface_id=10, name="C10", side=0, t=[0.0, 1.0, 2.0],
                        fx=[0.0, 100.0, 200.0], fy=[0.0, 0.0, 0.0], fz=[0.0, 0.0, 0.0]),
        RcforcInterface(interface_id=10, name="C10", side=1, t=[0.0, 1.0, 2.0],
                        fx=[0.0, 100.0, 200.0], fy=[0.0, 0.0, 0.0], fz=[0.0, 0.0, 0.0]),
    ]
    return BinoutData(matsum=matsum, rcforc=rcforc, glstat=None)


def test_csv_written_with_expected_header(tmp_path):
    # contact_map=None(keyword 없음) → pseudo 노드 강등이지만 엣지는 생성
    csv_path = write_energy_flow_csv(tmp_path, _make_binout(), None, d3plot_path=None)
    assert csv_path is not None and csv_path.exists()
    rows = list(csv.reader(open(csv_path)))
    assert rows[0] == ["cid", "src_id", "src_name", "dst_id", "dst_name",
                       "name", "peak_force", "t_engage", "total_impulse",
                       "total_work", "confidence"]
    assert len(rows) >= 2   # header + >=1 edge
    # cid 10 엣지 존재
    assert any(r[0] == "10" for r in rows[1:])


def test_none_binout_skips(tmp_path):
    assert write_energy_flow_csv(tmp_path, None, None) is None
    assert not (tmp_path / "energy_flow_edges.csv").exists()


def test_no_matsum_skips(tmp_path):
    assert write_energy_flow_csv(tmp_path, BinoutData(matsum=None), None) is None
