#!/usr/bin/env python3

"""
Convert a SPARTA dump surf file to a PATO Tecplot mapping file.

Each SPARTA triangular surface element is represented by its centroid.
The requested SPARTA surface quantity is associated with that centroid.

Usage:
    python3 sparta2pato.py --input surf.dump --output sparta_surface

Output:
    sparta_surface_0.dat
    sparta_surface_1.dat
"""

import argparse
from pathlib import Path


# =============================================================================
# SPARTA -> TECPLOT FIELD MAPPING
# =============================================================================

# Format:
#
#     "Tecplot variable name": "SPARTA dump column name"
#
# X, Y, and Z are generated automatically from the SPARTA triangle vertices.

OUTPUT_FIELDS = {
    "qConvCFD": "v_surf_qConvSPARTA",
}


# =============================================================================
# COMMAND-LINE ARGUMENTS
# =============================================================================

def parse_arguments():

    parser = argparse.ArgumentParser(
        description=(
            "Convert a SPARTA surface dump to a PATO Tecplot "
            "surface mapping file."
        )
    )

    parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Input SPARTA surface dump file."
    )

    parser.add_argument(
        "--output",
        "-o",
        required=True,
        type=Path,
        help=(
            "Output base name. "
            "Produces <output>_0.dat and <output>_1.dat."
        )
    )

    return parser.parse_args()


# =============================================================================
# READ SPARTA SURFACE DUMP
# =============================================================================

def read_sparta_surface_dump(filename):

    with open(filename, "r") as f:
        lines = f.readlines()

    header = None
    surfaces = []

    i = 0

    while i < len(lines):

        line = lines[i].strip()

        if line.startswith("ITEM: SURFS"):

            header = line[len("ITEM: SURFS"):].strip().split()

            i += 1

            while i < len(lines):

                data_line = lines[i].strip()

                # Stop at the next SPARTA section.
                if data_line.startswith("ITEM:"):
                    break

                if data_line:

                    values = data_line.split()

                    if len(values) != len(header):
                        raise ValueError(
                            f"Expected {len(header)} values, "
                            f"but found {len(values)}.\n"
                            f"Line:\n{data_line}"
                        )

                    surface = {}

                    for name, value in zip(header, values):

                        if name == "id":
                            surface[name] = int(value)
                        else:
                            surface[name] = float(value)

                    surfaces.append(surface)

                i += 1

            break

        i += 1

    if header is None:
        raise ValueError(
            f'Could not find "ITEM: SURFS" in {filename}.'
        )

    return header, surfaces


# =============================================================================
# VALIDATE REQUESTED SPARTA FIELDS
# =============================================================================

def validate_fields(header):

    for tecplot_name, sparta_name in OUTPUT_FIELDS.items():

        if sparta_name not in header:
            raise ValueError(
                f'SPARTA field "{sparta_name}" required for '
                f'Tecplot field "{tecplot_name}" was not found.'
            )


# =============================================================================
# CALCULATE TRIANGLE CENTROIDS
# =============================================================================

def calculate_centroids(surfaces):

    centroids = []

    for surface in surfaces:

        x = (
            surface["v1x"]
            + surface["v2x"]
            + surface["v3x"]
        ) / 3.0

        y = (
            surface["v1y"]
            + surface["v2y"]
            + surface["v3y"]
        ) / 3.0

        z = (
            surface["v1z"]
            + surface["v2z"]
            + surface["v3z"]
        ) / 3.0

        centroids.append((x, y, z))

    return centroids


# =============================================================================
# WRITE TECPLOT FILE
# =============================================================================

def write_tecplot(filename, centroids, surfaces):

    number_of_points = len(surfaces)

    with open(filename, "w") as f:

        # TITLE
        f.write('TITLE = "SPARTA Surface Data"\n')

        # VARIABLES
        f.write('VARIABLES = "X"\n')
        f.write('"Y"\n')
        f.write('"Z"\n')
        f.write('"qConvCFD"\n')

        # ZONE
        f.write('ZONE T="SPARTA Surface"\n')
        f.write(
            f'Ordered I={number_of_points}, J=1, K=1,\n'
        )
        f.write('DATAPACKING=BLOCK\n')
        f.write(
            'DT=(SINGLE SINGLE SINGLE SINGLE)\n'
        )

        # X block
        for x, y, z in centroids:
            f.write(f"{x:.16e}\n")

        # Y block
        for x, y, z in centroids:
            f.write(f"{y:.16e}\n")

        # Z block
        for x, y, z in centroids:
            f.write(f"{z:.16e}\n")

        # qConvCFD block
        for surface in surfaces:
            f.write(
                f"{surface['v_surf_qConvSPARTA']:.16e}\n"
            )

        # for tecplot_name, sparta_name in OUTPUT_FIELDS.items():

        #     for surface in surfaces:
        #         f.write(
        #             f"{surface[sparta_name]:.16e}\n"
        #         )


# =============================================================================
# MAIN
# =============================================================================

def main():

    args = parse_arguments()

    print(f"Reading SPARTA surface dump: {args.input}")

    header, surfaces = read_sparta_surface_dump(args.input)

    print(
        f"Found {len(surfaces)} SPARTA surface elements."
    )

    validate_fields(header)

    centroids = calculate_centroids(surfaces)

    if len(centroids) != len(surfaces):
        raise RuntimeError(
            "Number of centroids does not match "
            "number of SPARTA surfaces."
        )

    # Two identical mapping files for the current steady-state test.
    output_files = [
        Path(f"{args.output}_0"),
        Path(f"{args.output}_1"),
    ]

    for output_file in output_files:

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        write_tecplot(
            output_file,
            centroids,
            surfaces
        )

        print(f"Wrote: {output_file}")

    print("Conversion complete.")


if __name__ == "__main__":
    main()