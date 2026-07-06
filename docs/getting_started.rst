Getting Started
===============

Installation
------------

SEAMM MDI is a Python library. It depends on the ``pymdi`` package (the MDI
Library's Python bindings), ``numpy``, and ``seamm-util`` (for unit handling).

.. code-block:: bash

   pip install seamm_mdi

To actually run a calculation you also need an **engine** — an external code
wrapped as an MDI engine — installed and reachable. SEAMM ships small engine
wrappers for MOPAC and xTB (in the ``mopac_step`` / ``xtb_step`` packages); the
engine runs the code through its Python API and speaks the MDI protocol, so it
needs only the code and ``pymdi``, not SEAMM itself.

A first engine
--------------

``MDIEngine`` is the driver. You give it a callable that builds the command to
launch the engine (pointed at the driver's ``hostname``/``port``) and the list
of atomic numbers, then drive it:

.. code-block:: python

   import numpy as np
   from seamm_mdi import MDIEngine

   def build_argv(hostname, port):
       # Whatever launches your MDI engine wrapper, pointed at the driver.
       return [
           "python", "my_engine.py", "-mdi",
           f"-role ENGINE -name MYCODE -method TCP -port {port} "
           f"-hostname {hostname}",
       ]

   # A water molecule (O, H, H).
   xyz = np.array([[0.0, 0.0, 0.0], [0.76, 0.59, 0.0], [-0.76, 0.59, 0.0]])

   with MDIEngine(build_argv, elements=[8, 1, 1]) as engine:
       engine.set_coordinates(xyz, units="Å")
       print("energy:", engine.energy(units="kcal/mol"), "kcal/mol")

The engine is launched once when the ``with`` block is entered and shut down
cleanly when it exits; in between you can call ``set_coordinates`` / ``energy``
/ ``forces`` as many times as you like.

In practice a SEAMM step builds ``build_argv`` from a *model chemistry*
(``get_mdi_engine_command`` on the owning program step), so the user just
"sets up a model chemistry and goes". See the :doc:`user_guide`.
