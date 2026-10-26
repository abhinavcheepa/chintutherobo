#include "legs_ik.h"
#include "config.h"
#include <math.h>

LegsKinematics LegsIK;

LegsKinematics::LegsKinematics()
    : l1_hip_(LINK1_HIP_MM),
      l2_thigh_(LINK2_THIGH_MM),
      l3_shank_(LINK3_SHANK_MM),
      min_height_mm_(LEG_HEIGHT_MIN_MM),
      max_height_mm_(LEG_HEIGHT_MAX_MM) {}

bool LegsKinematics::solve_leg_ik(float height_mm, float offset_x_mm, float roll_trim_deg, bool is_left_leg, LegJointAngles &out_joints) {
    bool reachable = true;

    // 1. Clamp height within feasible mechanical bounds
    if (height_mm < min_height_mm_) {
        height_mm = min_height_mm_;
        reachable = false;
    } else if (height_mm > max_height_mm_) {
        height_mm = max_height_mm_;
        reachable = false;
    }

    // 2. Hip Roll is directly mapped from roll trim with direction symmetry
    float roll_cmd = is_left_leg ? roll_trim_deg : -roll_trim_deg;
    if (roll_cmd > 20.0f) roll_cmd = 20.0f;
    if (roll_cmd < -20.0f) roll_cmd = -20.0f;
    out_joints.hip_roll_deg = roll_cmd;

    // 3. Planar 2-Link model for thigh (L2) and shank (L3)
    // The target coordinate of the wheel axle relative to hip pitch joint:
    float x = offset_x_mm;
    float z = -height_mm; // Negative downwards

    float d_sq = x * x + z * z;
    float d = sqrt(d_sq);

    // Max reach check with 6mm buffer against straight-leg singularity
    float max_reach = l2_thigh_ + l3_shank_ - 6.0f;
    float min_reach = fabs(l2_thigh_ - l3_shank_) + 5.0f;

    if (d > max_reach) {
        d = max_reach;
        reachable = false;
    } else if (d < min_reach) {
        d = min_reach;
        reachable = false;
    }
    d_sq = d * d; // Update squared distance with clamped value

    // Law of Cosines for Knee angle:
    // d^2 = L2^2 + L3^2 - 2*L2*L3*cos(pi - theta_knee)
    // cos(angle_knee_internal) = (L2^2 + L3^2 - d^2) / (2 * L2 * L3)
    float cos_knee = (l2_thigh_ * l2_thigh_ + l3_shank_ * l3_shank_ - d_sq) / (2.0f * l2_thigh_ * l3_shank_);
    if (cos_knee > 1.0f) cos_knee = 1.0f;
    if (cos_knee < -1.0f) cos_knee = -1.0f;

    float knee_internal_rad = acos(cos_knee);
    // Relative flexion angle from straight leg:
    float knee_bend_rad = M_PI - knee_internal_rad;

    // Angle of vector (x, z) from vertical (-Z axis):
    float beta_rad = atan2(x, -z);

    // Law of Cosines for angle at thigh:
    float cos_thigh = (l2_thigh_ * l2_thigh_ + d_sq - l3_shank_ * l3_shank_) / (2.0f * l2_thigh_ * d);
    if (cos_thigh > 1.0f) cos_thigh = 1.0f;
    if (cos_thigh < -1.0f) cos_thigh = -1.0f;

    float gamma_rad = acos(cos_thigh);

    // Hip pitch angle relative to vertical:
    float hip_pitch_rad = beta_rad + gamma_rad;

    // Convert to degrees and assign to output
    out_joints.hip_pitch_deg = hip_pitch_rad * (180.0f / M_PI);
    out_joints.knee_pitch_deg = -knee_bend_rad * (180.0f / M_PI); // Knee flexes backwards

    return reachable;
}
