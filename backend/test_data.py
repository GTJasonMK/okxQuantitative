# 数据获取测试脚本
# 用于验证数据获取和存储模块是否正常工作

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from app.config import config, DATA_DIR, TIMEFRAMES
from app.core import DataFetcher, DataStorage, DataManager, InstType, create_fetcher


def test_data_fetcher():
    """测试数据获取功能"""
    print("=" * 60)
    print("测试数据获取模块")
    print("=" * 60)

    # 创建数据获取器（使用模拟盘）
    fetcher = create_fetcher(is_simulated=True)
    if not fetcher:
        print("创建数据获取器失败，请确保已安装 python-okx")
        print("安装命令: pip install python-okx")
        return False

    # 测试获取实时行情
    print("\n1. 获取BTC-USDT实时行情...")
    ticker = fetcher.get_ticker("BTC-USDT")
    if ticker:
        print(f"   交易对: {ticker.inst_id}")
        print(f"   最新价: {ticker.last}")
        print(f"   24h涨跌: {ticker.change_24h:.2f}%")
        print(f"   24h成交量: {ticker.vol_24h}")
    else:
        print("   获取失败")

    # 测试获取K线数据
    print("\n2. 获取BTC-USDT 1小时K线（最近10条）...")
    candles = fetcher.get_candles("BTC-USDT", "1H", limit=10)
    if candles:
        print(f"   获取到 {len(candles)} 条K线")
        print(f"   最早: {candles[0].datetime}")
        print(f"   最新: {candles[-1].datetime}")
        print(f"   最新收盘价: {candles[-1].close}")
    else:
        print("   获取失败")

    # 测试获取交易产品列表
    print("\n3. 获取现货交易对列表...")
    instruments = fetcher.get_instruments(InstType.SPOT)
    if instruments:
        usdt_pairs = [i for i in instruments if i["quote_ccy"] == "USDT"]
        print(f"   总交易对数: {len(instruments)}")
        print(f"   USDT交易对数: {len(usdt_pairs)}")
        print(f"   示例: {[i['inst_id'] for i in usdt_pairs[:5]]}")
    else:
        print("   获取失败")

    return True


def test_data_storage():
    """测试数据存储功能"""
    print("\n" + "=" * 60)
    print("测试数据存储模块")
    print("=" * 60)

    # 创建存储器
    db_path = DATA_DIR / "test_market.db"
    storage = DataStorage(db_path)

    # 创建测试数据
    from app.core import Candle
    test_candles = [
        Candle(
            timestamp=int((datetime.now() - timedelta(hours=i)).timestamp() * 1000),
            open=100 + i,
            high=105 + i,
            low=95 + i,
            close=102 + i,
            volume=1000 + i * 100,
            volume_ccy=100000 + i * 10000,
        )
        for i in range(10, 0, -1)
    ]

    # 测试保存
    print("\n1. 保存测试K线数据...")
    saved = storage.save_candles("TEST-USDT", "1H", test_candles)
    print(f"   保存了 {saved} 条数据")

    # 测试查询
    print("\n2. 查询K线数据...")
    candles = storage.get_latest_candles("TEST-USDT", "1H", 5)
    print(f"   查询到 {len(candles)} 条数据")

    # 测试获取数据范围
    print("\n3. 获取数据时间范围...")
    range_info = storage.get_candle_range("TEST-USDT", "1H")
    if range_info:
        oldest, newest, count = range_info
        print(f"   最早: {datetime.fromtimestamp(oldest/1000)}")
        print(f"   最新: {datetime.fromtimestamp(newest/1000)}")
        print(f"   总数: {count}")

    # 测试获取同步状态
    print("\n4. 获取同步状态...")
    status = storage.get_sync_status()
    for s in status:
        print(f"   {s['inst_id']} {s['timeframe']}: {s['candle_count']}条")

    # 清理测试数据
    print("\n5. 清理测试数据...")
    deleted = storage.delete_candles("TEST-USDT")
    print(f"   删除了 {deleted} 条数据")

    storage.close()
    return True


def test_data_manager():
    """测试数据管理器（整合获取和存储）"""
    print("\n" + "=" * 60)
    print("测试数据管理器")
    print("=" * 60)

    # 创建组件
    fetcher = create_fetcher(is_simulated=True)
    if not fetcher:
        print("无法测试数据管理器（数据获取器创建失败）")
        return False

    db_path = DATA_DIR / "market.db"
    storage = DataStorage(db_path)
    manager = DataManager(storage, fetcher)

    # 测试同步数据
    print("\n1. 同步 BTC-USDT 1小时K线（最近3天）...")
    synced = manager.sync_candles("BTC-USDT", "1H", days=3)
    print(f"   同步了 {synced} 条数据")

    # 测试获取数据
    print("\n2. 从本地获取最新100条K线...")
    candles = manager.get_candles_with_sync("BTC-USDT", "1H", count=100, auto_sync=False)
    print(f"   获取到 {len(candles)} 条数据")

    if candles:
        print(f"   时间范围: {candles[0].datetime} ~ {candles[-1].datetime}")
        print(f"   最新收盘价: {candles[-1].close}")

    # 显示已有数据
    print("\n3. 查看已同步的交易对...")
    symbols = storage.get_available_symbols()
    for s in symbols:
        print(f"   {s['inst_id']} ({s['inst_type']}): {s['timeframes']}")

    storage.close()
    return True


def main():
    """主测试函数"""
    print("OKX量化交易系统 - 数据模块测试")
    print(f"数据目录: {DATA_DIR}")
    print(f"支持的时间周期: {list(TIMEFRAMES.keys())}")

    # 运行测试
    results = []

    results.append(("数据获取", test_data_fetcher()))
    results.append(("数据存储", test_data_storage()))
    results.append(("数据管理", test_data_manager()))

    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    for name, passed in results:
        status = "通过" if passed else "失败"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    main()
