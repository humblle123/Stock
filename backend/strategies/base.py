from abc import ABC, abstractmethod
from schemas.models import StockSignal


class BaseStrategy(ABC):
    """选股策略基类"""

    name: str = "base"
    description: str = "基础策略"

    @abstractmethod
    def screen(self, market_data: dict) -> list[StockSignal]:
        """
        执行筛选逻辑
        :param market_data: 市场数据（从数据层获取）
        :return: 符合条件的股票信号列表
        """
        raise NotImplementedError

    def validate(self) -> bool:
        """策略预检查"""
        return True
