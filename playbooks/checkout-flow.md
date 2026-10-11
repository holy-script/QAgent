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
- cart_total: `total == round((sum(i.price * i.qty for i in items) - discount) * (1 + tax_rate), 2)`
  - source: both
  - bindings: items=api:/api/cart.items, discount=api:/api/cart.discount, total=ui:[data-testid=cart-total], tax_rate=const:0.08
- cart_badge: `badge == sum(i.qty for i in items)`
  - kind: dom
  - bindings: badge=ui:[data-testid=cart-badge], items=api:/api/cart.items

### Edge cases
- Quantity set to 0
- Apply expired coupon

## Flow: apply-coupon
Severity: high

### Steps
1. Open /products
2. Add 2 items to cart
3. Go to /cart
4. Enter the coupon code
5. Click Apply Coupon

### Expect
- Discount is applied to the total

### Test data
- coupon: SAVE10

### Formulas
- discounted_total: `total == round((sum(i.price * i.qty for i in items) - discount) * (1 + tax_rate), 2)`
  - bindings: items=api:/api/cart.items, discount=api:/api/cart.discount, total=ui:[data-testid=cart-total], tax_rate=const:0.08

## Flow: payment
Severity: critical

### Steps
1. Open /products
2. Add item to cart
3. Open /checkout
4. Click Pay now
5. Click Pay now
6. Click Pay now

### Expect
- Every payment attempt succeeds
