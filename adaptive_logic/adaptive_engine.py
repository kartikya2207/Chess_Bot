"""
Adaptive Engine Module

Integrates adaptive learning, style analysis, and weight adaptation
into the chess engine workflow.
"""

from typing import List, Dict, Tuple
from engine.board import ChessBoard, Color
from engine.evaluation import EvaluationFunction
from engine.search import SearchEngine
from player_profile.player_profile import PlayerProfile
from player_profile.profile_manager import PlayerProfileManager
from .style_analyzer import StyleAnalyzer
from .weight_adapter import WeightAdapter


class AdaptiveEngine:
    """
    Main adaptive engine that combines chess engine with learning capabilities.
    """
    
    def __init__(self, player_id: str, search_depth: int = 4, profiles_dir: str = "profiles"):
        """
        Initialize adaptive engine.
        
        Args:
            player_id: Unique identifier for the player
            search_depth: Maximum search depth for engine
            profiles_dir: Directory for storing player profiles
        """
        self.player_id = player_id
        
        # Initialize components
        self.evaluator = EvaluationFunction()
        self.search_engine = SearchEngine(self.evaluator, search_depth)
        self.profile_manager = PlayerProfileManager(profiles_dir)
        self.style_analyzer = StyleAnalyzer()
        self.weight_adapter = WeightAdapter(self.evaluator)
        
        # Load or create player profile
        # Try to load from database first, then JSON
        from player_profile.database import PlayerDatabase
        db = PlayerDatabase()
        db_profile = db.get_profile(player_id)
        
        if db_profile:
            # Load from database
            self.profile = PlayerProfile.from_database_dict(db_profile)
        else:
            # Load or create from JSON
            self.profile = self.profile_manager.get_or_create_profile(player_id)
        
        # Move history for current game
        self.current_game_moves: List[Dict] = []
        self.board = ChessBoard()
        
        # Apply initial adaptation
        self.update_adaptation()
    
    def make_player_move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """
        Record and make a player move.
        
        Args:
            from_pos: Move source square
            to_pos: Move destination square
            
        Returns:
            True if move is legal, False otherwise
        """
        if self.board.turn != Color.WHITE:  # Assume player is white
            return False
        
        # Validate move first (without making it)
        if not self.board.is_legal_move(from_pos, to_pos):
            return False
        
        # Analyze move before making it (on current board state)
        move_analysis = self.style_analyzer.analyze_move(self.board, from_pos, to_pos, Color.WHITE)
        
        # Make the move (make_move also validates, but we already checked)
        if not self.board.make_move(from_pos, to_pos):
            return False
        
        # Store move analysis
        move_analysis['color'] = 'white'
        move_analysis['from'] = from_pos
        move_analysis['to'] = to_pos
        self.current_game_moves.append(move_analysis)
        self.profile.update_stats(move_analysis)
        
        # Update profile periodically
        if len(self.current_game_moves) % 5 == 0:
            self._update_profile_from_moves()
            self.update_adaptation()
        
        return True
    
    def make_engine_move(self) -> Tuple[Tuple[int, int], Tuple[int, int]]:
        """
        Generate and make engine move.
        
        Returns:
            (from_pos, to_pos) tuple of engine move
        """
        if self.board.turn != Color.BLACK:  # Assume engine is black
            return None
        
        # Find best move
        best_move = self.search_engine.find_best_move(self.board, Color.BLACK)
        
        if best_move:
            from_pos, to_pos = best_move
            # Make the move - verify it succeeds
            if self.board.make_move(from_pos, to_pos):
                return best_move
            else:
                # Move failed - this shouldn't happen, but log it
                print(f"Warning: Engine move {from_pos} -> {to_pos} failed!")
                return None
        
        return None
    
    def update_adaptation(self):
        """Update evaluation weights based on current player profile"""
        self.weight_adapter.apply_adaptation(self.profile)
    
    def _update_profile_from_moves(self):
        """Update profile statistics from recent moves"""
        if len(self.current_game_moves) >= 5:
            recent_moves = self.current_game_moves[-10:]  # Last 10 moves
            self.profile = self.style_analyzer.update_profile_from_moves(self.profile, recent_moves)
    
    def start_new_game(self):
        """Start a new game"""
        self.board = ChessBoard()
        self.current_game_moves = []
        self.profile.record_game_start()
        self.profile_manager.save_profile(self.profile)
        self.update_adaptation()
    
    def end_game(self):
        """End current game and save profile to database and JSON"""
        if len(self.current_game_moves) >= 5:
            self.profile = self.style_analyzer.update_profile_from_moves(self.profile, self.current_game_moves)
        
        # Save to JSON (existing method)
        self.profile_manager.save_profile(self.profile)
        
        # Also save to database
        from player_profile.database import PlayerDatabase
        db = PlayerDatabase()
        
        # Get database representation
        db_data = self.profile.get_database_dict()
        db_data['player_id'] = self.player_id
        
        # Update database
        existing = db.get_profile(self.player_id)
        if existing:
            # Calculate game statistics for this game
            game_stats = {
                'aggressive': db_data['aggressive'],
                'defensive': db_data['defensive'],
                'positional': db_data['positional'],
                'tactical': db_data['tactical'],
                'endgame': db_data.get('endgame', 50.0),
                'blunder_rate': db_data['blunder_rate'],
                'games_played': 1,  # Increment by 1
                'moves_recorded': len(self.current_game_moves)
            }
            db.update_after_game(self.player_id, game_stats)
        else:
            # Create new profile
            db.create_profile(self.player_id, self.profile.player_name, {
                'aggressive': db_data['aggressive'],
                'defensive': db_data['defensive'],
                'positional': db_data['positional'],
                'tactical': db_data['tactical'],
                'endgame': db_data.get('endgame', 50.0),
                'mistake_control': db_data['mistake_control'],
                'blunder_rate': db_data['blunder_rate']
            })
        
        self.current_game_moves = []
    
    def get_player_style_info(self) -> Dict:
        """Get current player style information"""
        return {
            'primary_style': self.profile.get_primary_style(),
            'style_percentages': self.profile.get_style_percentages(),
            'adaptation_explanation': self.weight_adapter.get_adaptation_explanation(self.profile)
        }
    
    def set_search_depth(self, depth: int):
        """Set engine search depth"""
        self.search_engine.set_depth(depth)

