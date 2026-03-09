import math

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float64
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster

from vesc_msgs.msg import VescStateStamped


class VESCToOdom(Node):

    def __init__(self):
        super().__init__('vesc_to_odom')

        # ===============================
        # Subscribers
        # ===============================
        self.create_subscription(
            VescStateStamped,
            '/sensors/core',
            self.vesc_cb,
            10
        )

        self.create_subscription(
            Float64,
            '/commands/servo/position',
            self.servo_cb,
            10
        )

        # ===============================
        # Publishers
        # ===============================
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

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

        # ===============================
        # SERVO CALIBRATION
        # ===============================
        self.servo_center = 0.50
        self.servo_left_limit = 0.85
        self.servo_right_limit = 0.15

        # ===============================
        # ODOM STATE
        # ===============================
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0

        self.current_servo = self.servo_center
        self.last_time = None

        self.get_logger().info("VESC → Odom node started")

    # ======================================================
    # Servo callback
    # ======================================================
    def servo_cb(self, msg):
        self.current_servo = msg.data

    # ======================================================
    # Convert ERPM -> vehicle linear velocity
    # ======================================================
    def erpm_to_velocity(self, erpm):
        motor_rpm = erpm / self.motor_pole_pairs
        wheel_rpm = motor_rpm / self.gear_ratio
        wheel_angular_velocity = wheel_rpm * (2.0 * math.pi / 60.0)
        velocity = wheel_angular_velocity * self.wheel_radius
        return velocity

    # ======================================================
    # Convert servo position -> steering angle
    # ======================================================
    def servo_to_steering(self, servo_pos):
        servo_pos = max(self.servo_right_limit,
                        min(self.servo_left_limit, servo_pos))

        if servo_pos >= self.servo_center:
            # LEFT turn
            normalized = (
                (servo_pos - self.servo_center) /
                (self.servo_left_limit - self.servo_center)
            )
        else:
            # RIGHT turn
            normalized = (
                (servo_pos - self.servo_center) /
                (self.servo_center - self.servo_right_limit)
            )

        steering_angle = normalized * self.max_steering_angle
        return steering_angle

    # ======================================================
    # VESC callback
    # ======================================================
    def vesc_cb(self, msg):
        current_time = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

        if self.last_time is None:
            self.last_time = current_time
            return

        dt = current_time - self.last_time
        self.last_time = current_time

        if dt <= 0.0 or dt > 1.0:
            return

        # 1. Read ERPM and convert to vehicle speed
        erpm = msg.state.speed
        velocity = self.erpm_to_velocity(erpm)

        # 2. Read servo position and convert to steering angle
        steering_angle = self.servo_to_steering(self.current_servo)

        # 3. Ackermann bicycle model
        if abs(self.wheelbase) > 1e-6:
            yaw_rate = velocity / self.wheelbase * math.tan(steering_angle)
        else:
            yaw_rate = 0.0

        # 4. Integrate pose
        self.x += velocity * math.cos(self.yaw) * dt
        self.y += velocity * math.sin(self.yaw) * dt
        self.yaw += yaw_rate * dt

        # 5. Publish odom + TF
        self.publish_odom(msg, velocity, yaw_rate)

    # ======================================================
    # Publish odometry and TF
    # ======================================================
    def publish_odom(self, msg, velocity, yaw_rate):
        odom = Odometry()
        odom.header.stamp = msg.header.stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_footprint'

        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0

        qz = math.sin(self.yaw / 2.0)
        qw = math.cos(self.yaw / 2.0)

        odom.pose.pose.orientation.x = 0.0
        odom.pose.pose.orientation.y = 0.0
        odom.pose.pose.orientation.z = qz
        odom.pose.pose.orientation.w = qw

        odom.twist.twist.linear.x = velocity
        odom.twist.twist.angular.z = yaw_rate

        self.odom_pub.publish(odom)

        tf_msg = TransformStamped()
        tf_msg.header.stamp = msg.header.stamp
        tf_msg.header.frame_id = 'odom'
        tf_msg.child_frame_id = 'base_footprint'

        tf_msg.transform.translation.x = self.x
        tf_msg.transform.translation.y = self.y
        tf_msg.transform.translation.z = 0.0

        tf_msg.transform.rotation.x = 0.0
        tf_msg.transform.rotation.y = 0.0
        tf_msg.transform.rotation.z = qz
        tf_msg.transform.rotation.w = qw

        self.tf_broadcaster.sendTransform(tf_msg)


def main(args=None):
    rclpy.init(args=args)
    node = VESCToOdom()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()