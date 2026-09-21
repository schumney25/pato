#!/usr/bin/env python3
"""
Convert a PATO/OpenFOAM porousMat surface and temperature field to a
3-D SPARTA explicit surface file.

The converter:
  1. Selects a PATO solution time (explicit value or "latest").
  2. Reads constant/porousMat/polyMesh/{points,faces,boundary}.
  3. Extracts the boundary patch named "cylinder".
  4. Reads <time>/porousMat/Ta and extracts boundaryField/cylinder.
  5. Converts triangular faces directly and quadrilateral faces into two
     triangles while preserving the parent-face temperature.
  6. Compacts the referenced PATO points into a SPARTA point list.
  7. Writes a SPARTA read_surf-compatible file with a per-triangle
     custom temperature value.

SPARTA input corresponding to the output file:
    read_surf <file> custom temperature float 0
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Point:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Triangle:
    # PATO point indices, retained for internal provenance.
    pato_points: tuple[int, int, int]

    # PATO boundary-face local index.
    parent_face: int

    # PATO boundary-face temperature.
    temperature: float


# ---------------------------------------------------------------------------
# OpenFOAM text utilities
# ---------------------------------------------------------------------------

def strip_comments(text: str) -> str:
    """Remove // and /* ... */ comments."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*?$", "", text, flags=re.MULTILINE)
    return text


def extract_delimited(
    text: str,
    start: int,
    opening: str,
    closing: str,
) -> tuple[str, int]:
    """Return the contents of the delimited block beginning at/after start."""
    open_pos = text.find(opening, start)
    if open_pos < 0:
        raise ValueError(f"Could not find opening '{opening}'.")

    depth = 0
    for i in range(open_pos, len(text)):
        c = text[i]
        if c == opening:
            depth += 1
        elif c == closing:
            depth -= 1
            if depth == 0:
                return text[open_pos + 1:i], i + 1

    raise ValueError(
        f"Unterminated block beginning with '{opening}'."
    )


def extract_parenthesized(text: str, start: int) -> tuple[str, int]:
    return extract_delimited(text, start, "(", ")")


def extract_braced(text: str, start: int) -> tuple[str, int]:
    return extract_delimited(text, start, "{", "}")


def parse_declared_list(text: str, keyword: str) -> tuple[int, str]:
    """
    Find an OpenFOAM list in a standard file such as points/faces.

    OpenFOAM mesh files normally have a header like:

        FoamFile
        {
            ...
            object points;
        }

        168515
        (
            ...
        )

    The object name is therefore NOT immediately followed by the count.
    """
    object_match = re.search(
        rf"\bobject\s+{re.escape(keyword)}\s*;",
        text,
        flags=re.DOTALL,
    )
    if not object_match:
        raise ValueError(
            f"Could not find OpenFOAM object '{keyword}' in mesh file."
        )

    # The first '<integer> (' after the object declaration is the list
    # count/body pair. Restrict the search to the portion following the
    # object declaration so unrelated header integers cannot be selected.
    m = re.search(
        r"\b(\d+)\s*\(",
        text[object_match.end():],
        flags=re.DOTALL,
    )
    if not m:
        raise ValueError(f"Could not find list '{keyword}'.")

    count = int(m.group(1))
    list_start = object_match.end() + m.start()
    contents, _ = extract_parenthesized(text, list_start)
    return count, contents


# ---------------------------------------------------------------------------
# PATO mesh parsing
# ---------------------------------------------------------------------------

def read_points(path: Path) -> list[Point]:
    text = strip_comments(path.read_text(encoding="utf-8"))
    count, body = parse_declared_list(text, path.stem)

    # Points are stored as:
    # (x y z)
    matches = re.findall(
        r"\(\s*"
        r"([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)\s+"
        r"([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)\s+"
        r"([+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?)"
        r"\s*\)",
        body,
    )

    if len(matches) != count:
        raise ValueError(
            f"{path}: declared {count} points, parsed {len(matches)}."
        )

    return [Point(float(x), float(y), float(z)) for x, y, z in matches]


def read_faces(path: Path) -> list[list[int]]:
    text = strip_comments(path.read_text(encoding="utf-8"))
    count, body = parse_declared_list(text, path.stem)

    # Each OpenFOAM face is:
    # N(i0 i1 ...)
    #
    # There may be whitespace between N and '('.
    face_matches = re.finditer(
        r"(\d+)\s*\(([^()]*)\)",
        body,
        flags=re.DOTALL,
    )

    faces: list[list[int]] = []

    for match in face_matches:
        n = int(match.group(1))
        indices = [int(v) for v in match.group(2).split()]

        if len(indices) != n:
            raise ValueError(
                f"{path}: face declares {n} vertices but contains "
                f"{len(indices)} indices."
            )

        faces.append(indices)

    if len(faces) != count:
        raise ValueError(
            f"{path}: declared {count} faces, parsed {len(faces)}."
        )

    return faces


def read_boundary_patch(path: Path, patch_name: str) -> tuple[int, int]:
    """
    Return (startFace, nFaces) for a named OpenFOAM boundary patch.
    """
    text = strip_comments(path.read_text(encoding="utf-8"))

    # Find the named patch block.
    m = re.search(
        rf"\b{re.escape(patch_name)}\s*\{{(.*?)\}}",
        text,
        flags=re.DOTALL,
    )
    if not m:
        raise ValueError(
            f"Boundary patch '{patch_name}' was not found in {path}."
        )

    block = m.group(1)

    nfaces_match = re.search(r"\bnFaces\s+(\d+)\s*;", block)
    start_match = re.search(r"\bstartFace\s+(\d+)\s*;", block)

    if not nfaces_match or not start_match:
        raise ValueError(
            f"Boundary patch '{patch_name}' is missing nFaces or startFace."
        )

    return int(start_match.group(1)), int(nfaces_match.group(1))


# ---------------------------------------------------------------------------
# PATO Ta parsing
# ---------------------------------------------------------------------------

def read_ta_boundary(path: Path, patch_name: str) -> list[float]:
    """
    Extract the nonuniform scalar list in:
        boundaryField
        {
            <patch_name>
            {
                ...
                value nonuniform List<scalar>
                N
                (
                    ...
                );
            }
        }
    """
    text = strip_comments(path.read_text(encoding="utf-8"))

    bf_match = re.search(
        r"\bboundaryField\s*\{",
        text,
        flags=re.DOTALL,
    )
    if not bf_match:
        raise ValueError(f"{path}: boundaryField block not found.")

    # Locate the requested patch after boundaryField.
    patch_match = re.search(
        rf"\b{re.escape(patch_name)}\s*\{{",
        text[bf_match.end():],
        flags=re.DOTALL,
    )
    if not patch_match:
        raise ValueError(
            f"{path}: boundary patch '{patch_name}' not found in Ta."
        )

    patch_start = bf_match.end() + patch_match.start()
    patch_body, _ = extract_braced(text, patch_start)

    value_match = re.search(
        r"\bvalue\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(",
        patch_body,
        flags=re.DOTALL,
    )
    if not value_match:
        raise ValueError(
            f"{path}: no nonuniform scalar 'value' found for patch "
            f"'{patch_name}'."
        )

    count = int(value_match.group(1))
    values_body, _ = extract_parenthesized(patch_body, value_match.start())

    # Scalar values are whitespace-separated.
    values = [float(v) for v in values_body.split()]

    if len(values) != count:
        raise ValueError(
            f"{path}: Ta declares {count} boundary values but parsed "
            f"{len(values)}."
        )

    return values


# ---------------------------------------------------------------------------
# Time selection
# ---------------------------------------------------------------------------

def is_numeric_time_dir(path: Path) -> bool:
    if not path.is_dir():
        return False
    try:
        float(path.name)
        return True
    except ValueError:
        return False


def find_solution_time(case_dir: Path, requested: str) -> tuple[str, Path]:
    porous_mat = "porousMat"

    if requested.lower() != "latest":
        try:
            numeric_time = float(requested)
        except ValueError as exc:
            raise ValueError(
                f"Invalid --time '{requested}'. Use a numeric time or "
                f"'latest'."
            ) from exc

        # Prefer the exact directory spelling if it exists.
        direct = case_dir / requested / porous_mat / "Ta"
        if direct.is_file():
            return requested, direct

        # Otherwise locate a numerically equivalent directory.
        candidates = [
            p for p in case_dir.iterdir()
            if is_numeric_time_dir(p)
        ]
        matches = [p for p in candidates if math.isclose(
            float(p.name), numeric_time, rel_tol=0.0, abs_tol=1.0e-15
        )]

        if not matches:
            raise FileNotFoundError(
                f"No PATO solution time matching {requested!r} was found."
            )

        time_dir = matches[0]
        ta = time_dir / porous_mat / "Ta"
        if not ta.is_file():
            raise FileNotFoundError(f"Missing Ta field: {ta}")

        return time_dir.name, ta

    candidates: list[tuple[float, Path, Path]] = []

    for p in case_dir.iterdir():
        if not is_numeric_time_dir(p):
            continue

        ta = p / porous_mat / "Ta"
        if ta.is_file():
            candidates.append((float(p.name), p, ta))

    if not candidates:
        raise FileNotFoundError(
            "No numeric PATO solution directories containing "
            "<time>/porousMat/Ta were found."
        )

    _, time_dir, ta = max(candidates, key=lambda item: item[0])
    return time_dir.name, ta


# ---------------------------------------------------------------------------
# Geometry / triangulation
# ---------------------------------------------------------------------------

def vector_sub(a: Point, b: Point) -> tuple[float, float, float]:
    return a.x - b.x, a.y - b.y, a.z - b.z


def cross(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def dot(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def face_normal(face: list[int], points: list[Point]) -> tuple[float, float, float]:
    """
    Newell normal for an ordered polygon. This is useful as the parent-face
    orientation reference, without changing the actual PATO geometry.
    """
    nx = ny = nz = 0.0

    for i, idx in enumerate(face):
        jdx = face[(i + 1) % len(face)]
        p = points[idx]
        q = points[jdx]

        nx += (p.y - q.y) * (p.z + q.z)
        ny += (p.z - q.z) * (p.x + q.x)
        nz += (p.x - q.x) * (p.y + q.y)

    return nx, ny, nz


def triangle_normal(
    tri: tuple[int, int, int],
    points: list[Point],
) -> tuple[float, float, float]:
    p0 = points[tri[0]]
    p1 = points[tri[1]]
    p2 = points[tri[2]]

    return cross(
        vector_sub(p1, p0),
        vector_sub(p2, p0),
    )


def triangle_area2(
    tri: tuple[int, int, int],
    points: list[Point],
) -> float:
    n = triangle_normal(tri, points)
    return math.sqrt(dot(n, n))


def triangulate_face(
    face: list[int],
    points: list[Point],
    parent_face: int,
    temperature: float,
) -> list[Triangle]:
    """
    Convert one PATO boundary face to one or more SPARTA triangles.

    Current intentionally conservative policy:
      - 3 vertices: direct
      - 4 vertices: deterministic diagonal (0,2)
      - >4 vertices: reject rather than silently apply an unvalidated
        polygon triangulation algorithm.
    """
    # Remove immediate duplicate indices, which should not normally occur.
    cleaned: list[int] = []
    for idx in face:
        if not cleaned or idx != cleaned[-1]:
            cleaned.append(idx)

    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()

    if len(cleaned) == 3:
        tri = (cleaned[0], cleaned[1], cleaned[2])

        if triangle_area2(tri, points) <= 0.0:
            raise ValueError(
                f"Degenerate triangular boundary face {parent_face}."
            )

        return [Triangle(tri, parent_face, temperature)]

    if len(cleaned) == 4:
        # Preserve the PATO polygon ordering. The second triangle shares
        # diagonal (0,2), so both inherit the parent's orientation.
        tri_a = (cleaned[0], cleaned[1], cleaned[2])
        tri_b = (cleaned[0], cleaned[2], cleaned[3])

        parent_n = face_normal(cleaned, points)

        for tri in (tri_a, tri_b):
            if triangle_area2(tri, points) <= 0.0:
                raise ValueError(
                    f"Degenerate triangle generated from PATO face "
                    f"{parent_face}."
                )

        # If numerical/mesh ordering causes the generated triangles to
        # point opposite to the parent polygon, reverse each triangle.
        if dot(triangle_normal(tri_a, points), parent_n) < 0.0:
            tri_a = (tri_a[0], tri_a[2], tri_a[1])

        if dot(triangle_normal(tri_b, points), parent_n) < 0.0:
            tri_b = (tri_b[0], tri_b[2], tri_b[1])

        return [
            Triangle(tri_a, parent_face, temperature),
            Triangle(tri_b, parent_face, temperature),
        ]

    raise ValueError(
        f"PATO boundary face {parent_face} has {len(cleaned)} vertices. "
        "This first converter version supports only triangles and quads."
    )


# ---------------------------------------------------------------------------
# SPARTA surface construction
# ---------------------------------------------------------------------------

def build_sparta_surface(
    boundary_faces: list[list[int]],
    temperatures: list[float],
    points: list[Point],
) -> tuple[list[Point], list[Triangle], dict[int, int]]:
    """
    Extract referenced PATO points and renumber them compactly for SPARTA.
    Returns:
      sparta_points
      triangles
      pato_point_to_sparta_point
    """
    if len(boundary_faces) != len(temperatures):
        raise ValueError(
            "Boundary face count and temperature count do not match."
        )

    triangles: list[Triangle] = []

    referenced: set[int] = set()

    for local_face, (face, temperature) in enumerate(
        zip(boundary_faces, temperatures)
    ):
        for idx in face:
            if idx < 0 or idx >= len(points):
                raise ValueError(
                    f"Boundary face {local_face} references invalid "
                    f"PATO point index {idx}."
                )
            referenced.add(idx)

        triangles.extend(
            triangulate_face(
                face=face,
                points=points,
                parent_face=local_face,
                temperature=temperature,
            )
        )

    # Deterministic compact numbering based on ascending PATO point index.
    ordered_pato_points = sorted(referenced)
    pato_to_sparta = {
        pato_idx: sparta_idx
        for sparta_idx, pato_idx in enumerate(ordered_pato_points, start=1)
    }

    sparta_points = [points[idx] for idx in ordered_pato_points]

    return sparta_points, triangles, pato_to_sparta


def validate_surface(
    triangles: list[Triangle],
    points: list[Point],
    pato_to_sparta: dict[int, int],
) -> None:
    """Validate connectivity and geometry before writing."""
    for i, tri in enumerate(triangles, start=1):
        p = tri.pato_points

        try:
            s = tuple(pato_to_sparta[idx] for idx in p)
        except KeyError as exc:
            raise ValueError(
                f"Triangle {i} references a PATO point that was not mapped."
            ) from exc

        if len(set(s)) != 3:
            raise ValueError(f"Triangle {i} has duplicate point indices.")

        if triangle_area2(p, points) <= 0.0:
            raise ValueError(f"Triangle {i} has zero area.")

        if not math.isfinite(tri.temperature):
            raise ValueError(
                f"Triangle {i} has non-finite temperature "
                f"{tri.temperature!r}."
            )


def write_sparta_surface(
    output: Path,
    points: list[Point],
    triangles: list[Triangle],
    pato_to_sparta: dict[int, int],
) -> None:
    with output.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# PATO -> SPARTA surface generated by pato2sparta.py\n")
        f.write(f"{len(points)} points\n")
        f.write(f"{len(triangles)} triangles\n")
        f.write("\n")
        f.write("Points\n")
        f.write("\n")

        for i, p in enumerate(points, start=1):
            f.write(
                f"{i} "
                f"{p.x:.16g} "
                f"{p.y:.16g} "
                f"{p.z:.16g}\n"
            )

        f.write("\n")
        f.write("Triangles\n")
        f.write("\n")

        for i, tri in enumerate(triangles, start=1):
            p1 = pato_to_sparta[tri.pato_points[0]]
            p2 = pato_to_sparta[tri.pato_points[1]]
            p3 = pato_to_sparta[tri.pato_points[2]]

            f.write(
                f"{i} {p1} {p2} {p3} "
                f"{tri.temperature:.16g}\n"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a PATO/OpenFOAM porousMat surface and Ta field "
            "to a 3-D SPARTA read_surf surface file."
        )
    )

    parser.add_argument(
        "--case",
        required=True,
        type=Path,
        help="PATO case directory.",
    )

    parser.add_argument(
        "--time",
        required=True,
        default="latest",
        help="PATO solution time, e.g. 1.1e-05, or 'latest'.",
    )

    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output SPARTA surface filename.",
    )

    parser.add_argument(
        "--patch",
        default="cylinder",
        help="PATO boundary patch to convert (default: cylinder).",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    case = args.case.resolve()

    if not case.is_dir():
        raise FileNotFoundError(f"PATO case directory not found: {case}")

    poly_mesh = case / "constant" / "porousMat" / "polyMesh"

    points_file = poly_mesh / "points"
    faces_file = poly_mesh / "faces"
    boundary_file = poly_mesh / "boundary"

    for path in (points_file, faces_file, boundary_file):
        if not path.is_file():
            raise FileNotFoundError(f"Required PATO mesh file not found: {path}")

    solution_time, ta_file = find_solution_time(case, args.time)

    print(f"PATO case:       {case}")
    print(f"Solution time:   {solution_time}")
    print(f"Boundary patch:  {args.patch}")

    points = read_points(points_file)
    faces = read_faces(faces_file)
    start_face, n_faces = read_boundary_patch(
        boundary_file,
        args.patch,
    )

    temperatures = read_ta_boundary(
        ta_file,
        args.patch,
    )

    if start_face < 0 or start_face + n_faces > len(faces):
        raise ValueError(
            f"Boundary patch '{args.patch}' extends beyond the faces list: "
            f"startFace={start_face}, nFaces={n_faces}, "
            f"total_faces={len(faces)}."
        )

    if len(temperatures) != n_faces:
        raise ValueError(
            f"Patch '{args.patch}' has {n_faces} faces, but Ta contains "
            f"{len(temperatures)} boundary values."
        )

    boundary_faces = faces[start_face:start_face + n_faces]

    n_tri_pato = sum(len(face) == 3 for face in boundary_faces)
    n_quad_pato = sum(len(face) == 4 for face in boundary_faces)

    other = [
        (i, len(face))
        for i, face in enumerate(boundary_faces)
        if len(face) not in (3, 4)
    ]

    print(f"PATO points:     {len(points)}")
    print(f"PATO faces:      {len(faces)}")
    print(f"Patch faces:     {n_faces}")
    print(f"Patch triangles: {n_tri_pato}")
    print(f"Patch quads:     {n_quad_pato}")

    if other:
        examples = ", ".join(
            f"{idx}({n} vertices)" for idx, n in other[:5]
        )
        raise ValueError(
            "Unsupported polygon(s) found in the selected boundary patch. "
            f"Examples: {examples}"
        )

    sparta_points, triangles, mapping = build_sparta_surface(
        boundary_faces=boundary_faces,
        temperatures=temperatures,
        points=points,
    )

    validate_surface(
        triangles=triangles,
        points=points,
        pato_to_sparta=mapping,
    )

    if not temperatures:
        raise ValueError("No boundary temperatures were read.")

    tmin = min(temperatures)
    tmax = max(temperatures)
    tmean = sum(temperatures) / len(temperatures)

    print(f"SPARTA points:   {len(sparta_points)}")
    print(f"SPARTA triangles: {len(triangles)}")
    print(f"Ta min:          {tmin:.8g}")
    print(f"Ta max:          {tmax:.8g}")
    print(f"Ta mean:         {tmean:.8g}")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    write_sparta_surface(
        output=args.output,
        points=sparta_points,
        triangles=triangles,
        pato_to_sparta=mapping,
    )

    print(f"Output:          {args.output}")
    print()
    print(
        "SPARTA read command:"
        f"  read_surf {args.output} custom temperature float 0"
    )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
