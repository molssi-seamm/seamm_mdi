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
            mdi.MDI_Send(0.5 * float(coords.sum()), 1, mdi.MDI_DOUBLE, comm)
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
        elif command == "<FORCES":
            forces = np.full(3 * natoms, -0.5)
            mdi.MDI_Send(forces.tolist(), 3 * natoms, mdi.MDI_DOUBLE, comm)
        elif command == "EXIT":
            break


if __name__ == "__main__":
    main()
