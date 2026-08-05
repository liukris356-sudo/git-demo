from glob import glob
import os

from setuptools import find_packages, setup


package_name = "force_sensor_yl"

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
    zip_safe=True,
    maintainer="ROS Developer",
    maintainer_email="user@example.com",
    description="ROS2 driver for the SRI M3815CA2 six-axis force sensor",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "force_sensor_yl_node = force_sensor_yl.node:main",
            "force_sensor_yl_stream = force_sensor_yl.cli:main",
            "force_sensor_yl_monitor = force_sensor_yl.monitor:main",
        ],
    },
)
