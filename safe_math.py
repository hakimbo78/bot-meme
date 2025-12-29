"""
Safe Math Utility - Division by Zero Protection

Production-grade defensive guards for all arithmetic operations.
Ensures scanner never crashes due to zero/null/missing values.
"""
from typing import Union, Optional


def safe_div(
    numerator: Union[int, float, None],
    denominator: Union[int, float, None],
    default: float = 0.0
) -> float:
    """
    Universal safe division helper.
    
    Handles:
    - Zero denominator
    - None/null values
    - Negative numbers (preserves sign)
    
    Args:
        numerator: Value to divide
        denominator: Value to divide by
        default: Return value if division impossible (default: 0.0)
        
    Returns:
        Division result or default value
        
    Examples:
        >>> safe_div(10, 2)
        5.0
        >>> safe_div(10, 0)
        0.0
        >>> safe_div(10, None, default=1.0)
        1.0
        >>> safe_div(None, 10)
        0.0
    """
    # Check for None/null values
    if numerator is None or denominator is None:
        return default
    
    # Check for zero denominator
    if denominator == 0:
        return default
    
    # Check for non-numeric values
    try:
        result = float(numerator) / float(denominator)
        return result
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def safe_div_percentage(
    current: Union[int, float, None],
    previous: Union[int, float, None],
    default: float = 0.0
) -> float:
    """
    Safe percentage change calculation.
    
    Calculates: ((current - previous) / previous) * 100
    
    Args:
        current: Current value
        previous: Previous/baseline value
        default: Return value if calculation impossible (default: 0.0)
        
    Returns:
        Percentage change or default value
        
    Examples:
        >>> safe_div_percentage(150, 100)
        50.0
        >>> safe_div_percentage(50, 100)
        -50.0
        >>> safe_div_percentage(100, 0)
        0.0
    """
    if current is None or previous is None:
        return default
    
    if previous == 0:
        return default
    
    try:
        change = ((float(current) - float(previous)) / float(previous)) * 100
        return change
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def safe_ratio(
    value1: Union[int, float, None],
    value2: Union[int, float, None],
    default: float = 0.0
) -> float:
    """
    Safe ratio calculation (absolute value comparison).
    
    Calculates: abs(value1 - value2) / value2
    
    Args:
        value1: First value
        value2: Second value (denominator)
        default: Return value if calculation impossible (default: 0.0)
        
    Returns:
        Ratio or default value
    """
    if value1 is None or value2 is None:
        return default
    
    if value2 == 0:
        return default
    
    try:
        ratio = abs(float(value1) - float(value2)) / float(value2)
        return ratio
    except (TypeError, ValueError, ZeroDivisionError):
        return default
