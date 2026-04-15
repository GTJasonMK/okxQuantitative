class ResearchDeleteBlockedError(RuntimeError):
    def __init__(self, *, message: str, error_code: str, **payload):
        self.message = message
        self.error_code = error_code
        self.payload = payload
        super().__init__(message)

    def to_detail(self) -> dict[str, object]:
        return {
            'message': self.message,
            'error_code': self.error_code,
            **self.payload,
        }


class CollectionSessionDeleteBlockedError(ResearchDeleteBlockedError):
    @classmethod
    def active_session(cls, session_id: str):
        return cls(
            message='active collection sessions cannot be deleted',
            error_code='collection_session_active',
            session_id=session_id,
        )

    @classmethod
    def referenced_by_datasets(cls, session_id: str, dataset_ids: list[str]):
        return cls(
            message='delete referenced datasets first',
            error_code='collection_session_referenced_by_dataset',
            session_id=session_id,
            blocking_dataset_ids=list(dataset_ids),
            blocking_dataset_count=len(dataset_ids),
        )


class DatasetDeleteBlockedError(ResearchDeleteBlockedError):
    @classmethod
    def referenced_by_training_runs(cls, dataset_id: str, run_ids: list[str]):
        return cls(
            message='delete referenced training runs first',
            error_code='dataset_referenced_by_training_run',
            dataset_id=dataset_id,
            blocking_training_run_ids=list(run_ids),
            blocking_training_run_count=len(run_ids),
        )
