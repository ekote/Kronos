# The commerce deck, explained super simply 🧸

*A plain-words guide to `openmercato-deck.pdf`. No computer words. If you can
picture a lemonade stand and a busy day, you're ready.*

---

## What is this thing?

Imagine your online shop is a **lemonade stand**, and every time someone buys, a
little bell rings 🔔. A robot listens to all the bells and **guesses how much
you'll sell in the next little while** — like guessing how busy you'll be.

The robot is **Kronos**. Your shop is **Open Mercato**. The robot lives on
Microsoft's big computers (**Azure**). Put together, they **watch your sales as
they happen and guess what comes next** — and ring an alarm if something goes
wrong.

---

## The picture: counting the bells 🛎️

- On a **normal day**, the bells ring in a steady rhythm. The robot guesses the
  next stretch pretty well — about **2 out of 3** times it gets the direction
  right. ✅
- On a **big sale day**, the bells go crazy (lots of buying!). The robot notices
  the rush and **waves a flag** so you can get ready — make more lemonade, add
  more helpers. 🎉
- If your **checkout breaks** (nobody can pay!), the bells suddenly go quiet. No
  robot can predict that — but this one **notices the silence fast** and **rings
  an alarm** so you fix it right away. 🚨

That last part is the whole point.

---

## Walking through the slides

**Slide 1 — "Forecast it. Act on it."** Your shop already sends out bells (orders).
The robot turns them into guesses you can act on.

**Slide 2 — the factory line.** Bells → tidy boxes → the robot's guess → an alarm
if needed. It works two ways: with Microsoft **Fabric**, or with plain **Azure**.

**Slide 3 — three truths.** It guesses sales well (~**70%**), it can't predict a
surprise (like a broken checkout), but it **catches the surprise super fast**
(~**5 minutes**).

**Slide 4 — the sales line.** The black line is how much you *really* sold each
minute. The dotted line is the robot's **guess**. See the tall spike? That's a
**flash sale**. See the deep dip? That's the **checkout outage** — and the little
flag says the alarm rang **5 minutes** later.

**Slide 5 — the "am I still right?" meter.** Normally low and calm. When checkout
broke, it shot up — that's the robot **raising its hand**.

**Slide 6 — the flags (signals).** When the robot feels sure sales will jump, it
sends a note so you can prepare. Most notes were right.

**Slide 7 — the ending.** Bells → guess → act, around and around, all day.

---

## The three things to remember 🌟

1. **It's a good guesser** about how busy you'll be.
2. **It's honest** — it won't pretend to predict a broken checkout or a surprise.
3. **It tells on itself** the second its guesses go wrong, so you fix problems fast.

---

## Two grown-up reminders (small print) 🔍

- The numbers come from a **pretend shop day** we made up (always the same, so
  it's easy to retell). It shows the *machine works* — it's **not** a promise about
  your real sales. 🚫🪄
- The robot learned on **stock-market** data first, so for your shop it works best
  after it **practices on your own sales** (that's called fine-tuning).

---

**Learn more:** [Open Mercato](https://github.com/open-mercato/open-mercato),
[Kronos](https://github.com/shiyu-coder/Kronos), and the full design in
[`../architecture.md`](../architecture.md).
