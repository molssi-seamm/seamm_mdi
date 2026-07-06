========
SEAMM MDI
========

A reusable `MDI <https://molssi-mdi.github.io/MDI_Library/>`_ (MolSSI Driver
Interface) driver facility for SEAMM. It lets a SEAMM step launch a
quantum-chemistry (or other) engine **once** and drive it for many
energy/force evaluations over the MDI protocol, instead of relaunching the
external code for every geometry. This is a large win for the inexpensive codes
(semiempirical methods, forcefields) whose run time is dominated by start-up.

The central class is :class:`~seamm_mdi.MDIEngine`, a small, unit-aware driver:

.. code-block:: python

   from seamm_mdi import MDIEngine

   with MDIEngine(build_argv, elements=[8, 1, 1]) as engine:
       engine.set_coordinates(xyz, units="Å")
       energy = engine.energy(units="kcal/mol")
       forces = engine.forces(units="kcal/mol/Å")

.. grid:: 1 1 2 2

   .. grid-item-card:: Getting Started
      :margin: 0 3 0 0

      Install SEAMM MDI and run a first engine.

      .. button-link:: ./getting_started.html
         :color: primary
         :expand:

         To the Getting Started Guide

   .. grid-item-card:: User Guide
      :margin: 0 3 0 0

      The ``MDIEngine`` API in full: launching, driving, and units.

      .. button-link:: ./user_guide.html
         :color: primary
         :expand:

         To the User Guide

   .. grid-item-card:: Developer Guide
      :margin: 0 3 0 0

      Design, decisions, and the MDI-facility campaign.

      .. button-link:: ./developer_guide/index.html
         :color: primary
         :expand:

         To the Developer Guide

   .. grid-item-card:: API Reference
      :margin: 0 3 0 0

      The module and class reference.

      .. button-link:: ./api.html
         :color: primary
         :expand:

         To the API Reference

.. toctree::
   :maxdepth: 2
   :hidden:
   :titlesonly:

   getting_started
   user_guide
   developer_guide/index
   api
