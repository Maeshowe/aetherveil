"""Universe Manager — Determines which tickers to process.

Two-tier system:
- CORE: Always-active market structure nodes (SPY, QQQ, IWM, DIA)
- FOCUS: Dynamic tickers that explain CORE behavior

The manager maintains FOCUS membership based on:
1. Structural importance (index weights)
2. Microstructure stress signals
3. Calendar events (earnings, rebalancing)
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal


# CORE tickers — always active
CORE_TICKERS = frozenset(["SPY", "QQQ", "IWM", "DIA"])


@dataclass
class FocusEntry:
    """Represents why a ticker is in FOCUS."""
    
    ticker: str
    entry_date: date
    reason: Literal["structural", "stress", "event"]
    details: str
    days_inactive: int = 0  # Consecutive days without entry condition


@dataclass
class UniverseState:
    """Current state of the universe."""
    
    core: frozenset[str] = field(default_factory=lambda: CORE_TICKERS)
    focus: dict[str, FocusEntry] = field(default_factory=dict)
    
    def all_tickers(self) -> set[str]:
        """Return all active tickers (CORE + FOCUS)."""
        return set(self.core) | set(self.focus.keys())
    
    def is_core(self, ticker: str) -> bool:
        """Check if ticker is in CORE."""
        return ticker.upper() in self.core
    
    def is_focus(self, ticker: str) -> bool:
        """Check if ticker is in FOCUS."""
        return ticker.upper() in self.focus


class UniverseManager:
    """Manages CORE and FOCUS universe membership.
    
    Responsibilities:
    - Maintain CORE tickers (always active)
    - Promote tickers to FOCUS based on rules
    - Remove tickers from FOCUS after 3 inactive days
    - Track entry reasons for explainability
    
    Usage:
        manager = UniverseManager()
        
        # Get current active tickers
        tickers = manager.get_active_tickers()
        
        # Update FOCUS based on new diagnostics
        manager.promote_if_stressed(ticker="NVDA", z_gex=-2.5, unusualness=75)
        
        # Daily cleanup
        manager.expire_inactive()
    """
    
    def __init__(self) -> None:
        """Initialize with CORE tickers only."""
        self.state = UniverseState()
    
    def get_active_tickers(self) -> set[str]:
        """Return all currently active tickers (CORE + FOCUS).
        
        Returns:
            Set of uppercase ticker symbols
        """
        return self.state.all_tickers()
    
    def get_core_tickers(self) -> frozenset[str]:
        """Return CORE tickers (always SPY, QQQ, IWM, DIA).
        
        Returns:
            Frozen set of CORE ticker symbols
        """
        return self.state.core
    
    def get_focus_tickers(self) -> dict[str, FocusEntry]:
        """Return current FOCUS tickers with entry metadata.
        
        Returns:
            Dictionary mapping ticker → FocusEntry
        """
        return self.state.focus.copy()
    
    def promote_structural(
        self,
        ticker: str,
        index: Literal["SPY", "QQQ", "IWM", "DIA"],
        rank: int,
        entry_date: date
    ) -> bool:
        """Promote ticker to FOCUS based on index weight.
        
        Rules:
        - SPY: Top 15
        - QQQ: Top 10
        - IWM/DIA: Top 10
        
        Args:
            ticker: Symbol to promote
            index: Which index this relates to
            rank: Position in index (1-based)
            entry_date: Date of promotion
            
        Returns:
            True if promoted, False if already in FOCUS
        """
        ticker = ticker.upper()
        
        # Check if already in FOCUS
        if ticker in self.state.focus:
            # Reset inactivity counter
            self.state.focus[ticker].days_inactive = 0
            return False
        
        # Check rank threshold
        threshold = 15 if index == "SPY" else 10
        if rank > threshold:
            return False
        
        # Promote
        self.state.focus[ticker] = FocusEntry(
            ticker=ticker,
            entry_date=entry_date,
            reason="structural",
            details=f"Rank {rank} in {index}",
            days_inactive=0
        )
        return True
    
    def promote_if_stressed(
        self,
        ticker: str,
        unusualness: float | None,
        z_gex: float | None,
        dark_share: float | None,
        entry_date: date,
        z_block: float | None = None,
    ) -> bool:
        """Promote ticker to FOCUS if microstructure is stressed.

        Stress conditions (any one triggers entry):
        - unusualness >= 70
        - |z_gex| >= 2.0
        - dark_share >= 0.65
        - |z_block| >= 2.0

        Args:
            ticker: Symbol to check
            unusualness: Unusualness score (0-100 percentile)
            z_gex: GEX z-score
            dark_share: Raw dark pool share (0-1)
            entry_date: Date of promotion
            z_block: Block intensity z-score

        Returns:
            True if promoted, False otherwise
        """
        ticker = ticker.upper()

        # Check stress conditions
        reasons = []

        if unusualness is not None and unusualness >= 70:
            reasons.append(f"U={unusualness:.1f}")

        if z_gex is not None and abs(z_gex) >= 2.0:
            reasons.append(f"Z_GEX={z_gex:+.1f}")

        if dark_share is not None and dark_share >= 0.65:
            reasons.append(f"DarkShare={dark_share:.2%}")

        if z_block is not None and abs(z_block) >= 2.0:
            reasons.append(f"Z_block={z_block:+.1f}")

        if not reasons:
            return False

        # Check if already in FOCUS
        if ticker in self.state.focus:
            # Reset inactivity counter
            self.state.focus[ticker].days_inactive = 0
            return False

        # Promote
        self.state.focus[ticker] = FocusEntry(
            ticker=ticker,
            entry_date=entry_date,
            reason="stress",
            details=", ".join(reasons),
            days_inactive=0
        )
        return True
    
    def promote_event(
        self,
        ticker: str,
        event_type: Literal["earnings", "rebalancing", "macro"],
        event_date: date,
        entry_date: date
    ) -> bool:
        """Promote ticker to FOCUS due to calendar event.
        
        Args:
            ticker: Symbol to promote
            event_type: Type of event
            event_date: Date of the event
            entry_date: Date of promotion
            
        Returns:
            True if promoted, False if already in FOCUS
        """
        ticker = ticker.upper()
        
        # Check if already in FOCUS
        if ticker in self.state.focus:
            # Reset inactivity counter
            self.state.focus[ticker].days_inactive = 0
            return False
        
        # Promote
        self.state.focus[ticker] = FocusEntry(
            ticker=ticker,
            entry_date=entry_date,
            reason="event",
            details=f"{event_type} on {event_date.strftime('%Y-%m-%d')}",
            days_inactive=0
        )
        return True
    
    def mark_active(self, ticker: str) -> None:
        """Mark ticker as active (reset inactivity counter).
        
        Args:
            ticker: Symbol that met an entry condition today
        """
        ticker = ticker.upper()
        if ticker in self.state.focus:
            self.state.focus[ticker].days_inactive = 0
    
    def increment_inactive(self, ticker: str) -> None:
        """Increment inactivity counter for ticker.
        
        Args:
            ticker: Symbol that did NOT meet any entry condition today
        """
        ticker = ticker.upper()
        if ticker in self.state.focus:
            self.state.focus[ticker].days_inactive += 1
    
    def expire_inactive(self, threshold: int = 3) -> set[str]:
        """Remove FOCUS tickers that have been inactive for threshold days.
        
        Args:
            threshold: Number of consecutive inactive days before removal (default: 3)
            
        Returns:
            Set of tickers that were removed
        """
        to_remove = {
            ticker
            for ticker, entry in self.state.focus.items()
            if entry.days_inactive >= threshold
        }
        
        for ticker in to_remove:
            del self.state.focus[ticker]
        
        return to_remove
    
    def enforce_focus_cap(
        self,
        max_focus: int = 30,
        scores: dict[str, float] | None = None,
        z_gex_values: dict[str, float] | None = None,
    ) -> set[str]:
        """Enforce maximum FOCUS size by removing lowest-priority tickers.

        Priority order (highest priority kept first):
        1. Structural tickers always stay
        2. Highest unusualness score (U_t)
        3. Highest |Z_GEX| (tiebreaker)

        Args:
            max_focus: Maximum number of FOCUS tickers (default: 30)
            scores: Dict of ticker → unusualness score for ranking
            z_gex_values: Dict of ticker → |Z_GEX| for tiebreaking

        Returns:
            Set of tickers that were removed
        """
        if len(self.state.focus) <= max_focus:
            return set()

        scores = scores or {}
        z_gex_values = z_gex_values or {}

        # Separate structural from non-structural
        structural = {
            t for t, e in self.state.focus.items()
            if e.reason == "structural"
        }

        # If structural alone exceeds cap, don't cut them
        if len(structural) >= max_focus:
            return set()

        # How many non-structural slots available
        non_structural_slots = max_focus - len(structural)

        # Rank non-structural by: score desc, then |z_gex| desc
        non_structural = [
            t for t in self.state.focus if t not in structural
        ]

        non_structural.sort(
            key=lambda t: (
                scores.get(t, 0.0),
                abs(z_gex_values.get(t, 0.0)),
            ),
            reverse=True,
        )

        # Keep top non_structural_slots, remove the rest
        to_remove = set(non_structural[non_structural_slots:])

        for ticker in to_remove:
            del self.state.focus[ticker]

        return to_remove

    def reset_focus(self) -> None:
        """Clear all FOCUS tickers (keeps CORE intact).

        Useful for testing or manual reset.
        """
        self.state.focus.clear()
