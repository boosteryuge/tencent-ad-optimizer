#!/usr/bin/env python3
"""命令行启动脚本（自动把 src 加入路径）。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from ad_optimizer.cli import main

if __name__ == "__main__":
    main()
