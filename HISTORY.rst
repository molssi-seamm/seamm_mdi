=======
History
=======

2026.7.27 -- Bugfix: honor an environment-variable prefix on the engine command
    * An engine launch command may lead with ``VAR=value`` assignments (e.g.
      ``OMP_NUM_THREADS=1``) to pin the engine's threads. Those are a shell
      convention, and ``MDIEngine`` launches the engine without a shell, so the
      first assignment was being taken as the program name -- the engine failed
      to start with ``FileNotFoundError: 'OMP_NUM_THREADS=1'`` (seen driving the
      xTB engine from the Dimer Builder). ``MDIEngine`` now applies any such
      leading assignments to the engine's environment instead, so the engine
      launches correctly and runs with the requested thread count.

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
