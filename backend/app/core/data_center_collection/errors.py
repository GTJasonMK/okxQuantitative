class CollectionSessionBootstrapError(RuntimeError):
    def __init__(self, *, session_id: str, detail: str, error_code: str = 'bootstrap_failed'):
        self.session_id = session_id
        self.detail = str(detail)
        self.error_code = error_code
        super().__init__(self.detail)
