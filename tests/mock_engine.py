# -*- coding: utf-8 -*-

"""A minimal MDI engine for testing the seamm_mdi driver.

It speaks just enough of the MDI protocol to exercise ``MDIEngine``, returning a
deterministic energy/forces from the coordinates it receives (in bohr), so tests
can verify the protocol and the unit conversions without a real QM code.

    energy   = 0.5 * sum(coords_bohr)          [hartree]
    forces   = -0.5 for every component        [hartree/bohr]  (-dE/dx)

Run as:  python mock_engine.py -mdi "-role ENGINE -name MOCK -method TCP \\
             -port <port> -hostname <host>"
"""

import argparse

import numpy as np

import mdi


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-mdi", required=True)
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
        "SCF",
        "<ENERGY",
        "<FORCES",
        "EXIT",
    ):
        mdi.MDI_Register_command("@DEFAULT", command)

    natoms = 0
    coords = None

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
        elif command == "SCF":
            pass
        elif command == "<ENERGY":
            mdi.MDI_Send(0.5 * float(coords.sum()), 1, mdi.MDI_DOUBLE, comm)
        elif command == "<FORCES":
            forces = np.full(3 * natoms, -0.5)
            mdi.MDI_Send(forces.tolist(), 3 * natoms, mdi.MDI_DOUBLE, comm)
        elif command == "EXIT":
            break


if __name__ == "__main__":
    main()
