"""Base interface for AUREX specialist trading and yield engines."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from aurex.core.models import MarketType, Opportunity


class BaseSpecialistEngine(ABC):
    """Abstract interface for domain specialist engines."""

    @property
    @abstractmethod
    def engine_id(self) -> str:
        """Unique identifier of the specialist engine."""
        pass

    @property
    @abstractmethod
    def market_type(self) -> MarketType:
        """Market type handled by this engine."""
        pass

    @abstractmethod
    def scan_opportunities(self) -> List[Opportunity]:
        """Scan domain universe and return viable opportunities."""
        pass

    @abstractmethod
    def get_market_telemetry(self) -> Dict[str, Any]:
        """Return engine health, liquidity conditions, and market regimes."""
        pass
