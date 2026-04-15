from .data_manager import DataManager
from .storage_backtest import StorageBacktestMixin
from .storage_assistant import StorageAssistantMixin
from .storage_base import StorageCoreMixin
from .storage_fills import StorageFillMixin
from .storage_journal import StorageJournalMixin
from .storage_live_orders import StorageLiveOrderMixin
from .storage_market_streams import StorageMarketStreamsMixin
from .storage_research_platform_delete import StorageResearchPlatformDeleteMixin
from .storage_research_platform_dataset import StorageResearchPlatformDatasetMixin
from .storage_research_platform_training import StorageResearchPlatformTrainingMixin
from .storage_research_platform import StorageResearchPlatformMixin
from .storage_risk import StorageRiskMixin
from .storage_scanner import StorageScannerMixin
from .storage_trend_research import StorageTrendResearchMixin


class DataStorage(
    StorageResearchPlatformDeleteMixin,
    StorageResearchPlatformTrainingMixin,
    StorageResearchPlatformDatasetMixin,
    StorageResearchPlatformMixin,
    StorageTrendResearchMixin,
    StorageMarketStreamsMixin,
    StorageCoreMixin,
    StorageFillMixin,
    StorageBacktestMixin,
    StorageLiveOrderMixin,
    StorageAssistantMixin,
    StorageJournalMixin,
    StorageRiskMixin,
    StorageScannerMixin,
):
    """组合后的数据存储入口。"""

    pass
