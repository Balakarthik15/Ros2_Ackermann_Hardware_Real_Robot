import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
from geometry_msgs.msg import TwistStamped
import math
import time


class AckermannToVESC(Node):

    def __init__(self):
        super().__init__('ackermann_to_vesc')

        self.create_subscription(TwistStamped, '/cmd_vel', self.cmd_vel_cb, 10)
        self.pub_motor = self.create_publisher(Float64, '/commands/motor/speed', 10)
        self.pub_servo = self.create_publisher(Float64, '/commands/servo/position', 10)

        # Robot
        self.wheelbase = 0.285
        self.wheel_radius = 0.055
        self.max_steering_angle = math.radians(35)

        # Motor / drivetrain
        self.motor_pole_pairs = 2
        self.gear_ratio = 10.45
        self.max_erpm = 30000.0

        # Servo calibration
        # Keep these exactly as in your current working file
        self.servo_center = 0.50
        self.servo_left_limit = 0.85
        self.servo_right_limit = 0.15

        # Safety
        # Keep timeout and hard ERPM clamp only
        self.max_vehicle_speed = 0.3
        self.timeout = 0.5
        self.last_cmd_time = time.time()

        # State
        self.velocity = 0.0
        self.steering = 0.0

        self.create_timer(0.05, self.publish_cmd)  # 20 Hz

        self.get_logger().info(
            'Ackermann -> VESC node started (normal mode, TwistStamped input)\n'
            f'  max_vehicle_speed={self.max_vehicle_speed} m/s\n'
            f'  max_steering_angle_deg={math.degrees(self.max_steering_angle):.1f}\n'
            f'  gear_ratio={self.gear_ratio}\n'
            f'  motor_pole_pairs={self.motor_pole_pairs}'
        )

    def cmd_vel_cb(self, msg: TwistStamped):
        self.velocity = msg.twist.linear.x

        if abs(self.velocity) > 0.05:
            self.steering = math.atan(
                msg.twist.angular.z * self.wheelbase / self.velocity
            )
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
        steering_angle = max(
            -self.max_steering_angle,
            min(self.max_steering_angle, steering_angle)
        )

        normalized = steering_angle / self.max_steering_angle

        if normalized >= 0.0:
            servo = self.servo_center + normalized * (
                self.servo_left_limit - self.servo_center
            )
        else:
            servo = self.servo_center + normalized * (
                self.servo_center - self.servo_right_limit
            )

        return servo

    def publish_cmd(self):
        if time.time() - self.last_cmd_time > self.timeout:
            motor_erpm = 0.0
            servo_position = self.servo_center
        else:
            velocity = max(
                -self.max_vehicle_speed,
                min(self.max_vehicle_speed, self.velocity)
            )

            motor_erpm = self.velocity_to_erpm(velocity)
            servo_position = self.steering_to_servo(self.steering)

            motor_erpm = max(
                -self.max_erpm,
                min(self.max_erpm, motor_erpm)
            )

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