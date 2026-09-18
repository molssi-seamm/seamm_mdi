# -*- coding: utf-8 -*-

"""Tests for the seamm_mdi MDIEngine driver, using a mock MDI engine."""

import os
import sys
from pathlib import Path

import numpy as np
import pytest

from seamm_mdi import MDIEngine
from seamm_mdi.mdi_engine import _split_env_prefix
from seamm_util import Q_

MOCK = str(Path(__file__).resolve().parent / "mock_engine.py")


def _build_argv(hostname, port):
    return [
        sys.executable,
        MOCK,
        "-mdi",
        f"-role ENGINE -name MOCK -method TCP -port {port} -hostname {hostname}",
    ]


@pytest.fixture()
def engine():
    with MDIEngine(_build_argv, elements=[8, 1, 1], timeout=30.0) as eng:
        yield eng


def test_energy_roundtrip(engine):
    # Mock energy = 0.5 * sum(coords in bohr).
    xyz_bohr = np.array([[1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0]])
    engine.set_coordinates(xyz_bohr, units="bohr")
    assert engine.energy(units="hartree") == pytest.approx(0.5 * 6.0)


def test_coordinate_units_converted(engine):
    # The same physical geometry in bohr and in Å must give the same energy,
    # because MDIEngine converts Å -> bohr before sending.
    xyz_bohr = np.array([[1.0, 0.5, 0.0], [0.0, 2.0, 1.0], [0.3, 0.0, 3.0]])
    engine.set_coordinates(xyz_bohr, units="bohr")
    e_bohr = engine.energy()

    xyz_ang = Q_(xyz_bohr, "bohr").m_as("Å")
    engine.set_coordinates(xyz_ang, units="Å")
    e_ang = engine.energy()

    assert e_ang == pytest.approx(e_bohr)


def test_energy_units_converted(engine):
    xyz = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])
    engine.set_coordinates(xyz, units="bohr")
    e_h = engine.energy(units="hartree")
    e_kcal = engine.energy(units="kcal/mol")
    assert e_kcal == pytest.approx(Q_(e_h, "hartree").m_as("kcal/mol"))


def test_forces_units_converted(engine):
    xyz = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])
    engine.set_coordinates(xyz, units="bohr")
    f_native = engine.forces()  # hartree/bohr, all -0.5
    assert f_native.shape == (3, 3)
    assert np.allclose(f_native, -0.5)

    f_conv = engine.forces(units="kcal/mol/Å")
    expected = Q_(-0.5, "hartree/bohr").m_as("kcal/mol/Å")
    assert np.allclose(f_conv, expected)


def test_multiple_evaluations_reuse_one_engine(engine):
    # Drive several geometries through the one persistent engine.
    for scale in (1.0, 2.0, 3.0):
        engine.set_coordinates(np.eye(3) * scale, units="bohr")
        assert engine.energy() == pytest.approx(0.5 * 3.0 * scale)
    assert engine.n_energy_calls == 3


def test_call_counters(engine):
    engine.set_coordinates(np.eye(3), units="bohr")
    engine.energy()
    engine.energy()
    engine.forces()
    assert engine.n_energy_calls == 2
    assert engine.n_force_calls == 1


def test_cell_and_stress_roundtrip(engine):
    """>CELL is sent in bohr; <STRESS comes back in hartree/bohr^3 (echoed cell)."""
    engine.set_coordinates(np.zeros((3, 3)))
    cell = np.diag([10.0, 12.0, 14.0])  # Å
    engine.set_cell(cell, units="Å")
    stress = engine.stress()
    bohr = Q_(1.0, "Å").m_as("bohr")
    assert stress.shape == (3, 3)
    assert np.allclose(stress, cell * bohr)
    # Units are converted on the way out too.
    gpa = engine.stress(units="GPa")
    assert np.allclose(gpa, Q_(stress, "hartree/bohr**3").m_as("GPa"))


def test_supports_reports_commands(engine):
    assert engine.supports(">CELL")
    assert engine.supports("<STRESS")
    assert not engine.supports("<HESSIAN")


def test_wrong_atom_count_raises(engine):
    with pytest.raises(ValueError):
        engine.set_coordinates(np.zeros((4, 3)), units="bohr")


def test_split_env_prefix_no_prefix():
    argv = ["python", "engine.py", "-mdi", "OPT=x=y"]
    out, env = _split_env_prefix(argv)
    # Only a *leading* run of VAR=value tokens is a prefix; the program's own
    # arguments (even if they contain '=') are left alone, and env is None so
    # Popen inherits the parent environment unchanged.
    assert out == argv
    assert env is None


def test_split_env_prefix_pulls_leading_assignments():
    argv = ["OMP_NUM_THREADS=1", "MKL_NUM_THREADS=1", "python", "engine.py"]
    out, env = _split_env_prefix(argv)
    assert out == ["python", "engine.py"]
    assert env["OMP_NUM_THREADS"] == "1"
    assert env["MKL_NUM_THREADS"] == "1"
    # The overlay is a copy of the real environment plus the assignments.
    assert env["PATH"] == os.environ["PATH"]


def test_env_prefixed_argv_launches(monkeypatch):
    # An engine argv carrying a leading OMP_NUM_THREADS=1 prefix (the xTB
    # convention, meant for a shell) must still launch under the shell-less
    # Popen: MDIEngine routes the prefix into env= rather than exec'ing it.
    def build_argv(hostname, port):
        argv = _build_argv(hostname, port)
        return ["OMP_NUM_THREADS=1", "MKL_NUM_THREADS=1", *argv]

    with MDIEngine(build_argv, elements=[8, 1, 1], timeout=30.0) as eng:
        eng.set_coordinates(np.eye(3), units="bohr")
        assert eng.energy() == pytest.approx(0.5 * 3.0)
