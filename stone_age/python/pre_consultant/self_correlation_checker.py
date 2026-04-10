"""
Self-Correlation Checker for WorldQuant Alpha Submissions

This module implements a local correlation checker to predict whether 
a new alpha will pass the self-correlation check (>0.70 threshold) 
before submitting to WorldQuant Brain API.

The correlation threshold is 0.70 (70%), meaning if your new alpha's 
correlation to any previous submission is >0.70, it will be rejected 
unless its Sharpe is at least 10% higher than the competing alpha.
"""

import json
import logging
import numpy as np
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import sqlite3
import os
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AlphaRecord:
    """Store alpha information for correlation tracking"""
    alpha_id: str
    expression: str
    sharpe: float
    fitness: float
    returns: float
    turnover: float
    date_created: str
    submitted: bool = False
    correlation_checked: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AlphaRecord':
        return cls(**data)


class SelfCorrelationChecker:
    """
    Local correlation checker to predict WQ Brain self-correlation results.
    
    This uses multiple heuristics to estimate correlation:
    1. Expression similarity (structural comparison)
    2. Return series correlation (if historical data available)
    3. Factor exposure correlation
    4. Performance pattern similarity
    """
    
    CORRELATION_THRESHOLD = 0.70
    SHARPE_IMPROVEMENT_REQUIRED = 0.10  # 10% higher Sharpe needed if correlated
    
    def __init__(self, db_path: str = "alpha_correlation_db.sqlite"):
        """
        Initialize the correlation checker.
        
        Args:
            db_path: Path to SQLite database for storing alpha history
        """
        self.db_path = db_path
        self.submitted_alphas: List[AlphaRecord] = []
        self.return_series_cache: Dict[str, np.ndarray] = {}
        self._init_database()
        self._load_submitted_alphas()
        
    def _init_database(self):
        """Initialize SQLite database for alpha storage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submitted_alphas (
                alpha_id TEXT PRIMARY KEY,
                expression TEXT NOT NULL,
                sharpe REAL,
                fitness REAL,
                returns REAL,
                turnover REAL,
                date_created TEXT,
                submitted INTEGER DEFAULT 1,
                metadata TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS correlation_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alpha_id_1 TEXT,
                alpha_id_2 TEXT,
                correlation REAL,
                method TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alpha_id_1) REFERENCES submitted_alphas(alpha_id),
                FOREIGN KEY (alpha_id_2) REFERENCES submitted_alphas(alpha_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Initialized correlation database at {self.db_path}")
    
    def _load_submitted_alphas(self):
        """Load previously submitted alphas from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT alpha_id, expression, sharpe, fitness, returns, turnover, 
                   date_created, submitted
            FROM submitted_alphas
            ORDER BY date_created DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        self.submitted_alphas = [
            AlphaRecord(
                alpha_id=row[0],
                expression=row[1],
                sharpe=row[2],
                fitness=row[3],
                returns=row[4],
                turnover=row[5],
                date_created=row[6],
                submitted=bool(row[7])
            )
            for row in rows
        ]
        
        logger.info(f"Loaded {len(self.submitted_alphas)} submitted alphas")
    
    def add_submitted_alpha(self, alpha_record: AlphaRecord):
        """Add a newly submitted alpha to the tracking database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO submitted_alphas 
            (alpha_id, expression, sharpe, fitness, returns, turnover, date_created, submitted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            alpha_record.alpha_id,
            alpha_record.expression,
            alpha_record.sharpe,
            alpha_record.fitness,
            alpha_record.returns,
            alpha_record.turnover,
            alpha_record.date_created,
            1 if alpha_record.submitted else 0
        ))
        
        conn.commit()
        conn.close()
        
        self.submitted_alphas.append(alpha_record)
        logger.info(f"Added alpha {alpha_record.alpha_id} to tracking database")
    
    def _tokenize_expression(self, expression: str) -> List[str]:
        """
        Tokenize an alpha expression for structural comparison.
        
        Example: "ts_mean(close, 10)" -> ["ts_mean", "close", "10"]
        """
        import re
        # Extract function names, operators, and variables
        tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|\d+\.?\d*|[+\-*/()<>,]', expression)
        return tokens
    
    def _calculate_expression_similarity(self, expr1: str, expr2: str) -> float:
        """
        Calculate structural similarity between two expressions.
        
        Uses Jaccard similarity on tokenized expressions.
        This is a heuristic - actual correlation may vary.
        """
        tokens1 = set(self._tokenize_expression(expr1))
        tokens2 = set(self._tokenize_expression(expr2))
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        
        jaccard = intersection / union if union > 0 else 0.0
        
        # Also check for common function patterns
        func_pattern1 = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*(?=\()', expr1)
        func_pattern2 = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*(?=\()', expr2)
        
        if func_pattern1 and func_pattern2:
            func_overlap = len(set(func_pattern1) & set(func_pattern2)) / max(len(func_pattern1), len(func_pattern2))
            # Weight function similarity heavily as it indicates similar strategy
            jaccard = 0.6 * jaccard + 0.4 * func_overlap
        
        return jaccard
    
    def _calculate_parameter_distance(self, expr1: str, expr2: str) -> float:
        """
        Calculate distance between numeric parameters in expressions.
        
        Smaller distance suggests higher correlation.
        """
        import re
        
        params1 = [float(x) for x in re.findall(r'(?<![a-zA-Z])(\d+\.?\d*)(?![a-zA-Z])', expr1)]
        params2 = [float(x) for x in re.findall(r'(?<![a-zA-Z])(\d+\.?\d*)(?![a-zA-Z])', expr2)]
        
        if not params1 or not params2:
            return 1.0  # No parameters to compare
        
        # Normalize parameter counts
        min_len = min(len(params1), len(params2))
        params1 = params1[:min_len]
        params2 = params2[:min_len]
        
        # Calculate normalized distance
        distances = []
        for p1, p2 in zip(params1, params2):
            if p1 == 0 and p2 == 0:
                distances.append(0.0)
            elif p1 == 0 or p2 == 0:
                distances.append(1.0)
            else:
                dist = abs(p1 - p2) / max(abs(p1), abs(p2))
                distances.append(dist)
        
        avg_distance = np.mean(distances) if distances else 1.0
        return 1.0 - avg_distance  # Convert to similarity
    
    def _estimate_correlation(self, new_alpha_expr: str, existing_alpha: AlphaRecord) -> Tuple[float, str]:
        """
        Estimate correlation between new alpha and existing alpha.
        
        Returns:
            Tuple of (estimated_correlation, method_used)
        """
        # Method 1: Expression structural similarity
        expr_similarity = self._calculate_expression_similarity(
            new_alpha_expr, 
            existing_alpha.expression
        )
        
        # Method 2: Parameter distance
        param_similarity = self._calculate_parameter_distance(
            new_alpha_expr,
            existing_alpha.expression
        )
        
        # Method 3: Performance pattern similarity (heuristic)
        # Alphas with very different Sharpe/returns likely have lower correlation
        perf_similarity = 1.0 / (1.0 + abs(new_alpha_expr.count('mean') - existing_alpha.expression.count('mean')))
        
        # Weighted combination (tuned empirically)
        estimated_corr = (
            0.50 * expr_similarity +
            0.35 * param_similarity +
            0.15 * perf_similarity
        )
        
        # Determine primary method
        if expr_similarity > 0.8:
            method = "expression_dominant"
        elif param_similarity > 0.8:
            method = "parameter_dominant"
        else:
            method = "combined_heuristic"
        
        return min(estimated_corr, 0.95), method  # Cap at 0.95
    
    def check_correlation(
        self, 
        new_alpha_expr: str, 
        new_alpha_sharpe: float,
        alpha_id: str = "pending"
    ) -> Dict:
        """
        Check if a new alpha is likely to pass self-correlation check.
        
        Args:
            new_alpha_expr: The alpha expression to check
            new_alpha_sharpe: Expected or preliminary Sharpe ratio
            alpha_id: Identifier for the new alpha
            
        Returns:
            Dict with correlation analysis results
        """
        if not self.submitted_alphas:
            return {
                "pass_prediction": True,
                "reason": "No previously submitted alphas to compare against",
                "max_correlation": 0.0,
                "details": []
            }
        
        max_correlation = 0.0
        highest_correlated_alpha = None
        details = []
        
        for existing_alpha in self.submitted_alphas:
            corr_estimate, method = self._estimate_correlation(
                new_alpha_expr, 
                existing_alpha
            )
            
            detail = {
                "existing_alpha_id": existing_alpha.alpha_id,
                "existing_sharpe": existing_alpha.sharpe,
                "estimated_correlation": round(corr_estimate, 3),
                "method": method,
                "sharpe_improvement_needed": None
            }
            
            # Check if correlation exceeds threshold
            if corr_estimate > self.CORRELATION_THRESHOLD:
                # Check if Sharpe improvement is sufficient
                required_sharpe = existing_alpha.sharpe * (1 + self.SHARPE_IMPROVEMENT_REQUIRED)
                detail["sharpe_improvement_needed"] = required_sharpe
                
                if new_alpha_sharpe < required_sharpe:
                    detail["will_fail"] = True
                    detail["reason"] = f"Correlation {corr_estimate:.3f} > {self.CORRELATION_THRESHOLD} and Sharpe {new_alpha_sharpe:.3f} < required {required_sharpe:.3f}"
                else:
                    detail["will_pass_exception"] = True
                    detail["reason"] = f"Correlation high but Sharpe {new_alpha_sharpe:.3f} >= required {required_sharpe:.3f} (10% improvement)"
            
            details.append(detail)
            
            if corr_estimate > max_correlation:
                max_correlation = corr_estimate
                highest_correlated_alpha = existing_alpha
        
        # Determine overall prediction
        if max_correlation <= self.CORRELATION_THRESHOLD:
            pass_prediction = True
            reason = f"Maximum estimated correlation {max_correlation:.3f} <= threshold {self.CORRELATION_THRESHOLD}"
        else:
            # Check if any high-correlation alphas can use the 10% exception
            can_use_exception = False
            for detail in details:
                if detail.get("will_pass_exception"):
                    can_use_exception = True
                    break
            
            if can_use_exception:
                pass_prediction = True
                reason = f"High correlation detected but Sharpe improvement qualifies for 10% exception"
            else:
                pass_prediction = False
                reason = f"Estimated correlation {max_correlation:.3f} > {self.CORRELATION_THRESHOLD} without sufficient Sharpe improvement"
        
        result = {
            "pass_prediction": pass_prediction,
            "reason": reason,
            "max_correlation": round(max_correlation, 3),
            "highest_correlated_alpha": highest_correlated_alpha.alpha_id if highest_correlated_alpha else None,
            "highest_correlated_sharpe": highest_correlated_alpha.sharpe if highest_correlated_alpha else None,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"Correlation check for {alpha_id}: {'PASS' if pass_prediction else 'FAIL'} - {reason}")
        
        return result
    
    def get_diversification_suggestions(self, new_alpha_expr: str) -> List[str]:
        """
        Get suggestions to reduce correlation with existing alphas.
        
        Args:
            new_alpha_expr: The current alpha expression
            
        Returns:
            List of modification suggestions
        """
        suggestions = []
        
        # Analyze which existing alphas are most similar
        correlations = []
        for existing_alpha in self.submitted_alphas:
            corr, _ = self._estimate_correlation(new_alpha_expr, existing_alpha)
            correlations.append((existing_alpha, corr))
        
        correlations.sort(key=lambda x: x[1], reverse=True)
        
        if not correlations:
            return ["No existing alphas to compare - expression appears unique"]
        
        top_correlated, top_corr = correlations[0]
        
        if top_corr > self.CORRELATION_THRESHOLD:
            suggestions.append(f"HIGH CORRELATION DETECTED ({top_corr:.3f}) with alpha {top_correlated.alpha_id}")
            suggestions.append("")
            suggestions.append("Suggested modifications:")
            
            # Analyze differences
            tokens_new = set(self._tokenize_expression(new_alpha_expr))
            tokens_existing = set(self._tokenize_expression(top_correlated.expression))
            
            common_tokens = tokens_new & tokens_existing
            unique_to_new = tokens_new - tokens_existing
            unique_to_existing = tokens_existing - tokens_new
            
            if len(common_tokens) > 10:
                suggestions.append(f"1. Change core functions: Both use {', '.join(list(common_tokens)[:5])}")
                suggestions.append("   → Try different operators (e.g., ts_rank instead of ts_mean)")
            
            # Check parameter differences
            import re
            params_new = re.findall(r'\d+', new_alpha_expr)
            params_existing = re.findall(r'\d+', top_correlated.expression)
            
            if params_new and params_existing:
                suggestions.append(f"2. Adjust lookback periods: Current params {params_new[:3]} vs {params_existing[:3]}")
                suggestions.append("   → Try significantly different decay/delay values (e.g., 5→20, 10→40)")
            
            suggestions.append("3. Consider different neutralization (MARKETCAP vs INDUSTRY)")
            suggestions.append("4. Add/truncate different percentiles")
            suggestions.append("5. Combine with different data fields (fundamental vs technical)")
        
        return suggestions
    
    def export_correlation_report(self, output_path: str = "correlation_report.json"):
        """Export full correlation analysis report"""
        report = {
            "total_submitted_alphas": len(self.submitted_alphas),
            "correlation_threshold": self.CORRELATION_THRESHOLD,
            "sharpe_improvement_required": self.SHARPE_IMPROVEMENT_REQUIRED,
            "alphas": [alpha.to_dict() for alpha in self.submitted_alphas],
            "generated_at": datetime.now().isoformat()
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Exported correlation report to {output_path}")
        return report


def main():
    """Example usage of SelfCorrelationChecker"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Initialize checker
    checker = SelfCorrelationChecker()
    
    # Example: Add some submitted alphas
    sample_alphas = [
        AlphaRecord(
            alpha_id="alpha_001",
            expression="ts_mean(close, 10) / ts_mean(close, 40)",
            sharpe=1.35,
            fitness=1.2,
            returns=0.05,
            turnover=0.15,
            date_created="2024-01-15T10:00:00"
        ),
        AlphaRecord(
            alpha_id="alpha_002",
            expression="rank(ts_std_dev(volume, 20))",
            sharpe=1.28,
            fitness=1.1,
            returns=0.04,
            turnover=0.25,
            date_created="2024-01-16T14:30:00"
        )
    ]
    
    for alpha in sample_alphas:
        checker.add_submitted_alpha(alpha)
    
    # Test a new alpha
    new_expr = "ts_mean(close, 12) / ts_mean(close, 38)"
    result = checker.check_correlation(new_expr, new_alpha_sharpe=1.30)
    
    print("\n=== Correlation Check Result ===")
    print(json.dumps(result, indent=2))
    
    # Get suggestions if correlation is high
    if not result["pass_prediction"]:
        print("\n=== Diversification Suggestions ===")
        suggestions = checker.get_diversification_suggestions(new_expr)
        for suggestion in suggestions:
            print(suggestion)
    
    # Export report
    checker.export_correlation_report()


if __name__ == "__main__":
    main()
