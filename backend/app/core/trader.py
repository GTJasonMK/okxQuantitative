# OKX 交易模块
# 封装 OKX Trading API 和 Account API
# 支持同时运行模拟盘和实盘两种模式

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from threading import Lock
import types
from decimal import Decimal, InvalidOperation, ROUND_DOWN

# python-okx / okx-sdk 依赖在部分环境（仅做回测/数据服务）可能未安装。
# 这里做可选导入：保证后端可启动、单元测试可运行；真正调用交易功能时再报出明确错误。
def _missing_okx_dep(*args, **kwargs):  # pragma: no cover
    raise ModuleNotFoundError("缺少依赖 okx（python-okx/okx-sdk），请先安装后再使用交易功能")


try:  # pragma: no cover
    import okx.Trade as Trade
except Exception:
    Trade = types.SimpleNamespace(TradeAPI=_missing_okx_dep)

try:  # pragma: no cover
    import okx.Account as Account
except Exception:
    Account = types.SimpleNamespace(AccountAPI=_missing_okx_dep)

from ..config import config


@dataclass
class OrderResult:
    """下单结果"""
    success: bool
    order_id: str = ""
    client_order_id: str = ""
    error_code: str = ""
    error_message: str = ""


@dataclass
class CancelResult:
    """撤单结果"""
    success: bool
    order_id: str = ""
    error_code: str = ""
    error_message: str = ""


class OKXTrader:
    """
    OKX 交易执行器

    封装 OKX Trade API，提供下单、撤单、查询订单等功能
    支持指定模式（模拟盘/实盘）
    """

    def __init__(self, is_simulated: bool = True):
        """
        初始化交易器

        Args:
            is_simulated: True=模拟盘, False=实盘
        """
        self._is_simulated = is_simulated
        self._trade_api = None
        self._init_api()

    def _init_api(self):
        """初始化 Trade API"""
        # 先清空旧实例：避免配置变更为无效后仍使用旧 API 继续下单
        self._trade_api = None
        # 按实例模式选择对应的密钥，避免 simulated/live 请求串用“当前模式”的密钥
        creds = config.okx.demo if self._is_simulated else config.okx.live
        if not creds.is_valid():
            print(f"[OKXTrader-{'模拟盘' if self._is_simulated else '实盘'}] API 密钥未配置，交易功能不可用")
            return

        try:
            flag = "1" if self._is_simulated else "0"
            self._trade_api = Trade.TradeAPI(
                api_key=creds.api_key,
                api_secret_key=creds.secret_key,
                passphrase=creds.passphrase,
                flag=flag,
                debug=False
            )
            print(f"[OKXTrader] 初始化成功，模式: {'模拟盘' if self._is_simulated else '实盘'}")
        except Exception as e:
            print(f"[OKXTrader] 初始化失败: {e}")
            self._trade_api = None

    def reinit(self):
        """重新初始化（配置变更后调用）"""
        self._init_api()

    @property
    def is_available(self) -> bool:
        """检查交易功能是否可用"""
        return self._trade_api is not None

    @property
    def mode(self) -> str:
        """获取当前模式"""
        return "simulated" if self._is_simulated else "live"

    def place_order(
        self,
        inst_id: str,
        side: str,
        order_type: str,
        size: str,
        price: str = "",
        td_mode: str = "cash",
        client_order_id: str = ""
    ) -> OrderResult:
        """
        下单

        Args:
            inst_id: 交易对，如 "BTC-USDT"
            side: 交易方向，"buy" 或 "sell"
            order_type: 订单类型，"market"（市价）或 "limit"（限价）
            size: 委托数量
            price: 委托价格（限价单必填）
            td_mode: 交易模式，"cash"（现货）、"isolated"（逐仓）、"cross"（全仓）
            client_order_id: 客户端订单ID（可选）

        Returns:
            OrderResult: 下单结果
        """
        if not self.is_available:
            return OrderResult(
                success=False,
                error_code="API_NOT_AVAILABLE",
                error_message="交易 API 未初始化，请检查 API 密钥配置"
            )

        try:
            params: Dict[str, Any] = {
                "instId": inst_id,
                "tdMode": td_mode,
                "side": side,
                "ordType": order_type,
                "sz": size,
                "px": price if order_type == "limit" else "",
                "clOrdId": client_order_id,
            }

            # 关键：OKX 现货市价单 BUY 默认以 quote_ccy 作为 sz 单位（例如 USDT），
            # 但本项目（前端/策略）统一把 size 视为 base_ccy 数量（例如 BTC）。
            # 这里显式指定 tgtCcy=base_ccy，避免“买入数量单位错配”导致的严重交易偏差。
            if order_type == "market":
                params["tgtCcy"] = "base_ccy"

            try:
                result = self._trade_api.place_order(**params)
            except TypeError as e:
                # 若 SDK 不支持 tgtCcy 参数，宁可拒单也不要用默认行为继续下单（会造成数量单位错配）。
                if order_type == "market" and "tgtCcy" in str(e):
                    return OrderResult(
                        success=False,
                        error_code="UNSUPPORTED_SDK",
                        error_message="当前 OKX SDK 不支持 market 单的 tgtCcy 参数，无法保证 size 单位为基础币。请升级 python-okx 后再下单。",
                    )
                raise

            if result.get("code") == "0":
                data = result.get("data", [{}])[0]
                return OrderResult(
                    success=True,
                    order_id=data.get("ordId", ""),
                    client_order_id=data.get("clOrdId", "")
                )
            else:
                return OrderResult(
                    success=False,
                    error_code=result.get("code", ""),
                    error_message=result.get("msg", "下单失败")
                )
        except Exception as e:
            return OrderResult(
                success=False,
                error_code="EXCEPTION",
                error_message=str(e)
            )

    def cancel_order(
        self,
        inst_id: str,
        order_id: str = "",
        client_order_id: str = ""
    ) -> CancelResult:
        """
        撤销订单

        Args:
            inst_id: 交易对
            order_id: 订单ID（与 client_order_id 二选一）
            client_order_id: 客户端订单ID

        Returns:
            CancelResult: 撤单结果
        """
        if not self.is_available:
            return CancelResult(
                success=False,
                error_code="API_NOT_AVAILABLE",
                error_message="交易 API 未初始化"
            )

        try:
            result = self._trade_api.cancel_order(
                instId=inst_id,
                ordId=order_id,
                clOrdId=client_order_id
            )

            if result.get("code") == "0":
                data = result.get("data", [{}])[0]
                return CancelResult(
                    success=True,
                    order_id=data.get("ordId", "")
                )
            else:
                return CancelResult(
                    success=False,
                    error_code=result.get("code", ""),
                    error_message=result.get("msg", "撤单失败")
                )
        except Exception as e:
            return CancelResult(
                success=False,
                error_code="EXCEPTION",
                error_message=str(e)
            )

    def get_order(self, inst_id: str, order_id: str) -> Optional[Dict[str, Any]]:
        """
        查询单个订单详情

        Args:
            inst_id: 交易对
            order_id: 订单ID

        Returns:
            订单详情字典，失败返回 None
        """
        if not self.is_available:
            return None

        try:
            result = self._trade_api.get_order(instId=inst_id, ordId=order_id)
            if result.get("code") == "0" and result.get("data"):
                return result["data"][0]
            return None
        except Exception as e:
            print(f"[OKXTrader] 查询订单失败: {e}")
            return None

    def get_pending_orders(
        self,
        inst_type: str = "SPOT",
        inst_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取当前未成交订单列表

        Args:
            inst_type: 交易类型，"SPOT"、"SWAP"、"FUTURES"
            inst_id: 交易对（可选，不填则返回所有）

        Returns:
            订单列表
        """
        if not self.is_available:
            return []

        try:
            result = self._trade_api.get_order_list(
                instType=inst_type,
                instId=inst_id
            )
            if result.get("code") == "0":
                return result.get("data", [])
            return []
        except Exception as e:
            print(f"[OKXTrader] 获取未成交订单失败: {e}")
            return []

    def get_order_history(
        self,
        inst_type: str = "SPOT",
        inst_id: str = "",
        limit: str = "50"
    ) -> List[Dict[str, Any]]:
        """
        获取历史订单（最近7天）

        Args:
            inst_type: 交易类型
            inst_id: 交易对（可选）
            limit: 返回数量限制

        Returns:
            订单列表
        """
        if not self.is_available:
            return []

        try:
            result = self._trade_api.get_orders_history(
                instType=inst_type,
                instId=inst_id,
                limit=limit
            )
            if result.get("code") == "0":
                return result.get("data", [])
            return []
        except Exception as e:
            print(f"[OKXTrader] 获取历史订单失败: {e}")
            return []

    def get_fills(
        self,
        inst_type: str = "SPOT",
        inst_id: str = "",
        limit: str = "50"
    ) -> List[Dict[str, Any]]:
        """
        获取成交记录（最近3天）

        Args:
            inst_type: 交易类型
            inst_id: 交易对（可选）
            limit: 返回数量限制

        Returns:
            成交记录列表
        """
        if not self.is_available:
            return []

        try:
            result = self._trade_api.get_fills(
                instType=inst_type,
                instId=inst_id,
                limit=limit
            )
            if result.get("code") == "0":
                return result.get("data", [])
            return []
        except Exception as e:
            print(f"[OKXTrader] 获取成交记录失败: {e}")
            return []

    def get_fills_history(
        self,
        inst_type: str = "SPOT",
        inst_id: str = "",
        limit: str = "100",
        after: str = "",
        before: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取历史成交记录（最近3个月）

        Args:
            inst_type: 交易类型
            inst_id: 交易对（可选）
            limit: 返回数量限制（最大100）
            after: 请求此ID之前的数据（用于分页）
            before: 请求此ID之后的数据

        Returns:
            成交记录列表
        """
        if not self.is_available:
            return []

        try:
            result = self._trade_api.get_fills_history(
                instType=inst_type,
                instId=inst_id,
                limit=limit,
                after=after,
                before=before
            )
            if result.get("code") == "0":
                return result.get("data", [])
            print(f"[OKXTrader] 获取历史成交记录失败: {result.get('msg')}")
            return []
        except Exception as e:
            print(f"[OKXTrader] 获取历史成交记录异常: {e}")
            return []

    def get_all_fills_history(
        self,
        inst_type: str = "SPOT"
    ) -> List[Dict[str, Any]]:
        """
        获取所有历史成交记录（自动分页获取最近3个月全部数据）

        Args:
            inst_type: 交易类型

        Returns:
            成交记录列表（按时间倒序）
        """
        all_fills = []
        after = ""
        max_iterations = 100  # 防止无限循环

        for _ in range(max_iterations):
            fills = self.get_fills_history(
                inst_type=inst_type,
                limit="100",
                after=after
            )

            if not fills:
                break

            all_fills.extend(fills)

            # 获取最后一条的ID用于分页
            last_fill = fills[-1]
            next_after = str(last_fill.get("billId", "") or "")

            # 防御性处理：部分环境/版本可能不返回 billId，或 billId 不推进导致重复拉取同一页。
            # 若无法推进分页，直接退出，避免最多 100 次重复请求导致限流/卡死。
            if not next_after:
                print("[OKXTrader] 历史成交记录分页缺少 billId，已停止分页以避免重复拉取")
                break
            if next_after == after:
                print(f"[OKXTrader] 历史成交记录分页 billId 未推进（billId={next_after}），已停止分页")
                break

            after = next_after

            # 如果返回数量少于limit，说明已经没有更多数据
            if len(fills) < 100:
                break

        print(f"[OKXTrader] 共获取 {len(all_fills)} 条历史成交记录")
        return all_fills

    # ==================== 合约交易相关 ====================

    def set_leverage(
        self,
        inst_id: str,
        lever: str,
        mgn_mode: str = "cross",
        pos_side: str = ""
    ) -> Dict[str, Any]:
        """
        设置杠杆倍数

        Args:
            inst_id: 合约ID，如 "BTC-USDT-SWAP"
            lever: 杠杆倍数，如 "10"
            mgn_mode: 保证金模式，"cross"（全仓）或 "isolated"（逐仓）
            pos_side: 持仓方向（仅逐仓双向持仓时需要），"long" 或 "short"

        Returns:
            设置结果
        """
        if not self.is_available:
            return {"error": "API 未初始化"}

        try:
            result = self._trade_api.set_leverage(
                instId=inst_id,
                lever=lever,
                mgnMode=mgn_mode,
                posSide=pos_side if pos_side else None
            )
            if result.get("code") == "0":
                return {"success": True, "data": result.get("data", [])}
            return {"success": False, "error": result.get("msg", "设置杠杆失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_leverage(self, inst_id: str, mgn_mode: str = "cross") -> Dict[str, Any]:
        """
        获取杠杆倍数

        Args:
            inst_id: 合约ID
            mgn_mode: 保证金模式

        Returns:
            杠杆信息
        """
        if not self.is_available:
            return {"error": "API 未初始化"}

        try:
            result = self._trade_api.get_leverage(
                instId=inst_id,
                mgnMode=mgn_mode
            )
            if result.get("code") == "0" and result.get("data"):
                return {"success": True, "data": result["data"]}
            return {"success": False, "error": result.get("msg", "获取杠杆失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def place_contract_order(
        self,
        inst_id: str,
        side: str,
        pos_side: str,
        order_type: str,
        size: str,
        price: str = "",
        td_mode: str = "cross",
        reduce_only: bool = False,
        client_order_id: str = ""
    ) -> OrderResult:
        """
        合约下单

        Args:
            inst_id: 合约ID，如 "BTC-USDT-SWAP"
            side: 交易方向，"buy" 或 "sell"
            pos_side: 持仓方向，"long"（多头）或 "short"（空头）
                      - 开多: side=buy, pos_side=long
                      - 开空: side=sell, pos_side=short
                      - 平多: side=sell, pos_side=long
                      - 平空: side=buy, pos_side=short
            order_type: 订单类型，"market" 或 "limit"
            size: 委托数量（张数）
            price: 委托价格（限价单必填）
            td_mode: 保证金模式，"cross"（全仓）或 "isolated"（逐仓）
            reduce_only: 是否只减仓
            client_order_id: 客户端订单ID

        Returns:
            OrderResult: 下单结果
        """
        if not self.is_available:
            return OrderResult(
                success=False,
                error_code="API_NOT_AVAILABLE",
                error_message="交易 API 未初始化"
            )

        try:
            result = self._trade_api.place_order(
                instId=inst_id,
                tdMode=td_mode,
                side=side,
                posSide=pos_side,
                ordType=order_type,
                sz=size,
                px=price if order_type == "limit" else "",
                reduceOnly=reduce_only,
                clOrdId=client_order_id
            )

            if result.get("code") == "0":
                data = result.get("data", [{}])[0]
                return OrderResult(
                    success=True,
                    order_id=data.get("ordId", ""),
                    client_order_id=data.get("clOrdId", "")
                )
            else:
                return OrderResult(
                    success=False,
                    error_code=result.get("code", ""),
                    error_message=result.get("msg", "下单失败")
                )
        except Exception as e:
            return OrderResult(
                success=False,
                error_code="EXCEPTION",
                error_message=str(e)
            )


class OKXAccount:
    """
    OKX 账户管理器

    封装 OKX Account API，提供账户余额、持仓查询等功能
    支持指定模式（模拟盘/实盘）
    """

    def __init__(self, is_simulated: bool = True):
        """
        初始化账户管理器

        Args:
            is_simulated: True=模拟盘, False=实盘
        """
        self._is_simulated = is_simulated
        self._account_api = None
        self._init_api()

    def _init_api(self):
        """初始化 Account API"""
        # 先清空旧实例：避免配置变更为无效后仍使用旧 API（模式/密钥错配风险）
        self._account_api = None
        # 按实例模式选择对应的密钥，避免 simulated/live 请求串用“当前模式”的密钥
        creds = config.okx.demo if self._is_simulated else config.okx.live
        if not creds.is_valid():
            print(f"[OKXAccount-{'模拟盘' if self._is_simulated else '实盘'}] API 密钥未配置，账户功能不可用")
            return

        try:
            flag = "1" if self._is_simulated else "0"
            self._account_api = Account.AccountAPI(
                api_key=creds.api_key,
                api_secret_key=creds.secret_key,
                passphrase=creds.passphrase,
                flag=flag,
                debug=False
            )
            print(f"[OKXAccount] 初始化成功，模式: {'模拟盘' if self._is_simulated else '实盘'}")
        except Exception as e:
            print(f"[OKXAccount] 初始化失败: {e}")
            self._account_api = None

    def reinit(self):
        """重新初始化（配置变更后调用）"""
        self._init_api()

    @property
    def is_available(self) -> bool:
        """检查账户功能是否可用"""
        return self._account_api is not None

    @property
    def mode(self) -> str:
        """获取当前模式"""
        return "simulated" if self._is_simulated else "live"

    def get_balance(self, ccy: str = "") -> Dict[str, Any]:
        """
        获取账户余额

        Args:
            ccy: 币种，如 "USDT"、"BTC"，不填返回所有

        Returns:
            余额信息字典
        """
        if not self.is_available:
            return {"error": "API 未初始化"}

        try:
            result = self._account_api.get_account_balance(ccy=ccy)
            print(f"[OKXAccount-{self.mode}] get_account_balance 返回: code={result.get('code')}, msg={result.get('msg')}")
            if result.get("code") == "0" and result.get("data"):
                return result["data"][0]
            return {"error": result.get("msg", "获取余额失败"), "code": result.get("code")}
        except Exception as e:
            print(f"[OKXAccount] get_balance 异常: {e}")
            return {"error": str(e)}

    def get_positions(self, inst_type: str = "", inst_id: str = "") -> List[Dict[str, Any]]:
        """
        获取持仓信息

        Args:
            inst_type: 交易类型，"SPOT"、"SWAP"、"FUTURES"
            inst_id: 交易对（可选）

        Returns:
            持仓列表
        """
        if not self.is_available:
            return []

        try:
            result = self._account_api.get_positions(
                instType=inst_type,
                instId=inst_id
            )
            if result.get("code") == "0":
                return result.get("data", [])
            return []
        except Exception as e:
            print(f"[OKXAccount] 获取持仓失败: {e}")
            return []

    def get_max_avail_size(
        self,
        inst_id: str,
        td_mode: str = "cash",
        *,
        last_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        获取最大可交易数量（统一输出 maxBuy/maxSell）

        Args:
            inst_id: 交易对
            td_mode: 交易模式，"cash"（现货）

        Returns:
            包含 maxBuy/maxSell 的字典（均按基础币数量返回，便于直接作为现货下单 sz）。

        说明（非常重要）：
        - OKX 有两个相近接口：
          1) /api/v5/account/max-avail-size：返回 availBuy/availSell（现货：availBuy 为计价币，availSell 为基础币）
          2) /api/v5/account/max-size：返回 maxBuy/maxSell（在 UI 里 maxSell 常表示“卖出后可得到的计价币数量”）
        - 项目里（前端下单、实时引擎）把“数量 size/sz”统一视为基础币数量（例如 BTC）。
          为避免单位混乱，这里做兼容与归一化输出：maxBuy=最大可买基础币数量，maxSell=最大可卖基础币数量。
        """
        if not self.is_available:
            return {"maxBuy": "0", "maxSell": "0"}

        # 1) 先获取 max-avail-size（可用余额口径，含 availBuy/availSell）
        avail_payload: Dict[str, Any] = {}
        try:
            resp = self._account_api.get_max_avail_size(instId=inst_id, tdMode=td_mode)
            if resp.get("code") == "0" and resp.get("data"):
                avail_payload = resp["data"][0] or {}
        except Exception as e:
            # 不直接 return：后面仍可尝试 max-size
            print(f"[OKXAccount] 获取 max-avail-size 失败: {e}")

        # 兼容：若某些 SDK 版本直接在 get_max_avail_size 返回 maxBuy/maxSell，则保持原样返回
        if avail_payload and ("maxBuy" in avail_payload or "maxSell" in avail_payload):
            return {
                "maxBuy": str(avail_payload.get("maxBuy", "0") or "0"),
                "maxSell": str(avail_payload.get("maxSell", "0") or "0"),
            }

        avail_buy = str(avail_payload.get("availBuy", "0") or "0")
        avail_sell = str(avail_payload.get("availSell", "0") or "0")

        # 2) 获取 max-size（最大可下单量口径），用于推导“最大可买基础币数量”
        max_buy_base: str = "0"
        max_sell_quote: str = "0"
        try:
            get_max_order_size = getattr(self._account_api, "get_max_order_size", None)
            if callable(get_max_order_size):
                resp2 = get_max_order_size(instId=inst_id, tdMode=td_mode)
                if resp2.get("code") == "0" and resp2.get("data"):
                    data2 = resp2["data"][0] or {}
                    max_buy_base = str(data2.get("maxBuy", "0") or "0")
                    max_sell_quote = str(data2.get("maxSell", "0") or "0")
        except Exception as e:
            print(f"[OKXAccount] 获取 max-size 失败: {e}")

        # 3) 兜底：若 max-size 不可用，但 availBuy 存在，则用“外部注入的最新价”估算 maxBuy（基础币数量）
        # 说明：这里刻意不直接依赖 CachedDataFetcher 等缓存模块，避免交易模块与行情/缓存强耦合。
        if (
            (not max_buy_base or max_buy_base in ("0", "0.0"))
            and avail_buy not in ("", "0", "0.0")
            and last_price is not None
        ):
            try:
                avail_buy_dec = Decimal(avail_buy)
                price_dec = Decimal(str(last_price))
                if avail_buy_dec > 0 and price_dec > 0:
                    # 保守向下取整，避免由于四舍五入导致超出可买量而被交易所拒单
                    est = (avail_buy_dec / price_dec).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
                    max_buy_base = str(est)
            except (InvalidOperation, ValueError, TypeError) as e:
                print(f"[OKXAccount] 估算 maxBuy 失败: {e}")
            except Exception as e:
                print(f"[OKXAccount] 估算 maxBuy 异常: {e}")

        # 4) 统一输出：maxSell 使用 availSell（基础币可卖数量），避免把 maxSell(计价币) 误当作基础币数量
        return {
            "maxBuy": max_buy_base or "0",
            "maxSell": avail_sell or "0",
            # 附带原始字段，便于 UI/排障（不影响旧调用方 get("maxBuy"/"maxSell")）
            "availBuy": avail_buy,
            "availSell": avail_sell,
            "maxSellQuote": max_sell_quote,
        }

    def get_account_config(self) -> Dict[str, Any]:
        """
        获取账户配置信息

        Returns:
            账户配置信息
        """
        if not self.is_available:
            return {}

        try:
            result = self._account_api.get_account_config()
            if result.get("code") == "0" and result.get("data"):
                return result["data"][0]
            return {}
        except Exception as e:
            print(f"[OKXAccount] 获取账户配置失败: {e}")
            return {}

    def set_position_mode(self, pos_mode: str) -> Dict[str, Any]:
        """
        设置持仓模式

        Args:
            pos_mode: "long_short_mode"（双向持仓）或 "net_mode"（单向持仓）

        Returns:
            设置结果
        """
        if not self.is_available:
            return {"success": False, "error": "API 未初始化"}

        try:
            result = self._account_api.set_position_mode(posMode=pos_mode)
            if result.get("code") == "0":
                return {"success": True}
            return {"success": False, "error": result.get("msg", "设置持仓模式失败")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_contract_positions(
        self,
        inst_type: str = "SWAP",
        inst_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取合约持仓

        Args:
            inst_type: "SWAP"（永续）或 "FUTURES"（交割）
            inst_id: 合约ID（可选）

        Returns:
            持仓列表，每项包含:
            - instId: 合约ID
            - posSide: 持仓方向 long/short/net
            - pos: 持仓数量
            - avgPx: 开仓均价
            - upl: 未实现盈亏
            - uplRatio: 未实现盈亏比率
            - lever: 杠杆倍数
            - liqPx: 强平价格
            - margin: 保证金
            - mgnMode: 保证金模式
        """
        if not self.is_available:
            return []

        try:
            result = self._account_api.get_positions(
                instType=inst_type,
                instId=inst_id
            )
            if result.get("code") == "0":
                return result.get("data", [])
            return []
        except Exception as e:
            print(f"[OKXAccount] 获取合约持仓失败: {e}")
            return []

    def get_max_contract_size(
        self,
        inst_id: str,
        td_mode: str = "cross"
    ) -> Dict[str, Any]:
        """
        获取合约最大可开仓数量

        Args:
            inst_id: 合约ID
            td_mode: 保证金模式，"cross"（全仓）或 "isolated"（逐仓）

        Returns:
            包含 maxBuy（最大可开多）和 maxSell（最大可开空）的字典
        """
        if not self.is_available:
            return {"maxBuy": "0", "maxSell": "0"}

        try:
            # 合约最大可开仓数量对应 OKX 的 max-size（maxBuy/maxSell）。
            # 优先调用 get_max_order_size；若 SDK 不支持则退化为 get_max_avail_size（可能不包含 maxBuy/maxSell）。
            get_max_order_size = getattr(self._account_api, "get_max_order_size", None)
            if callable(get_max_order_size):
                result = get_max_order_size(instId=inst_id, tdMode=td_mode)
            else:
                result = self._account_api.get_max_avail_size(instId=inst_id, tdMode=td_mode)
            if result.get("code") == "0" and result.get("data"):
                return result["data"][0]
            return {"maxBuy": "0", "maxSell": "0"}
        except Exception as e:
            print(f"[OKXAccount] 获取合约最大可开仓量失败: {e}")
            return {"maxBuy": "0", "maxSell": "0"}


class TradingManager:
    """
    交易管理器

    管理模拟盘和实盘两套 Trader 和 Account 实例
    """
    _instance: Optional['TradingManager'] = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 模拟盘实例（延迟初始化，首次使用时创建）
        self._simulated_trader: Optional[OKXTrader] = None
        self._simulated_account: Optional[OKXAccount] = None

        # 实盘实例（延迟初始化，首次使用时创建）
        self._live_trader: Optional[OKXTrader] = None
        self._live_account: Optional[OKXAccount] = None

        print("[TradingManager] 就绪（延迟初始化，首次使用时创建实例）")

    def _init_all(self):
        """初始化所有实例"""
        # 先清空旧实例，防止配置失效后仍使用旧密钥
        self._simulated_trader = None
        self._simulated_account = None
        self._live_trader = None
        self._live_account = None

        # 分别初始化两套实例：哪一套密钥没配就不创建对应实例（避免“用错密钥”）
        has_demo = config.okx.demo.is_valid()
        has_live = config.okx.live.is_valid()
        if not has_demo and not has_live:
            print("[TradingManager] 模拟盘/实盘 API 密钥均未配置，已清空所有交易实例")
            return

        print("[TradingManager] 初始化交易实例...")
        if has_demo:
            self._simulated_trader = OKXTrader(is_simulated=True)
            self._simulated_account = OKXAccount(is_simulated=True)
        else:
            print("[TradingManager] 模拟盘 API 密钥未配置，跳过模拟盘实例初始化")

        if has_live:
            self._live_trader = OKXTrader(is_simulated=False)
            self._live_account = OKXAccount(is_simulated=False)
        else:
            print("[TradingManager] 实盘 API 密钥未配置，跳过实盘实例初始化")

    def reinit(self):
        """重新初始化所有实例（配置变更后调用）"""
        self._init_all()

    def get_trader(self, mode: str = "simulated") -> OKXTrader:
        """
        获取指定模式的交易器

        Args:
            mode: "simulated" 或 "live"

        Returns:
            OKXTrader 实例
        """
        if mode == "live":
            if self._live_trader is None:
                self._live_trader = OKXTrader(is_simulated=False)
            return self._live_trader
        else:
            if self._simulated_trader is None:
                self._simulated_trader = OKXTrader(is_simulated=True)
            return self._simulated_trader

    def get_account(self, mode: str = "simulated") -> OKXAccount:
        """
        获取指定模式的账户管理器

        Args:
            mode: "simulated" 或 "live"

        Returns:
            OKXAccount 实例
        """
        if mode == "live":
            if self._live_account is None:
                self._live_account = OKXAccount(is_simulated=False)
            return self._live_account
        else:
            if self._simulated_account is None:
                self._simulated_account = OKXAccount(is_simulated=True)
            return self._simulated_account


# 全局交易管理器实例
_trading_manager: Optional[TradingManager] = None


def get_trading_manager() -> TradingManager:
    """获取交易管理器单例"""
    global _trading_manager
    if _trading_manager is None:
        _trading_manager = TradingManager()
    return _trading_manager


def get_trader(mode: str = "simulated") -> OKXTrader:
    """
    获取指定模式的交易器

    Args:
        mode: "simulated" 或 "live"
    """
    return get_trading_manager().get_trader(mode)


def get_account(mode: str = "simulated") -> OKXAccount:
    """
    获取指定模式的账户管理器

    Args:
        mode: "simulated" 或 "live"
    """
    return get_trading_manager().get_account(mode)
