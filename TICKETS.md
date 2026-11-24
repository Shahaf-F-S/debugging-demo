# Tickets

Bug reports from users, QA and support. Work through the **core** tickets in order; continue with the
**stretch** tickets if you have time.

For every ticket:

1. **Reproduce** it as a failing test (in a new file, e.g. `tests/test_ticket_c3.py`).
2. **Find the rule** in [DESIGN.md](DESIGN.md) that the code breaks.
3. **Locate** where the code starts doing something different from that rule.
4. **Explain** the root cause in one sentence, in terms of the design.
5. **Fix** it with the smallest change that makes your test pass, and keep all the other tests green.
6. **Hunt the family:** look for the same mistake elsewhere in the code.

Useful tools: the debugger (breakpoints, Evaluate Expression), `python check.py`, the `FakeClock` fixture
(`clock.advance(days=31)`), the sqlite3 command line or DB Browser for SQLite, `git log` / `git bisect`, and
`python -m mypy peerpay` (it only checks the functions that have type hints).

---

## Core

### C1 · Every transfer fails after one typo
> **From:** QA team
>
> At 10:02 a tester sent money to the number `12345` on purpose and got "invalid phone number". Correct.
> But since then **every** transfer, by every user, fails with "invalid phone number", even to valid
> numbers. Restarting the server fixes it.

### C2 · "Total received: ₪0.00"
> **From:** Yossi
>
> My statement says I received 2 transfers, and the total received is ₪0.00. I definitely received ₪50.

### C3 · "Sent ✓", but nothing was sent
> **From:** Dana
>
> I sent ₪20 to 050-000-0000. I got one digit of my friend's number wrong, and that number isn't registered.
> The app said "Sent ✓". My friend got nothing, nothing is pending, and my balance didn't change. So was it
> sent or not?

### C4 · "Expires tomorrow", but it already expired
> **From:** Yossi
>
> My pending list said Dana's transfer expires tomorrow evening. I accepted it this evening and got
> "transfer has expired".

### C5 · A long note ate my ₪100
> **From:** Noa
>
> I sent Dana ₪100 with a long note (I listed everything we bought for the party). The app crashed with an
> error. ₪100 is gone from my balance, there is no transfer in my list, and Dana didn't get anything.

### C6 · Yossi's phone number turned into `05*-***-4567`
> **From:** Support team
>
> Yossi logged in fine at 12:30. Since then he gets "wrong phone number or password". In the testing DB his
> phone number is now `05*-***-4567`. Nobody edited his account.

### C7 · My notifications screen is always empty
> **From:** Noa
>
> I get push messages on my phone when someone sends me money, but the notifications screen in the app is
> always empty. QA adds: it's empty for everyone, and it even "works" with a made-up token.

---

## Stretch

### S1 · Every notification says "expired"
> **From:** Dana
>
> Every notification I get says "Your transfer … expired", even when Yossi accepted it. And Yossi says he never
> gets a notification when I send him money.

### S2 · I sent ₪19.99, Yossi received ₪19.98
> **From:** Dana
>
> I paid Yossi back ₪19.99 for the pizza. He received ₪19.98. Sending ₪20.00 works fine.

### S3 · Today's transfers "expired" tonight
> **From:** QA team
>
> Our test server has been running for five weeks. Transfers sent this morning were cancelled as "expired" by
> tonight's job. Also, "cancel my last transfer" cancelled one I sent last week instead of the one I had just
> sent.

### S4 · A support credit disappeared
> **From:** Support team
>
> We credited Noa ₪30 compensation with `tools/support.py` while the server was running. After her next
> transfer, the ₪30 was gone.

### S5 · ₪5,000 pulled from the bank for a ₪50 top-up
> **From:** QA team
>
> I topped up ₪50. The wallet shows +₪50, but the bank's log says 5000.00 shekels were pulled.
