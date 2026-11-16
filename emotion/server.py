"""声刻 情绪识别服务入口（默认端口 50001）。

实现已迁移到 ``voicesculptor_emotion`` 包；保留本文件作为
``_run-emotion.cmd`` 使用的薄壳，保证 ``python server.py --port 50001``
的启动方式不变。
"""

from voicesculptor_emotion import main as _main

if __name__ == '__main__':
    _main.main()
