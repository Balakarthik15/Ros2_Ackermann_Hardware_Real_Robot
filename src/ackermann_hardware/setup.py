from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'ackermann_hardware'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        #  THIS installs launch files
        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Alex Prediger',
    maintainer_email='alex.prediger@th-koeln.de',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': ['joint_states = ackermann_hardware.joint_states:main',
                            'ackermann_to_vesc = ackermann_hardware.ackermann_to_vesc:main',
                            'vesc_to_odom = ackermann_hardware.vesc_to_odom:main'
        ],
    },
)
