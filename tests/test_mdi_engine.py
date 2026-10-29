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


def test_start_is_tried_again(monkeypatch):
    """An engine that fails to start (here, one that exits without connecting) is
    started again, on a new port; after the last attempt the error is raised."""
    calls = []

    def build_argv(hostname, port):
        calls.append(port)
        if len(calls) == 1:
            return [sys.executable, "-c", "import sys; sys.exit(3)"]
        return _build_argv(hostname, port)

    eng = MDIEngine(build_argv, elements=[8, 1, 1], timeout=3.0)
    eng.start_retry_wait = 0.1
    with eng:
        eng.set_coordinates(np.eye(3), units="bohr")
        assert eng.energy() == pytest.approx(0.5 * 3.0)
    assert len(calls) == 2

    def never(hostname, port):
        return [sys.executable, "-c", "import sys; sys.exit(3)"]

    eng = MDIEngine(never, elements=[8, 1, 1], timeout=2.0)
    eng.start_attempts = 2
    eng.start_retry_wait = 0.1
    with pytest.raises(RuntimeError, match="could not be started in 2 attempts"):
        eng.start()


def test_fingerprints(engine):
    """An engine without the fingerprint commands gives None."""
    assert engine.fingerprints() is None


def test_fingerprints_from_engine():
    def argv(hostname, port):
        return _build_argv(hostname, port) + ["--fingerprint"]

    with MDIEngine(argv, elements=[8, 1, 1], timeout=30.0) as eng:
        assert eng.supports("<FINGERPRINT")
        assert eng.fingerprints() == {"energy": None, "hessian": None}
        eng.set_coordinates(np.zeros((3, 3)), units="bohr")
        eng.energy()
        # Several times, as a driver asks after each structure: a receive that read
        # past its buffer failed at random on what followed it in memory
        for _ in range(20):
            records = eng.fingerprints()
            assert records["energy"]["fingerprint"] == "sha256:mock"
            assert records["energy"]["note"] == "Å ² — not ASCII"
            assert len(records["energy"]["files"]["orca.inp"]) == 33 * 200
            assert records["hessian"] is None


def test_fingerprints_with_garbage_after_the_message(monkeypatch):
    """pymdi reads a received string as a C string, past the end of its n-byte
    buffer; when the bytes there are not UTF-8 its own decode fails. The driver
    receives into a buffer of its own with a NUL, so what follows never counts."""
    import ctypes
    import json
    import types

    from seamm_mdi import mdi_engine

    text = json.dumps({"energy": {"fingerprint": "sha256:x"}, "hessian": None})
    payload = text.encode()

    def recv(count, datatype, comm, buf=None):
        if datatype == fake.MDI_INT:
            return len(payload)
        if buf is None:
            # As pymdi does: n bytes, then whatever follows in memory
            return (payload[:count] + b"\xff\xc9 garbage").decode("utf-8")
        ctypes.memmove(buf, payload, count)
        # garbage after the n bytes is outside the buffer we pass, except the NUL
        return None

    fake = types.SimpleNamespace(
        MDI_INT=1,
        MDI_CHAR=4,
        MDI_Send_Command=lambda command, comm: None,
        MDI_Recv=recv,
        MDI_Check_Command_Exists=lambda node, command, comm: True,
    )
    monkeypatch.setattr(mdi_engine, "mdi", fake)
    engine = object.__new__(MDIEngine)
    engine._comm = None
    assert engine.fingerprints() == {
        "energy": {"fingerprint": "sha256:x"},
        "hessian": None,
    }


def test_local_engines_dial_the_loopback_address():
    """Local engines get 127.0.0.1, not "localhost", whose lookup failed for minutes
    on a Mac (2026-10-29)."""
    seen = []

    def build_argv(hostname, port):
        seen.append(hostname)
        return _build_argv(hostname, port)

    with MDIEngine(build_argv, elements=[8, 1, 1], timeout=30.0) as eng:
        eng.set_coordinates(np.eye(3), units="bohr")
        eng.energy()
    assert seen == ["127.0.0.1"]


def test_start_backs_off(monkeypatch):
    """Between attempts the engine waits 2, 10 and 30 s (scaled by
    start_retry_wait), riding out a short outage."""
    from seamm_mdi import mdi_engine

    waits = []
    monkeypatch.setattr(mdi_engine.time, "sleep", lambda s: waits.append(s))

    def never(hostname, port):
        return [sys.executable, "-c", "import sys; sys.exit(3)"]

    eng = MDIEngine(never, elements=[8, 1, 1], timeout=1.0)
    assert eng.start_attempts == 4
    with pytest.raises(RuntimeError, match="could not be started in 4 attempts"):
        eng.start()
    assert waits == [2.0, 10.0, 30.0]


def _n_sockets():
    import stat

    fd_dir = "/dev/fd" if os.path.isdir("/dev/fd") else "/proc/self/fd"
    n = 0
    for name in os.listdir(fd_dir):
        try:
            if stat.S_ISSOCK(os.fstat(int(name)).st_mode):
                n += 1
        except (OSError, ValueError):
            pass
    return n


def test_engines_do_not_leak_sockets():
    """Each engine start opened a listening socket (MDI_Init) and an accepted
    connection that were never closed; a job with ~100 engines then ran out of
    descriptors on a Mac (2026-10-29). Starting and closing engines leaves none."""
    with MDIEngine(_build_argv, elements=[8, 1, 1], timeout=30.0) as eng:
        eng.set_coordinates(np.eye(3), units="bohr")
        eng.energy()
    before = _n_sockets()
    for _ in range(5):
        with MDIEngine(_build_argv, elements=[8, 1, 1], timeout=30.0) as eng:
            eng.set_coordinates(np.eye(3), units="bohr")
            eng.energy()
    assert _n_sockets() == before


def test_close_sockets_only_on_the_port():
    """Only the sockets on the engine's port are closed."""
    import socket

    from seamm_mdi.mdi_engine import _close_sockets_on_port

    mine = socket.socket()
    mine.bind(("127.0.0.1", 0))
    mine.listen()
    other = socket.socket()
    other.bind(("127.0.0.1", 0))
    try:
        assert _close_sockets_on_port(mine.getsockname()[1]) == 1
        assert other.getsockname()[1] > 0  # still open
        with pytest.raises(OSError):
            mine.getsockname()
    finally:
        other.close()
        try:
            mine.close()
        except OSError:
            pass
