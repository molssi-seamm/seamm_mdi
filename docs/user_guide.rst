User Guide
==========

``seamm_mdi`` provides one public class, :class:`~seamm_mdi.MDIEngine`, a
driver that launches an MDI engine and drives it for repeated energy/force
evaluations. This guide covers the launch contract, the driving API, units, and
the client/server model.

Launching an engine
--------------------

.. code-block:: python

   MDIEngine(build_argv, elements, *, name="SEAMM",
             hostname="localhost", timeout=60.0)

``build_argv`` is a callable ``build_argv(hostname, port) -> list[str]`` that
returns the command line to start the engine, pointed at the driver's
``hostname`` and ``port``. The engine **must** be launched with
``-role ENGINE`` so that it *connects to* the driver (see `The client/server
model`_ below). In a SEAMM step this callable is usually built from the model
chemistry's ``get_mdi_engine_command`` so the engine, method, charge, and
multiplicity all come from the user's Model Chemistry choice.

``elements`` is the list of atomic numbers, in coordinate order, and is fixed
for the life of the engine.

The engine is started with :meth:`~seamm_mdi.MDIEngine.start`, or by entering
the object as a context manager, which is the recommended form:

.. code-block:: python

   with MDIEngine(build_argv, elements=[8, 1, 1]) as engine:
       ...   # drive the engine here

``start`` picks a free port, begins listening, launches the engine, accepts its
connection, and sends the fixed topology (number of atoms and elements).
:meth:`~seamm_mdi.MDIEngine.close` (called automatically on exit) tells the
engine to shut down and reaps the process.

.. note::
   MDI keeps global state, so use **one active engine per process**.

Driving the engine
------------------

.. code-block:: python

   engine.set_coordinates(xyz, units="Å")   # (n, 3) or flat (3n,)
   e = engine.energy(units="kcal/mol")       # a float
   f = engine.forces(units="kcal/mol/Å")     # an (n, 3) array

You can call these repeatedly for different geometries — that is the whole
point, since the engine is launched only once. The number of evaluations is
tracked in ``engine.n_energy_calls`` and ``engine.n_force_calls`` (handy for
reporting how many times the external code ran).

Units
-----

All unit conversion is done **inside** ``MDIEngine`` (via ``seamm_util.Q_``),
so callers never sprinkle conversions through their own code. Each method takes
an optional ``units=`` string; the defaults are MDI-native:

======================  ==================  ==========================
Method                  Default units       Example override
======================  ==================  ==========================
``set_coordinates``     ``bohr``            ``units="Å"``
``energy``              ``hartree``         ``units="kcal/mol"``
``forces``              ``hartree/bohr``    ``units="kcal/mol/Å"``
======================  ==================  ==========================

Any unit string ``pint`` understands is accepted.

The client/server model
------------------------

MDI decides which side is the network server from ``-role``: the **driver
listens** on its port and the **engine connects to it** (that is why the engine
gets the ``-hostname``). ``MDIEngine`` is the driver, so it listens; engines
dial in. This is the only direction that works when one driver serves several
engines, and — importantly — it is the direction that will work for remote
execution, where the driver runs on the SEAMM JobServer and the engine, launched
on a compute node, dials back to it.

The present release launches the engine as a local subprocess (``localhost``).
Launching the engine remotely through the SEAMM executor (queue submission, with
the engine dialing back to the JobServer) is planned; the driving API above will
be unchanged.
