# contact_map 파서를 .k 발췌 tmp_path 픽스처로 검증 (172/173/TIED 92 + 강등 케이스)
"""Tests for contact_map.parse_contact_map.

A minimal keyword excerpt (mirroring Test_Impact_A: CID 172/173 automatic
surface-to-surface + one TIED CID 92 with two single-part segment sets) is
written to tmp_path and the resolution rules are asserted.
"""
from __future__ import annotations

import pytest

from koo_deep_report.core.contact_map import parse_contact_map


# --- minimal keyword excerpt --------------------------------------------------
# PID 1,2 elements feed the two TIED segment sets; PID 24,25 are master parts.
_KEXCERPT = """\
*KEYWORD
*PART
$ part 1
Front\\Metal
         1        13        23
*PART
$ part 2
Front\\Wall
         2        14        24
*PART
Impactor
        24         1        29
*PART
RigidWall
        25         2        30
*ELEMENT_SOLID
       1       1      11      12      13      14      15      16      17      18
       2       1      13      14      15      16      17      18      19      20
       3       2      31      32      33      34      35      36      37      38
       4       2      33      34      35      36      37      38      39      40
*SET_SEGMENT_TITLE
                                                                     SegmentSet1
         1     0.000     0.000     0.000     0.000      MECH         0
        11        12        13        13     0.000     0.000     0.000     0.000
        14        15        16        16     0.000     0.000     0.000     0.000
*SET_SEGMENT_TITLE
                                                                     SegmentSet2
         2     0.000     0.000     0.000     0.000      MECH         0
        31        32        33        33     0.000     0.000     0.000     0.000
        34        35        36        36     0.000     0.000     0.000     0.000
*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID
$$     CID      NAME
        92                                                        Contact Region
$$    SSID      MSID     SSTYP     MSTYP    SBOXID    MBOXID       SPR       MPR
         1         2         0         0         0         0         1         1
$$      FS        FD        DC        VC       VDC    PENCHK        BT        DT
       0.0       0.0       0.0       0.0      10.0         0       0.0       0.0
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID
$$     CID      NAME
       172                                                           Contact_172
$$    SSID      MSID     SSTYP     MSTYP    SBOXID    MBOXID       SPR       MPR
         0        25         5         3         0         0         0         0
$$      FS        FD        DC        VC       VDC    PENCHK        BT        DT
       0.3       0.2       0.0       0.0      10.0         1       0.0     1e+20
*CONTACT_AUTOMATIC_SURFACE_TO_SURFACE_ID
$$     CID      NAME
       173                                                           Contact_173
$$    SSID      MSID     SSTYP     MSTYP    SBOXID    MBOXID       SPR       MPR
         0        24         5         3         0         0         0         0
$$      FS        FD        DC        VC       VDC    PENCHK        BT        DT
       0.3       0.2       0.0       0.0      10.0         1       0.0     1e+20
*END
"""

# One TIED card whose segment set spans two parts 50/50 → majority share 0.5
# → demotion to kind="iface".
_KEXCERPT_MIXED = """\
*KEYWORD
*ELEMENT_SOLID
       1       1      11      12      13      14      15      16      17      18
       2       2      21      22      23      24      25      26      27      28
*SET_SEGMENT_TITLE
                                                                        MixedSet
         7     0.000     0.000     0.000     0.000      MECH         0
        11        12        13        13     0.000     0.000     0.000     0.000
        21        22        23        23     0.000     0.000     0.000     0.000
*SET_PART_LIST_TITLE
                                                                        BigSet
         8     0.000     0.000     0.000     0.000      MECH
         1         2
*CONTACT_TIED_SURFACE_TO_SURFACE_OFFSET_ID
$$     CID      NAME
        50                                                          Mixed Region
$$    SSID      MSID     SSTYP     MSTYP    SBOXID    MBOXID       SPR       MPR
         7         8         0         2         0         0         1         1
*END
"""


@pytest.fixture
def kfile(tmp_path):
    p = tmp_path / "excerpt.k"
    p.write_text(_KEXCERPT)
    return p


@pytest.fixture
def kfile_mixed(tmp_path):
    p = tmp_path / "mixed.k"
    p.write_text(_KEXCERPT_MIXED)
    return p


# --- rule 4 (all) + rule 1 (part id direct) ----------------------------------
def test_cid_172_all_slave_part_master(kfile):
    part_names = {24: "Impactor", 25: "RigidWall"}
    cmap = parse_contact_map(kfile, part_names)
    e = cmap.endpoints[172]
    assert e.slave.kind == "all"
    assert e.slave.node_id == "iface:172"
    assert e.master.kind == "part"
    assert e.master.part_id == 25
    assert e.master.node_id == "25"
    assert e.master.name == "RigidWall"
    assert e.confidence == 1.0


def test_cid_173_master_part_24(kfile):
    cmap = parse_contact_map(kfile, {24: "Impactor"})
    e = cmap.endpoints[173]
    assert e.slave.kind == "all"
    assert e.master.kind == "part"
    assert e.master.part_id == 24
    assert e.master.name == "Impactor"
    assert e.confidence == 1.0


# --- rule 3 (segment set majority → single part, share 1.0) ------------------
def test_cid_92_tied_both_parts(kfile):
    cmap = parse_contact_map(kfile, {1: "Front\\Metal", 2: "Front\\Wall"})
    e = cmap.endpoints[92]
    assert e.slave.kind == "part"
    assert e.slave.part_id == 1
    assert e.slave.node_id == "1"
    assert e.slave.name == "Front\\Metal"
    assert e.master.kind == "part"
    assert e.master.part_id == 2
    assert e.master.name == "Front\\Wall"
    assert e.confidence >= 0.9


def test_no_demotions_in_clean_deck(kfile):
    cmap = parse_contact_map(kfile, {})
    demoted = sum(
        1 for e in cmap.endpoints.values()
        if e.slave.kind == "iface" or e.master.kind == "iface"
    )
    assert demoted == 0
    assert len(cmap.endpoints) == 3
    assert "INCLUDE" in cmap.note


# --- part_names fallback ------------------------------------------------------
def test_part_name_fallback_when_missing(kfile):
    cmap = parse_contact_map(kfile, part_names=None)
    e = cmap.endpoints[172]
    assert e.master.name == "Part_25"


# --- rule 2 (set_part multi member → kind="set") + rule 3 low-share demotion --
def test_mixed_set_demotes_and_set_part(kfile_mixed):
    cmap = parse_contact_map(kfile_mixed, {1: "A", 2: "B"})
    e = cmap.endpoints[50]
    # slave: segment set spanning two parts 50/50 → share 0.5 → demoted iface
    assert e.slave.kind == "iface"
    assert e.slave.node_id == "iface:50"
    # master: *SET_PART with 2 members → kind="set"
    assert e.master.kind == "set"
    assert e.master.node_id == "set:8"
    # endpoint confidence = min(0.5 slave, 1.0 master) = 0.5
    assert e.confidence == pytest.approx(0.5, abs=1e-6)
    assert "demoted" in cmap.note


# --- rule 5 (keyword absent) --------------------------------------------------
def test_missing_keyword_file(tmp_path):
    cmap = parse_contact_map(tmp_path / "does_not_exist.k", {})
    assert cmap.endpoints == {}
    assert "not found" in cmap.note
