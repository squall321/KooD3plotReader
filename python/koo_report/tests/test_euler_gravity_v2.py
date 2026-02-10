#!/usr/bin/env python3
"""
PART 2: Understanding WHY no standard Euler angle convention produces
all 26 directions correctly, and what the CORRECT angles should be.

Key finding from Part 1:
  v = Rx(roll) * Ry(pitch) * [0,0,-1]
  gives 16/26 correct (all faces, 10/12 edges, 0/8 corners).

The problem: Euler angle rotations are NOT commutative. When we apply
pitch=45 after roll=45, the result is NOT the same as rotating 45
degrees in each axis independently. The second rotation acts on the
ALREADY-ROTATED axes.

For corners, we need pitch = arctan(1/sqrt(2)) = 35.264 degrees
(not 45 degrees) to get equal x,y,z components.

This script:
1. Derives the correct pitch angle for corners mathematically
2. Shows what the actual correct angles should be for all 26 directions
3. Tests both the "naive" 45-degree angles and the corrected angles
4. Identifies the two edge failures (E05, E06) and their fix
"""

import numpy as np


def Rx(angle_deg):
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])

def Ry(angle_deg):
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])

def Rz(angle_deg):
    a = np.radians(angle_deg)
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


s2 = 1.0 / np.sqrt(2)
s3 = 1.0 / np.sqrt(3)

# The formula we found works best:
# impact_direction = Rx(roll) * Ry(pitch) * [0, 0, -1]
#
# Let's derive what pitch angle gives equal x,y,z for corners.
# With roll=45, pitch=p, and g=[0,0,-1]:
#
# v = Rx(45) * Ry(p) * [0,0,-1]
# Ry(p)*[0,0,-1] = [-sin(p), 0, -cos(p)]
# Rx(45)*[-sin(p), 0, -cos(p)] = [-sin(p), cos(p)/sqrt(2), -cos(p)/sqrt(2)]
#   (wait, let me compute properly)

print("=" * 80)
print(" MATHEMATICAL DERIVATION OF CORRECT CORNER ANGLES")
print("=" * 80)
print()

# v = Rx(roll) * Ry(pitch) * [0, 0, -1]
# Step 1: Ry(p) * [0, 0, -1] = [sin(p)*(-1)... let me just compute]

pitch_sym = 45  # symbolic
g = np.array([0, 0, -1])

print("For the formula v = Rx(roll) * Ry(pitch) * [0,0,-1]:")
print()
print("Step 1: Ry(p) * [0,0,-1] = [-sin(p), 0, -cos(p)]")
print("Step 2: Rx(r) * [-sin(p), 0, -cos(p)] = ")
print("  x = -sin(p)")
print("  y =  sin(r)*cos(p)")  # Wait, let me be careful
print("  z = ... let me compute numerically")
print()

# Let me verify with actual matrices
for roll in [0, 45, 90, 135, 180]:
    for pitch in [-90, -45, 0, 45, 90]:
        v = Rx(roll) @ Ry(pitch) @ g
        if np.linalg.norm(v) > 1e-10:
            v = v / np.linalg.norm(v)
        print(f"  roll={roll:+4d}, pitch={pitch:+4d} -> ({v[0]:+7.4f}, {v[1]:+7.4f}, {v[2]:+7.4f})")
    print()

print()
print("=" * 80)
print(" ALGEBRAIC ANALYSIS")
print("=" * 80)
print()
print("Rx(r) * Ry(p) * [0,0,-1]:")
print()

# Compute symbolically using the matrices
# Ry(p) * [0,0,-1]:
#   [cos(p)*0 + sin(p)*(-1), 0, -sin(p)*0 + cos(p)*(-1)]
#   = [-sin(p), 0, -cos(p)]

# Rx(r) * [-sin(p), 0, -cos(p)]:
#   x = -sin(p)
#   y = cos(r)*0 - sin(r)*(-cos(p)) = sin(r)*cos(p)
#   z = sin(r)*0 + cos(r)*(-cos(p)) = -cos(r)*cos(p)

print("  v = [-sin(p), sin(r)*cos(p), -cos(r)*cos(p)]")
print()
print("  For a corner like Back_Right_Top (expected: [+s3, +s3, -s3]):")
print("    -sin(p) = s3       =>  sin(p) = -1/sqrt(3), so p < 0")
print("    sin(r)*cos(p) = s3")
print("    -cos(r)*cos(p) = -s3  =>  cos(r)*cos(p) = s3")
print()
print("  From the Y and Z components:")
print("    sin(r)*cos(p) = s3")
print("    cos(r)*cos(p) = s3")
print("    => tan(r) = 1 => r = 45 degrees  (CORRECT!)")
print()
print("  From the X component:")
print("    sin(p) = -1/sqrt(3)")
print("    p = -arcsin(1/sqrt(3)) = -35.264 degrees  (NOT -45!)")
print()

# Verify
p_corner = -np.degrees(np.arcsin(1/np.sqrt(3)))
print(f"  Correct pitch for 'Back_Right_Top' corner: {p_corner:.4f} degrees")
print(f"  (vs. the naive value of -45 degrees)")
print()

# Verify it works
v = Rx(45) @ Ry(p_corner) @ g
print(f"  Rx(45) * Ry({p_corner:.4f}) * [0,0,-1] = ({v[0]:+.6f}, {v[1]:+.6f}, {v[2]:+.6f})")
print(f"  Expected:                                ({s3:+.6f}, {s3:+.6f}, {-s3:+.6f})")
print(f"  Match: {np.allclose(v, [s3, s3, -s3], atol=1e-6)}")
print()

print("=" * 80)
print(" CORRECT ANGLES FOR ALL 26 DIRECTIONS")
print("=" * 80)
print()
print("Given v = Rx(roll) * Ry(pitch) * [0,0,-1] = [-sin(p), sin(r)*cos(p), -cos(r)*cos(p)]")
print()
print("We can solve for roll and pitch given any target direction (dx, dy, dz):")
print("  sin(p) = -dx")
print("  cos(p) = sqrt(dy^2 + dz^2)   [positive root, since we restrict p to [-90,90]]")
print("  tan(r) = dy / (-dz)  when dz != 0")
print("  r = atan2(dy, -dz)   [general case]")
print()

# For each expected direction, compute the correct roll and pitch
print(f"{'Direction':30s} {'Expected':40s} {'roll':>8s} {'pitch':>8s} {'Verify':40s} {'Match':>5s}")
print("-" * 140)

EXPECTED = {
    "F1_Back":    np.array([0, 0, -1]),
    "F2_Front":   np.array([0, 0,  1]),
    "F3_Right":   np.array([1, 0,  0]),
    "F4_Left":    np.array([-1, 0, 0]),
    "F5_Top":     np.array([0, 1,  0]),
    "F6_Bottom":  np.array([0, -1, 0]),
    "E01_Back_Right":    np.array([ s2, 0, -s2]),
    "E02_Back_Left":     np.array([-s2, 0, -s2]),
    "E03_Back_Top":      np.array([ 0,  s2, -s2]),
    "E04_Back_Bottom":   np.array([ 0, -s2, -s2]),
    "E05_Front_Right":   np.array([ s2, 0,  s2]),
    "E06_Front_Left":    np.array([-s2, 0,  s2]),
    "E07_Front_Top":     np.array([ 0,  s2,  s2]),
    "E08_Front_Bottom":  np.array([ 0, -s2,  s2]),
    "E09_Right_Top":     np.array([ s2,  s2, 0]),
    "E10_Right_Bottom":  np.array([ s2, -s2, 0]),
    "E11_Left_Top":      np.array([-s2,  s2, 0]),
    "E12_Left_Bottom":   np.array([-s2, -s2, 0]),
    "C1_Back_Right_Top":     np.array([ s3,  s3, -s3]),
    "C2_Back_Right_Bottom":  np.array([ s3, -s3, -s3]),
    "C3_Back_Left_Top":      np.array([-s3,  s3, -s3]),
    "C4_Back_Left_Bottom":   np.array([-s3, -s3, -s3]),
    "C5_Front_Right_Top":    np.array([ s3,  s3,  s3]),
    "C6_Front_Right_Bottom": np.array([ s3, -s3,  s3]),
    "C7_Front_Left_Top":     np.array([-s3,  s3,  s3]),
    "C8_Front_Left_Bottom":  np.array([-s3, -s3,  s3]),
}

# The given angle assignments
GIVEN_ANGLES = {
    "F1_Back":    (0, 0),
    "F2_Front":   (180, 0),
    "F3_Right":   (0, -90),
    "F4_Left":    (0, 90),
    "F5_Top":     (90, 0),
    "F6_Bottom":  (-90, 0),
    "E01_Back_Right":    (0, -45),
    "E02_Back_Left":     (0, 45),
    "E03_Back_Top":      (45, 0),
    "E04_Back_Bottom":   (-45, 0),
    "E05_Front_Right":   (180, 45),
    "E06_Front_Left":    (180, -45),
    "E07_Front_Top":     (135, 0),
    "E08_Front_Bottom":  (-135, 0),
    "E09_Right_Top":     (90, -45),
    "E10_Right_Bottom":  (-90, -45),
    "E11_Left_Top":      (90, 45),
    "E12_Left_Bottom":   (-90, 45),
    "C1_Back_Right_Top":     (45, -45),
    "C2_Back_Right_Bottom":  (-45, -45),
    "C3_Back_Left_Top":      (45, 45),
    "C4_Back_Left_Bottom":   (-45, 45),
    "C5_Front_Right_Top":    (135, 45),
    "C6_Front_Right_Bottom": (-135, 45),
    "C7_Front_Left_Top":     (135, -45),
    "C8_Front_Left_Bottom":  (-135, -45),
}

correct_angles = {}
for name, d in EXPECTED.items():
    dx, dy, dz = d
    # v = [-sin(p), sin(r)*cos(p), -cos(r)*cos(p)]
    # sin(p) = -dx => p = arcsin(-dx)
    pitch = np.degrees(np.arcsin(-dx))
    cos_p = np.cos(np.arcsin(-dx))
    
    if cos_p < 1e-10:
        # Pure X direction, roll is arbitrary (we choose 0)
        roll = 0.0
    else:
        # tan(r) = (dy) / (-dz)
        # r = atan2(dy, -dz)
        roll = np.degrees(np.arctan2(dy, -dz))
    
    correct_angles[name] = (roll, pitch)
    
    # Verify
    v = Rx(roll) @ Ry(pitch) @ g
    match = np.allclose(v, d, atol=1e-6)
    
    given_r, given_p = GIVEN_ANGLES[name]
    angle_match = (abs(roll - given_r) < 0.01 and abs(pitch - given_p) < 0.01)
    
    print(f"{name:30s} ({dx:+.4f},{dy:+.4f},{dz:+.4f})  "
          f"roll={roll:+8.3f} pitch={pitch:+8.3f}  "
          f"verify=({v[0]:+.4f},{v[1]:+.4f},{v[2]:+.4f})  "
          f"{'OK' if match else 'FAIL':>5s}"
          f"{'  *** ANGLE DIFFERS ***' if not angle_match else ''}")

print()
print()
print("=" * 80)
print(" COMPARISON: GIVEN ANGLES vs CORRECT ANGLES")
print("=" * 80)
print()
print(f"{'Direction':30s} {'Given roll':>10s} {'Given pitch':>11s} {'Correct roll':>12s} {'Correct pitch':>13s} {'Match':>6s}")
print("-" * 90)

n_match = 0
n_diff = 0
for name in EXPECTED:
    gr, gp = GIVEN_ANGLES[name]
    cr, cp = correct_angles[name]
    match = (abs(gr - cr) < 0.1 and abs(gp - cp) < 0.1)
    if match:
        n_match += 1
    else:
        n_diff += 1
    print(f"{name:30s} {gr:+10.3f} {gp:+11.3f} {cr:+12.3f} {cp:+13.3f} "
          f"{'OK' if match else '*** DIFF ***':>6s}")

print()
print(f"  Matching: {n_match}/26")
print(f"  Different: {n_diff}/26")

print()
print()
print("=" * 80)
print(" ANALYSIS OF THE TWO EDGE FAILURES (E05, E06)")
print("=" * 80)
print()

for name in ["E05_Front_Right", "E06_Front_Left"]:
    gr, gp = GIVEN_ANGLES[name]
    cr, cp = correct_angles[name]
    d = EXPECTED[name]
    
    v_given = Rx(gr) @ Ry(gp) @ g
    v_correct = Rx(cr) @ Ry(cp) @ g
    
    print(f"  {name}:")
    print(f"    Expected direction: ({d[0]:+.4f}, {d[1]:+.4f}, {d[2]:+.4f})")
    print(f"    Given angles: roll={gr:+.1f}, pitch={gp:+.1f}")
    print(f"    Correct angles: roll={cr:+.3f}, pitch={cp:+.3f}")
    print(f"    Result with given angles:   ({v_given[0]:+.4f}, {v_given[1]:+.4f}, {v_given[2]:+.4f})")
    print(f"    Result with correct angles: ({v_correct[0]:+.4f}, {v_correct[1]:+.4f}, {v_correct[2]:+.4f})")
    print()
    print(f"    Issue: With roll=180, pitch swaps left/right because")
    print(f"    Rx(180) flips Y and Z, then Ry(pitch) rotates in the")
    print(f"    flipped coordinate system.")
    print()

print()
print("=" * 80)
print(" ANALYSIS OF CORNER FAILURES")
print("=" * 80)
print()

for name in ["C1_Back_Right_Top", "C5_Front_Right_Top"]:
    gr, gp = GIVEN_ANGLES[name]
    cr, cp = correct_angles[name]
    d = EXPECTED[name]
    
    v_given = Rx(gr) @ Ry(gp) @ g
    v_correct = Rx(cr) @ Ry(cp) @ g
    
    print(f"  {name}:")
    print(f"    Expected direction: ({d[0]:+.4f}, {d[1]:+.4f}, {d[2]:+.4f})")
    print(f"    Given angles: roll={gr:+.1f}, pitch={gp:+.1f}")
    print(f"    Correct angles: roll={cr:+.3f}, pitch={cp:+.3f}")
    print(f"    Result with given angles:   ({v_given[0]:+.4f}, {v_given[1]:+.4f}, {v_given[2]:+.4f})")
    print(f"    Result with correct angles: ({v_correct[0]:+.4f}, {v_correct[1]:+.4f}, {v_correct[2]:+.4f})")
    print()

print()
print("=" * 80)
print(" ALTERNATIVE: Ry(pitch) * Rx(roll) * [0,0,-1]  (pitch first in matrix)")
print("=" * 80)
print()
print("v = Ry(p) * Rx(r) * [0,0,-1]:")
print("  Rx(r)*[0,0,-1] = [0, sin(r), -cos(r)]")
print("  Ry(p)*[0, sin(r), -cos(r)] = [-cos(r)*sin(p), sin(r), -cos(r)*cos(p)]")
print()
print("  v = [-cos(r)*sin(p), sin(r), -cos(r)*cos(p)]")
print()

# Check what angles this needs
print(f"{'Direction':30s} {'roll':>8s} {'pitch':>8s} {'Verify':40s} {'Match':>5s}")
print("-" * 100)

correct_angles_v2 = {}
for name, d in EXPECTED.items():
    dx, dy, dz = d
    # v = [-cos(r)*sin(p), sin(r), -cos(r)*cos(p)]
    # sin(r) = dy => r = arcsin(dy)
    roll = np.degrees(np.arcsin(dy))
    cos_r = np.cos(np.radians(roll))
    
    if cos_r < 1e-10:
        pitch = 0.0
    else:
        # -cos(r)*sin(p) = dx => sin(p) = -dx/cos(r)
        # -cos(r)*cos(p) = dz => cos(p) = -dz/cos(r)
        # p = atan2(sin(p), cos(p)) = atan2(-dx/cos(r), -dz/cos(r)) = atan2(-dx, -dz)
        pitch = np.degrees(np.arctan2(-dx, -dz))
    
    correct_angles_v2[name] = (roll, pitch)
    
    v = Ry(pitch) @ Rx(roll) @ g
    match = np.allclose(v, d, atol=1e-6)
    
    given_r, given_p = GIVEN_ANGLES[name]
    angle_match = (abs(roll - given_r) < 0.1 and abs(pitch - given_p) < 0.1)
    
    print(f"{name:30s} roll={roll:+8.3f} pitch={pitch:+8.3f}  "
          f"verify=({v[0]:+.4f},{v[1]:+.4f},{v[2]:+.4f})  "
          f"{'OK' if match else 'FAIL':>5s}"
          f"{'  *** ANGLE DIFFERS ***' if not angle_match else ''}")

print()
print()
print("=" * 80)
print(" TESTING THE 'DIRECT VECTOR' APPROACH")
print("=" * 80)
print()
print("Since Euler angles cannot produce the 26 cuboid directions with simple")
print("45-degree increments, maybe the intent is to compute the direction")
print("directly without Euler angles.")
print()
print("For the 26 directions of a cuboid, each direction is a normalized")
print("combination of {-1, 0, +1} for each axis:")
print("  Faces:   one component = +/-1, others = 0")
print("  Edges:   two components = +/-1/sqrt(2), one = 0")
print("  Corners: three components = +/-1/sqrt(3)")
print()
print("The roll/pitch angles might simply be a PARAMETERIZATION that encodes")
print("which components are active, not actual rotation angles.")
print()
print("Interpretation: use roll to encode Y component, pitch to encode X component,")
print("and derive Z from the direction name (back=-1, front=+1, neither=0):")
print()
print("  sign_x = -sin(pitch_rad)    pitch=-90 -> +1, pitch=+90 -> -1")
print("  sign_y = sin(roll_rad)      roll=+90  -> +1, roll=-90  -> -1")
print("  sign_z = -cos(roll_rad)*cos(pitch_rad)")
print()
print("This is exactly Rx(roll)*Ry(pitch)*[0,0,-1] which we already tested.")
print("The issue is that at 45-degree pitch and roll, the components are NOT equal.")

print()
print()
print("=" * 80)
print(" FINAL SUMMARY")
print("=" * 80)
print()
print("1. The best Euler convention is: v = Rx(roll) * Ry(pitch) * [0, 0, -1]")
print("   This gives: v = [-sin(pitch), sin(roll)*cos(pitch), -cos(roll)*cos(pitch)]")
print()
print("2. This formula works PERFECTLY for all 6 faces (0/90/180 degree angles)")
print("   and 10 of 12 edges (where only one of roll or pitch is nonzero).")
print()
print("3. It FAILS for:")
print("   - 2 edges (E05_Front_Right, E06_Front_Left): roll=180 flips the pitch axis")
print("   - All 8 corners: 45-degree pitch with 45-degree roll produces")
print("     components (0.707, 0.500, 0.500) instead of (0.577, 0.577, 0.577)")
print()
print("4. For the corners, the correct pitch is NOT 45 degrees but rather")
print(f"   arcsin(1/sqrt(3)) = {np.degrees(np.arcsin(1/np.sqrt(3))):.4f} degrees")
print()
print("5. For the front edges (E05, E06), the correct pitch is:")
print(f"   For E05 (Front_Right): roll=180, pitch=-45  (not +45)")
print(f"   For E06 (Front_Left):  roll=180, pitch=+45  (not -45)")
print(f"   The sign of pitch flips when roll=180 because X is inverted.")
print()
print("6. CONCLUSION: The 26-angle table uses 'conceptual' angles that don't")
print("   directly plug into standard Euler rotations. Two approaches:")
print()
print("   APPROACH A: Use the corrected angles (35.264 deg for corners,")
print("               swapped pitch sign for front edges)")
print()
print("   APPROACH B: Use a 'component-wise' formula instead of Euler rotation:")
print("     dx = -sign(pitch) * |sin(pitch_rad)|")
print("     dy = sign(roll) * |sin(roll_rad)| * (1 if |roll|<=90 else ... )")
print("     dz = derived from roll direction")
print("     Then normalize.")
print()
print("   APPROACH C (RECOMMENDED): Pre-compute the 26 direction vectors")
print("   directly from the face/edge/corner names, and use the roll/pitch")
print("   angles only as identifiers, not as rotation parameters.")
print()

# Show the corrected angle table
print()
print("=" * 80)
print(" CORRECTED ANGLE TABLE (for v = Rx(roll) * Ry(pitch) * [0,0,-1])")
print("=" * 80)
print()
print(f"{'Name':30s} {'Original roll':>13s} {'Original pitch':>14s} {'Correct roll':>12s} {'Correct pitch':>13s}")
print("-" * 90)

for name in EXPECTED:
    gr, gp = GIVEN_ANGLES[name]
    cr, cp = correct_angles[name]
    changed = (abs(gr - cr) > 0.1 or abs(gp - cp) > 0.1)
    marker = " ***" if changed else ""
    print(f"{name:30s} {gr:+13.3f} {gp:+14.3f} {cr:+12.3f} {cp:+13.3f}{marker}")

print()
print("  *** = angle differs from original")


if __name__ == "__main__":
    pass
