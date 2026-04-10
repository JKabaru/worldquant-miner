"""
Simple Alpha Generator for Streamlit Dashboard
Generates diverse alpha expressions without requiring external API calls.
"""

import random
import re
from typing import List, Dict, Optional

class SimpleAlphaGenerator:
    """Generate alpha expressions using predefined templates and operators."""
    
    def __init__(self):
        # Time series operators
        self.ts_operators = [
            'ts_mean', 'ts_std_dev', 'ts_zscore', 'ts_delta', 'ts_returns',
            'ts_rank', 'ts_max', 'ts_min', 'ts_product', 'ts_sum',
            'ts_corr', 'ts_covariance', 'ts_beta', 'ts_ir', 'ts_skewness',
            'ts_kurtosis', 'ts_pctl', 'ts_count', 'ts_decay_linear',
            'ts_decay_exp', 'ts_gap', 'ts_diff', 'ts_divide', 'ts_fama_macbeth'
        ]
        
        # Cross-sectional operators
        self.cs_operators = [
            'rank', 'cs_rank', 'cs_zscore', 'cs_divide', 'cs_subtract',
            'cs_add', 'cs_product', 'cs_mean', 'cs_std_dev', 'cs_max',
            'cs_min', 'cs_sum', 'cs_count', 'cs_decay_linear'
        ]
        
        # Basic data fields
        self.price_fields = ['close', 'open', 'high', 'low', 'vwap', 'returns']
        self.volume_fields = ['volume', 'value', 'turnover', 'amt']
        self.fundamental_fields = [
            'market_cap', 'pe_ratio', 'pb_ratio', 'ps_ratio', 'pcf_ratio',
            'dividend_yield', 'roe', 'roa', 'gross_margin', 'operating_margin',
            'net_margin', 'asset_turnover', 'inventory_turnover', 'receivables_turnover'
        ]
        
        # Lookback periods
        self.short_periods = [5, 10, 12, 15, 20]
        self.medium_periods = [21, 30, 42, 60, 63]
        self.long_periods = [90, 120, 126, 180, 250, 252]
        
        # Neutralization options
        self.neutralizations = ['industry', 'subindustry', 'market', 'sector']
        
        # Strategy templates
        self.templates = {
            'mean_reversion': self._generate_mean_reversion,
            'momentum': self._generate_momentum,
            'volume_price': self._generate_volume_price,
            'volatility': self._generate_volatility,
            'fundamental': self._generate_fundamental,
            'combination': self._generate_combination
        }
    
    def generate_single_alpha(self, strategy_type: str = 'random_mix', complexity: int = 3) -> str:
        """
        Generate a single alpha expression.
        
        Args:
            strategy_type: Type of strategy ('mean_reversion', 'momentum', etc.)
            complexity: Complexity level (1-5)
        
        Returns:
            Alpha expression string
        """
        if strategy_type == 'random_mix':
            strategy_type = random.choice(list(self.templates.keys()))
        
        if strategy_type in self.templates:
            return self.templates[strategy_type](complexity)
        else:
            return self._generate_mean_reversion(complexity)
    
    def _generate_mean_reversion(self, complexity: int) -> str:
        """Generate mean reversion strategy."""
        period = random.choice(self.short_periods + self.medium_periods)
        field = random.choice(self.price_fields)
        
        if complexity <= 2:
            # Simple: -ts_zscore(field, period)
            expr = f"-ts_zscore({field}, {period})"
        elif complexity <= 4:
            # Medium: rank(-ts_delta(ts_mean(field, period), 1))
            ts_period = random.choice(self.medium_periods)
            expr = f"rank(-ts_delta(ts_mean({field}, {ts_period}), 1))"
        else:
            # Complex: Combine multiple mean reversion signals
            period1 = random.choice(self.short_periods)
            period2 = random.choice(self.medium_periods)
            field2 = random.choice([f for f in self.price_fields if f != field])
            expr = f"ts_zscore(-ts_delta({field}, 1), {period1}) + ts_zscore(-ts_delta({field2}, 1), {period2})"
        
        return self._add_neutralization(expr, complexity)
    
    def _generate_momentum(self, complexity: int) -> str:
        """Generate momentum strategy."""
        period = random.choice(self.medium_periods + self.long_periods)
        field = random.choice(self.price_fields)
        
        if complexity <= 2:
            # Simple: ts_returns(field, period)
            expr = f"ts_returns({field}, {period})"
        elif complexity <= 4:
            # Medium: rank(ts_delta(field, period)) / ts_std_dev(field, period)
            expr = f"rank(ts_delta({field}, {period})) / (ts_std_dev({field}, {period}) + 0.001)"
        else:
            # Complex: Multi-period momentum
            period1 = random.choice(self.medium_periods)
            period2 = random.choice(self.long_periods)
            expr = f"(ts_returns({field}, {period1}) * 0.6 + ts_returns({field}, {period2}) * 0.4)"
        
        return self._add_neutralization(expr, complexity)
    
    def _generate_volume_price(self, complexity: int) -> str:
        """Generate volume-price relationship strategy."""
        period = random.choice(self.medium_periods)
        price_field = random.choice(self.price_fields)
        volume_field = random.choice(self.volume_fields)
        
        if complexity <= 2:
            # Simple: rank(ts_corr(price, volume, period))
            expr = f"rank(ts_corr({price_field}, {volume_field}, {period}))"
        elif complexity <= 4:
            # Medium: Volume-weighted price momentum
            expr = f"rank(ts_sum({price_field} * {volume_field}, {period}) / (ts_sum({volume_field}, {period}) + 0.001))"
        else:
            # Complex: Volume-price divergence
            period1 = random.choice(self.short_periods)
            period2 = random.choice(self.medium_periods)
            expr = f"ts_zscore(ts_corr({price_field}, {volume_field}, {period1}), {period2})"
        
        return self._add_neutralization(expr, complexity)
    
    def _generate_volatility(self, complexity: int) -> str:
        """Generate volatility-based strategy."""
        period = random.choice(self.medium_periods)
        field = random.choice(self.price_fields)
        
        if complexity <= 2:
            # Simple: -ts_std_dev(field, period)
            expr = f"-ts_std_dev({field}, {period})"
        elif complexity <= 4:
            # Medium: Volatility-adjusted returns
            ret_period = random.choice(self.short_periods)
            expr = f"ts_returns({field}, {ret_period}) / (ts_std_dev({field}, {period}) + 0.001)"
        else:
            # Complex: Volatility regime detection
            short_vol = random.choice(self.short_periods)
            long_vol = random.choice(self.long_periods)
            expr = f"rank(ts_std_dev({field}, {short_vol}) / (ts_std_dev({field}, {long_vol}) + 0.001))"
        
        return self._add_neutralization(expr, complexity)
    
    def _generate_fundamental(self, complexity: int) -> str:
        """Generate fundamental-based strategy."""
        field = random.choice(self.fundamental_fields)
        period = random.choice(self.medium_periods)
        
        if complexity <= 2:
            # Simple: rank(field)
            expr = f"rank({field})"
        elif complexity <= 4:
            # Medium: Fundamental momentum
            expr = f"rank(ts_delta({field}, {period}))"
        else:
            # Complex: Fundamental ratio with price
            price_field = random.choice(self.price_fields)
            expr = f"rank({field}) * ts_zscore({price_field}, {period})"
        
        return self._add_neutralization(expr, complexity)
    
    def _generate_combination(self, complexity: int) -> str:
        """Generate combination of multiple strategies."""
        # Generate 2-3 sub-expressions
        num_components = min(complexity, 3)
        components = []
        
        strategies = random.sample(list(self.templates.keys()), num_components)
        for strategy in strategies:
            if strategy != 'combination':  # Avoid recursion
                comp = self.templates[strategy](min(complexity - 1, 3))
                components.append(f"({comp})")
        
        if len(components) >= 2:
            # Combine with weights
            if len(components) == 2:
                expr = f"{components[0]} * 0.5 + {components[1]} * 0.5"
            else:
                weight = 1.0 / len(components)
                expr = " + ".join([f"{c} * {weight:.2f}" for c in components])
        else:
            expr = components[0] if components else self._generate_mean_reversion(complexity)
        
        return self._add_neutralization(expr, complexity)
    
    def _add_neutralization(self, expr: str, complexity: int) -> str:
        """Optionally add neutralization to expression."""
        if complexity >= 3 and random.random() > 0.5:
            neutralization = random.choice(self.neutralizations)
            # Wrap with group operation
            expr = f"group_zscore({expr}, {neutralization})"
        return expr
    
    def generate_batch(self, count: int = 5, strategy_type: str = 'random_mix') -> List[str]:
        """Generate a batch of alpha expressions."""
        alphas = []
        for i in range(count):
            complexity = random.randint(2, 5)
            alpha = self.generate_single_alpha(strategy_type, complexity)
            alphas.append(alpha)
        return alphas
    
    def validate_expression(self, expr: str) -> bool:
        """Basic validation of alpha expression syntax."""
        if not expr or len(expr) < 5:
            return False
        
        # Check for balanced parentheses
        if expr.count('(') != expr.count(')'):
            return False
        
        # Check for basic operator patterns
        valid_operators = self.ts_operators + self.cs_operators + ['group_zscore', 'rank']
        has_operator = any(op in expr for op in valid_operators)
        
        return has_operator


# Convenience function for Streamlit
def generate_alpha(strategy: str = 'random_mix', complexity: int = 3) -> str:
    """Generate a single alpha expression."""
    generator = SimpleAlphaGenerator()
    return generator.generate_single_alpha(strategy, complexity)


if __name__ == '__main__':
    # Test generation
    gen = SimpleAlphaGenerator()
    
    print("Testing Alpha Generation:")
    print("=" * 60)
    
    for strategy in ['mean_reversion', 'momentum', 'volume_price', 'volatility', 'combination']:
        alpha = gen.generate_single_alpha(strategy, complexity=3)
        print(f"\n{strategy.upper()}:")
        print(f"  {alpha}")
        print(f"  Valid: {gen.validate_expression(alpha)}")
    
    print("\n" + "=" * 60)
    print("\nRandom Mix Examples:")
    for i in range(5):
        alpha = gen.generate_single_alpha('random_mix', complexity=random.randint(2, 5))
        print(f"{i+1}. {alpha}")
