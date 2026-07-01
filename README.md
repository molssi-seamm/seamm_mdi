# seamm_mdi

A reusable [MDI](https://molssi-mdi.github.io/MDI_Library/) driver facility for
SEAMM. It lets a SEAMM step launch a quantum-chemistry (or other) engine once and
drive it for many energy/force evaluations over the MDI protocol, instead of
re-launching the code for every geometry.

The `MDIEngine` class is the driver: it listens on a TCP port, launches the
engine (which connects back), and exposes a small, unit-aware API:

```python
from seamm_mdi import MDIEngine

with MDIEngine(build_argv, elements=[8, 1, 1]) as engine:
    engine.set_coordinates(xyz, units="Å")
    e = engine.energy(units="kcal/mol")
    f = engine.forces(units="kcal/mol/Å")
```

`build_argv(hostname, port)` returns the argv that launches the engine wrapper
(e.g. from a program step's `get_mdi_engine_command`), pointed at the driver's
`hostname`/`port`. Unit conversions are handled inside `MDIEngine`
(`seamm_util.Q_`); the default units are MDI-native (bohr, hartree, hartree/bohr).

Status: local-mode (localhost) first cut. Remote/queue launching via the SEAMM
executor is planned.
