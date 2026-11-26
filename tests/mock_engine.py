# -*- coding: utf-8 -*-

"""A minimal MDI engine for testing the seamm_mdi driver.

It speaks just enough of the MDI protocol to exercise ``MDIEngine``, returning a
deterministic energy/forces from the coordinates it receives (in bohr), so tests
can verify the protocol and the unit conversions without a real QM code.

    energy   = 0.5 * sum(coords_bohr)          [hartree]
    forces   = -0.5 for every component        [hartree/bohr]  (-dE/dx)
    stress   = the cell vectors it was sent    [hartree/bohr^3] (zeros if none)

Run as:  python mock_engine.py -mdi "-role ENGINE -name MOCK -method TCP \\
             -port <port> -hostname <host>"
"""

import argparse
import json

import numpy as np

import mdi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-mdi", required=True)
    parser.add_argument("--fingerprint", action="store_true")
    # a factor on the energy, to tell engines apart when several are live
    parser.add_argument("--scale", type=float, default=1.0)
    # <SPIN: "open" sends <S**2> = 0.7556, S(S+1) = 0.75; "closed" sends NaN
    parser.add_argument("--spin", choices=("open", "closed"), default=None)
    # SAVE_GUESS / RESTORE_GUESS / TIGHT_SCF / NORMAL_SCF; their effect shows in
    # the energy: +1000 while tight, +10 per RESTORE_GUESS since the last SAVE_GUESS
    parser.add_argument("--guess", action="store_true")
    args = parser.parse_args()

    mdi.MDI_Init(args.mdi)
    comm = mdi.MDI_Accept_Communicator()

    mdi.MDI_Register_node("@DEFAULT")
    for command in (
        "<NATOMS",
        ">NATOMS",
        "<NAME",
        ">ELEMENTS",
        ">COORDS",
        ">CELL",
        "SCF",
        "<ENERGY",
        "<FORCES",
        "<STRESS",
        "EXIT",
    ):
        mdi.MDI_Register_command("@DEFAULT", command)
    if args.fingerprint:
        mdi.MDI_Register_command("@DEFAULT", "<FINGERPRINT_LENGTH")
        mdi.MDI_Register_command("@DEFAULT", "<FINGERPRINT")
    if args.spin is not None:
        mdi.MDI_Register_command("@DEFAULT", "<SPIN")
    if args.guess:
        for command in ("SAVE_GUESS", "RESTORE_GUESS", "TIGHT_SCF", "NORMAL_SCF"):
            mdi.MDI_Register_command("@DEFAULT", command)
    tight = False
    restores = 0
    records = {"energy": None, "hessian": None}

    natoms = 0
    coords = None
    cell = np.zeros(9)

    while True:
        command = mdi.MDI_Recv_Command(comm)
        if command == ">NATOMS":
            natoms = int(np.asarray(mdi.MDI_Recv(1, mdi.MDI_INT, comm)).flat[0])
            coords = np.zeros(3 * natoms)
        elif command == "<NATOMS":
            mdi.MDI_Send(natoms, 1, mdi.MDI_INT, comm)
        elif command == "<NAME":
            mdi.MDI_Send("MOCK", mdi.MDI_NAME_LENGTH, mdi.MDI_CHAR, comm)
        elif command == ">ELEMENTS":
            mdi.MDI_Recv(natoms, mdi.MDI_INT, comm)  # accepted, unused
        elif command == ">COORDS":
            coords = np.asarray(mdi.MDI_Recv(3 * natoms, mdi.MDI_DOUBLE, comm))
        elif command == ">CELL":
            cell = np.asarray(mdi.MDI_Recv(9, mdi.MDI_DOUBLE, comm))
        elif command == "<STRESS":
            # Echo the cell so the driver can check the round trip.
            mdi.MDI_Send(cell.tolist(), 9, mdi.MDI_DOUBLE, comm)
        elif command == "SCF":
            pass
        elif command == "<ENERGY":
            energy = args.scale * 0.5 * float(coords.sum())
            energy += (1000.0 if tight else 0.0) + 10.0 * restores
            mdi.MDI_Send(energy, 1, mdi.MDI_DOUBLE, comm)
            # A record about as long as a real one, with text that has to be escaped
            records["energy"] = {
                "program": "MOCK",
                "fingerprint": "sha256:mock",
                "files": {"orca.inp": "! B2PLYP D3ZERO cc-pVTZ\n%SCF\nEND\n" * 200},
                "note": "Å ² — not ASCII",
            }
        elif command in ("<FINGERPRINT_LENGTH", "<FINGERPRINT"):
            text = json.dumps(records, sort_keys=True)
            if command == "<FINGERPRINT_LENGTH":
                mdi.MDI_Send(len(text), 1, mdi.MDI_INT, comm)
            else:
                mdi.MDI_Send(text, len(text), mdi.MDI_CHAR, comm)
        elif command == "<SPIN":
            values = [0.7556, 0.75] if args.spin == "open" else [np.nan, np.nan]
            mdi.MDI_Send(values, 2, mdi.MDI_DOUBLE, comm)
        elif command == "<FORCES":
            forces = np.full(3 * natoms, -0.5)
            mdi.MDI_Send(forces.tolist(), 3 * natoms, mdi.MDI_DOUBLE, comm)
        elif command == "SAVE_GUESS":
            restores = 0
        elif command == "RESTORE_GUESS":
            restores += 1
        elif command in ("TIGHT_SCF", "NORMAL_SCF"):
            tight = command == "TIGHT_SCF"
        elif command == "EXIT":
            break


if __name__ == "__main__":
    main()
