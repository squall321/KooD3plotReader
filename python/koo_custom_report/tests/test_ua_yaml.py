# unified_analyzer 용 YAML 합성이 공유 폴더의 남의 산출물을 건드리지 않는지 검증하는 시험
"""`koo_custom_report.runner.build_ua_yaml` 시험.

커스텀 보고서는 `-o Run_*/Output/report` 로 deep 산출물과 같은 폴더에 싣는 것이
문서화된 관례다(`__main__` 독스트링). 그 폴더에는 deep 이 쓴
analysis_result.json 이 이미 있고, unified_analyzer 는 output.json 이 참이면
그 파일을 조건 없이 다시 쓴다. 세트만 도는 실행에는 motion/element_quality/
hotspot_clusters 가 없으므로 전부 빈 배열로 덮어써진다.
커스텀 보고서는 set_reports/<세트>/metrics.json 만 읽으므로 JSON 이 필요 없다.
"""
import sys

from koo_custom_report.runner import CustomReportConfig, SetSpec, build_ua_yaml

fails = []


def chkb(name, cond):
    if not cond:
        fails.append(name)
    print(f"  {'OK ' if cond else 'NG '} {name}")


cfg = CustomReportConfig(threads=4)
cfg.set_reports.append(SetSpec(name="PKG", set_type="part", set_id=5,
                               fields=["von_mises"], planes=["xy"]))
yaml_text = build_ua_yaml("/data/run/d3plot", "/data/run/Output/report", cfg)
lines = [ln.strip() for ln in yaml_text.splitlines()]

print("build_ua_yaml:")
chkb("analysis_result.json 을 쓰지 않는다 (json: false)", "json: false" in lines)
chkb("json: true 가 없다", "json: true" not in lines)
chkb("세트 시계열 CSV 는 그대로 받는다 (csv: true)", "csv: true" in lines)
chkb("출력 폴더는 그대로 전달된다", any("/data/run/Output/report" in ln for ln in lines))
chkb("세트 정의는 그대로 실린다", any(ln.startswith("- name:") and "PKG" in ln for ln in lines))
chkb("왜 json 을 끄는지 사유가 YAML 에 남는다",
     any(ln.startswith("#") and "analysis_result.json" in ln for ln in lines))

print()


def test_all():
    """pytest 진입점 — 이 함수가 없으면 `no tests ran` 으로 조용히 지나간다."""
    assert not fails, "실패 %d 건:\n  - %s" % (len(fails), "\n  - ".join(fails))


if __name__ == "__main__":
    if fails:
        print(f"[FAIL] 실패 {len(fails)} 건")
        for f in fails:
            print("   -", f)
        sys.exit(1)
    print("[PASS] 실패 0 건")
