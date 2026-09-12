import logging
import threading
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from redis import Redis

from return_agent_contracts.domain import ReviewerGateConfig
from return_agent_runtime.graph import ReturnRuntime
from return_agent_runtime.ports import RuntimeDependencies

from .checkpoint import checkpoint_saver
from .db import make_engine, make_sessions
from .fake_model import TypedFakeModel
from .journal import CommandJournal
from .model import ModelSettings, StructuredModel
from .providers import HttpProviders
from .settings import Settings
from .workers import CommandWorker, EventPublisher


class AgentComposition:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = make_engine(settings.database_url)
        self.redis = Redis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5, socket_connect_timeout=5)
        self.providers = HttpProviders(settings.api_base_url, settings.internal_service_token.get_secret_value())
        self.model = TypedFakeModel() if settings.profile == "integrated-demo" else StructuredModel(ModelSettings.from_env(host=settings.host_secrets))
        self.journal = CommandJournal(make_sessions(self.engine))
        self.stop = threading.Event()
        self.threads, self.failures = [], {}
        self.dependencies = RuntimeDependencies(model=self.model, context=self.providers, policy=self.providers, evidence=self.providers, verification=self.providers, human=self.providers, memory=self.providers, clock=lambda: datetime.now(timezone.utc), gates=ReviewerGateConfig())

    @contextmanager
    def runtime(self, observer):
        with checkpoint_saver(self.settings.database_url) as saver:
            yield ReturnRuntime(replace(self.dependencies, observer=observer), saver)

    def start(self):
        with checkpoint_saver(self.settings.database_url) as saver:
            saver.get_tuple({"configurable": {"thread_id": "readiness-probe"}})
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
        tasks = {"event-publisher": EventPublisher(self.journal, self.redis).tick}
        for index in range(self.settings.concurrency):
            worker = CommandWorker(self.engine, self.journal, self.redis, self.runtime, consumer=f"agent-{uuid4().hex}-{index}")
            tasks[f"command-{index}"] = worker.tick
        for name, tick in tasks.items():
            self.failures[name] = True
            thread = threading.Thread(target=run, args=(name, tick), name=name, daemon=True)
            self.threads.append(thread)
            thread.start()

    def ready(self):
        return bool(self.threads) and all(thread.is_alive() for thread in self.threads) and not any(self.failures.values())

    def close(self):
        self.stop.set()
        for thread in self.threads:
            thread.join(5)
        self.providers.close()
        self.redis.close()
        self.engine.dispose()
