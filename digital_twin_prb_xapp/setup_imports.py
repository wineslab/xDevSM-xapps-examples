import sys
import os

# Add the path to xapp_framework
xapp_framework_path = os.path.abspath('xDevSM')
if xapp_framework_path not in sys.path:
    sys.path.append(xapp_framework_path)

# Add the path to sm_py_framework within xapp_framework
sm_py_framework_path = os.path.join(xapp_framework_path, 'xDevSM/sm_framework')
if sm_py_framework_path not in sys.path:
    sys.path.append(sm_py_framework_path)