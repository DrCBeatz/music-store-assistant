# discounts.py
"""
Module for applying discounts to prices and determining discount codes.
"""

from math import ceil as math_ceil

def ceil(x: float, s: float) -> float:
    """
    Round a number up to the nearest multiple of another number.
    
    Parameters:
    - x (float): The number to be rounded up.
    - s (float): The multiple to round up to.
    
    Returns:
    float: x rounded up to the nearest multiple of s.
    """

    if s == 0:
        raise ValueError("The multiple 's' must not be zero.")
    return s * math_ceil(x/s)

def apply_discount(price: float, discount: float) -> float:
    """
    Apply a discount to a price based on predefined discount brackets.
    
    Parameters:
    - price (float): The original price of the item.
    - discount (float): The discount rate to be applied.
    
    Returns:
    float: The discounted price.
    """
    BRACKET_1 = 20
    BRACKET_2 = 50
    BRACKET_3 = 100
    FACTOR = 0.68
    ROUND_1 = 10
    ROUND_2 = 5

    cost = price * discount
    if price < BRACKET_1:
        return price
    elif BRACKET_1 <= price < BRACKET_2:
        return ceil(cost / FACTOR, ROUND_1) - 0.01
    elif BRACKET_2 <= price < BRACKET_3:
        return ceil(cost / FACTOR, ROUND_2) - 0.01
    else:  # price >= BRACKET_3
        return ceil(cost / FACTOR, ROUND_1) - 0.01

discount_codes = {
    "B":      0.6,
    "BY":     0.6 * 0.9,
    "BYY":    0.6 * 0.9 * 0.9,
    "B15":    0.6 * 0.85,
    "B20":    0.6 * 0.8,
    "B25":    0.6 * 0.75,
    "B25+5":  0.6 * 0.75 * 0.95,
    "A":      0.5,
    "AY":     0.5 * 0.9,
    "A20":    0.5 * 0.8,
}

def calculate_cost(retail: float, discount: str = "A") -> float:
    """
    Calculate the cost after applying a specific discount code.
    
    Parameters:
    - retail (float): The original retail price.
    - discount (str, optional): The discount code to be applied. Default is "A".
    
    Returns:
    float: The cost after the discount has been applied, rounded up to 2 decimal places.
    """
    if discount not in discount_codes:
        raise ValueError(f"Discount code {discount} not found.")
    cost = retail * discount_codes[discount]
    return round(cost, 2)

def calculate_discount(retail: float, cost: float, default: str = "A") -> str:
    """
    Determine the discount code applied based on the original retail price and the final cost.
    
    Parameters:
    - retail (float): The original retail price.
    - cost (float): The final cost after a discount has been applied.
    - default (str, optional): The default discount code to return if no match is found. Default is "A".
    
    Returns:
    float: The discount rate applied or the default discount rate if no match is found.
    """
    for _, code in discount_codes.items():
        cost_calc = round(code * retail, 2)
        if cost_calc == round(cost, 2):
            return code
    return discount_codes[default]

def profit_margin(revenue: float, cost: float) -> float:
    """
    Calculate the profit margin of a product.

    Parameters:
    revenue (float): The total revenue from the sale.
    cost (float): The total cost of the product sold.

    Returns:
    float: The profit margin as a percentage, rounded to a maximum of two decimal points.
    """
    # Ensure the inputs are numbers and revenue is not zero
    if not all(isinstance(i, (int, float)) for i in [revenue, cost]) or revenue == 0:
        raise ValueError("Invalid input or revenue cannot be zero.")
    
    # Calculate and return the profit margin
    return round(((revenue - cost) / revenue) * 100, 2)
