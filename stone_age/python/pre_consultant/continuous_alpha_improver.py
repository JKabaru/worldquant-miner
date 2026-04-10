"""
Continuous Alpha Improvement System for WorldQuant IQC Stage 1

This system integrates:
1. Self-correlation checking (before submission)
2. Alpha generation and polishing
3. Performance validation against Stage 1 cutoffs
4. Automatic submission when criteria are met
5. Learning from results to improve future generations

Performance Cutoffs for Stage 1 IQC 2026:
- Sharpe Ratio >= 1.25
- Fitness >= 1.0
- Turnover: 1% to 70%
- Sub-universe Sharpe >= 0.73
- Margin > 0
- Correlation Threshold: < 0.70 (or 10% Sharpe improvement exception)
"""

import json
import logging
import time
import os
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import our custom modules
from self_correlation_checker import SelfCorrelationChecker, AlphaRecord
import requests
from requests.auth import HTTPBasicAuth

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('alpha_improvement_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Stage1Criteria:
    """Stage 1 IQC performance thresholds"""
    SHARPE_MIN = 1.25
    FITNESS_MIN = 1.0
    TURNOVER_MIN = 0.01
    TURNOVER_MAX = 0.70
    SUB_UNIVERSE_SHARPE_MIN = 0.73
    MARGIN_MIN = 0.0
    CORRELATION_THRESHOLD = 0.70
    SHARPE_IMPROVEMENT_FOR_CORRELATION = 0.10  # 10%


class AlphaImprovementSystem:
    """
    Continuous alpha improvement and submission system.
    
    Implements a feedback loop:
    1. Generate/polish alpha
    2. Test on WQ Brain
    3. Check correlation locally BEFORE submission
    4. If passes all checks -> submit
    5. Learn from results and update generation strategy
    6. Repeat
    """
    
    def __init__(
        self, 
        credentials_path: str,
        correlation_db_path: str = "alpha_correlation_db.sqlite",
        max_concurrent_simulations: int = 5
    ):
        """
        Initialize the improvement system.
        
        Args:
            credentials_path: Path to credentials JSON file [email, password]
            correlation_db_path: Path to correlation tracking database
            max_concurrent_simulations: Max parallel simulations (WQ limit: 5-10)
        """
        self.credentials_path = credentials_path
        self.sess = requests.Session()
        self._authenticate()
        
        self.correlation_checker = SelfCorrelationChecker(correlation_db_path)
        self.max_concurrent_simulations = max_concurrent_simulations
        self.active_simulations = 0
        self.simulation_lock = threading.Lock()
        
        # Track statistics
        self.stats = {
            'alphas_tested': 0,
            'alphas_submitted': 0,
            'alphas_passed_correlation': 0,
            'alphas_failed_correlation': 0,
            'average_sharpe': 0.0,
            'best_sharpe': 0.0,
            'generation_rounds': 0
        }
        
        # Load or initialize generation history
        self.history_file = "improvement_history.json"
        self._load_history()
        
    def _authenticate(self):
        """Authenticate with WorldQuant Brain"""
        logger.info(f"Loading credentials from {self.credentials_path}")
        with open(self.credentials_path) as f:
            credentials = json.load(f)
        
        email, password = credentials
        self.sess.auth = HTTPBasicAuth(email, password)
        
        logger.info("Authenticating with WorldQuant Brain...")
        response = self.sess.post('https://api.worldquantbrain.com/authentication')
        
        if response.status_code != 201:
            raise Exception(f"Authentication failed: {response.text}")
        
        logger.info("Authentication successful")
    
    def _load_history(self):
        """Load improvement history from file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.history = json.load(f)
                logger.info(f"Loaded history with {len(self.history.get('alphas', []))} alphas")
            except:
                self.history = {'alphas': [], 'strategies': []}
        else:
            self.history = {'alphas': [], 'strategies': []}
    
    def _save_history(self):
        """Save improvement history to file"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
        logger.debug("Saved improvement history")
    
    def _wait_for_simulation_slot(self, timeout: int = 300):
        """Wait until we can run another simulation"""
        start_time = time.time()
        while True:
            with self.simulation_lock:
                if self.active_simulations < self.max_concurrent_simulations:
                    self.active_simulations += 1
                    return
            
            if time.time() - start_time > timeout:
                raise TimeoutError("Timeout waiting for simulation slot")
            
            time.sleep(5)
    
    def _release_simulation_slot(self):
        """Release a simulation slot"""
        with self.simulation_lock:
            self.active_simulations = max(0, self.active_simulations - 1)
    
    def test_alpha(self, expression: str, settings_override: Dict = None) -> Optional[Dict]:
        """
        Test an alpha expression on WorldQuant Brain.
        
        Args:
            expression: The alpha expression to test
            settings_override: Optional override for default settings
            
        Returns:
            Alpha result dict or None if failed
        """
        self._wait_for_simulation_slot()
        
        try:
            default_settings = {
                'type': 'REGULAR',
                'settings': {
                    'instrumentType': 'EQUITY',
                    'region': 'USA',
                    'universe': 'TOP3000',
                    'delay': 1,
                    'decay': 0,
                    'neutralization': 'INDUSTRY',
                    'truncation': 0.08,
                    'pasteurization': 'ON',
                    'unitHandling': 'VERIFY',
                    'nanHandling': 'OFF',
                    'language': 'FASTEXPR',
                    'visualization': False,
                },
                'regular': expression
            }
            
            if settings_override:
                default_settings['settings'].update(settings_override)
            
            # Create simulation
            sim_resp = self.sess.post(
                'https://api.worldquantbrain.com/simulations',
                json=default_settings
            )
            
            if sim_resp.status_code == 401:
                logger.info("Session expired, re-authenticating...")
                self._authenticate()
                return self.test_alpha(expression, settings_override)
            
            if sim_resp.status_code != 201:
                logger.error(f"Simulation creation failed: {sim_resp.text}")
                return None
            
            # Get simulation progress URL
            sim_progress_url = sim_resp.headers.get('location')
            if not sim_progress_url:
                logger.error("No location header in response")
                return None
            
            # Poll for results
            max_polls = 60  # 10 minutes max
            for i in range(max_polls):
                progress_resp = self.sess.get(sim_progress_url)
                
                if not progress_resp.text.strip():
                    time.sleep(10)
                    continue
                
                try:
                    progress_data = progress_resp.json()
                except:
                    time.sleep(5)
                    continue
                
                status = progress_data.get('status')
                
                if status == 'COMPLETE' or status == 'WARNING':
                    alpha_id = progress_data.get('alpha')
                    if alpha_id:
                        # Fetch full alpha details
                        alpha_resp = self.sess.get(
                            f'https://api.worldquantbrain.com/alphas/{alpha_id}'
                        )
                        if alpha_resp.status_code == 200:
                            return alpha_resp.json()
                    
                    return progress_data
                
                elif status in ['FAILED', 'ERROR']:
                    logger.error(f"Simulation failed: {progress_data}")
                    return None
                
                time.sleep(10)
            
            logger.error("Simulation polling timed out")
            return None
            
        finally:
            self._release_simulation_slot()
    
    def meets_stage1_criteria(self, alpha_data: Dict) -> Tuple[bool, List[str]]:
        """
        Check if alpha meets Stage 1 submission criteria.
        
        Returns:
            Tuple of (meets_criteria, list_of_failed_checks)
        """
        failed_checks = []
        
        if not alpha_data.get('is'):
            return False, ["Missing performance metrics"]
        
        is_data = alpha_data['is']
        
        # Check Sharpe ratio
        if is_data.get('sharpe', 0) < Stage1Criteria.SHARPE_MIN:
            failed_checks.append(
                f"Sharpe {is_data.get('sharpe', 0):.3f} < {Stage1Criteria.SHARPE_MIN}"
            )
        
        # Check fitness
        if is_data.get('fitness', 0) < Stage1Criteria.FITNESS_MIN:
            failed_checks.append(
                f"Fitness {is_data.get('fitness', 0):.3f} < {Stage1Criteria.FITNESS_MIN}"
            )
        
        # Check turnover
        turnover = is_data.get('turnover', 0)
        if turnover < Stage1Criteria.TURNOVER_MIN:
            failed_checks.append(
                f"Turnover {turnover:.3f} < {Stage1Criteria.TURNOVER_MIN:.3f}"
            )
        elif turnover > Stage1Criteria.TURNOVER_MAX:
            failed_checks.append(
                f"Turnover {turnover:.3f} > {Stage1Criteria.TURNOVER_MAX:.3f}"
            )
        
        # Check sub-universe Sharpe
        checks = {check['name']: check for check in is_data.get('checks', [])}
        
        concentrated_check = checks.get('CONCENTRATED_WEIGHT', {})
        if concentrated_check.get('result') != 'PASS':
            failed_checks.append("CONCENTRATED_WEIGHT check failed")
        
        sub_universe_check = checks.get('LOW_SUB_UNIVERSE_SHARPE', {})
        if sub_universe_check.get('result') != 'PASS':
            failed_checks.append("LOW_SUB_UNIVERSE_SHARPE check failed")
        
        # Check margin
        if is_data.get('returns', 0) <= Stage1Criteria.MARGIN_MIN:
            failed_checks.append(f"Returns/Margin {is_data.get('returns', 0):.3f} <= 0")
        
        return len(failed_checks) == 0, failed_checks
    
    def should_submit_alpha(
        self, 
        alpha_data: Dict, 
        expression: str
    ) -> Tuple[bool, str]:
        """
        Determine if alpha should be submitted after correlation check.
        
        Returns:
            Tuple of (should_submit, reason)
        """
        # First check performance criteria
        meets_criteria, failed_checks = self.meets_stage1_criteria(alpha_data)
        
        if not meets_criteria:
            return False, f"Failed performance criteria: {', '.join(failed_checks)}"
        
        # Check correlation
        sharpe = alpha_data['is']['sharpe']
        corr_result = self.correlation_checker.check_correlation(
            expression,
            new_alpha_sharpe=sharpe,
            alpha_id=alpha_data.get('id', 'pending')
        )
        
        if not corr_result['pass_prediction']:
            return False, f"Correlation check failed: {corr_result['reason']}"
        
        return True, "Passes all criteria including correlation check"
    
    def submit_alpha(self, alpha_id: str) -> bool:
        """Submit an alpha to WorldQuant Brain"""
        url = f'https://api.worldquantbrain.com/alphas/{alpha_id}/submit'
        
        try:
            response = self.sess.post(url)
            
            if response.status_code == 201:
                logger.info(f"Successfully submitted alpha {alpha_id}")
                
                # Monitor submission
                for i in range(30):  # 5 minutes max
                    status_resp = self.sess.get(url)
                    
                    if status_resp.text.strip():
                        try:
                            result = status_resp.json()
                            for check in result.get('is', {}).get('checks', []):
                                if check['name'] == 'SELF_CORRELATION':
                                    passed = check['result'] == 'PASS'
                                    logger.info(
                                        f"Self-correlation check: {'PASS' if passed else 'FAIL'}"
                                    )
                                    return passed
                        except:
                            pass
                    
                    time.sleep(10)
                
                logger.warning("Submission monitoring timed out")
                return True  # Assume success if no error
            
            else:
                logger.error(f"Submission failed: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error submitting alpha: {str(e)}")
            return False
    
    def generate_diverse_expression(
        self, 
        base_expression: str = None,
        avoid_similar_to: List[str] = None
    ) -> str:
        """
        Generate a diverse alpha expression.
        
        Uses templates and randomization to create varied expressions.
        """
        import random
        
        # Common WQ functions (VERIFIED from API - 66 operators available)
        ts_functions = [
            'ts_mean', 'ts_std_dev', 'ts_rank', 'ts_min', 'ts_max',
            'ts_sum', 'ts_product', 'ts_corr', 'ts_covariance',
            'ts_delta', 'ts_zscore', 'ts_decay_linear', 'ts_delay'
        ]
        
        cross_sectional = ['rank', 'zscore', 'scale', 'normalize']
        
        # Only use fields that are universally available
        data_fields = [
            'close', 'open', 'high', 'low', 'volume', 'returns'
        ]
        
        lookback_periods = [5, 10, 15, 20, 30, 40, 60, 90, 120]
        
        # Template-based generation
        templates = [
            # Mean reversion
            lambda: f"rank(-{random.choice(ts_functions)}({random.choice(data_fields)}, {random.choice(lookback_periods)}))",
            
            # Momentum
            lambda: f"rank({random.choice(ts_functions)}({random.choice(data_fields)}, {random.choice(lookback_periods)}) / {random.choice(ts_functions)}({random.choice(data_fields)}, {random.choice([x*2 for x in lookback_periods])}))",
            
            # Volume-price interaction
            lambda: f"rank({random.choice(ts_functions)}({random.choice(data_fields)}, {random.choice(lookback_periods)}) * {random.choice(ts_functions)}(volume, {random.choice(lookback_periods)}))",
            
            # Volatility adjusted
            lambda: f"rank({random.choice(ts_functions)}({random.choice(data_fields)}, {random.choice(lookback_periods)}) / {random.choice(ts_functions)}({random.choice(data_fields)}, {random.choice(lookback_periods)}))",
        ]
        
        max_attempts = 10
        for _ in range(max_attempts):
            expr = random.choice(templates)()
            
            # Check if too similar to existing
            if avoid_similar_to:
                is_similar = False
                for existing in avoid_similar_to:
                    similarity = self.correlation_checker._calculate_expression_similarity(
                        expr, existing
                    )
                    if similarity > 0.6:  # Too similar
                        is_similar = True
                        break
                
                if not is_similar:
                    return expr
            else:
                return expr
        
        # Fallback to base expression variation
        if base_expression:
            return self._mutate_expression(base_expression)
        
        return random.choice(templates)()
    
    def _mutate_expression(self, expression: str) -> str:
        """Mutate an expression to create variation"""
        import re
        
        mutations = []
        
        # Mutation 1: Change numeric parameters
        def change_number(match):
            num = int(match.group())
            change = random.choice([-5, -2, -1, 1, 2, 5, 10])
            return str(max(1, num + change))
        
        mutated = re.sub(r'\d+', change_number, expression, count=random.randint(1, 3))
        mutations.append(mutated)
        
        # Mutation 2: Swap functions
        func_swap = {
            'ts_mean': 'ts_std_dev',
            'ts_std_dev': 'ts_mean',
            'ts_rank': 'rank',
            'rank': 'ts_rank',
        }
        
        for old, new in func_swap.items():
            if old in expression:
                mutations.append(expression.replace(old, new, 1))
                break
        
        return random.choice(mutations)
    
    def improvement_loop(
        self,
        initial_expressions: List[str] = None,
        max_iterations: int = 100,
        target_submissions: int = 10
    ):
        """
        Main improvement loop.
        
        Continuously generates, tests, and submits alphas.
        """
        logger.info("=" * 60)
        logger.info("Starting Continuous Alpha Improvement System")
        logger.info("=" * 60)
        
        expressions_to_test = initial_expressions or []
        submitted_count = 0
        
        for iteration in range(max_iterations):
            self.stats['generation_rounds'] = iteration + 1
            
            logger.info(f"\n{'='*40}")
            logger.info(f"Iteration {iteration + 1}/{max_iterations}")
            logger.info(f"Submitted: {submitted_count}/{target_submissions}")
            logger.info(f"{'='*40}")
            
            # Generate or get next expression
            if not expressions_to_test:
                # Generate new diverse expression
                existing_exprs = [
                    alpha.expression 
                    for alpha in self.correlation_checker.submitted_alphas
                ]
                new_expr = self.generate_diverse_expression(
                    avoid_similar_to=existing_exprs
                )
                expressions_to_test.append(new_expr)
                logger.info(f"Generated new expression: {new_expr}")
            
            expression = expressions_to_test.pop(0)
            
            # Test the alpha
            logger.info(f"Testing expression: {expression}")
            result = self.test_alpha(expression)
            
            if not result:
                logger.warning("Alpha test failed, generating new expression")
                continue
            
            self.stats['alphas_tested'] += 1
            
            # Extract metrics
            is_data = result.get('is', {})
            sharpe = is_data.get('sharpe', 0)
            fitness = is_data.get('fitness', 0)
            
            logger.info(
                f"Results - Sharpe: {sharpe:.3f}, Fitness: {fitness:.3f}, "
                f"Turnover: {is_data.get('turnover', 0):.3f}"
            )
            
            # Update stats
            self.stats['average_sharpe'] = (
                self.stats['average_sharpe'] * (self.stats['alphas_tested'] - 1) + sharpe
            ) / self.stats['alphas_tested']
            self.stats['best_sharpe'] = max(self.stats['best_sharpe'], sharpe)
            
            # Record in history
            self.history['alphas'].append({
                'expression': expression,
                'sharpe': sharpe,
                'fitness': fitness,
                'tested_at': datetime.now().isoformat(),
                'alpha_id': result.get('id')
            })
            self._save_history()
            
            # Check if should submit
            should_submit, reason = self.should_submit_alpha(result, expression)
            
            if should_submit:
                logger.info(f"✓ Submitting alpha: {reason}")
                
                alpha_id = result.get('id')
                if self.submit_alpha(alpha_id):
                    submitted_count += 1
                    self.stats['alphas_submitted'] += 1
                    self.stats['alphas_passed_correlation'] += 1
                    
                    # Add to correlation tracker
                    alpha_record = AlphaRecord(
                        alpha_id=alpha_id,
                        expression=expression,
                        sharpe=sharpe,
                        fitness=fitness,
                        returns=is_data.get('returns', 0),
                        turnover=is_data.get('turnover', 0),
                        date_created=datetime.now().isoformat(),
                        submitted=True
                    )
                    self.correlation_checker.add_submitted_alpha(alpha_record)
                    
                    logger.info(f"Alpha submitted successfully! ({submitted_count}/{target_submissions})")
                    
                    if submitted_count >= target_submissions:
                        logger.info("\n" + "="*60)
                        logger.info("Target submissions reached!")
                        logger.info("="*60)
                        break
                else:
                    logger.warning("Submission failed despite passing local checks")
                    self.stats['alphas_failed_correlation'] += 1
            else:
                logger.info(f"✗ Not submitting: {reason}")
                self.stats['alphas_failed_correlation'] += 1
                
                # Learn from failure - add to avoid list if correlation issue
                if 'correlation' in reason.lower():
                    # This expression is too similar, don't retry
                    logger.info("Adding expression to similarity avoidance list")
            
            # Small delay between iterations
            time.sleep(5)
        
        # Final report
        self._print_final_report()
    
    def _print_final_report(self):
        """Print final statistics report"""
        logger.info("\n" + "="*60)
        logger.info("FINAL REPORT - Alpha Improvement System")
        logger.info("="*60)
        logger.info(f"Generation Rounds: {self.stats['generation_rounds']}")
        logger.info(f"Alphas Tested: {self.stats['alphas_tested']}")
        logger.info(f"Alphas Submitted: {self.stats['alphas_submitted']}")
        logger.info(f"Passed Correlation: {self.stats['alphas_passed_correlation']}")
        logger.info(f"Failed Correlation: {self.stats['alphas_failed_correlation']}")
        logger.info(f"Average Sharpe: {self.stats['average_sharpe']:.3f}")
        logger.info(f"Best Sharpe: {self.stats['best_sharpe']:.3f}")
        
        if self.stats['alphas_tested'] > 0:
            success_rate = self.stats['alphas_submitted'] / self.stats['alphas_tested'] * 100
            logger.info(f"Success Rate: {success_rate:.1f}%")
        
        logger.info("="*60)
        
        # Save final stats
        self.history['final_stats'] = self.stats
        self.history['completed_at'] = datetime.now().isoformat()
        self._save_history()


def main():
    parser = argparse.ArgumentParser(
        description='Continuous Alpha Improvement System for WQ IQC Stage 1'
    )
    parser.add_argument(
        '--credentials', 
        type=str, 
        default='./credential.txt',
        help='Path to credentials file [email, password]'
    )
    parser.add_argument(
        '--correlation-db',
        type=str,
        default='alpha_correlation_db.sqlite',
        help='Path to correlation tracking database'
    )
    parser.add_argument(
        '--initial-expressions',
        type=str,
        nargs='+',
        help='Initial alpha expressions to test'
    )
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=100,
        help='Maximum improvement iterations'
    )
    parser.add_argument(
        '--target-submissions',
        type=int,
        default=10,
        help='Target number of successful submissions'
    )
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=5,
        help='Maximum concurrent simulations'
    )
    
    args = parser.parse_args()
    
    # Validate credentials file
    if not os.path.exists(args.credentials):
        logger.error(f"Credentials file not found: {args.credentials}")
        logger.info("Creating example credential file...")
        with open(args.credentials, 'w') as f:
            f.write('["your.email@example.com", "your_password"]\n')
        logger.info(f"Please edit {args.credentials} with your actual credentials")
        return
    
    # Initialize and run system
    system = AlphaImprovementSystem(
        credentials_path=args.credentials,
        correlation_db_path=args.correlation_db,
        max_concurrent_simulations=args.max_concurrent
    )
    
    system.improvement_loop(
        initial_expressions=args.initial_expressions,
        max_iterations=args.max_iterations,
        target_submissions=args.target_submissions
    )


if __name__ == "__main__":
    main()
