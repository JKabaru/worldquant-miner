# WorldQuant IQC Stage 1 - Continuous Alpha Improvement System

## Overview

This system provides an automated, self-improving pipeline for generating, testing, and submitting alphas to WorldQuant Brain for IQC Stage 1. The key innovation is **local correlation checking** that predicts whether an alpha will pass the self-correlation check BEFORE submission, saving significant time and API calls.

## Key Features

### 1. Self-Correlation Checker (`self_correlation_checker.py`)
- **Predicts correlation** with previously submitted alphas using multiple heuristics:
  - Expression structural similarity (token-based Jaccard similarity)
  - Parameter distance analysis
  - Function pattern matching
  - Performance pattern similarity
- **Implements the 10% exception rule**: If correlation > 0.70, checks if Sharpe is ≥10% higher
- **Provides diversification suggestions** when high correlation is detected
- **Persistent SQLite database** tracks all submitted alphas

### 2. Continuous Alpha Improver (`continuous_alpha_improver.py`)
- **Closed-loop improvement system** that learns from each iteration
- **Automatic criteria validation** against Stage 1 cutoffs:
  - Sharpe Ratio ≥ 1.25
  - Fitness ≥ 1.0
  - Turnover: 1% - 70%
  - Sub-universe Sharpe ≥ 0.73
  - Margin > 0
- **Concurrent simulation management** (respects WQ's 5-10 simulation limit)
- **Diverse expression generation** with template-based strategies:
  - Mean reversion
  - Momentum
  - Volume-price interaction
  - Volatility-adjusted returns
- **Automatic mutation** of expressions to avoid correlation

## Installation

```bash
cd /workspace/stone_age/python/pre_consultant
pip install -r requirements.txt
```

## Setup Credentials

Create a `credential.txt` file in JSON format:

```json
["joekabaru@gmail.com", "your_password"]
```

**⚠️ Security Note**: Never commit credentials to git. The file is in `.gitignore`.

## Quick Start

### Option 1: Test Correlation Checker Only

```bash
python self_correlation_checker.py
```

This demonstrates the correlation checking with sample alphas.

### Option 2: Run Full Improvement System

```bash
python continuous_alpha_improver.py \
  --credentials ./credential.txt \
  --target-submissions 10 \
  --max-iterations 100 \
  --max-concurrent 5
```

### Option 3: With Initial Expressions

```bash
python continuous_alpha_improver.py \
  --credentials ./credential.txt \
  --initial-expressions \
    "rank(ts_mean(close, 10))" \
    "ts_std_dev(volume, 20) / ts_mean(volume, 20)" \
  --target-submissions 5
```

## Command-Line Options

```
--credentials PATH          Path to credentials file (default: ./credential.txt)
--correlation-db PATH       Path to correlation database (default: alpha_correlation_db.sqlite)
--initial-expressions EXPR  Initial alpha expressions to test
--max-iterations N          Maximum improvement iterations (default: 100)
--target-submissions N      Target number of successful submissions (default: 10)
--max-concurrent N          Maximum concurrent simulations (default: 5)
```

## How It Works

### Workflow Diagram

```
┌─────────────────┐
│ Generate Alpha  │
│ Expression      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Test on WQ      │
│ Brain API       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Check Stage 1   │◄── Sharpe, Fitness, Turnover, etc.
│ Criteria        │
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│ Local           │◄── Compare with submitted alphas
│ Correlation     │    Estimate correlation score
│ Check           │
└────────┬────────┘
         │ PASS (< 0.70 or 10% Sharpe boost)
         ▼
┌─────────────────┐
│ Submit to       │
│ WorldQuant      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Add to          │◄── Update local database
│ Correlation DB  │    Learn for next iteration
└─────────────────┘
```

### Correlation Estimation Algorithm

The system uses a weighted combination of:

1. **Expression Similarity (50%)**: Jaccard similarity on tokenized expressions
2. **Parameter Distance (35%)**: How similar are the numeric parameters
3. **Function Pattern (15%)**: Overlap in function names used

```python
estimated_corr = (
    0.50 * expr_similarity +
    0.35 * param_similarity +
    0.15 * perf_similarity
)
```

### 10% Exception Rule

If `correlation > 0.70`:
- Calculate required Sharpe: `existing_sharpe × 1.10`
- If `new_sharpe >= required_sharpe`: **PASS** (exception applies)
- Otherwise: **FAIL** (too correlated without sufficient improvement)

## Output Files

### Generated During Execution

- `alpha_correlation_db.sqlite` - SQLite database of submitted alphas
- `improvement_history.json` - Complete history of tested alphas
- `alpha_improvement_system.log` - Detailed execution logs
- `correlation_report.json` - Exportable correlation analysis report

### Example Log Output

```
2026-04-10 08:06:24 - INFO - ========================================
2026-04-10 08:06:24 - INFO - Iteration 1/100
2026-04-10 08:06:24 - INFO - Submitted: 0/10
2026-04-10 08:06:24 - INFO - ========================================
2026-04-10 08:06:24 - INFO - Generated new expression: rank(-ts_mean(close, 20))
2026-04-10 08:06:24 - INFO - Testing expression: rank(-ts_mean(close, 20))
2026-04-10 08:06:34 - INFO - Results - Sharpe: 1.320, Fitness: 1.150, Turnover: 0.180
2026-04-10 08:06:34 - INFO - ✓ Submitting alpha: Passes all criteria including correlation check
2026-04-10 08:06:44 - INFO - Alpha submitted successfully! (1/10)
```

## Performance Cutoffs (Stage 1 IQC 2026)

| Metric | Threshold | Description |
|--------|-----------|-------------|
| Sharpe Ratio | ≥ 1.25 | Risk-adjusted return |
| Fitness | ≥ 1.0 | Combined score (Sharpe × returns / turnover) |
| Turnover | 1% - 70% | Daily portfolio trading rate |
| Sub-universe Sharpe | ≥ 0.73 | Performance across stock subsets |
| Margin | > 0 | Positive expected profit |
| Correlation | < 0.70 | Max correlation with previous submissions |

## Tips for Better Results

### 1. Diversify Expression Templates
Add more templates to `generate_diverse_expression()`:
```python
templates.append(
    lambda: f"ts_rank({random.choice(data_fields)}, {random.choice(lookback_periods)}) - ts_rank({random.choice(data_fields)}, {random.choice(lookback_periods)})"
)
```

### 2. Tune Mutation Strategy
Adjust `_mutate_expression()` to make larger/smaller changes based on failure patterns.

### 3. Monitor Correlation Report
Regularly check `correlation_report.json` to identify clusters of similar alphas.

### 4. Use the 10% Exception Strategically
If you have a very strong alpha (Sharpe > 1.5), it can override correlation with weaker previous submissions.

## Troubleshooting

### "Authentication failed"
- Verify credentials format: `["email", "password"]`
- Check for extra spaces or quotes
- Ensure email matches your WQ Brain account

### "Simulation limit exceeded"
- Reduce `--max-concurrent` to 3-5
- Wait for existing simulations to complete
- The system automatically queues and retries

### "Correlation check failed"
- Review diversification suggestions in logs
- Try significantly different lookback periods (e.g., 10→60)
- Change core functions (ts_mean → ts_rank)
- Use different data fields (close → volume)

### High failure rate on correlation
- Your expression pool may be too homogeneous
- Increase diversity in generation templates
- Consider manual expression injection via `--initial-expressions`

## Integration with Existing Code

This system complements the existing miners:

- `promising_alpha_miner.py` - Can use our correlation checker before parameter variation
- `alpha_expression_miner.py` - Integrate correlation check in variation loop
- `successful_alpha_submitter.py` - Replace with our smarter submission logic

Example integration:
```python
from self_correlation_checker import SelfCorrelationChecker

checker = SelfCorrelationChecker()

# Before submitting any alpha
result = checker.check_correlation(expression, sharpe_ratio)
if result['pass_prediction']:
    submit_alpha(alpha_id)
else:
    print(result['reason'])
    # Get suggestions to improve
    suggestions = checker.get_diversification_suggestions(expression)
```

## Advanced Usage

### Custom Correlation Thresholds

```python
checker = SelfCorrelationChecker()
checker.CORRELATION_THRESHOLD = 0.65  # Stricter threshold
```

### Export and Analyze History

```python
import json

with open('improvement_history.json') as f:
    history = json.load(f)

# Analyze best performers
best_alphas = sorted(history['alphas'], key=lambda x: x['sharpe'], reverse=True)[:10]
```

### Batch Processing Multiple Strategies

Run multiple instances with different focuses:
```bash
# Mean reversion focus
python continuous_alpha_improver.py --target-submissions 5 &

# Momentum focus  
python continuous_alpha_improver.py --target-submissions 5 &

# Volume-based focus
python continuous_alpha_improver.py --target-submissions 5 &
```

## Future Enhancements

1. **Machine Learning Model**: Train on historical alpha performance to predict success
2. **Genetic Algorithms**: Evolve expressions over generations
3. **Real-time Correlation**: Fetch actual return series from WQ API for precise correlation
4. **Multi-region Support**: Test across different regions (USA, China, etc.)
5. **GUI Dashboard**: Visual interface for monitoring progress

## References

- [WorldQuant Brain API Documentation](https://api.worldquantbrain.com/docs)
- [Alpha101 Formulas](https://github.com/yliu7949/Alpha101)
- [Karpathy AutoResearch](https://github.com/karpathy/autoresearch) - Inspiration for self-improvement loop

## License

MIT License - See LICENSE file in repository root.

## Support

For issues or questions:
1. Check logs in `alpha_improvement_system.log`
2. Review correlation report: `correlation_report.json`
3. Verify credentials and API access
4. Ensure you haven't exceeded WQ simulation limits

---

**Good luck with IQC Stage 1!** 🚀
