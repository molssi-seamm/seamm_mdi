=======
History
=======

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
