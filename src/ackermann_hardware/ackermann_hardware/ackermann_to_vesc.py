import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64
from geometry_msgs.msg import Twist
import math
import time


class AckermannToVESC(Node):

    def __init__(self):
        super().__init__('ackermann_to_vesc')

        # ===============================
        # Subscribers
        # ===============================
        self.create_subscription(
            Twist, '/cmd_vel', self.cmd_vel_cb, 10)

        # ===============================
        # Publishers
        # ===============================
        self.pub_motor = self.create_publisher(
            Float64, '/commands/motor/speed', 10)

        self.pub_servo = self.create_publisher(
            Float64, '/commands/servo/position', 10)

        # ===============================
        # ROBOT PARAMETERS
        # ===============================
        self.wheelbase = 0.285
        self.wheel_radius = 0.055
        self.max_steering_angle = math.radians(45)

        # ===============================
        # MOTOR PARAMETERS
        # ===============================
        self.motor_pole_pairs = 7
        self.gear_ratio = 3.0
        self.max_erpm = 30000.0

        # ===============================
        # SERVO CALIBRATION
        # ===============================
        self.servo_center = 0.50
        self.servo_left_limit = 0.85
        self.servo_right_limit = 0.15

        # ===============================
        # SAFETY
        # ===============================
        self.max_vehicle_speed = 4.0
        self.timeout = 0.5
        self.last_cmd_time = time.time()

        self.velocity = 0.0
        self.steering = 0.0

        self.create_timer(0.05, self.publish_cmd)

        self.get_logger().info("Ackermann → VESC node started (REAL ROBOT CONFIG)")

    # ======================================================
    # cmd_vel callback
    # ======================================================
    def cmd_vel_cb(self, msg):

        self.velocity = msg.linear.x

        # Real Ackermann steering
        if abs(self.velocity) > 0.05:
            self.steering = math.atan(
                msg.angular.z * self.wheelbase / self.velocity)
        else:
            # No in-place turning for Ackermann car
            self.steering = 0.0

        self.last_cmd_time = time.time()

    # ======================================================
    # Velocity → ERPM conversion
    # ======================================================
    def velocity_to_erpm(self, velocity_mps):

        # Wheel angular velocity (rad/s)
        wheel_angular_velocity = velocity_mps / self.wheel_radius

        # Convert to RPM
        wheel_rpm = wheel_angular_velocity * 60.0 / (2.0 * math.pi)

        # Apply gear ratio
        motor_rpm = wheel_rpm * self.gear_ratio

        # Convert to ERPM
        erpm = motor_rpm * self.motor_pole_pairs

        return erpm

    # ======================================================
    # Steering → Servo mapping
    # ======================================================
    def steering_to_servo(self, steering_angle):

        # Clamp steering to mechanical limit
        steering_angle = max(
            -self.max_steering_angle,
            min(self.max_steering_angle, steering_angle))

        # Normalize between -1 and +1
        normalized = steering_angle / self.max_steering_angle

        if normalized >= 0:
            # LEFT
            servo = self.servo_center + normalized * \
                (self.servo_left_limit - self.servo_center)
        else:
            # RIGHT
            servo = self.servo_center + normalized * \
                (self.servo_center - self.servo_right_limit)

        return servo

    # ======================================================
    # Main publish loop
    # ======================================================
    def publish_cmd(self):

        if time.time() - self.last_cmd_time > self.timeout:
            motor_erpm = 0.0
            servo_position = self.servo_center
        else:

            # Clamp speed
            velocity = max(
                -self.max_vehicle_speed,
                min(self.max_vehicle_speed, self.velocity))

            motor_erpm = self.velocity_to_erpm(velocity)
            servo_position = self.steering_to_servo(self.steering)

            # Final ERPM clamp
            motor_erpm = max(
                -self.max_erpm,
                min(self.max_erpm, motor_erpm))

        self.pub_motor.publish(Float64(data=motor_erpm))
        self.pub_servo.publish(Float64(data=servo_position))


def main():
    rclpy.init()
    node = AckermannToVESC()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()