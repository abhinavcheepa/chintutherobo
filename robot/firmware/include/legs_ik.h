#ifndef LEGS_IK_H
#define LEGS_IK_H

#include <Arduino.h>

struct LegJointAngles {
    float hip_roll_deg;   // Roll servo (lateral leveling)
    float hip_pitch_deg;  // Upper thigh servo
    float knee_pitch_deg; // Knee joint servo
};

class LegsKinematics {
public:
    LegsKinematics();

    /**
     * @brief Computes joint angles for a single leg given vertical height and horizontal offset.
     * @param height_mm Target vertical extension (80mm to 180mm).
     * @param offset_x_mm Fore-aft foot offset (default 0.0 for pure vertical balance line).
     * @param roll_trim_deg Roll adjustment for chassis tilt compensation.
     * @param is_left_leg True for left leg, false for right leg.
     * @param out_joints Output struct populated with target servo angles.
     * @return True if reachable within workspace, false if clamped.
     */
    bool solve_leg_ik(float height_mm, float offset_x_mm, float roll_trim_deg, bool is_left_leg, LegJointAngles &out_joints);

    // Workspace limit getters
    float get_min_height_mm() const { return min_height_mm_; }
    float get_max_height_mm() const { return max_height_mm_; }

private:
    const float l1_hip_;   // 72 mm
    const float l2_thigh_; // 120 mm
    const float l3_shank_; // 101 mm

    const float min_height_mm_;
    const float max_height_mm_;
};

extern LegsKinematics LegsIK;

#endif // LEGS_IK_H
