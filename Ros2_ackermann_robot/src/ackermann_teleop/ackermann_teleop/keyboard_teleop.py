import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist

import sys
import termios
import tty
import time
import select


class KeyboardTeleop(Node):
    def __init__(self):
        super().__init__('keyboard_teleop')

        # Publish to standard ROS cmd_vel
        self.cmd_pub = self.create_publisher(
            Twist,
            '/cmd_vel',
            10
        )

        self.velocity = 0.0
        self.steering = 0.0

        # tuning parameters
        self.vel_step = 0.1
        self.steer_step = 0.1

        self.max_vel = 2.0
        self.max_steer = 0.6  # radians

        self.get_logger().info(
            "Controls: W/S velocity | A/D steering | SPACE stop | Ctrl+C quit"
        )

    def publish_once(self):
        msg = Twist()

        msg.linear.x = float(self.velocity)
        msg.angular.z = float(self.steering)

        self.cmd_pub.publish(msg)

    def clamp(self):
        self.velocity = max(-self.max_vel, min(self.max_vel, self.velocity))
        self.steering = max(-self.max_steer, min(self.max_steer, self.steering))

    def run(self):
        old_settings = termios.tcgetattr(sys.stdin)

        try:
            tty.setcbreak(sys.stdin.fileno())
            last_pub = time.time()

            while rclpy.ok():

                # publish continuously at 10 Hz
                now = time.time()
                if now - last_pub >= 0.1:
                    self.publish_once()
                    last_pub = now

                rclpy.spin_once(self, timeout_sec=0.0)

                # non-blocking key read
                if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                    key = sys.stdin.read(1)

                    if key == 'w':
                        self.velocity += self.vel_step
                    elif key == 's':
                        self.velocity -= self.vel_step
                    elif key == 'a':
                        self.steering += self.steer_step
                    elif key == 'd':
                        self.steering -= self.steer_step
                    elif key == ' ':
                        self.velocity = 0.0
                        self.steering = 0.0

                    self.clamp()

                    self.get_logger().info(
                        f"velocity={self.velocity:.2f}, steering={self.steering:.2f}"
                    )

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


def main():
    rclpy.init()
    node = KeyboardTeleop()

    try:
        node.run()
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()