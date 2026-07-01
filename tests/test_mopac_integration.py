# -*- coding: utf-8 -*-

"""Integration test: drive the real MOPAC MDI engine through seamm_mdi.

Skipped unless the ``seamm-mopac`` conda environment (with ``mdi`` and
``mopactools``) and the ``mopac_step`` package are available, so it runs on a
developer/production machine but not in a bare CI environment. It also exercises
the cross-environment design: the driver runs here, the engine in ``seamm-mopac``
via ``conda run``.
"""

import importlib
import importlib.resources
import shutil
import subprocess

import numpy as np
import pytest

from seamm_mdi import MDIEngine


def _engine_available():
    if shutil.which("conda") is None:
        return False
    try:
        importlib.import_module("mopac_step")
    except Exception:
        return False
    result = subprocess.run(
        [
            "conda",
            "run",
            "-n",
            "seamm-mopac",
            "python",
            "-c",
            "import mdi, mopactools.api",
        ],
        capture_output=True,
    )
    return result.returncode == 0


def test_real_mopac_water():
    if not _engine_available():
        pytest.skip("seamm-mopac MDI engine environment not available")

    mopac_mdi = str(importlib.resources.files("mopac_step") / "data" / "mopac_mdi.py")

    def build_argv(hostname, port):
        return [
            "conda",
            "run",
            "--live-stream",
            "-n",
            "seamm-mopac",
            "python",
            mopac_mdi,
            "-mdi",
            f"-role ENGINE -name MOPAC -method TCP -port {port} "
            f"-hostname {hostname}",
            "--method",
            "PM7",
            "--charge",
            "0",
            "--multiplicity",
            "1",
        ]

    xyz = np.array(
        [[0.0, 0.0, 0.0], [0.7572, 0.5859, 0.0], [-0.7572, 0.5859, 0.0]]
    )  # water, Å
    with MDIEngine(build_argv, elements=[8, 1, 1], timeout=120.0) as engine:
        engine.set_coordinates(xyz, units="Å")
        e_kcal = engine.energy(units="kcal/mol")
        e_h = engine.energy(units="hartree")
        forces = engine.forces(units="kcal/mol/Å")

    # PM7 heat of formation of water is about -57.8 kcal/mol.
    assert -70.0 < e_kcal < -45.0
    # Energy-unit conversion is self-consistent.
    from seamm_util import Q_

    assert e_kcal == pytest.approx(Q_(e_h, "hartree").m_as("kcal/mol"))
    assert forces.shape == (3, 3)
    assert np.isfinite(forces).all()
