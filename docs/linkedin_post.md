# LinkedIn post (draft, edit before posting)

One point on the discount rate moves my TCS valuation by roughly ₹180 to ₹220 a share.

I built a discounted cash flow app that anyone can stress-test: five-year forecast, WACC with a
beta I computed from five years of weekly returns, scenarios, a 10,000-run Monte Carlo, a peer
cross-check and a reverse DCF. On the 27 Nov 2026 data my model value was ₹1,766 against a
₹2,640 close; the price implies about 18.8% annual revenue growth if everything else holds.
That gap says as much about my assumptions (a 13.6% cost of capital) as about the market.

Stack: Python, FastAPI, NumPy, Next.js, TypeScript, three.js, GitHub Actions, Vercel.

What I learned: the terminal value was about two thirds of the answer, so showing how sensitive
it is matters more than the single number.

Live: https://quant-project-2.vercel.app
Code: https://github.com/Pravin292/Quant_Project-2

Educational project, not investment advice.
