"""Offline adversary definitions for the local agent-economy simulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

HONEST = "honest"
LOW_QUALITY = "low_quality"
COLLUDING_VERIFIER = "colluding_verifier"
SPAM_BIDDER = "spam_bidder"
REPUTATION_FARMER = "reputation_farmer"
REPEATED_DISPUTER = "repeated_disputer"
SYBIL_DUPLICATE = "sybil_duplicate"
OVERPRICED_BIDDER = "overpriced_bidder"
UNDERPRICED_FAILED_BIDDER = "underpriced_failed_bidder"


@dataclass(frozen=True)
class AdversaryRule:
    kind: str
    description: str
    default_quality: float
    default_bid_multiplier: float

    def as_record(self) -> Mapping[str, object]:
        return {
            "kind": self.kind,
            "description": self.description,
            "default_quality": self.default_quality,
            "default_bid_multiplier": self.default_bid_multiplier,
        }


ADVERSARY_RULES: Mapping[str, AdversaryRule] = {
    HONEST: AdversaryRule(HONEST, "Completes work and verifies independently.", 1.0, 1.0),
    LOW_QUALITY: AdversaryRule(LOW_QUALITY, "Submits low-quality artifacts likely to fail verification.", 0.2, 0.8),
    COLLUDING_VERIFIER: AdversaryRule(COLLUDING_VERIFIER, "Accepts allied bad work rather than quality.", 0.9, 1.0),
    SPAM_BIDDER: AdversaryRule(SPAM_BIDDER, "Places many noisy bids and does not deliver reliable work.", 0.1, 0.4),
    REPUTATION_FARMER: AdversaryRule(REPUTATION_FARMER, "Accumulates easy wins to inflate reputation.", 0.95, 0.7),
    REPEATED_DISPUTER: AdversaryRule(REPEATED_DISPUTER, "Opens repeated disputes even after deterministic evidence.", 0.6, 0.9),
    SYBIL_DUPLICATE: AdversaryRule(SYBIL_DUPLICATE, "Duplicates identity traits across multiple agents.", 0.4, 0.6),
    OVERPRICED_BIDDER: AdversaryRule(OVERPRICED_BIDDER, "Bids above task reward and should be rejected.", 0.8, 1.8),
    UNDERPRICED_FAILED_BIDDER: AdversaryRule(UNDERPRICED_FAILED_BIDDER, "Wins with a very low bid then fails quality.", 0.15, 0.1),
}
