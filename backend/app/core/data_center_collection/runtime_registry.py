class CollectionRuntimeRegistry:
    def __init__(self):
        self._runtimes: dict[str, object] = {}

    def register(self, session_id: str, runtime: object) -> None:
        if self.active_session_id() is not None:
            raise ValueError('active collection session already exists')
        self._runtimes[session_id] = runtime

    def get(self, session_id: str) -> object | None:
        return self._runtimes.get(session_id)

    def unregister(self, session_id: str) -> None:
        self._runtimes.pop(session_id, None)

    def active_session_id(self) -> str | None:
        return next(iter(self._runtimes), None)
