==========================================
Campaign: an MDI driver facility for SEAMM
==========================================

:Date: 2026-07-06
:Packages: ``seamm_mdi`` (new), ``dimer_builder_step``, ``seamm``,
           ``mopac_step``

Summary
=======

This campaign created ``seamm_mdi``, a reusable driver for the `MDI
<https://molssi-mdi.github.io/MDI_Library/>`_ (MolSSI Driver Interface), and
used it as the energy engine for the new Dimer Builder plug-in's
energy-based contact search. It grew out of the Dimer Builder work: rather than
run an external code once per geometry through a sub-flowchart, drive a
**persistent** engine over MDI and evaluate many geometries cheaply.

Motivation
==========

Several SEAMM drivers (energy scans, reaction paths, and Dimer Builder's
contact search) need the energy — and sometimes the gradient — at many nearby
geometries. Launching the external code afresh for each point is dominated by
the code's start-up time, especially for the inexpensive methods one actually
uses for these tasks (semiempirical, forcefields). MDI solves this: launch the
engine **once**, then send geometries and read back energies/forces over a
socket.

It also simplifies the user experience. Instead of assembling a sub-flowchart
inside a step, the user sets up a *model chemistry* and the step drives it. And
it keeps SEAMM's dependencies off the compute cluster: only a lightweight
engine wrapper needs to be there, not the whole driver stack.

Architecture
============

``MDIEngine`` (driver)
    A small driver object. ``start()`` picks a free TCP port, begins listening,
    launches the engine, accepts its connection, and sends the fixed topology
    (natoms, elements). Then ``set_coordinates`` / ``energy`` / ``forces`` drive
    it for as many geometries as wanted; ``close()`` sends ``EXIT`` and reaps the
    engine. Used as a context manager.

Units in one place
    Every driving method takes an optional ``units=`` string and converts via
    ``seamm_util.Q_``. Defaults are MDI-native (bohr, hartree, hartree/bohr).
    This keeps conversion out of every consumer.

Engine wrappers, reused
    The engine side is the existing ``mopac_mdi.py`` / ``tblite_mdi.py`` wrapper
    scripts (in ``mopac_step`` / ``xtb_step``): standalone scripts that wrap the
    code's Python API and speak MDI. An engine does **not** need native MDI
    support — any code with a Python API can be wrapped. They are ``-role
    ENGINE`` (connect-only), so no change was needed to reuse them.

Key decisions
=============

Socket direction: driver listens, engine connects
--------------------------------------------------

Per the MDI standard, ``-role`` picks the network server: the **driver listens**
on its port and the **engine connects** to it (hence the engine gets
``-hostname``). This is the only direction that works when one driver serves
several engines. It is also the direction that works for SEAMM's distributed
execution model: the driver runs on the JobServer and the engine, launched on a
compute node, **dials back** to the JobServer (the allowed direction through
institutional firewalls; a port range is opened to the cluster by the local
admin — the approach QCArchive uses successfully). The engine wrapper never has
to be reached *into* on the compute node.

.. note::
   A stale comment in ``lammps_step`` claims "the QM engine is the listener";
   that is incorrect. The driver listens; the engine connects. (Two small
   LAMMPS cleanups fall out of this: fix that comment and drop a superfluous
   ``-hostname`` on the driver launch line.)

Local now, remote later
------------------------

The first release launches the engine as a local subprocess (``localhost``).
Remote launching through the SEAMM executor — ship the wrapper, submit to the
queue, engine dials back — is planned; it mirrors the normal remote-code flow
(input files in, requested files back) with the socket replacing most of the
file round-trip. Crucially, SEAMM itself is never installed on the cluster.

Cross-package changes
=====================

``dimer_builder_step``
    Added ``contact method = energy``: read the upstream ``_model_chemistry``
    (a Model Chemistry step, as LAMMPS does), start one dimer engine, and find
    the energy **minimum** along each approach axis to anchor the scan (falling
    back to the van der Waals contact for orientations with no binding well).
    ``seamm_mdi`` is imported lazily, so the van der Waals path has no dependency
    on it.

``seamm`` (core)
    Added ``Node.previous_nodes(node_type=None)`` and the matching
    ``TkNode.previous_nodes`` — a reusable way to find preceding steps of a given
    type. Dimer Builder uses it to show a "needs a Model Chemistry step" hint
    only when one is not already upstream.

``mopac_step``
    The ``mopac_mdi.py`` engine logged connection/build/timing/exit lines at
    INFO, cluttering driver output. Demoted to DEBUG so normal runs are quiet;
    the driver reports what it needs (which model chemistry, how many calls).

Status and remaining work
==========================

Done and validated (against real MOPAC, across conda environments):
``MDIEngine`` local mode, unit conversions, and the Dimer Builder energy-contact
search.

Remaining:

* Remote / executor launching of the engine (the queue + dial-back path).
* An ``orca_mdi.py`` wrapper (ORCA has no native MDI, but has a Python API).
* Retrofit ``energy_scan`` and ``reaction_path`` (and eventually the LAMMPS
  QM path) onto the facility.
* Demote the ``tblite_mdi.py`` / ``mace_mdi.py`` engine logging as was done for
  MOPAC; and the two LAMMPS comment/launch cleanups noted above.
