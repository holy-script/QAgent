import os
B = "https://qagent-web-mu.vercel.app/"
def login(s):
    pg = s.page
    pg.goto(B + "login"); pg.wait_for_timeout(1500)
    pg.fill("input[type=email]", os.environ["QAGENT_EMAIL"]); pg.fill("input[type=password]", os.environ["QAGENT_PASSWORD"]); pg.keyboard.press("Enter")
    pg.wait_for_url(lambda u: "/login" not in u, timeout=20000); pg.wait_for_timeout(2500)
CARD = '[class*="rounded-xl"]'
