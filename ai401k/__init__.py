"""ai401k: an AI-assisted 401k allocation and monthly rebalancing kit.

The Python package does all the arithmetic (data, optimisation, signals, guardrails, trades) so that
every number is reproducible. Claude Code sits on top as the "investment committee": it runs the
engine, researches the market, writes the memo and asks the human for approval.
"""
__version__ = "1.0.0"
SLEEVES = ["US_EQ", "INTL_EQ", "BONDS", "GOLD", "CASH"]
