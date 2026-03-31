import math
from typing import Optional

import rclpy
from rclpy.node import Node

from std_msgs.msg import Float64
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster

from vesc_msgs.msg import VescStateStamped


class VESCToOdomF1TenthStyle(Node):
    def __init__(self):
        super().__init__('vesc_to_odom')

        # -----------------------------
        # Parameters
        # -----------------------------
        self.declare_parameter('odom_topic', '/odom')
        self.declare_parameter('vesc_core_topic', '/sensors/core')
        self.declare_parameter('servo_sensor_topic', '/sensors/servo_position_command')

        self.declare_parameter('odom_frame', 'odom')
        self.declare_parameter('base_frame', 'base_footprint')
        self.declare_parameter('publish_tf', False)
        self.declare_parameter('use_servo_cmd_to_calc_angular_velocity', True)

        # F1TENTH-style calibrated conversions
        self.declare_parameter('speed_to_erpm_gain', 3627.3)
        self.declare_parameter('speed_to_erpm_offset', 0.0)
        self.declare_parameter('steering_angle_to_servo_gain', 0.573)
        self.declare_parameter('steering_angle_to_servo_offset', 0.50)

        self.declare_parameter('wheelbase', 0.285)
        self.declare_parameter('speed_deadband', 0.05)

        # Helpful if your sign is opposite
        self.declare_parameter('invert_speed_sign', False)

        self.odom_topic = self.get_parameter('odom_topic').value
        self.vesc_core_topic = self.get_parameter('vesc_core_topic').value
        self.servo_sensor_topic = self.get_parameter('servo_sensor_topic').value

        self.odom_frame = self.get_parameter('odom_frame').value
        self.base_frame = self.get_parameter('base_frame').value
        self.publish_tf = self.get_parameter('publish_tf').value
        self.use_servo_cmd = self.get_parameter(
            'use_servo_cmd_to_calc_angular_velocity'
        ).value

        self.speed_to_erpm_gain = float(self.get_parameter('speed_to_erpm_gain').value)
        self.speed_to_erpm_offset = float(self.get_parameter('speed_to_erpm_offset').value)
        self.steering_to_servo_gain = float(
            self.get_parameter('steering_angle_to_servo_gain').value
        )
        self.steering_to_servo_offset = float(
            self.get_parameter('steering_angle_to_servo_offset').value
        )

        self.wheelbase = float(self.get_parameter('wheelbase').value)
        self.speed_deadband = float(self.get_parameter('speed_deadband').value)
        self.invert_speed_sign = bool(self.get_parameter('invert_speed_sign').value)

        if abs(self.speed_to_erpm_gain) < 1e-9:
            raise ValueError('speed_to_erpm_gain must not be zero')
        if self.use_servo_cmd and abs(self.steering_to_servo_gain) < 1e-9:
            raise ValueError('steering_angle_to_servo_gain must not be zero')

        # -----------------------------
        # State
        # -----------------------------
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0

        self.last_stamp: Optional[float] = None
        self.last_servo_cmd: Optional[float] = None

        # -----------------------------
        # ROS interfaces
        # -----------------------------
        self.odom_pub = self.create_publisher(Odometry, self.odom_topic, 10)
        self.tf_broadcaster = TransformBroadcaster(self) if self.publish_tf else None

        self.create_subscription(
            VescStateStamped,
            self.vesc_core_topic,
            self.vesc_state_callback,
            10
        )

        if self.use_servo_cmd:
            self.create_subscription(
                Float64,
                self.servo_sensor_topic,
                self.servo_cmd_callback,
                10
            )

        self.get_logger().info('VESCToOdom F1TENTH-style node started')
        self.get_logger().info(f'  vesc_core_topic: {self.vesc_core_topic}')
        self.get_logger().info(f'  servo_sensor_topic: {self.servo_sensor_topic}')
        self.get_logger().info(f'  odom_topic: {self.odom_topic}')
        self.get_logger().info(f'  odom_frame: {self.odom_frame}')
        self.get_logger().info(f'  base_frame: {self.base_frame}')
        self.get_logger().info(f'  use_servo_cmd_to_calc_angular_velocity: {self.use_servo_cmd}')
        self.get_logger().info(f'  speed_to_erpm_gain: {self.speed_to_erpm_gain}')
        self.get_logger().info(f'  speed_to_erpm_offset: {self.speed_to_erpm_offset}')
        self.get_logger().info(f'  steering_angle_to_servo_gain: {self.steering_to_servo_gain}')
        self.get_logger().info(f'  steering_angle_to_servo_offset: {self.steering_to_servo_offset}')
        self.get_logger().info(f'  invert_speed_sign: {self.invert_speed_sign}')

    def servo_cmd_callback(self, msg: Float64) -> None:
        self.last_servo_cmd = msg.data

    def erpm_to_speed(self, erpm: float) -> float:
        # F1TENTH uses (-erpm - offset) / gain
        sign = -1.0 if self.invert_speed_sign else 1.0
        speed = (sign * erpm - self.speed_to_erpm_offset) / self.speed_to_erpm_gain

        if abs(speed) < self.speed_deadband:
            speed = 0.0
        return speed

    def servo_to_steering_angle(self, servo_cmd: float) -> float:
        return (servo_cmd - self.steering_to_servo_offset) / self.steering_to_servo_gain

    def stamp_to_sec(self, stamp) -> float:
        return float(stamp.sec) + float(stamp.nanosec) * 1e-9

    def vesc_state_callback(self, msg: VescStateStamped) -> None:
        if self.use_servo_cmd and self.last_servo_cmd is None:
            return

        current_time = self.stamp_to_sec(msg.header.stamp)

        if self.last_stamp is None:
            self.last_stamp = current_time
            return

        dt = current_time - self.last_stamp
        self.last_stamp = current_time

        if dt <= 0.0 or dt > 1.0:
            return

        # 1) ERPM -> vehicle speed
        current_speed = self.erpm_to_speed(msg.state.speed)

        # 2) Servo command -> steering angle -> yaw rate
        current_steering_angle = 0.0
        current_angular_velocity = 0.0

        if self.use_servo_cmd:
            current_steering_angle = self.servo_to_steering_angle(self.last_servo_cmd)
            current_angular_velocity = current_speed * math.tan(current_steering_angle) / self.wheelbase

        # 3) Propagate odom
        x_dot = current_speed * math.cos(self.yaw)
        y_dot = current_speed * math.sin(self.yaw)

        self.x += x_dot * dt
        self.y += y_dot * dt
        if self.use_servo_cmd:
            self.yaw += current_angular_velocity * dt

        # 4) Publish
        self.publish_odom(msg, current_speed, current_angular_velocity)

    def publish_odom(
        self,
        vesc_msg: VescStateStamped,
        current_speed: float,
        current_angular_velocity: float
    ) -> None:
        odom = Odometry()
        odom.header.stamp = vesc_msg.header.stamp
        odom.header.frame_id = self.odom_frame
        odom.child_frame_id = self.base_frame

        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0

        odom.pose.pose.orientation.x = 0.0
        odom.pose.pose.orientation.y = 0.0
        odom.pose.pose.orientation.z = math.sin(self.yaw / 2.0)
        odom.pose.pose.orientation.w = math.cos(self.yaw / 2.0)

        # F1TENTH-style simple covariances
        odom.pose.covariance[0] = 0.2    # x
        odom.pose.covariance[7] = 0.2    # y
        odom.pose.covariance[35] = 0.4   # yaw

        odom.twist.twist.linear.x = current_speed
        odom.twist.twist.linear.y = 0.0
        odom.twist.twist.angular.z = current_angular_velocity

        odom.twist.covariance[0] = 0.2
        odom.twist.covariance[7] = 0.2
        odom.twist.covariance[35] = 0.4

        self.odom_pub.publish(odom)

        if self.publish_tf and self.tf_broadcaster is not None:
            tf_msg = TransformStamped()
            tf_msg.header.stamp = vesc_msg.header.stamp
            tf_msg.header.frame_id = self.odom_frame
            tf_msg.child_frame_id = self.base_frame

            tf_msg.transform.translation.x = self.x
            tf_msg.transform.translation.y = self.y
            tf_msg.transform.translation.z = 0.0

            tf_msg.transform.rotation.x = 0.0
            tf_msg.transform.rotation.y = 0.0
            tf_msg.transform.rotation.z = odom.pose.pose.orientation.z
            tf_msg.transform.rotation.w = odom.pose.pose.orientation.w

            self.tf_broadcaster.sendTransform(tf_msg)


def main(args=None):
    rclpy.init(args=args)
    node = VESCToOdomF1TenthStyle()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()