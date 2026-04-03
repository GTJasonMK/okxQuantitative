from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..agent.schemas import AgentInstTypeEnum, AgentModeEnum


class AssistantAgentSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", description="会话标题")
    inst_id: str = Field(default="", description="关注的交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="会话元数据")


class AssistantAgentTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: Optional[str] = Field(default=None, description="已有会话 ID")
    title: str = Field(default="", description="新会话标题")
    message: str = Field(..., min_length=1, description="用户输入")
    inst_id: str = Field(default="", description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    market_context: Dict[str, Any] = Field(default_factory=dict, description="前端附带上下文")
    max_tool_rounds: int = Field(default=4, ge=1, le=8, description="最多工具轮数")


class AssistantAgentToolDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    input_schema: Dict[str, Any] = Field(default_factory=dict)
