import logging
import threading


class BackgroundWorkers:
    def __init__(self, tasks):
        self.tasks = tasks
        self.stop = threading.Event()
        self.failures = {name: True for name in tasks}
        self.threads = []

    def start(self):
        def run(name, tick):
            while not self.stop.is_set():
                try:
                    tick()
                    self.failures[name] = False
                except Exception:
                    self.failures[name] = True
                    logging.getLogger(__name__).warning("Worker %s unavailable; retrying in 2 seconds", name)
                    self.stop.wait(2)
                self.stop.wait(0.1)
        for name, tick in self.tasks.items():
            thread = threading.Thread(target=run, args=(name, tick), name=name, daemon=True)
            self.threads.append(thread)
            thread.start()

    def ready(self):
        return bool(self.threads) and all(thread.is_alive() for thread in self.threads) and not any(self.failures.values())

    def close(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(35)
