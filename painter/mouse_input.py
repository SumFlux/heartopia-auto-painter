"""
使用 pynput 等包来实现高兼容性的鼠标点击与移动。
避免直接调用底层 ctypes.windll.user32.SendInput 或 SetCursorPos
防止因 Windows DPI 缩放、多显示器坐标偏移导致点击游戏外、以及数组结构体包装越界造成的 Python 崩溃。
"""

import time
from pynput.mouse import Controller, Button

mouse = Controller()

def move_to(x, y):
    """
    移动鼠标到绝对屏幕坐标 (x, y)
    """
    mouse.position = (int(x), int(y))

def click_at(x, y, delay=0.015):
    """
    带真实按压模拟的瞬间延迟点击：移动 -> 按下 -> 延迟 -> 抬起
    适合部分拦截较严格或需要物理反馈间隔的游戏
    """
    # 1. 移动过去
    mouse.position = (int(x), int(y))
    # 给系统坐标刷新留一点微弱的时间
    time.sleep(0.01)
    
    # 2. 按下
    mouse.press(Button.left)
    
    # 3. 按住一会儿
    time.sleep(delay)
    
    # 4. 松开
    mouse.release(Button.left)
