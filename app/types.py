from typing import Optional, TypedDict


class EmailReplyTo(TypedDict):
    archived: bool
    created_at: Optional[str]
    email_address: str
    id: str
    is_default: bool
    service_id: str
    updated_at: Optional[bool]


class TemplateStatistics(TypedDict):
    count: int
    template_id: str
    template_name: str
    template_type: str
    is_precompiled_letter: bool
    status: str


class StatisticsSimple(TypedDict):
    requested: int
    delivered: int
    failed: int

class Statistics(StatisticsSimple):
    failed_percentage: str
    show_warning: bool

class ServiceStatisticsSimple(TypedDict):
    sms: StatisticsSimple
    email: StatisticsSimple
    letter: StatisticsSimple
    
class ServiceStatistics(TypedDict):
    sms: Statistics
    email: Statistics
    letter: Statistics