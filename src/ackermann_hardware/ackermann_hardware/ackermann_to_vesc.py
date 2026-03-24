import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
from geometry_msgs.msg import Twist
import math
import time


class AckermannToVESC(Node):

    def __init__(self):
        super().__init__('ackermann_to_vesc')

        self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_cb, 10)
        self.pub_motor = self.create_publisher(Float64, '/commands/motor/speed', 10)
        self.pub_servo = self.create_publisher(Float64, '/commands/servo/position', 10)

        # Robot
        self.wheelbase = 0.285
        self.wheel_radius = 0.055
        self.max_steering_angle = math.radians(45)

        # Motor / drivetrain
        self.motor_pole_pairs = 2
        self.gear_ratio = 10.45
        self.max_erpm = 30000.0

        # Servo calibration
        self.servo_center = 0.50
        self.servo_left_limit = 0.85
        self.servo_right_limit = 0.15

        # Safety / mapping mode
        self.max_vehicle_speed = 0.20  # m/s, slow mapping mode
        self.timeout = 0.5              # s
        self.last_cmd_time = time.time()

        # Slow-drive tuning
        self.max_manual_erpm = 900   # cap ERPM for mapping
        self.start_erpm = 700.0        # minimum ERPM to overcome deadband
        self.velocity_deadband = 0.02  # m/s below this, stop
        self.max_erpm_step = 40.0       # ERPM change per timer tick

        # State
        self.velocity = 0.0
        self.steering = 0.0
        self.last_erpm_cmd = 0.0

        self.create_timer(0.05, self.publish_cmd)  # 20 Hz

        self.get_logger().info(
            'Ackermann → VESC node started (slow mapping mode)\n'
            f'  max_vehicle_speed={self.max_vehicle_speed} m/s\n'
            f'  max_manual_erpm={self.max_manual_erpm}\n'
            f'  start_erpm={self.start_erpm}\n'
            f'  max_erpm_step={self.max_erpm_step} per cycle'
        )

    def cmd_vel_cb(self, msg: Twist):
        self.velocity = msg.linear.x

        # Ackermann steering only makes sense while moving
        if abs(self.velocity) > 0.05:
            self.steering = math.atan(msg.angular.z * self.wheelbase / self.velocity)
        else:
            self.steering = 0.0

        self.last_cmd_time = time.time()

    def velocity_to_erpm(self, velocity_mps: float) -> float:
        wheel_angular_velocity = velocity_mps / self.wheel_radius
        wheel_rpm = wheel_angular_velocity * 60.0 / (2.0 * math.pi)
        motor_rpm = wheel_rpm * self.gear_ratio
        erpm = motor_rpm * self.motor_pole_pairs
        return erpm

    def steering_to_servo(self, steering_angle: float) -> float:
        steering_angle = max(-self.max_steering_angle,
                             min(self.max_steering_angle, steering_angle))

        normalized = steering_angle / self.max_steering_angle

        if normalized >= 0.0:
            servo = self.servo_center + normalized * (self.servo_left_limit - self.servo_center)
        else:
            servo = self.servo_center + normalized * (self.servo_center - self.servo_right_limit)

        return servo

    def apply_deadband_compensation(self, velocity: float, erpm: float) -> float:
        """
        If command is non-zero but too small to move the car, push it up to start_erpm.
        Keeps sign. Only applied when |velocity| > deadband.
        """
        if abs(velocity) < self.velocity_deadband:
            return 0.0

        sign = 1.0 if velocity > 0.0 else -1.0
        mag = abs(erpm)

        if mag < self.start_erpm:
            mag = self.start_erpm

        return sign * mag

    def apply_erpm_ramp(self, target_erpm: float) -> float:
        delta = target_erpm - self.last_erpm_cmd
        delta = max(-self.max_erpm_step, min(self.max_erpm_step, delta))
        cmd = self.last_erpm_cmd + delta
        self.last_erpm_cmd = cmd
        return cmd

    def publish_cmd(self):
        if time.time() - self.last_cmd_time > self.timeout:
            target_erpm = 0.0
            servo_position = self.servo_center
        else:
            # Clamp vehicle speed for mapping
            velocity = max(-self.max_vehicle_speed,
                           min(self.max_vehicle_speed, self.velocity))

            # Convert to ERPM
            target_erpm = self.velocity_to_erpm(velocity)

            # Deadband compensation
            target_erpm = self.apply_deadband_compensation(velocity, target_erpm)

            # Safety clamp
            target_erpm = max(-self.max_manual_erpm,
                              min(self.max_manual_erpm, target_erpm))

            servo_position = self.steering_to_servo(self.steering)

        # Smooth ERPM ramp
        motor_erpm = self.apply_erpm_ramp(target_erpm)

        # Final hard safety clamp
        motor_erpm = max(-self.max_erpm, min(self.max_erpm, motor_erpm))

        self.pub_motor.publish(Float64(data=float(motor_erpm)))
        self.pub_servo.publish(Float64(data=float(servo_position)))


def main():
    rclpy.init()
    node = AckermannToVESC()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
