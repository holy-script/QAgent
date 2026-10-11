# Playbook: Checkout flow
base_url: http://localhost:8001

## Flow: add-to-cart
Severity: high

### Steps
1. Open /products
2. Add 2 items to cart
3. Go to /cart

### Expect
- Cart shows 2 items
- Total is visible

### Test data
- qty: 2
- coupon: EXPIRED10

### Formulas
- cart_total: `total == round(sum(i.price * i.qty for i in items) * (1 + tax_rate), 2)`
  - source: both
  - bindings: items=api:/api/cart.items, total=ui:[data-testid=cart-total], tax_rate=const:0.08

### Edge cases
- Quantity set to 0
- Apply expired coupon
