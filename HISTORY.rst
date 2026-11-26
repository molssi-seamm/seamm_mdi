=======
History
=======

2026.11.26 -- The reference guess and a tight SCF for finite differences
    * MDIEngine.save_guess() and restore_guess() keep the orbitals of the engine's last
      SCF and start a later SCF from them (custom SAVE_GUESS / RESTORE_GUESS; ORCA's
      engine first), so every point of a finite difference can start from the same
      reference orbitals rather than from the previous point's.
    * MDIEngine.tight_scf() tightens the engine's SCF for finite differences and puts
      it back (custom TIGHT_SCF / NORMAL_SCF).
    * Each returns False when the engine does not have the command.

2026.11.24 -- Bugfix: several MDI engines can be live at once
    * Calling MDI_Init for every engine gave every engine's communicator the same
      number, so with two engines live (e.g. an optimizer's cheap-level engine next to
      the expensive one) the first engine's commands were answered silently by the
      second. Now a process has one MDI listener while any engine is live; each engine
      is accepted on its own communicator, engines are started one at a time, and
      closing one closes only its own connection. When the last engine closes, the
      listener is closed too, so long loops of engines still leak no sockets.

2026.11.23 -- The spin contamination of an engine's open-shell calculations
    * ``MDIEngine.spin()`` returns <S**2> and its ideal value S(S+1) for the engine's
      last energy and gradient, through the engine's custom ``<SPIN`` command, so a
      driver can store them although the engine's output stays where it runs. It is
      None for an engine without the command, and (None, None) for a closed-shell
      calculation.

2026.11.11 --Fingerprints for engines that send only their settings
    * An MDI engine that runs where SEAMM's own packages are not installed, such as
      xTB's tblite engine in its own environment, can now send the record of its
      settings without the fingerprint; ``MDIEngine.fingerprints`` completes the
      record, so every code's calculations are fingerprinted the same way.

2026.10.29 -- Bugfix: a long loop of engines ran out of file descriptors
    * Every engine start left two sockets open: the listener that MDI_Init opens and
      the connection to the engine, which pymdi has no call to close. A job that
      started many engines -- one per species in a Thermochemistry CBH ladder, about
      100 in 13 iterations -- then ran out of file descriptors (256 for a macOS
      JobServer) and could start no more engines, failing with "nodename nor
      servname provided, or not known". The engine's sockets are now closed when it
      is closed, and after a failed start.
    * A local engine now dials back to the loopback address 127.0.0.1 rather than
      "localhost", so that no name lookup is needed.
    * Starting is tried four times, waiting 2, 10 and 30 seconds between attempts
      (before, three times within three seconds), to ride out a short outage.

2026.10.28.1 -- Bugfix: the fingerprints from an MDI engine could not be read
    * ``MDIEngine.fingerprints()`` failed with "'utf-8' codec can't decode byte 0xff
      ..." for real records. pymdi receives a string into a buffer of exactly its
      length, with no terminating NUL, and then reads it as a C string, past its end
      into whatever follows in memory. The fingerprints are now received into a
      buffer with room for the NUL and decoded exactly.

2026.10.28 -- Fingerprints of an engine's calculations
    * New ``MDIEngine.fingerprints()``: the fingerprints of the settings of the
      engine's last energy and Hessian calculations, from engines that answer the
      custom ``<FINGERPRINT_LENGTH`` and ``<FINGERPRINT`` commands (ORCA's, from
      orca-step 2026.10.28), or None. A step stores them with its results, so that
      results from an MDI engine can be compared with those of the code's own step.

2026.10.19 -- Bugfix: an engine that occasionally failed to start
    * Starting an MDI engine is tried up to three times, each on a new port: an
      engine occasionally failed to start when engines were started one after
      another (a geomeTRIC optimization starts one for each step), and the next
      attempt succeeds. If none does, the error says so.

2026.9.18 -- Periodic cells and stress
    * Added ``MDIEngine.set_cell()`` (``>CELL``) and ``MDIEngine.stress()``
      (``<STRESS``) so a driver can evaluate periodic systems, e.g. the Energy
      step labelling structures with an MLFF. The mock test engine echoes the
      cell as the stress.

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
