import pytest
from qagent.browser.extractor import extract_candidates_from_html


def test_extract_candidates_from_sample_html():
    sample_html = """
    <html>
        <body>
            <header>
                <a href="/home" id="nav-home">Home</a>
                <a href="/cart" data-testid="cart-link">Cart (0)</a>
            </header>
            <main>
                <h1>Products</h1>
                <div class="product">
                    <span>Wireless Headphones - $99</span>
                    <button id="add-headphones" data-testid="add-btn-1">Add to Cart</button>
                </div>
                <div class="product">
                    <span>Mechanical Keyboard - $149</span>
                    <button class="btn primary" data-testid="add-btn-2">Add to Cart</button>
                </div>
                <form>
                    <input type="text" name="coupon" placeholder="Coupon Code" />
                    <button type="submit">Apply Coupon</button>
                </form>
            </main>
        </body>
    </html>
    """

    candidates = extract_candidates_from_html(sample_html)
    assert len(candidates) >= 5
    assert len(candidates) <= 40

    # Ensure IDs are 1-based sequential integers
    assert [c.id for c in candidates] == list(range(1, len(candidates) + 1))

    # Verify attributes
    labels = [c.label for c in candidates]
    assert any("Home" in l for l in labels)
    assert any("Add to Cart" in l for l in labels)
    assert any(c.tag == "input" and c.action_type == "fill" for c in candidates)
