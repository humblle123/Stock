from pydantic import BaseModel, Field
from typing import Optional


class StockSignal(BaseModel):
    """单只股票信号"""
    code: str = Field(description="股票代码")
    name: str = Field(description="股票名称")
    signal_type: str = Field(description="信号类型: technical/fundamental/sector")
    reason: str = Field(description="入选原因")
    metadata: dict = Field(default_factory=dict, description="附加数据")


class DailyBriefing(BaseModel):
    """每日简报"""
    date: str
    technical: list[StockSignal] = Field(default_factory=list)
    fundamental: list[StockSignal] = Field(default_factory=list)
    sector: list[StockSignal] = Field(default_factory=list)
    s2: list[StockSignal] = Field(default_factory=list)
    s3: list[StockSignal] = Field(default_factory=list)
    kd1: list[StockSignal] = Field(default_factory=list)
    summary: Optional[str] = None
