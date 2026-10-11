# Playbook: Checkout
base_url: http://localhost:8001
prd: PRD-checkout-v2

## Requirements
### REQ-1: Cart total applies the discount before tax
- prd_ref: §3.2 Pricing
- acceptance: total = (subtotal − discount) × (1 + tax_rate), rounded to 2 decimals
- priority: high

### REQ-2: Payments succeed reliably
- prd_ref: §5.1 Payment
- acceptance: Every payment attempt with a valid cart returns success. No server errors.
- priority: critical

### REQ-3: Checkout requires a valid postal code
- prd_ref: §4.1 Address form
- acceptance: Submitting without a postal code shows an inline error and blocks submission.
- priority: high

## Formulas
### F-1: cart_total
- rule: `total == round((sum(i.price * i.qty for i in items) - discount) * (1 + tax_rate), 2)`
- source: both
- bindings: items=api:/api/cart.items, discount=api:/api/cart.discount, total=ui:[data-testid=cart-total], tax_rate=const:0.08
- tolerance: 0.01
- verifies: REQ-1

## UX rules
### UX-1: Cart count is consistent across the app
- check: consistent_value
- targets: ui:[data-testid=cart-badge], api:/api/cart.count
- severity: medium

### UX-2: No loading state lasts longer than 2.5 seconds
- check: max_wait
- max_ms: 2500
- severity: high

### UX-3: Form errors are visible and explain the problem
- check: judged
- question: Is an error message visible next to the invalid field that says what is wrong?
- severity: medium

### UX-4: Prices use the same currency format everywhere
- check: format
- targets: ui:[data-testid=line-price], ui:[data-testid=cart-total]
- pattern: ^\$\d{1,3}(,\d{3})*\.\d{2}$
- severity: low

## Gotchas
### G-1: The cart badge updates only after /api/cart/add responds
- wait_for: api:/api/cart/add
- note: Reading the badge before the response arrives gives a stale count, which is not a bug.

### G-2: The coupon field is plain text and keeps its value after Apply
- note: Type the coupon, then click Apply. Do not press Enter.

## Edge cases
### EC-2: Expired coupon
- applies_to: apply-coupon
- expect: An error says the coupon is invalid or expired. The total does not change.
- covers: REQ-1
- test_data: coupon=EXPIRED10

### EC-3: Missing postal code
- applies_to: checkout
- expect: An inline error appears and the address is not saved.
- covers: REQ-3
- checks: UX-3
- test_data: postal=<empty>

## Flows
### Flow: add-to-cart
- covers: REQ-1
- checks: F-1, UX-1, UX-4
- severity: high

#### Steps
1. Open /products
2. Add 2 items to cart
3. Go to /cart

#### Expect
- Cart shows 2 items
- Total is visible

#### Test data
- qty: 2

### Flow: apply-coupon
- covers: REQ-1
- checks: F-1, UX-2
- severity: high

#### Steps
1. Open /products
2. Add 2 items to cart
3. Go to /cart
4. Enter the coupon code
5. Click Apply Coupon

#### Expect
- A discount is applied to the total

#### Test data
- coupon: SAVE10

### Flow: payment
- covers: REQ-2
- severity: critical

#### Steps
1. Open /products
2. Add item to cart
3. Open /checkout
4. Click Pay now
5. Click Pay now
6. Click Pay now

#### Expect
- Every payment attempt succeeds

### Flow: checkout
- covers: REQ-3
- severity: high

#### Steps
1. Open /checkout
2. Enter the postal code
3. Click Save address

#### Expect
- Address saved is shown

#### Test data
- postal: 12345

## Reasoning examples
### RX-1: Telling a slow API apart from a broken one
- scope: escalation, judge
- context: A spinner is visible and the expected element hasn't appeared. It could be slow, failed silently, or stuck.
- strategy:
  1. Check the network log for the request the step triggered.
  2. If it's still pending, wait until the time budget runs out, then report a timing finding, not a functional one.
  3. If it returned 4xx or 5xx, report a network finding and cite that call.
  4. If it returned 200 but the UI didn't update, report a UI-state finding and cite both the response and the screenshot.
