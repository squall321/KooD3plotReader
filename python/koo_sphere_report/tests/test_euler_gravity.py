#!/usr/bin/env python3
"""
Test all reasonable interpretations of applying roll/pitch Euler angles
to the gravity vector [0,0,-1] and find which interpretation produces
physically correct impact directions for the 26 cuboid drop orientations.

SUMMARY OF FINDINGS:
====================
1. No standard Euler convention maps the given 45-deg angle table
   to all 26 impact directions. Best standard formula scores 16/26.

2. The best Euler formula is: v = Rx(roll) * Ry(pitch) * [0,0,-1]
   = (-sin(p), sin(r)*cos(p), -cos(r)*cos(p))
   With CORRECTED angles (pitch=35.264 for corners), it scores 26/26.

3. A SIGN-DECODE approach treats angles as direction indicators (not
   rotation parameters) and achieves 26/26 with the ORIGINAL angles.

4. A NAME-BASED LOOKUP parsing face/edge/corner names also gives 26/26.

Coordinate system: X=right, Y=up, Z=back
"""

import numpy as np
from collections import OrderedDict


def Rx(angle_deg):
    """Rotation matrix about X axis."""
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])

def Ry(angle_deg):
    """Rotation matrix about Y axis."""
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])

def Rz(angle_deg):
    """Rotation matrix about Z axis."""
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


# ============================================================
# The 26 drop orientations: (roll_deg, pitch_deg)
# ============================================================
ANGLES = OrderedDict([
    # FACES (6)
    ("F1_Back",    (0, 0)),
    ("F2_Front",   (180, 0)),
    ("F3_Right",   (0, -90)),
    ("F4_Left",    (0, 90)),
    ("F5_Top",     (90, 0)),
    ("F6_Bottom",  (-90, 0)),
    # EDGES (12)
    ("E01_Back_Right",    (0, -45)),
    ("E02_Back_Left",     (0, 45)),
    ("E03_Back_Top",      (45, 0)),
    ("E04_Back_Bottom",   (-45, 0)),
    ("E05_Front_Right",   (180, 45)),
    ("E06_Front_Left",    (180, -45)),
    ("E07_Front_Top",     (135, 0)),
    ("E08_Front_Bottom",  (-135, 0)),
    ("E09_Right_Top",     (90, -45)),
    ("E10_Right_Bottom",  (-90, -45)),
    ("E11_Left_Top",      (90, 45)),
    ("E12_Left_Bottom",   (-90, 45)),
    # CORNERS (8)
    ("C1_Back_Right_Top",     (45, -45)),
    ("C2_Back_Right_Bottom",  (-45, -45)),
    ("C3_Back_Left_Top",      (45, 45)),
    ("C4_Back_Left_Bottom",   (-45, 45)),
    ("C5_Front_Right_Top",    (135, 45)),
    ("C6_Front_Right_Bottom", (-135, 45)),
    ("C7_Front_Left_Top",     (135, -45)),
    ("C8_Front_Left_Bottom",  (-135, -45)),
])

# ============================================================
# Expected impact directions (unit vectors in body frame)
# ============================================================
s2 = 1.0 / np.sqrt(2)
s3 = 1.0 / np.sqrt(3)

EXPECTED = OrderedDict([
    ("F1_Back",    np.array([ 0,  0, -1])),
    ("F2_Front",   np.array([ 0,  0,  1])),
    ("F3_Right",   np.array([ 1,  0,  0])),
    ("F4_Left",    np.array([-1,  0,  0])),
    ("F5_Top",     np.array([ 0,  1,  0])),
    ("F6_Bottom",  np.array([ 0, -1,  0])),
    ("E01_Back_Right",    np.array([ s2,  0, -s2])),
    ("E02_Back_Left",     np.array([-s2,  0, -s2])),
    ("E03_Back_Top",      np.array([ 0,  s2, -s2])),
    ("E04_Back_Bottom",   np.array([ 0, -s2, -s2])),
    ("E05_Front_Right",   np.array([ s2,  0,  s2])),
    ("E06_Front_Left",    np.array([-s2,  0,  s2])),
    ("E07_Front_Top",     np.array([ 0,  s2,  s2])),
    ("E08_Front_Bottom",  np.array([ 0, -s2,  s2])),
    ("E09_Right_Top",     np.array([ s2,  s2,  0])),
    ("E10_Right_Bottom",  np.array([ s2, -s2,  0])),
    ("E11_Left_Top",      np.array([-s2,  s2,  0])),
    ("E12_Left_Bottom",   np.array([-s2, -s2,  0])),
    ("C1_Back_Right_Top",     np.array([ s3,  s3, -s3])),
    ("C2_Back_Right_Bottom",  np.array([ s3, -s3, -s3])),
    ("C3_Back_Left_Top",      np.array([-s3,  s3, -s3])),
    ("C4_Back_Left_Bottom",   np.array([-s3, -s3, -s3])),
    ("C5_Front_Right_Top",    np.array([ s3,  s3,  s3])),
    ("C6_Front_Right_Bottom", np.array([ s3, -s3,  s3])),
    ("C7_Front_Left_Top",     np.array([-s3,  s3,  s3])),
    ("C8_Front_Left_Bottom",  np.array([-s3, -s3,  s3])),
])


def check_formula(name, compute_func):
    """Test a formula against all 26 expected directions."""
    n_ok = 0
    details = []
    for label, (roll, pitch) in ANGLES.items():
        v = compute_func(roll, pitch)
        norm = np.linalg.norm(v)
        v = v / norm if norm > 1e-10 else np.zeros(3)
        expected = EXPECTED[label]
        ok = np.allclose(v, expected, atol=1e-6)
        if ok:
            n_ok += 1
        details.append((label, roll, pitch, v, expected, ok))
    return n_ok, details


def print_details(name, n_ok, details, show_all=True, failures_only=False):
    """Print test results."""
    total = len(details)
    f_ok = sum(1 for d in details if d[0].startswith("F") and d[5])
    e_ok = sum(1 for d in details if d[0].startswith("E") and d[5])
    c_ok = sum(1 for d in details if d[0].startswith("C") and d[5])
    tag = " <<<< PERFECT" if n_ok == total else ""

    print(f"\n{'='*90}")
    print(f"  {name}")
    print(f"  Score: {n_ok}/{total}  (F:{f_ok}/6  E:{e_ok}/12  C:{c_ok}/8){tag}")
    print(f"{'='*90}")

    for label, roll, pitch, got, exp, ok in details:
        if failures_only and ok:
            continue
        if not show_all and ok:
            continue
        t = "OK " if ok else "BAD"
        g = f"({got[0]:+7.4f}, {got[1]:+7.4f}, {got[2]:+7.4f})"
        e = f"({exp[0]:+7.4f}, {exp[1]:+7.4f}, {exp[2]:+7.4f})"
        print(f"  [{t}] {label:28s} r={roll:+5.0f} p={pitch:+5.0f}  got={g}  exp={e}")


# ====================================================================
#  PART 1: Exhaustive search over all standard Euler interpretations
# ====================================================================
def part1_exhaustive_search():
    print()
    print("#" * 90)
    print("#  PART 1: EXHAUSTIVE SEARCH (576 standard Euler interpretations)")
    print("#" * 90)
    print()
    print("  Testing all combinations of:")
    print("    - 6 initial gravity vectors (+/-X, +/-Y, +/-Z)")
    print("    - 6 axis pairings for roll/pitch (Rx/Ry/Rz)")
    print("    - 4 sign combinations (+/-roll, +/-pitch)")
    print("    - 2 rotation orders (roll-first, pitch-first)")
    print("    - 2 transpose options (R or R^T)")

    gravity_vectors = {
        "-Z": np.array([0, 0, -1]),  "+Z": np.array([0, 0, 1]),
        "-Y": np.array([0, -1, 0]),  "+Y": np.array([0, 1, 0]),
        "-X": np.array([-1, 0, 0]),  "+X": np.array([1, 0, 0]),
    }
    axis_combos = {
        "Rx,Ry": (Rx, Ry), "Rx,Rz": (Rx, Rz), "Ry,Rx": (Ry, Rx),
        "Ry,Rz": (Ry, Rz), "Rz,Rx": (Rz, Rx), "Rz,Ry": (Rz, Ry),
    }

    results = []
    for gn, gv in gravity_vectors.items():
        for an, (Rr, Rp) in axis_combos.items():
            for sr, sp in [(1,1),(-1,1),(1,-1),(-1,-1)]:
                for order, combine in [("r*p", lambda a,b: a@b), ("p*r", lambda a,b: b@a)]:
                    for tr_label, tr in [("", False), ("^T", True)]:
                        def mk(roll, pitch, _sr=sr, _sp=sp, _g=gv,
                               _Rr=Rr, _Rp=Rp, _c=combine, _t=tr):
                            R = _c(_Rr(_sr*roll), _Rp(_sp*pitch))
                            return (R.T if _t else R) @ _g
                        sn = f"{sr:+d}r,{sp:+d}p"
                        nm = f"g={gn} {an} {sn} {order}{tr_label}"
                        n, d = check_formula(nm, mk)
                        results.append((n, nm, d))

    results.sort(key=lambda x: -x[0])
    print(f"\n  Tested {len(results)} interpretations.\n")
    print("  TOP 15:")
    for i, (s, n, _) in enumerate(results[:15]):
        tag = " <<<< PERFECT!" if s == 26 else ""
        print(f"    {i+1:3d}. {s:2d}/26  {n}{tag}")

    best = results[0][0]
    if best < 26:
        print(f"\n  RESULT: NO PERFECT MATCH. Best = {best}/26.")
        print("  All top results use g=-Z with roll=Rx, pitch=Ry.")
    return results


# ====================================================================
#  PART 2: Algebraic analysis of the best Euler formula
# ====================================================================
def part2_algebra():
    print()
    print("#" * 90)
    print("#  PART 2: ALGEBRAIC ANALYSIS OF BEST EULER FORMULA")
    print("#" * 90)
    print()
    print("  Best Euler formula: v = Rx(roll) * Ry(pitch) * [0, 0, -1]")
    print()
    print("  Step-by-step expansion:")
    print("    Ry(p) * [0, 0, -1] = [-sin(p),  0,  -cos(p)]")
    print("    Rx(r) * [-sin(p), 0, -cos(p)]:")
    print("      x = -sin(p)")
    print("      y =  0*cos(r) - (-cos(p))*sin(r) =  sin(r)*cos(p)")
    print("      z =  0*sin(r) + (-cos(p))*cos(r) = -cos(r)*cos(p)")
    print()
    print("  CLOSED FORM: v = ( -sin(p),  sin(r)*cos(p),  -cos(r)*cos(p) )")
    print()

    g = np.array([0, 0, -1])
    n, d = check_formula("Rx(r)*Ry(p)*[0,0,-1]", lambda r,p: Rx(r) @ Ry(p) @ g)
    print_details("Rx(r)*Ry(p)*[0,0,-1] with original angles", n, d, failures_only=True)

    print()
    print("  FAILURE ANALYSIS:")
    print()
    print("  Edge failures (E05, E06):")
    print("    E05_Front_Right: roll=180, pitch=+45")
    print("    v = (-sin(45), sin(180)*cos(45), -cos(180)*cos(45))")
    print("      = (-0.707,   0.000,             0.707)")
    print("    Expected: (+0.707, 0.000, +0.707)")
    print("    Issue: Rx(180) flips the meaning of pitch (X component sign).")
    print("    Correct pitch for this case: -45 (not +45).")
    print()
    print("  Corner failures (all 8):")
    print("    C1_Back_Right_Top: roll=45, pitch=-45")
    print("    v = (sin(45), sin(45)*cos(45), -cos(45)*cos(45))")
    print("      = (0.7071,  0.5000,          -0.5000)")
    print("    Expected: (0.5774, 0.5774, -0.5774)")
    print()
    print("    The X component is set by sin(pitch) alone = 0.707,")
    print("    while Y and Z share the remaining cos(pitch) = 0.707 factor.")
    print("    For equal components, we need:")
    print(f"      sin(p) = 1/sqrt(3) => p = {np.degrees(np.arcsin(1/np.sqrt(3))):.3f} deg  (not 45)")
    print()


# ====================================================================
#  PART 3: Corrected angle table for the Euler formula
# ====================================================================
def part3_corrected_angles():
    print()
    print("#" * 90)
    print("#  PART 3: CORRECTED ANGLE TABLE (for Euler formula)")
    print("#" * 90)
    print()
    print("  Inverse: given target (dx, dy, dz),  pitch = arcsin(-dx),  roll = atan2(dy, -dz)")
    print()

    g = np.array([0, 0, -1])
    print(f"  {'Name':28s} {'Original':>12s} {'Corrected':>14s}")
    print(f"  {'':28s} {'(r, p)':>12s} {'(r, p)':>14s}")
    print("  " + "-" * 58)

    n_diff = 0
    for name, exp in EXPECTED.items():
        dx, dy, dz = exp
        pitch = np.degrees(np.arcsin(np.clip(-dx, -1, 1)))
        cos_p = np.cos(np.radians(pitch))
        roll = np.degrees(np.arctan2(dy, -dz)) if cos_p > 1e-10 else 0.0
        v = Rx(roll) @ Ry(pitch) @ g
        assert np.allclose(v, exp, atol=1e-6), f"Verify failed: {name}"

        gr, gp = ANGLES[name]
        diff = not (abs(gr - roll) < 0.1 and abs(gp - pitch) < 0.1)
        if diff:
            n_diff += 1
        print(f"  {name:28s} ({gr:+4.0f},{gp:+4.0f})   "
              f"({roll:+8.3f},{pitch:+7.3f})  "
              f"{'  <-- DIFF' if diff else ''}")

    print(f"\n  {n_diff}/26 differ: 2 front edges (E05, E06) + 8 corners.")
    print(f"  All 26 produce correct vectors with corrected angles.")


# ====================================================================
#  PART 4: Sign-decode approach (26/26 with original angles)
# ====================================================================
def part4_sign_decode():
    print()
    print("#" * 90)
    print("#  PART 4: SIGN-DECODE APPROACH (26/26 with original angles)")
    print("#" * 90)
    print()
    print("  This approach treats roll and pitch as DIRECTION INDICATORS,")
    print("  not rotation angles. It extracts sign patterns to build")
    print("  normalized direction vectors directly.")
    print()
    print("  ALGORITHM:")
    print("    1. Z component from roll magnitude:")
    print("         |roll| < 90  => sz = -1  (back)")
    print("         |roll| > 90  => sz = +1  (front)")
    print("         |roll| = 90  => sz =  0  (neither)")
    print()
    print("    2. X component from pitch, FLIPPED when in front hemisphere:")
    print("         pitch < 0  => sx = +1  (right)   [flipped to -1 when |roll|>90]")
    print("         pitch > 0  => sx = -1  (left)    [flipped to +1 when |roll|>90]")
    print("         pitch = 0  => sx =  0")
    print("         When |pitch| >= 90, force sz = 0 (pure sideways)")
    print()
    print("    3. Y component from roll sign:")
    print("         0 < roll < 180   => sy = +1  (top)")
    print("         -180 < roll < 0  => sy = -1  (bottom)")
    print("         roll = 0 or 180  => sy =  0")
    print()
    print("    4. Normalize: v = (sx, sy, sz) / ||(sx, sy, sz)||")
    print()

    def sign_decode(roll, pitch):
        """Decode roll/pitch as direction sign indicators."""
        abs_r = abs(roll)
        abs_p = abs(pitch)

        # Z from roll quadrant (but suppress when |pitch|=90)
        if abs_p > 90 - 1e-6:
            sz = 0  # pure sideways, no back/front
        elif abs_r < 90 - 1e-6:
            sz = -1  # back
        elif abs_r > 90 + 1e-6:
            sz = 1   # front
        else:
            sz = 0   # pure top/bottom/right/left

        # X from pitch, flip when in front hemisphere
        flip_x = -1 if abs_r > 90 + 1e-6 else 1
        if pitch < -1e-6:
            sx = flip_x * 1   # right (or left if flipped)
        elif pitch > 1e-6:
            sx = flip_x * (-1) # left (or right if flipped)
        else:
            sx = 0

        # Y from roll sign
        if 1e-6 < roll < 180 - 1e-6:
            sy = 1   # top
        elif -180 + 1e-6 < roll < -1e-6:
            sy = -1  # bottom
        else:
            sy = 0

        v = np.array([float(sx), float(sy), float(sz)])
        n = np.linalg.norm(v)
        return v / n if n > 1e-10 else v

    n, d = check_formula("Sign-decode (with front-hemisphere X flip)", sign_decode)
    print_details("Sign-decode (with front-hemisphere X flip)", n, d, show_all=True)
    return n


# ====================================================================
#  PART 5: Name-based lookup (trivially 26/26)
# ====================================================================
def part5_lookup():
    print()
    print("#" * 90)
    print("#  PART 5: NAME-BASED LOOKUP (trivially 26/26)")
    print("#" * 90)
    print()
    print("  Parse direction keywords from the orientation name:")
    print()
    print("    def get_direction(name):")
    print("        x = +1 if 'Right' in name else (-1 if 'Left' in name else 0)")
    print("        y = +1 if 'Top' in name else (-1 if 'Bottom' in name else 0)")
    print("        z = -1 if 'Back' in name else (+1 if 'Front' in name else 0)")
    print("        return normalize(x, y, z)")

    def from_name(name):
        x = 1.0 if 'Right' in name else (-1.0 if 'Left' in name else 0.0)
        y = 1.0 if 'Top' in name else (-1.0 if 'Bottom' in name else 0.0)
        z = -1.0 if 'Back' in name else (1.0 if 'Front' in name else 0.0)
        v = np.array([x, y, z])
        return v / np.linalg.norm(v) if np.linalg.norm(v) > 1e-10 else v

    n_ok = sum(1 for name, exp in EXPECTED.items()
               if np.allclose(from_name(name), exp, atol=1e-6))
    print(f"\n  Result: {n_ok}/26 {'PERFECT' if n_ok == 26 else 'FAIL'}")


# ====================================================================
#  PART 6: Spherical distribution verification
# ====================================================================
def part6_distribution():
    print()
    print("#" * 90)
    print("#  PART 6: SPHERICAL DISTRIBUTION VERIFICATION")
    print("#" * 90)
    print()

    vectors = list(EXPECTED.values())
    all_unit = all(abs(np.linalg.norm(v) - 1.0) < 1e-6 for v in vectors)
    n_anti = sum(1 for v in vectors
                 if any(np.allclose(v, -w, atol=1e-6) for w in vectors))
    unique = []
    for v in vectors:
        if not any(np.allclose(v, u, atol=1e-6) for u in unique):
            unique.append(v)

    angs = []
    for i in range(len(vectors)):
        for j in range(i+1, len(vectors)):
            dot = np.clip(np.dot(vectors[i], vectors[j]), -1, 1)
            angs.append(np.degrees(np.arccos(dot)))
    angs.sort()

    print(f"  All unit vectors:       {all_unit}")
    print(f"  Antipodal partners:     {n_anti}/26 (all have their -v counterpart)")
    print(f"  Unique directions:      {len(unique)}/26")
    print(f"  Min angular separation: {angs[0]:.1f} deg (between adjacent corners)")
    print(f"  Median angular sep:     {angs[len(angs)//2]:.1f} deg")
    print(f"  Max angular sep:        {angs[-1]:.1f} deg (antipodal pairs)")
    print()

    for cat, pfx, nz in [("Faces", "F", 1), ("Edges", "E", 2), ("Corners", "C", 3)]:
        items = [(n, v) for n, v in EXPECTED.items() if n.startswith(pfx)]
        ok = all(np.sum(np.abs(v) > 1e-6) == nz for _, v in items)
        print(f"  {cat:8s} ({len(items):2d}): all have exactly {nz} nonzero component(s): {ok}")

    print()
    print("  The 26 directions correspond to the face centers (6), edge midpoints (12),")
    print("  and corner vertices (8) of a cube inscribed in a unit sphere.")


# ====================================================================
#  MAIN
# ====================================================================
def main():
    print("=" * 90)
    print(" EULER ANGLE INTERPRETATION TESTER FOR 26 CUBOID DROP ORIENTATIONS")
    print("=" * 90)
    print()
    print(" Coordinate system: X = right/left,  Y = top/bottom,  Z = back/front")
    print(" Goal: find the formula that maps (roll, pitch) -> impact direction vector")

    # Part 1: Exhaustive search
    results = part1_exhaustive_search()

    # Part 2: Why the best Euler formula fails
    part2_algebra()

    # Part 3: What corrected angles would work
    part3_corrected_angles()

    # Part 4: Sign-decode (the winner)
    decode_score = part4_sign_decode()

    # Part 5: Name-based lookup
    part5_lookup()

    # Part 6: Distribution check
    part6_distribution()

    # Final conclusions
    print()
    print("=" * 90)
    print(" CONCLUSIONS")
    print("=" * 90)
    print()
    print("  Three approaches to compute impact direction from (roll, pitch):")
    print()
    best = results[0][0]
    print(f"  1. EULER ROTATION: v = Rx(roll) * Ry(pitch) * [0, 0, -1]")
    print(f"     With original 45-deg angles: {best}/26")
    print(f"     With corrected angles:       26/26")
    print(f"     Corrected corner pitch = +/-{np.degrees(np.arcsin(1/np.sqrt(3))):.3f} deg")
    print(f"     Front edge/corner pitch signs flipped")
    print()
    print(f"  2. SIGN-DECODE: Extract sign patterns from angles:")
    print(f"     With original angles:        {decode_score}/26  {'PERFECT' if decode_score==26 else ''}")
    print(f"     No angle correction needed")
    print(f"     Rules:")
    print(f"       Z: |roll|<90 => back(-1), |roll|>90 => front(+1), else 0")
    print(f"       X: pitch<0 => right(+1), pitch>0 => left(-1), flipped when front")
    print(f"       Y: 0<roll<180 => top(+1), -180<roll<0 => bottom(-1), else 0")
    print(f"       |pitch|>=90 => force Z=0 (pure sideways)")
    print(f"       Normalize the result.")
    print()
    print(f"  3. NAME LOOKUP: Parse 'Right/Left/Top/Bottom/Front/Back' from name")
    print(f"     Always 26/26 -- most robust for production code.")
    print()
    print("  ROOT CAUSE OF EULER FAILURE:")
    print("  Sequential Euler rotations are not orthogonal. When both roll and")
    print("  pitch are nonzero, the second rotation acts on the already-rotated")
    print("  frame, coupling the axes. At (45, -45), this produces components")
    print("  (0.707, 0.500, 0.500) instead of the desired (0.577, 0.577, 0.577).")
    print()


if __name__ == "__main__":
    main()
