=======
History
=======

2026.7.15 -- Optional analytic Hessian over MDI
    * ``MDIEngine`` gained ``supports(command)`` (runtime capability discovery via
      MDI command introspection) and ``hessian()``, which returns the analytic
      Cartesian Hessian through a custom ``<HESSIAN`` command when the engine
      offers one, and raises ``NotImplementedError`` otherwise so the driver can
      finite-difference the forces instead.

2026.7.6 -- Initial release
    * A reusable MDI (MolSSI Driver Interface) driver facility for SEAMM.
    * The ``MDIEngine`` class launches an external engine once and drives it for
      many energy/force evaluations over MDI, instead of relaunching the code for
      every geometry -- a large speed-up for inexpensive codes dominated by
      start-up time.
    * Unit conversion is handled inside the class: ``set_coordinates``,
      ``energy``, and ``forces`` take an optional ``units`` argument (defaulting
      to the MDI-native bohr/hartree).
    * This first release launches the engine locally; remote launching through
      the SEAMM executor is planned.
