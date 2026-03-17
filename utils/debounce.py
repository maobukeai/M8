import threading


def debounce(wait):
    """防抖装饰器，确保函数在停止调用后wait秒执行"""

    def decorator(func):
        timer = None
        lock = threading.Lock()  # 保证线程安全

        def debounced(*args, **kwargs):
            nonlocal timer
            with lock:
                if timer is not None:
                    timer.cancel()  # 取消之前的定时器
                # 创建新的定时器，在wait秒后执行原函数
                timer = threading.Timer(wait, func, args=args, kwargs=kwargs)
                timer.start()

        return debounced

    return decorator
