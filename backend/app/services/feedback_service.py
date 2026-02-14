"""
Community Feedback Service — Lightweight user input and voting.

Stores corridor feedback and votes WITHOUT authentication (MVP).
NO impact on analytics — purely participatory.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
from collections import defaultdict
import json
import os
from pathlib import Path


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass
class Feedback:
    """User feedback on a corridor."""
    id: str
    corridor_id: str
    comment: str
    timestamp: str
    votes: int = 0
    
    @classmethod
    def create(cls, corridor_id: str, comment: str) -> "Feedback":
        """Create new feedback with auto-generated ID and timestamp."""
        import uuid
        return cls(
            id=str(uuid.uuid4())[:8],
            corridor_id=corridor_id,
            comment=comment,
            timestamp=datetime.now().isoformat(),
            votes=0
        )


@dataclass
class CorridorVotes:
    """Aggregated votes for a corridor."""
    corridor_id: str
    upvotes: int = 0
    downvotes: int = 0
    
    @property
    def net_votes(self) -> int:
        return self.upvotes - self.downvotes
    
    @property
    def support_level(self) -> str:
        """Human-readable support indicator."""
        net = self.net_votes
        if net > 10:
            return "Strong Support"
        elif net > 3:
            return "Community Support"
        elif net > 0:
            return "Some Support"
        elif net == 0:
            return "Neutral"
        elif net > -3:
            return "Some Concerns"
        else:
            return "Community Concerns"


# =============================================================================
# FEEDBACK SERVICE
# =============================================================================

class FeedbackService:
    """
    Manages community feedback and voting for corridors.
    
    Lightweight JSON file storage (no database required for MVP).
    """
    
    def __init__(self, data_dir: str = None):
        """
        Initialize feedback service.
        
        Args:
            data_dir: Directory for storing feedback data (default: ./data/feedback)
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent.parent / "data" / "feedback"
        
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.feedback_file = self.data_dir / "feedback.json"
        self.votes_file = self.data_dir / "votes.json"
        
        # In-memory caches (load from files)
        self._feedback: Dict[str, List[Feedback]] = defaultdict(list)  # corridor_id -> feedback list
        self._votes: Dict[str, CorridorVotes] = {}  # corridor_id -> votes
        
        self._load_data()
    
    def _load_data(self):
        """Load feedback and votes from files."""
        # Load feedback
        if self.feedback_file.exists():
            try:
                with open(self.feedback_file, 'r') as f:
                    data = json.load(f)
                    for corridor_id, items in data.items():
                        self._feedback[corridor_id] = [
                            Feedback(**item) for item in items
                        ]
            except (json.JSONDecodeError, KeyError):
                self._feedback = defaultdict(list)
        
        # Load votes
        if self.votes_file.exists():
            try:
                with open(self.votes_file, 'r') as f:
                    data = json.load(f)
                    for corridor_id, vote_data in data.items():
                        self._votes[corridor_id] = CorridorVotes(
                            corridor_id=corridor_id,
                            upvotes=vote_data.get('upvotes', 0),
                            downvotes=vote_data.get('downvotes', 0)
                        )
            except (json.JSONDecodeError, KeyError):
                self._votes = {}
    
    def _save_feedback(self):
        """Save feedback to file."""
        data = {
            corridor_id: [asdict(f) for f in feedback_list]
            for corridor_id, feedback_list in self._feedback.items()
        }
        with open(self.feedback_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _save_votes(self):
        """Save votes to file."""
        data = {
            corridor_id: {
                'upvotes': v.upvotes,
                'downvotes': v.downvotes
            }
            for corridor_id, v in self._votes.items()
        }
        with open(self.votes_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    # =========================================================================
    # FEEDBACK OPERATIONS
    # =========================================================================
    
    def add_feedback(self, corridor_id: str, comment: str) -> Feedback:
        """
        Add user feedback for a corridor.
        
        Args:
            corridor_id: Target corridor
            comment: User comment text
        
        Returns:
            Created Feedback object
        """
        feedback = Feedback.create(corridor_id, comment)
        self._feedback[corridor_id].append(feedback)
        self._save_feedback()
        return feedback
    
    def get_feedback(
        self, 
        corridor_id: str, 
        sort_by_votes: bool = True,
        limit: int = None
    ) -> List[Feedback]:
        """
        Get feedback for a corridor.
        
        Args:
            corridor_id: Target corridor
            sort_by_votes: Sort by vote count (default True)
            limit: Max results (default None = all)
        
        Returns:
            List of Feedback objects
        """
        feedback_list = self._feedback.get(corridor_id, [])
        
        if sort_by_votes:
            feedback_list = sorted(feedback_list, key=lambda f: f.votes, reverse=True)
        
        if limit:
            feedback_list = feedback_list[:limit]
        
        return feedback_list
    
    def vote_on_feedback(self, feedback_id: str, upvote: bool = True) -> Optional[Feedback]:
        """
        Vote on a specific feedback comment.
        
        Args:
            feedback_id: Target feedback ID
            upvote: True for upvote, False for downvote
        
        Returns:
            Updated Feedback or None if not found
        """
        for corridor_id, feedback_list in self._feedback.items():
            for feedback in feedback_list:
                if feedback.id == feedback_id:
                    feedback.votes += 1 if upvote else -1
                    self._save_feedback()
                    return feedback
        return None
    
    # =========================================================================
    # CORRIDOR VOTE OPERATIONS
    # =========================================================================
    
    def vote_corridor(self, corridor_id: str, upvote: bool = True) -> CorridorVotes:
        """
        Vote on a corridor (community support indicator).
        
        Args:
            corridor_id: Target corridor
            upvote: True for 👍, False for 👎
        
        Returns:
            Updated CorridorVotes
        """
        if corridor_id not in self._votes:
            self._votes[corridor_id] = CorridorVotes(corridor_id=corridor_id)
        
        votes = self._votes[corridor_id]
        if upvote:
            votes.upvotes += 1
        else:
            votes.downvotes += 1
        
        self._save_votes()
        return votes
    
    def get_corridor_votes(self, corridor_id: str) -> CorridorVotes:
        """
        Get votes for a corridor.
        
        Args:
            corridor_id: Target corridor
        
        Returns:
            CorridorVotes (creates empty if none exist)
        """
        if corridor_id not in self._votes:
            return CorridorVotes(corridor_id=corridor_id)
        return self._votes[corridor_id]
    
    # =========================================================================
    # COMBINED COMMUNITY DATA
    # =========================================================================
    
    def get_community_data(self, corridor_id: str, feedback_limit: int = 5) -> Dict[str, Any]:
        """
        Get all community data for a corridor.
        
        Args:
            corridor_id: Target corridor
            feedback_limit: Max feedback items to return
        
        Returns:
            Dict with votes and top feedback
        """
        votes = self.get_corridor_votes(corridor_id)
        feedback = self.get_feedback(corridor_id, sort_by_votes=True, limit=feedback_limit)
        
        return {
            "corridor_id": corridor_id,
            "votes": {
                "upvotes": votes.upvotes,
                "downvotes": votes.downvotes,
                "net": votes.net_votes,
                "support_level": votes.support_level
            },
            "feedback": [asdict(f) for f in feedback],
            "feedback_count": len(self._feedback.get(corridor_id, []))
        }


# Singleton instance
_feedback_service: Optional[FeedbackService] = None

def get_feedback_service() -> FeedbackService:
    """Get or create feedback service singleton."""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FeedbackService()
    return _feedback_service
