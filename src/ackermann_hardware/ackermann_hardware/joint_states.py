import rclpy
from rclpy.node import Node

from sensor_msgs.msg import JointState
from std_msgs.msg import Float64
from vesc_msgs.msg import VescStateStamped  # from /sensors/core

import math
import time


class JointStates(Node):

    def __init__(self):
        super().__init__('joint_states')

        # -------- Robot Constants --------
        self.pole_pairs = 7          # 14 poles
        self.gear_ratio = 3.0
        self.wheel_radius = 0.055    # meters

        # Steering calibration
        self.servo_min = 0.15
        self.servo_max = 0.85
        self.max_steering_angle = math.radians(45)

        # -------- State Variables --------
        self.current_erpm = 0.0
        self.current_servo = 0.5
        self.wheel_position = 0.0
        self.last_time = time.time()

        # -------- Subscribers --------
        self.create_subscription(
            VescStateStamped,
            '/sensors/core',
            self.vesc_callback,
            10)

        self.create_subscription(
            Float64,
            '/commands/servo/position',
            self.servo_callback,
            10)

        # -------- Publisher --------
        self.joint_pub = self.create_publisher(
            JointState,
            '/joint_states',
            10)

        # Timer for publishing
        self.create_timer(0.02, self.publish_joint_states)  # 50 Hz

    # -----------------------------------
    # VESC feedback callback
    # -----------------------------------
    def vesc_callback(self, msg):
        self.current_erpm = msg.state.speed

    # -----------------------------------
    # Servo callback
    # -----------------------------------
    def servo_callback(self, msg):
        self.current_servo = msg.data

    # -----------------------------------
    # Publish Joint States
    # -----------------------------------
    def publish_joint_states(self):

        now = time.time()
        dt = now - self.last_time
        self.last_time = now

        # ---- Convert ERPM to wheel angular velocity ----
        wheel_rpm = self.current_erpm / (self.pole_pairs * self.gear_ratio)
        wheel_angular_velocity = wheel_rpm * 2.0 * math.pi / 60.0

        # integrate position
        self.wheel_position += wheel_angular_velocity * dt

        # ---- Convert servo to steering angle ----
        normalized = (self.current_servo - self.servo_min) / (self.servo_max - self.servo_min)
        steering_angle = (normalized - 0.5) * 2.0 * self.max_steering_angle

        # ---- Create JointState message ----
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()

        msg.name = [
            'fr_left_steer_joint',
            'fr_right_steer_joint',
            'fr_left_wheel_joint',
            'fr_right_wheel_joint',
            're_left_wheel_joint',
            're_right_wheel_joint'
        ]
        msg.position = [
            steering_angle,
            steering_angle,
            self.wheel_position,
            self.wheel_position,
            self.wheel_position,
            self.wheel_position
        ]

        msg.velocity = [
            0.0,
            0.0,
            wheel_angular_velocity,
            wheel_angular_velocity,
            wheel_angular_velocity,
            wheel_angular_velocity
        ]

        self.joint_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = JointStates()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()