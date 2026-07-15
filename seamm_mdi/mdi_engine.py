# -*- coding: utf-8 -*-

"""Driver-side MDI engine facility for SEAMM.

``MDIEngine`` launches an MDI engine once and drives it for many energy/force
evaluations. The driver is the MDI *listener*: it binds a TCP port and the
engine connects back to it (the direction that works both locally and, later,
from a compute node dialing back to the JobServer). Unit conversions are handled
here, in one place, via ``seamm_util.Q_``.

Local mode only for now: the engine is launched as a subprocess on the same host
(``localhost``). Remote/queue launching through the SEAMM executor is planned.
"""

import logging
import signal
import socket
import subprocess

import numpy as np

import mdi
from seamm_util import Q_

logger = logging.getLogger(__name__)

# MDI-native units (what crosses the wire).
_MDI_LENGTH = "bohr"
_MDI_ENERGY = "hartree"
_MDI_FORCE = "hartree/bohr"
_MDI_HESSIAN = "hartree/bohr**2"


def _free_port(hostname="localhost"):
    """Find a free TCP port on ``hostname`` (small TOCTOU race, fine locally)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((hostname, 0))
        return s.getsockname()[1]
    finally:
        s.close()


class MDIEngine:
    """Drive an MDI engine for repeated energy/force evaluations.

    Parameters
    ----------
    build_argv : callable(hostname, port) -> list[str]
        Builds the argv that launches the engine wrapper, pointed at the driver's
        ``hostname``/``port`` (e.g. from a program step's
        ``get_mdi_engine_command``). The engine must be ``-role ENGINE`` so it
        connects back to the driver.
    elements : sequence[int]
        Atomic numbers of the atoms, in coordinate order. Fixed for the session.
    name : str
        The MDI driver name.
    hostname : str
        The host the engine should dial (``localhost`` in local mode).
    timeout : float
        Seconds to wait for the engine to connect before giving up.
    logger : logging.Logger

    Notes
    -----
    One active engine per process (MDI keeps global state). Use as a context
    manager, or call :meth:`start` / :meth:`close` explicitly.
    """

    def __init__(
        self,
        build_argv,
        elements,
        *,
        name="SEAMM",
        hostname="localhost",
        timeout=60.0,
        logger=logger,
    ):
        self._build_argv = build_argv
        self._elements = [int(z) for z in elements]
        self._natoms = len(self._elements)
        self._name = name
        self._hostname = hostname
        self._timeout = timeout
        self.logger = logger

        self._comm = None
        self._process = None
        self._started = False

        # How many times the engine has been asked to evaluate the structure.
        self.n_energy_calls = 0
        self.n_force_calls = 0
        self.n_hessian_calls = 0

    # ----------------------------------------------------------------- #
    # Lifecycle
    # ----------------------------------------------------------------- #

    def start(self):
        """Listen, launch the engine, accept its connection, send the topology."""
        if self._started:
            return self

        port = _free_port(self._hostname)
        mdi.MDI_Init(f"-role DRIVER -name {self._name} -method TCP -port {port}")

        argv = self._build_argv(self._hostname, port)
        self.logger.debug(f"Launching MDI engine: {argv}")
        self._process = subprocess.Popen(argv)

        try:
            self._comm = self._accept()
        except BaseException:
            self._kill_process()
            raise

        # Fixed topology for the session.
        mdi.MDI_Send_Command(">NATOMS", self._comm)
        mdi.MDI_Send(self._natoms, 1, mdi.MDI_INT, self._comm)
        mdi.MDI_Send_Command(">ELEMENTS", self._comm)
        mdi.MDI_Send(self._elements, self._natoms, mdi.MDI_INT, self._comm)

        self._started = True
        return self

    def _accept(self):
        """Accept the engine connection, with a best-effort timeout (Unix)."""
        if self._timeout and hasattr(signal, "SIGALRM"):

            def _handler(signum, frame):
                if self._process is not None and self._process.poll() is not None:
                    raise RuntimeError(
                        "MDI engine exited (return code "
                        f"{self._process.returncode}) before connecting -- check "
                        "the engine launch command and its environment."
                    )
                raise TimeoutError(
                    f"MDI engine did not connect within {self._timeout} s"
                )

            try:
                old = signal.signal(signal.SIGALRM, _handler)
            except ValueError:
                # Not in the main thread; fall back to a plain (blocking) accept.
                return mdi.MDI_Accept_Communicator()
            signal.setitimer(signal.ITIMER_REAL, self._timeout)
            try:
                return mdi.MDI_Accept_Communicator()
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, old)
        return mdi.MDI_Accept_Communicator()

    def close(self):
        """Tell the engine to exit and reap the process."""
        if self._comm is not None:
            try:
                mdi.MDI_Send_Command("EXIT", self._comm)
            except Exception as e:
                self.logger.warning(f"Error sending EXIT to the MDI engine: {e}")
            self._comm = None
        if self._process is not None:
            try:
                self._process.wait(timeout=self._timeout)
            except Exception:
                self._kill_process()
            self._process = None
        self._started = False

    def _kill_process(self):
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # ----------------------------------------------------------------- #
    # Driving
    # ----------------------------------------------------------------- #

    def set_coordinates(self, xyz, units=_MDI_LENGTH):
        """Send the atomic coordinates to the engine.

        Parameters
        ----------
        xyz : (n, 3) or (3n,) array-like
            The coordinates, in ``units``.
        units : str
            The units of ``xyz`` (default MDI-native bohr).
        """
        xyz = np.asarray(xyz, dtype=float).reshape(-1, 3)
        if xyz.shape[0] != self._natoms:
            raise ValueError(f"Expected {self._natoms} atoms, got {xyz.shape[0]}.")
        if units != _MDI_LENGTH:
            xyz = Q_(xyz, units).m_as(_MDI_LENGTH)
        mdi.MDI_Send_Command(">COORDS", self._comm)
        mdi.MDI_Send(xyz.ravel().tolist(), 3 * self._natoms, mdi.MDI_DOUBLE, self._comm)

    def energy(self, units=_MDI_ENERGY):
        """Return the total energy in ``units`` (default MDI-native hartree)."""
        self.n_energy_calls += 1
        mdi.MDI_Send_Command("<ENERGY", self._comm)
        raw = mdi.MDI_Recv(1, mdi.MDI_DOUBLE, self._comm)
        value = float(np.asarray(raw).flat[0])
        if units != _MDI_ENERGY:
            value = Q_(value, _MDI_ENERGY).m_as(units)
        return value

    def forces(self, units=_MDI_FORCE):
        """Return the forces as an (n, 3) array in ``units`` (default hartree/bohr)."""
        self.n_force_calls += 1
        mdi.MDI_Send_Command("<FORCES", self._comm)
        raw = mdi.MDI_Recv(3 * self._natoms, mdi.MDI_DOUBLE, self._comm)
        forces = np.asarray(raw, dtype=float).reshape(-1, 3)
        if units != _MDI_FORCE:
            forces = Q_(forces, _MDI_FORCE).m_as(units)
        return forces

    def supports(self, command, node="@DEFAULT"):
        """Whether the engine supports an MDI ``command`` (e.g. ``"<HESSIAN"``).

        Lets a driver discover an optional capability at runtime rather than
        being told in advance -- e.g. use the analytic Hessian if the engine
        offers one, else finite-difference the forces."""
        try:
            return bool(mdi.MDI_Check_Command_Exists(node, command, self._comm))
        except Exception as e:  # pragma: no cover - conservative fallback
            logger.debug(f"MDI_Check_Command_Exists({command}) failed: {e}")
            return False

    def hessian(self, units=_MDI_HESSIAN):
        """Return the analytic Cartesian Hessian as a (3n, 3n) array in ``units``
        (default hartree/bohr^2), via the engine's custom ``<HESSIAN`` command.

        Raises ``NotImplementedError`` if the engine does not support ``<HESSIAN``
        -- the caller should then finite-difference :meth:`forces` instead."""
        if not self.supports("<HESSIAN"):
            raise NotImplementedError(
                "This MDI engine does not provide an analytic Hessian (<HESSIAN)."
            )
        self.n_hessian_calls += 1
        n = 3 * self._natoms
        mdi.MDI_Send_Command("<HESSIAN", self._comm)
        raw = mdi.MDI_Recv(n * n, mdi.MDI_DOUBLE, self._comm)
        hessian = np.asarray(raw, dtype=float).reshape(n, n)
        if units != _MDI_HESSIAN:
            hessian = Q_(hessian, _MDI_HESSIAN).m_as(units)
        return hessian
