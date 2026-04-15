from app.core.trend_research.service_support import build_contract_state_snapshot


class ContractStatePoller:
    def __init__(self, *, fetcher, inst_id):
        self._fetcher = fetcher
        self._inst_id = inst_id

    def read_snapshot(self):
        return build_contract_state_snapshot(self._fetcher, self._inst_id)
