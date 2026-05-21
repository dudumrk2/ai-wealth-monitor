"""
Pydantic request/response schemas used across the application.
Centralizes all BaseModel definitions to keep route handlers clean.
"""
from pydantic import BaseModel
from typing import Optional


# ── Manual Investment ────────────────────────────────────────────────────────

class ManualInvestment(BaseModel):
    id: str
    name: str
    description: str
    balance: float
    monthly_deposit: float
    expected_yearly_yield: float
    start_date: str
    end_date: str
    owner: str = "user"


# ── Manual Stock Entry ───────────────────────────────────────────────────────

class ManualStockRequest(BaseModel):
    symbol: str
    name: str
    qty: float
    avgCostPrice: float
    currency: str = "USD"
    is_cash: Optional[bool] = False


# ── Gmail Settings ───────────────────────────────────────────────────────────

class GmailSettingsPayload(BaseModel):
    gmail_sender_email: Optional[str] = None
    gmail_subject: Optional[str] = None
    cron_day: Optional[int] = None
    cron_frequency_months: Optional[int] = None
    cron_fetch_emails_enabled: Optional[bool] = None
    cron_stock_prices_enabled: Optional[bool] = None
    cron_weekly_summary_enabled: Optional[bool] = None
    cron_agent_enabled: Optional[bool] = None
    telegram_chat_id: Optional[str] = None
