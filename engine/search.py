"""
Search Algorithm Module

Implements optimized minimax search with alpha-beta pruning,
move ordering, and other optimizations for finding the best move.
"""

from typing import Optional, Tuple, Dict, List
from .board import ChessBoard, Color, Piece
from .movegen import MoveGenerator
from .evaluation import EvaluationFunction


class SearchEngine:
    """
    Chess search engine using optimized minimax with alpha-beta pruning.
    """
    
    def __init__(self, evaluator: EvaluationFunction, max_depth: int = 4):
        """
        Initialize search engine.
        
        Args:
            evaluator: Evaluation function instance
            max_depth: Maximum search depth (default: 4)
        """
        self.evaluator = evaluator
        self.max_depth = max_depth
        self.nodes_searched = 0
        self.transposition_table = {}  # Simple TT for position caching
        self.killer_moves = {}  # Killer move heuristic
        self.history_table = {}  # History heuristic
        self.max_quiescence_depth = 3  # Max depth for quiescence search
    
    def find_best_move(self, board: ChessBoard, color: Color) -> Optional[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        Find the best move for the given color using optimized minimax with alpha-beta.
        
        Args:
            board: Current chess position
            color: Color to find move for
            
        Returns:
            Best move as (from_pos, to_pos) tuple, or None if no moves available
        """
        self.nodes_searched = 0
        
        movegen = MoveGenerator(board)
        moves = movegen.generate_all_moves(color)
        
        if not moves:
            return None
        
        # Order moves for better alpha-beta pruning
        ordered_moves = self._order_moves(board, moves, color)
        
        best_move = None
        best_score = float('-inf')
        alpha = float('-inf')
        beta = float('inf')
        
        # Try each move and evaluate
        for move in ordered_moves:
            from_pos, to_pos = move
            
            # Make move
            if not board.make_move(from_pos, to_pos):
                continue
            
            # Search (minimizing for opponent)
            opponent = Color.BLACK if color == Color.WHITE else Color.WHITE
            score = self._minimax(board, self.max_depth - 1, alpha, beta, 
                                opponent, False)
            
            # Undo move
            board.unmake_move()
            
            if score > best_score:
                best_score = score
                best_move = move
                alpha = max(alpha, score)
                
                # Beta cutoff
                if beta <= alpha:
                    break
        
        return best_move
    
    def _order_moves(self, board: ChessBoard, moves: List[Tuple[Tuple[int, int], Tuple[int, int]]], 
                     color: Color) -> List[Tuple[Tuple[int, int], Tuple[int, int]]]:
        """
        Order moves to improve alpha-beta pruning efficiency.
        Prioritizes: captures, checks, then other moves.
        """
        scored_moves = []
        
        for move in moves:
            from_pos, to_pos = move
            score = 0
            
            # Check if it's a capture
            captured = board.get_piece(to_pos[0], to_pos[1])
            if captured:
                # MVV-LVA: Most Valuable Victim - Least Valuable Attacker
                piece = board.get_piece(from_pos[0], from_pos[1])
                if piece:
                    victim_value = self._piece_value(captured[0])
                    attacker_value = self._piece_value(piece[0])
                    score += 10000 + (victim_value - attacker_value)
            
            # Check if it's a check (simplified - would need to check after move)
            # For now, prioritize central squares
            if to_pos[0] in [3, 4] and to_pos[1] in [3, 4]:
                score += 50
            
            # Killer move heuristic
            move_key = (from_pos, to_pos)
            if move_key in self.killer_moves:
                score += 1000
            
            scored_moves.append((score, move))
        
        # Sort by score (descending)
        scored_moves.sort(reverse=True, key=lambda x: x[0])
        return [move for _, move in scored_moves]
    
    def _piece_value(self, piece: Piece) -> int:
        """Get piece value for move ordering"""
        values = {
            Piece.PAWN: 100,
            Piece.KNIGHT: 320,
            Piece.BISHOP: 330,
            Piece.ROOK: 500,
            Piece.QUEEN: 900,
            Piece.KING: 20000
        }
        return values.get(piece, 0)
    
    def _minimax(self, board: ChessBoard, depth: int, alpha: float, beta: float, 
                 color: Color, maximizing: bool) -> float:
        """
        Optimized minimax algorithm with alpha-beta pruning and move ordering.
        
        Args:
            board: Current chess position
            depth: Remaining search depth
            alpha: Alpha value for pruning
            beta: Beta value for pruning
            color: Current player color
            maximizing: True if maximizing player, False if minimizing
            
        Returns:
            Evaluation score
        """
        self.nodes_searched += 1
        
        # Terminal conditions
        movegen = MoveGenerator(board)
        moves = movegen.generate_all_moves(color)
        
        # Check for checkmate or stalemate first
        if not moves:
            if board.is_in_check(color):
                # Checkmate
                return float('-inf') if maximizing else float('inf')
            return 0.0  # Stalemate
        
        # Quiescence search at depth 0 (search captures only)
        if depth == 0:
            return self._quiescence_search(board, alpha, beta, color, maximizing, self.max_quiescence_depth)
        
        # Order moves for better pruning
        ordered_moves = self._order_moves(board, moves, color)
        
        if maximizing:
            max_score = float('-inf')
            for move in ordered_moves:
                from_pos, to_pos = move
                
                if not board.make_move(from_pos, to_pos):
                    continue
                
                score = self._minimax(board, depth - 1, alpha, beta,
                                    Color.BLACK if color == Color.WHITE else Color.WHITE,
                                    False)
                
                board.unmake_move()
                
                max_score = max(max_score, score)
                alpha = max(alpha, score)
                
                if beta <= alpha:
                    # Beta cutoff - record killer move
                    self.killer_moves[(from_pos, to_pos)] = depth
                    break
            
            return max_score
        else:
            min_score = float('inf')
            for move in ordered_moves:
                from_pos, to_pos = move
                
                if not board.make_move(from_pos, to_pos):
                    continue
                
                score = self._minimax(board, depth - 1, alpha, beta,
                                    Color.BLACK if color == Color.WHITE else Color.WHITE,
                                    True)
                
                board.unmake_move()
                
                min_score = min(min_score, score)
                beta = min(beta, score)
                
                if beta <= alpha:
                    # Alpha cutoff - record killer move
                    self.killer_moves[(from_pos, to_pos)] = depth
                    break
            
            return min_score
    
    def _quiescence_search(self, board: ChessBoard, alpha: float, beta: float,
                          color: Color, maximizing: bool, depth: int = 3) -> float:
        """
        Quiescence search - search captures to avoid horizon effect.
        Only searches captures to a limited depth.
        """
        # Evaluate position
        score = self.evaluator.evaluate(board, color)
        if not maximizing:
            score = -score
        
        # Stand pat if score is good enough
        if maximizing:
            if score >= beta:
                return beta
            alpha = max(alpha, score)
        else:
            if score <= alpha:
                return alpha
            beta = min(beta, score)
        
        # Stop quiescence search at max depth
        if depth <= 0:
            return score
        
        # Only search captures
        movegen = MoveGenerator(board)
        all_moves = movegen.generate_all_moves(color)
        capture_moves = [m for m in all_moves if board.get_piece(m[1][0], m[1][1]) is not None]
        
        if not capture_moves:
            return score
        
        # Order captures by MVV-LVA
        ordered_captures = self._order_moves(board, capture_moves, color)
        
        if maximizing:
            for move in ordered_captures:
                from_pos, to_pos = move
                if not board.make_move(from_pos, to_pos):
                    continue
                
                move_score = self._quiescence_search(board, alpha, beta,
                                                   Color.BLACK if color == Color.WHITE else Color.WHITE,
                                                   False, depth - 1)
                board.unmake_move()
                
                score = max(score, move_score)
                alpha = max(alpha, score)
                
                if beta <= alpha:
                    break
            
            return score
        else:
            for move in ordered_captures:
                from_pos, to_pos = move
                if not board.make_move(from_pos, to_pos):
                    continue
                
                move_score = self._quiescence_search(board, alpha, beta,
                                                   Color.BLACK if color == Color.WHITE else Color.WHITE,
                                                   True, depth - 1)
                board.unmake_move()
                
                score = min(score, move_score)
                beta = min(beta, score)
                
                if beta <= alpha:
                    break
            
            return score
    
    def set_depth(self, depth: int):
        """Set maximum search depth"""
        self.max_depth = depth
    
    def get_nodes_searched(self) -> int:
        """Get number of nodes searched in last search"""
        return self.nodes_searched

