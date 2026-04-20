import math
import time
from typing import Optional

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float64
from geometry_msgs.msg import TwistStamped


class AckermannToVESCF1TenthStyle(Node):
    def __init__(self):
        super().__init__('ackermann_to_vesc')

        # -----------------------------
        # Topics
        # -----------------------------
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')
        self.declare_parameter('motor_speed_topic', '/commands/motor/speed')
        self.declare_parameter('servo_position_topic', '/commands/servo/position')

        # -----------------------------
        # Calibrated F1TENTH-style conversions
        # Keep these matched with vesc_to_odom.py
        # -----------------------------
        self.declare_parameter('speed_to_erpm_gain', 3627.3)
        self.declare_parameter('speed_to_erpm_offset', 0.0)
        self.declare_parameter('steering_angle_to_servo_gain', 0.573)
        self.declare_parameter('steering_angle_to_servo_offset', 0.50)

        # -----------------------------
        # Robot geometry
        # -----------------------------
        self.declare_parameter('wheelbase', 0.285)
        self.declare_parameter('max_steering_angle_deg', 35.0)

        # -----------------------------
        # Runtime / safety
        # -----------------------------
        self.declare_parameter('command_timeout', 0.5)
        self.declare_parameter('max_speed_mps', 0.5)
        self.declare_parameter('min_speed_for_steering_calc', 0.03)
        self.declare_parameter('small_omega_threshold', 0.02)
        self.declare_parameter('invert_speed_sign', False)

        # -----------------------------
        # Startup deadband compensation
        # -----------------------------
        self.declare_parameter('min_start_erpm', 1000.0)
        self.declare_parameter('min_running_erpm', 1000.0)
        self.declare_parameter('speed_command_deadband', 0.02)

        # -----------------------------
        # Read params
        # -----------------------------
        self.cmd_vel_topic = self.get_parameter('cmd_vel_topic').value
        self.motor_speed_topic = self.get_parameter('motor_speed_topic').value
        self.servo_position_topic = self.get_parameter('servo_position_topic').value

        self.speed_to_erpm_gain = float(self.get_parameter('speed_to_erpm_gain').value)
        self.speed_to_erpm_offset = float(self.get_parameter('speed_to_erpm_offset').value)
        self.steering_to_servo_gain = float(
            self.get_parameter('steering_angle_to_servo_gain').value
        )
        self.steering_to_servo_offset = float(
            self.get_parameter('steering_angle_to_servo_offset').value
        )

        self.wheelbase = float(self.get_parameter('wheelbase').value)
        self.max_steering_angle = math.radians(
            float(self.get_parameter('max_steering_angle_deg').value)
        )

        self.command_timeout = float(self.get_parameter('command_timeout').value)
        self.max_speed_mps = float(self.get_parameter('max_speed_mps').value)
        self.min_speed_for_steering_calc = float(
            self.get_parameter('min_speed_for_steering_calc').value
        )
        self.small_omega_threshold = float(
            self.get_parameter('small_omega_threshold').value
        )
        self.invert_speed_sign = bool(self.get_parameter('invert_speed_sign').value)

        self.min_start_erpm = float(self.get_parameter('min_start_erpm').value)
        self.min_running_erpm = float(self.get_parameter('min_running_erpm').value)
        self.speed_command_deadband = float(
            self.get_parameter('speed_command_deadband').value
        )

        if abs(self.speed_to_erpm_gain) < 1e-9:
            raise ValueError('speed_to_erpm_gain must not be zero')
        if abs(self.steering_to_servo_gain) < 1e-9:
            raise ValueError('steering_angle_to_servo_gain must not be zero')

        # -----------------------------
        # State
        # -----------------------------
        self.last_cmd_time = time.time()
        self.last_speed_cmd: float = 0.0
        self.last_steering_angle_cmd: float = 0.0
        self.robot_is_moving = False

        # -----------------------------
        # ROS interfaces
        # -----------------------------
        self.create_subscription(
            TwistStamped,
            self.cmd_vel_topic,
            self.cmd_vel_callback,
            10
        )

        self.motor_pub = self.create_publisher(Float64, self.motor_speed_topic, 10)
        self.servo_pub = self.create_publisher(Float64, self.servo_position_topic, 10)

        self.create_timer(0.05, self.publish_commands)  # 20 Hz

        self.get_logger().info('AckermannToVESC F1TENTH-style node started')
        self.get_logger().info(f'  cmd_vel_topic: {self.cmd_vel_topic}')
        self.get_logger().info(f'  motor_speed_topic: {self.motor_speed_topic}')
        self.get_logger().info(f'  servo_position_topic: {self.servo_position_topic}')
        self.get_logger().info(f'  speed_to_erpm_gain: {self.speed_to_erpm_gain}')
        self.get_logger().info(f'  speed_to_erpm_offset: {self.speed_to_erpm_offset}')
        self.get_logger().info(f'  steering_angle_to_servo_gain: {self.steering_to_servo_gain}')
        self.get_logger().info(f'  steering_angle_to_servo_offset: {self.steering_to_servo_offset}')
        self.get_logger().info(f'  wheelbase: {self.wheelbase}')
        self.get_logger().info(f'  max_steering_angle_deg: {math.degrees(self.max_steering_angle):.1f}')
        self.get_logger().info(f'  max_speed_mps: {self.max_speed_mps}')
        self.get_logger().info(f'  min_start_erpm: {self.min_start_erpm}')
        self.get_logger().info(f'  min_running_erpm: {self.min_running_erpm}')
        self.get_logger().info(f'  speed_command_deadband: {self.speed_command_deadband}')
        self.get_logger().info(f'  invert_speed_sign: {self.invert_speed_sign}')

    def cmd_vel_callback(self, msg: TwistStamped) -> None:
        v = float(msg.twist.linear.x)
        omega = float(msg.twist.angular.z)

        # Clamp commanded speed for safety
        v = max(-self.max_speed_mps, min(self.max_speed_mps, v))

        # Convert Twist -> steering angle
        steering_angle = self.last_steering_angle_cmd

        if abs(v) > 0.01:
            calc_v = v
            if abs(calc_v) < self.min_speed_for_steering_calc:
                calc_v = math.copysign(self.min_speed_for_steering_calc, calc_v)

            steering_angle = math.atan((omega * self.wheelbase) / calc_v)
        else:
            # Only center when both speed and yaw command are tiny.
            # Otherwise keep previous steering for low-speed precise turning.
            if abs(omega) < self.small_omega_threshold:
                steering_angle = 0.0

        steering_angle = max(
            -self.max_steering_angle,
            min(self.max_steering_angle, steering_angle)
        )

        self.last_speed_cmd = v
        self.last_steering_angle_cmd = steering_angle
        self.last_cmd_time = time.time()

    def speed_to_erpm(self, speed_mps: float) -> float:
        sign = -1.0 if self.invert_speed_sign else 1.0
        return self.speed_to_erpm_gain * (sign * speed_mps) + self.speed_to_erpm_offset

    def steering_angle_to_servo(self, steering_angle: float) -> float:
        return self.steering_to_servo_gain * steering_angle + self.steering_to_servo_offset

    def apply_start_deadband_compensation(self, speed_cmd: float, erpm_cmd: float) -> float:
        # Stop command
        if abs(speed_cmd) < self.speed_command_deadband:
            self.robot_is_moving = False
            return 0.0

        sign = 1.0 if speed_cmd > 0.0 else -1.0
        mag = abs(erpm_cmd)

        # Startup boost from standstill
        if not self.robot_is_moving:
            if mag < self.min_start_erpm:
                mag = self.min_start_erpm
            self.robot_is_moving = True
        else:
            # Keep enough ERPM so the robot does not stall immediately
            if mag < self.min_running_erpm:
                mag = self.min_running_erpm

        return sign * mag

    def publish_commands(self) -> None:
        # Timeout safety
        if time.time() - self.last_cmd_time > self.command_timeout:
            speed_cmd = 0.0
            steering_angle_cmd = 0.0
            self.robot_is_moving = False
        else:
            speed_cmd = self.last_speed_cmd
            steering_angle_cmd = self.last_steering_angle_cmd

        erpm = self.speed_to_erpm(speed_cmd)
        erpm = self.apply_start_deadband_compensation(speed_cmd, erpm)
        servo = self.steering_angle_to_servo(steering_angle_cmd)

        self.motor_pub.publish(Float64(data=float(erpm)))
        self.servo_pub.publish(Float64(data=float(servo)))


def main(args: Optional[list] = None):
    rclpy.init(args=args)
    node = AckermannToVESCF1TenthStyle()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()