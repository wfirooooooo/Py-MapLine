#!/usr/bin/env python
# coding=utf-8
# author: lu4nx <lx@shellcodes.org>

import sys
import time
import logging
import threading
import traceback
from optparse import OptionParser
import codecs

if sys.version_info.major == 2:
    from Queue import Empty, Queue
elif sys.version_info.major == 3:
    from queue import Empty, Queue


queue = Queue()
logging.basicConfig(
    filename='run.log',
    level=logging.DEBUG,
    format='%(asctime)s %(threadName)s %(levelname)s %(message)s',
    filemode='w'
)


class PrintProgressThread(threading.Thread):
    """进度输出线程，每3秒向日志里输出一次当前进度

    :param: line_total: 输入数据的总行数
    """

    def __init__(self, line_total):
        threading.Thread.__init__(self)
        self.total = line_total

    def run(self):
        while True:
            current = queue.qsize()

            if current == 0:
                logging.info("current: 100%")
                break

            progress = int(100 - (current / self.total) * 100)
            logging.info("Succeeded: %s%%" % progress)
            time.sleep(3)


class WorkThread(threading.Thread):
    """从队列中取得函数以及参数并执行"""

    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.task_queue = queue

    def run(self):
        while True:
            try:
                func, args = self.task_queue.get()

                if func:
                    func(args)
            except Exception:
                traceback.print_exc()
            finally:
                self.task_queue.task_done()


class ThreadPool(object):
    """线程池的具体实现

    :param thread_count: 线程池大小（线程数）
    """

    def __init__(self, thread_count=10):
        try:
            self.thread_count = int(thread_count)
        except Exception:
            raise SystemExit('thread_count not is a number')

        self.work_list = []
        self.init_threadpool()

    def init_threadpool(self):
        """初始化线程池，并启动线程"""
        self.work_queue = Queue()

        for _ in range(self.thread_count):
            t = WorkThread(self.work_queue)
            self.work_list.append(t)

            t.setDaemon(True)
            t.start()

    def putjob(self, work_func, func_args=None):
        """把任务放入线程池调动"""
        self.work_queue.put((work_func, func_args))

    def wait(self):
        self.work_queue.join()


def self_test():
    """线程池自测试"""
    # 注意必须要指定参数
    def test_func(*argv):
        """从队列中取得url并urlopen，然后打印句柄"""
        if sys.version_info.major == 2:
            from urllib2 import urlopen
        else:
            from urllib.request import urlopen

        while True:
            try:
                url = q.get(block=False)
                try:
                    sock = urlopen(url)
                    print(sock)
                    sock.close()
                except Exception:
                    traceback.print_exc()
                    continue
                finally:
                    q.task_done()
            except Empty:
                break

    q = Queue()
    urls = ['http://www.baidu.com',
            'http://www.qq.com'] * 10

    for url in urls:
        q.put(url)

    # (1) 创建线程池
    threadpool = ThreadPool(thread_count=10)
    # (2) 将任务放入任务队列
    for i in range(3):
        threadpool.putjob(test_func, func_args=None)
    # (3) 等待完成队列里所有任务
    threadpool.wait()


def load_module(module_name_string):
    if module_name_string.find(".") == -1:
        return __import__(module_name_string)

    module_name_list = module_name_string.split(".")
    module_obj = __import__(
        module_name_list[0],
        fromlist=module_name_list[1:]
    )

    return getattr(module_obj, module_name_list[-1])


def work(*argv):
    foreach_func = argv[0]

    while True:
        try:
            line = queue.get(block=False)
            foreach_func(line)
        except Empty:
            logging.info('Done')
            break
        except Exception:
            traceback.print_exc()


if __name__ == '__main__':
    usage = "usage: %prog [options] input_file module_name"
    parser = OptionParser(usage=usage)
    parser.add_option("-c", type='int', help=u"线程池大小", default=20)
    parser.add_option("--test", help=u"自测", action="store_true")
    (options, args) = parser.parse_args()

    if options.test:
        self_test()
        raise SystemExit()

    try:
        input_file = args[0]
        module_name = args[1]
    except IndexError:
        parser.print_help()
        raise SystemExit()

    threadpool_size = options.c

    logging.info(u"Loading: %s", module_name)
    module_obj = load_module(module_name)

    with codecs.open(input_file, encoding='utf-8', errors='ignore') as f:
        for line in f:
            queue.put(line.strip())

    threadpool = ThreadPool(thread_count=threadpool_size)
    logging.info("Thread Pool size: %d" % threadpool_size)

    print_progress_thread = PrintProgressThread(queue.qsize())
    print_progress_thread.start()

    for i in range(threadpool_size):
        threadpool.putjob(
            work,
            func_args=getattr(module_obj, "foreach")
        )

    print_progress_thread.join()
    threadpool.wait()
