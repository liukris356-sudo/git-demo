from glob import glob
import os

from setuptools import find_packages, setup


package_name = "force_sensor_ta67l"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            [f"resource/{package_name}"],
        ),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools", "pyserial"],
    tests_require=["pytest"],
    zip_safe=True,
    maintainer="ROS Developer",
    maintainer_email="user@example.com",
    description="ROS 2 serial driver for the TA67L six-axis force module",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "force_sensor_ta67l_node = force_sensor_ta67l.node:main",
            "force_sensor_ta67l_stream = force_sensor_ta67l.cli:main",
            "force_sensor_ta67l_monitor = force_sensor_ta67l.monitor:main",
        ],
    },
)
