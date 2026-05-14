from typing import Literal, Optional

from pydantic import BaseModel, Field


class LawFindItem(BaseModel):
    name: str = Field("", description="法规文件名")
    path: str = Field("", description="法规章节条款的路径名，如“民法典第一编婚姻家庭”或“民法典第一编婚姻家庭第一章总则”")
    content: Optional[str] = Field(None, description="法规条款内容，当匹配到具体到法规条款，才会有这个值")
    summary: Optional[str] = Field(None, description="法规章节或者条目的摘要, 如果未找到对应路径的法规内容，则为None，如用户想要查询的法规的章节不存在的时候")
    scenario: Optional[str] = Field(None, description="当content或者summary存在的时候，此字段描述法规内容适用场景")
    reason: Optional[str] = Field(None, description="当用户是通过案件查询法规的时候，此字段描述法规内容的参考理由")
    
class LawFindResponse(BaseModel):
    code: int = Field(200, description="状态码，200表示成功，其他表示失败")
    message: str = Field("", description="状态信息")
    summary_type: Optional[Literal["prompt", "text", "llm", "none"]] = Field(None, description="查询结果的摘要类型，prompt表示使用summary字段作为prompt， text表示直接输出summary内容，llm表示使用data和用户问题作为llm的输入，none表示不生成总结，直接返回原始数据")
    summary: Optional[str] = Field(None, description="查询结果的摘要内容，如果summary_type为prompt，则此字段为提示词内容；如果summary_type为text，则此字段为文本内容；如果summary_type为llm或者为none，则此字段为None")