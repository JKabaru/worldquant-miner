#!/bin/bash
# Quick Start Script for WorldQuant Alpha Improvement System
# This script helps you get started with the continuous alpha improvement system

set -e

echo "=========================================="
echo "WorldQuant IQC Stage 1 - Alpha Improvement System"
echo "=========================================="
echo ""

# Check if credential file exists
if [ ! -f "credential.txt" ]; then
    echo "⚠️  Credential file not found!"
    echo ""
    echo "Please create credential.txt with your WorldQuant credentials:"
    echo '["your.email@example.com", "your_password"]'
    echo ""
    exit 1
fi

# Validate credentials format
python3 -c "import json; json.load(open('credential.txt'))" 2>/dev/null || {
    echo "❌ Invalid credentials format!"
    echo "Expected: [\"email\", \"password\"]"
    echo "Example: [\"joekabaru@gmail.com\", \"mypassword\"]"
    exit 1
}

echo "✓ Credentials validated"
echo ""

# Check dependencies
echo "Checking dependencies..."
python3 -c "import requests, numpy" 2>/dev/null || {
    echo "Installing required packages..."
    pip install -q requests numpy
}
echo "✓ Dependencies OK"
echo ""

# Show available commands
echo "=========================================="
echo "Available Commands:"
echo "=========================================="
echo ""
echo "1. Test correlation checker (demo mode):"
echo "   python3 self_correlation_checker.py"
echo ""
echo "2. Run full improvement system:"
echo "   python3 continuous_alpha_improver.py --target-submissions 10"
echo ""
echo "3. Run with custom settings:"
echo "   python3 continuous_alpha_improver.py \\"
echo "     --target-submissions 5 \\"
echo "     --max-iterations 50 \\"
echo "     --max-concurrent 3"
echo ""
echo "4. Test specific expressions:"
echo "   python3 continuous_alpha_improver.py \\"
echo "     --initial-expressions \\"
echo "       'rank(ts_mean(close, 10))' \\"
echo "       'ts_std_dev(volume, 20)' \\"
echo "     --target-submissions 3"
echo ""
echo "=========================================="
echo "Stage 1 IQC Requirements:"
echo "=========================================="
echo "• Sharpe Ratio ≥ 1.25"
echo "• Fitness ≥ 1.0"
echo "• Turnover: 1% - 70%"
echo "• Sub-universe Sharpe ≥ 0.73"
echo "• Correlation < 0.70 (or 10% Sharpe improvement)"
echo ""
echo "=========================================="
echo "Output Files:"
echo "=========================================="
echo "• alpha_correlation_db.sqlite - Submitted alpha database"
echo "• improvement_history.json - Complete testing history"
echo "• alpha_improvement_system.log - Execution logs"
echo "• correlation_report.json - Correlation analysis"
echo ""
echo "Ready to start! Run one of the commands above."
echo "=========================================="
