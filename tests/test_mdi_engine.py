# -*- coding: utf-8 -*-

"""Tests for the seamm_mdi MDIEngine driver, using a mock MDI engine."""

import sys
from pathlib import Path

import numpy as np
import pytest

from seamm_mdi import MDIEngine
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


def test_wrong_atom_count_raises(engine):
    with pytest.raises(ValueError):
        engine.set_coordinates(np.zeros((4, 3)), units="bohr")
