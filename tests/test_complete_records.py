# -*- coding: utf-8 -*-

"""Engine records sent without fingerprints are completed on the driver's side."""

from seamm_util.fingerprint import calculation_record

from seamm_mdi.mdi_engine import complete_records


def test_a_record_without_fingerprint_is_completed():
    files = {"tblite settings": "method GFN2-xTB\naccuracy 1.0\n"}
    raw = {"program": "tblite", "version": "0.5.0", "files": files}
    done = complete_records({"energy": raw, "hessian": None})
    assert done["hessian"] is None
    assert done["energy"] == calculation_record("tblite", "0.5.0", files)
    assert done["energy"]["fingerprint"].startswith("sha256:")


def test_complete_records_are_unchanged():
    record = calculation_record("ORCA", "6.1.1", {"orca.inp": "! B3LYP DEF2-SVP"})
    assert complete_records({"energy": record}) == {"energy": record}
    assert complete_records(None) is None
